"""FastMCP server with conversation history search tools."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from .db import ensure_schema, get_connection, get_db_path
from .indexer import index_all, reindex as do_reindex

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    db_path: Path


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Initialize database and run incremental indexing on startup."""
    db_path = get_db_path()
    ensure_schema(db_path)
    stats = index_all(db_path)
    logger.info(
        f"Startup indexing: {stats['files']} files, "
        f"{stats['messages']} new messages, "
        f"{stats['skipped']} unchanged ({stats['duration_seconds']}s)"
    )
    yield AppContext(db_path=db_path)


mcp = FastMCP(
    "context-flow-search",
    instructions="Search Claude Code conversation history",
    lifespan=app_lifespan,
)


def _get_db_path(ctx: Context[ServerSession, AppContext]) -> Path:
    return ctx.request_context.lifespan_context.db_path


@mcp.tool()
def search_history(
    query: str,
    ctx: Context[ServerSession, AppContext],
    limit: int = 10,
    project: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """Search across all indexed Claude Code conversations.

    Args:
        query: Full-text search query (supports FTS5 syntax: AND, OR, NOT, "phrases")
        limit: Maximum number of results (default 10)
        project: Filter by project directory path (substring match)
        date_from: Filter messages from this date (ISO format, e.g. "2026-01-15")
        date_to: Filter messages up to this date (ISO format)
    """
    db_path = _get_db_path(ctx)
    conn = get_connection(db_path)

    try:
        # Build query with optional filters
        where_clauses = ["messages_fts MATCH ?"]
        params: list = [query]

        if project:
            where_clauses.append("s.project_dir LIKE ?")
            params.append(f"%{project}%")
        if date_from:
            where_clauses.append("m.timestamp >= ?")
            params.append(date_from)
        if date_to:
            where_clauses.append("m.timestamp <= ?")
            params.append(date_to + "T23:59:59Z" if "T" not in date_to else date_to)

        where = " AND ".join(where_clauses)
        params.append(limit)

        sql = f"""
            SELECT
                m.session_id,
                s.slug,
                s.project_dir,
                s.git_branch,
                m.role,
                m.timestamp,
                snippet(messages_fts, 0, '>>>', '<<<', '...', 40) as snippet
            FROM messages_fts
            JOIN messages m ON m.id = messages_fts.rowid
            JOIN sessions s ON s.session_id = m.session_id
            WHERE {where}
            ORDER BY rank
            LIMIT ?
        """

        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@mcp.tool()
def get_conversation(
    session_id_or_slug: str,
    ctx: Context[ServerSession, AppContext],
    around_timestamp: str | None = None,
    roles: list[str] | None = None,
    limit: int = 200,
) -> dict:
    """Retrieve messages from a specific conversation session.

    Args:
        session_id_or_slug: Session UUID or slug (e.g. "sorted-humming-fox")
        around_timestamp: If provided, return ~20 messages centered on this timestamp
        roles: Filter by message roles (e.g. ["user", "assistant"]). Options: user, assistant, tool_summary, plan
        limit: Maximum messages to return (default 200)
    """
    db_path = _get_db_path(ctx)
    conn = get_connection(db_path)

    try:
        # Find session by ID or slug (most recent if slug matches multiple)
        session = conn.execute(
            """SELECT * FROM sessions
               WHERE session_id = ? OR slug = ?
               ORDER BY last_timestamp DESC LIMIT 1""",
            (session_id_or_slug, session_id_or_slug)
        ).fetchone()

        if not session:
            return {"error": f"Session not found: {session_id_or_slug}"}

        session_id = session["session_id"]

        # Build message query
        where_clauses = ["session_id = ?"]
        params: list = [session_id]

        if roles:
            placeholders = ",".join("?" * len(roles))
            where_clauses.append(f"role IN ({placeholders})")
            params.extend(roles)

        where = " AND ".join(where_clauses)

        if around_timestamp:
            # Get ~10 messages before and ~10 after the target timestamp
            before = conn.execute(
                f"""SELECT id, session_id, role, content, timestamp, model
                    FROM messages WHERE {where} AND timestamp <= ?
                    ORDER BY timestamp DESC LIMIT 10""",
                params + [around_timestamp]
            ).fetchall()

            after = conn.execute(
                f"""SELECT id, session_id, role, content, timestamp, model
                    FROM messages WHERE {where} AND timestamp > ?
                    ORDER BY timestamp ASC LIMIT 10""",
                params + [around_timestamp]
            ).fetchall()

            messages = [dict(r) for r in reversed(before)] + [dict(r) for r in after]
        else:
            params.append(limit)
            messages = [
                dict(r) for r in conn.execute(
                    f"""SELECT id, session_id, role, content, timestamp, model
                        FROM messages WHERE {where}
                        ORDER BY timestamp ASC LIMIT ?""",
                    params
                ).fetchall()
            ]

        return {
            "session": dict(session),
            "messages": messages,
            "message_count": len(messages),
        }
    finally:
        conn.close()


@mcp.tool()
def list_sessions(
    ctx: Context[ServerSession, AppContext],
    limit: int = 20,
    project: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """List recent Claude Code sessions with metadata.

    Args:
        limit: Maximum sessions to return (default 20)
        project: Filter by project directory path (substring match)
        date_from: Filter sessions starting from this date (ISO format)
        date_to: Filter sessions up to this date (ISO format)
    """
    db_path = _get_db_path(ctx)
    conn = get_connection(db_path)

    try:
        where_clauses = []
        params: list = []

        if project:
            where_clauses.append("project_dir LIKE ?")
            params.append(f"%{project}%")
        if date_from:
            where_clauses.append("last_timestamp >= ?")
            params.append(date_from)
        if date_to:
            end = date_to + "T23:59:59Z" if "T" not in date_to else date_to
            where_clauses.append("first_timestamp <= ?")
            params.append(end)

        where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        params.append(limit)

        rows = conn.execute(
            f"""SELECT session_id, project_dir, slug, first_timestamp,
                       last_timestamp, message_count, git_branch, cwd
                FROM sessions {where}
                ORDER BY last_timestamp DESC
                LIMIT ?""",
            params
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


@mcp.tool()
def reindex(ctx: Context[ServerSession, AppContext]) -> dict:
    """Force a complete re-index of all conversation transcripts.

    Clears the existing index and rebuilds from scratch. Use when
    the index seems corrupted or out of sync.
    """
    db_path = _get_db_path(ctx)
    stats = do_reindex(db_path)
    return {
        "status": "complete",
        "files_indexed": stats["files"],
        "messages_indexed": stats["messages"],
        "sessions_found": stats["sessions"],
        "duration_seconds": stats["duration_seconds"],
    }

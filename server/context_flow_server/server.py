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
    tags: list[str] | None = None,
) -> list[dict]:
    """Search across all indexed Claude Code conversations.

    Args:
        query: Full-text search query (supports FTS5 syntax: AND, OR, NOT, "phrases")
        limit: Maximum number of results (default 10)
        project: Filter by project directory path (substring match)
        date_from: Filter messages from this date (ISO format, e.g. "2026-01-15")
        date_to: Filter messages up to this date (ISO format)
        tags: Filter to messages with ALL of these tags (e.g. ["review:ux", "insight"])
    """
    db_path = _get_db_path(ctx)
    conn = get_connection(db_path)

    try:
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

        # Tag filter: require ALL specified tags via repeated EXISTS subqueries
        if tags:
            for tag in tags:
                where_clauses.append(
                    "EXISTS (SELECT 1 FROM message_tags mt WHERE mt.message_id = m.id AND mt.tag = ?)"
                )
                params.append(tag)

        where = " AND ".join(where_clauses)
        params.append(limit)

        sql = f"""
            SELECT
                m.id,
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

    If the identifier is a slug that spans multiple sessions (via "continue"),
    all sessions in the chain are combined into one chronological stream.

    Args:
        session_id_or_slug: Session UUID or slug (e.g. "sorted-humming-fox")
        around_timestamp: If provided, return ~20 messages centered on this timestamp
        roles: Filter by message roles (e.g. ["user", "assistant"]). Options: user, assistant, tool_summary, plan
        limit: Maximum messages to return (default 200)
    """
    db_path = _get_db_path(ctx)
    conn = get_connection(db_path)

    try:
        # First, try exact session_id match
        session = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id_or_slug,)
        ).fetchone()

        if session:
            # Exact session ID match — single session
            sessions = [dict(session)]
            session_ids = [session["session_id"]]
        else:
            # Slug lookup — find ALL sessions in the chain
            rows = conn.execute(
                """SELECT * FROM sessions WHERE slug = ?
                   ORDER BY first_timestamp ASC""",
                (session_id_or_slug,)
            ).fetchall()

            if not rows:
                return {"error": f"Session not found: {session_id_or_slug}"}

            sessions = [dict(r) for r in rows]
            session_ids = [r["session_id"] for r in rows]

        # Build message query across all sessions in the chain
        placeholders = ",".join("?" * len(session_ids))
        where_clauses = [f"session_id IN ({placeholders})"]
        params: list = list(session_ids)

        if roles:
            role_placeholders = ",".join("?" * len(roles))
            where_clauses.append(f"role IN ({role_placeholders})")
            params.extend(roles)

        where = " AND ".join(where_clauses)

        if around_timestamp:
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
            "sessions": sessions,
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
    tags: list[str] | None = None,
) -> list[dict]:
    """List recent Claude Code sessions with metadata.

    Args:
        limit: Maximum sessions to return (default 20)
        project: Filter by project directory path (substring match)
        date_from: Filter sessions starting from this date (ISO format)
        date_to: Filter sessions up to this date (ISO format)
        tags: Filter to sessions with ALL of these tags (e.g. ["workstream:game-tracking", "has:tests"])
    """
    db_path = _get_db_path(ctx)
    conn = get_connection(db_path)

    try:
        where_clauses = []
        params: list = []

        if project:
            where_clauses.append("s.project_dir LIKE ?")
            params.append(f"%{project}%")
        if date_from:
            where_clauses.append("s.last_timestamp >= ?")
            params.append(date_from)
        if date_to:
            end = date_to + "T23:59:59Z" if "T" not in date_to else date_to
            where_clauses.append("s.first_timestamp <= ?")
            params.append(end)

        if tags:
            for tag in tags:
                where_clauses.append(
                    "EXISTS (SELECT 1 FROM session_tags st WHERE st.session_id = s.session_id AND st.tag = ?)"
                )
                params.append(tag)

        where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        params.append(limit)

        rows = conn.execute(
            f"""SELECT s.session_id, s.project_dir, s.slug, s.first_timestamp,
                       s.last_timestamp, s.message_count, s.git_branch, s.cwd
                FROM sessions s {where}
                ORDER BY s.last_timestamp DESC
                LIMIT ?""",
            params
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


@mcp.tool()
def tag_message(
    message_id: int,
    tags: list[str],
    ctx: Context[ServerSession, AppContext],
) -> dict:
    """Manually tag a message for future discoverability.

    Args:
        message_id: Integer message ID (from search_history or get_conversation results)
        tags: List of tag strings to apply (e.g. ["review:ux", "important"])
    """
    db_path = _get_db_path(ctx)
    conn = get_connection(db_path)

    try:
        # Verify message exists
        msg = conn.execute(
            "SELECT id, session_id, role, timestamp FROM messages WHERE id = ?",
            (message_id,)
        ).fetchone()
        if not msg:
            return {"error": f"Message not found: {message_id}"}

        conn.executemany(
            "INSERT OR IGNORE INTO message_tags (message_id, tag, source) VALUES (?, ?, ?)",
            [(message_id, tag, "manual") for tag in tags],
        )
        conn.commit()

        # Return updated tag list
        tag_rows = conn.execute(
            "SELECT tag, source FROM message_tags WHERE message_id = ?",
            (message_id,)
        ).fetchall()

        return {
            "message_id": message_id,
            "session_id": msg["session_id"],
            "role": msg["role"],
            "timestamp": msg["timestamp"],
            "tags": [{"tag": r["tag"], "source": r["source"]} for r in tag_rows],
        }
    finally:
        conn.close()


@mcp.tool()
def tag_session(
    session_id: str,
    tags: list[str],
    ctx: Context[ServerSession, AppContext],
) -> dict:
    """Manually tag a session (e.g. associate with a workstream).

    Args:
        session_id: Session UUID
        tags: List of tag strings (e.g. ["workstream:game-tracking", "important"])
    """
    db_path = _get_db_path(ctx)
    conn = get_connection(db_path)

    try:
        session = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        if not session:
            return {"error": f"Session not found: {session_id}"}

        conn.executemany(
            "INSERT OR IGNORE INTO session_tags (session_id, tag, source) VALUES (?, ?, ?)",
            [(session_id, tag, "manual") for tag in tags],
        )
        conn.commit()

        tag_rows = conn.execute(
            "SELECT tag, source FROM session_tags WHERE session_id = ?",
            (session_id,)
        ).fetchall()

        return {
            "session_id": session_id,
            "slug": session["slug"],
            "tags": [{"tag": r["tag"], "source": r["source"]} for r in tag_rows],
        }
    finally:
        conn.close()


@mcp.tool()
def list_tags(
    ctx: Context[ServerSession, AppContext],
    scope: str = "all",
) -> list[dict]:
    """List all tags with counts for discoverability.

    Args:
        scope: "all", "message", or "session"
    """
    db_path = _get_db_path(ctx)
    conn = get_connection(db_path)

    try:
        results: dict[str, dict] = {}

        if scope in ("all", "message"):
            rows = conn.execute(
                """SELECT tag, source, COUNT(*) as cnt
                   FROM message_tags GROUP BY tag, source
                   ORDER BY cnt DESC"""
            ).fetchall()
            for r in rows:
                tag = r["tag"]
                if tag not in results:
                    results[tag] = {"tag": tag, "scope": "message", "auto": 0, "manual": 0, "total": 0}
                results[tag][r["source"]] += r["cnt"]
                results[tag]["total"] += r["cnt"]

        if scope in ("all", "session"):
            rows = conn.execute(
                """SELECT tag, source, COUNT(*) as cnt
                   FROM session_tags GROUP BY tag, source
                   ORDER BY cnt DESC"""
            ).fetchall()
            for r in rows:
                tag = r["tag"]
                if tag not in results:
                    results[tag] = {"tag": tag, "scope": "session", "auto": 0, "manual": 0, "total": 0}
                elif results[tag]["scope"] == "message":
                    results[tag]["scope"] = "both"
                else:
                    results[tag]["scope"] = "session"
                results[tag][r["source"]] += r["cnt"]
                results[tag]["total"] += r["cnt"]

        return sorted(results.values(), key=lambda x: x["total"], reverse=True)
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

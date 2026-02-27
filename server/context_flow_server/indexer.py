"""JSONL transcript parser and incremental indexer."""

import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db import decode_project_dir, get_connection
from .tagger import auto_tag_messages, auto_tag_session

# Matches UUID hex strings with dashes (e.g. "70620f58-abcd-1234-ef56-789012345678")
_UUID_RE = re.compile(r"^[a-f0-9][a-f0-9-]+[a-f0-9]$")

logger = logging.getLogger(__name__)

# Entry types we skip entirely
SKIP_TYPES = frozenset({
    "progress", "system", "file-history-snapshot", "queue-operation",
})

# Tool summary formatters: tool_name -> callable(input_dict) -> str
def _format_tool_summary(tool_name: str, input_data: dict) -> str:
    """Format a tool_use block into a searchable summary line."""
    match tool_name:
        case "Read":
            return f"[Read] {input_data.get('file_path', '')}"
        case "Edit":
            return f"[Edit] {input_data.get('file_path', '')}"
        case "Write":
            return f"[Write] {input_data.get('file_path', '')}"
        case "Bash":
            cmd = input_data.get("command", "")
            return f"[Bash] {cmd[:200]}"
        case "Grep":
            pattern = input_data.get("pattern", "")
            path = input_data.get("path", "")
            return f"[Grep] pattern={pattern} path={path}"
        case "Glob":
            return f"[Glob] {input_data.get('pattern', '')}"
        case "Task":
            return f"[Task] {input_data.get('description', '')}"
        case "WebSearch":
            return f"[WebSearch] {input_data.get('query', '')}"
        case "WebFetch":
            return f"[WebFetch] {input_data.get('url', '')}"
        case _:
            return f"[{tool_name}]"


def _extract_from_entry(entry: dict) -> list[dict]:
    """Extract indexable messages from a single JSONL entry.

    Returns a list of dicts with keys: role, content, timestamp, model.
    """
    entry_type = entry.get("type")
    if entry_type in SKIP_TYPES:
        return []

    timestamp = entry.get("timestamp", "")
    message = entry.get("message", {})
    results = []

    if entry_type == "user":
        content = message.get("content") if isinstance(message, dict) else None

        # Only index actual human text input (string), not tool_result arrays
        if isinstance(content, str) and content.strip():
            results.append({
                "role": "user",
                "content": content,
                "timestamp": timestamp,
                "model": None,
            })

        # planContent is a separate high-value field
        plan = entry.get("planContent")
        if plan and isinstance(plan, str) and plan.strip():
            results.append({
                "role": "plan",
                "content": plan,
                "timestamp": timestamp,
                "model": None,
            })

    elif entry_type == "assistant":
        content_blocks = message.get("content", []) if isinstance(message, dict) else []
        if not isinstance(content_blocks, list):
            return []

        model = message.get("model") if isinstance(message, dict) else None

        # Collect text blocks
        text_parts = []
        tool_summaries = []

        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")

            if block_type == "text":
                text = block.get("text", "")
                if text.strip():
                    text_parts.append(text)

            elif block_type == "tool_use":
                tool_name = block.get("name", "Unknown")
                tool_input = block.get("input", {})
                if not isinstance(tool_input, dict):
                    tool_input = {}
                tool_summaries.append(
                    _format_tool_summary(tool_name, tool_input)
                )

        if text_parts:
            results.append({
                "role": "assistant",
                "content": "\n\n".join(text_parts),
                "timestamp": timestamp,
                "model": model,
            })

        if tool_summaries:
            results.append({
                "role": "tool_summary",
                "content": "\n".join(tool_summaries),
                "timestamp": timestamp,
                "model": model,
            })

    return results


def _parse_file(
    filepath: Path,
    byte_offset: int = 0,
) -> tuple[list[dict], dict[str, dict]]:
    """Parse a JSONL file from the given byte offset.

    Returns:
        (messages, session_metas)
        - messages: list of dicts with session_id, role, content, timestamp, model
        - session_metas: dict of session_id -> metadata dict
    """
    messages = []
    session_metas: dict[str, dict] = {}

    project_dir_name = filepath.parent.name
    project_dir = decode_project_dir(project_dir_name)

    with open(filepath, "rb") as f:
        if byte_offset > 0:
            f.seek(byte_offset)

        for raw_line in f:
            line = raw_line.strip()
            if not line or line[0:1] != b"{":
                continue

            # Handle null bytes and corruption
            try:
                line_str = line.decode("utf-8", errors="replace")
                line_str = line_str.replace("\x00", "")
                entry = json.loads(line_str)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            session_id = entry.get("sessionId")
            if not session_id:
                continue

            # Update session metadata
            if session_id not in session_metas:
                session_metas[session_id] = {
                    "session_id": session_id,
                    "project_dir": project_dir,
                    "slug": None,
                    "first_timestamp": None,
                    "last_timestamp": None,
                    "message_count": 0,
                    "git_branch": None,
                    "cwd": None,
                }

            meta = session_metas[session_id]
            ts = entry.get("timestamp")
            if ts:
                if meta["first_timestamp"] is None or ts < meta["first_timestamp"]:
                    meta["first_timestamp"] = ts
                if meta["last_timestamp"] is None or ts > meta["last_timestamp"]:
                    meta["last_timestamp"] = ts

            if entry.get("slug"):
                meta["slug"] = entry["slug"]
            if entry.get("gitBranch"):
                meta["git_branch"] = entry["gitBranch"]
            if entry.get("cwd"):
                meta["cwd"] = entry["cwd"]

            # Extract indexable messages
            extracted = _extract_from_entry(entry)
            for msg in extracted:
                msg["session_id"] = session_id
                meta["message_count"] += 1
            messages.extend(extracted)

    return messages, session_metas


def index_all(
    db_path: Path | str,
    transcript_root: Path | str | None = None,
) -> dict:
    """Incrementally index all JSONL transcript files.

    Returns stats dict with files, messages, sessions, skipped, duration_seconds.
    """
    if transcript_root is None:
        transcript_root = Path.home() / ".claude" / "projects"
    else:
        transcript_root = Path(transcript_root)

    if not transcript_root.exists():
        logger.warning(f"Transcript root does not exist: {transcript_root}")
        return {"files": 0, "messages": 0, "sessions": 0, "skipped": 0,
                "duration_seconds": 0.0}

    start = datetime.now(timezone.utc)
    conn = get_connection(db_path)

    total_messages = 0
    total_files = 0
    total_skipped = 0
    all_session_ids = set()

    try:
        # Collect all JSONL files, skipping subagents
        jsonl_files = []
        for root, dirs, files in os.walk(transcript_root):
            # Skip subagent directories
            if "subagents" in root.split(os.sep):
                continue
            for fn in files:
                if fn.endswith(".jsonl"):
                    jsonl_files.append(Path(root) / fn)

        logger.info(f"Found {len(jsonl_files)} JSONL files to check")

        for filepath in jsonl_files:
            try:
                file_size = filepath.stat().st_size
            except OSError:
                continue

            # Check indexed_files table
            row = conn.execute(
                "SELECT size, byte_offset FROM indexed_files WHERE path = ?",
                (str(filepath),)
            ).fetchone()

            if row is not None:
                stored_size = row["size"]
                stored_offset = row["byte_offset"]

                if file_size == stored_size:
                    # Unchanged — skip
                    total_skipped += 1
                    continue
                elif file_size > stored_size:
                    # File grew (append-only) — parse from where we left off
                    byte_offset = stored_offset
                elif file_size < stored_size:
                    # File shrank (rewritten, rare) — full re-parse
                    # Delete old messages for sessions from this file
                    logger.info(f"File shrank, re-indexing: {filepath}")
                    byte_offset = 0
                    # We can't easily track which sessions came from which file,
                    # so just re-parse. The session upsert handles duplicates.
            else:
                byte_offset = 0

            # Parse the file
            messages, session_metas = _parse_file(filepath, byte_offset)

            if messages or session_metas:
                # Upsert sessions
                for meta in session_metas.values():
                    _upsert_session(conn, meta)
                    all_session_ids.add(meta["session_id"])

                # Insert messages and capture IDs for tagging
                if messages:
                    # Get the current max ID before inserting
                    row = conn.execute(
                        "SELECT COALESCE(MAX(id), 0) AS max_id FROM messages"
                    ).fetchone()
                    max_id_before = row["max_id"]

                    conn.executemany(
                        """INSERT INTO messages
                           (session_id, role, content, timestamp, model)
                           VALUES (?, ?, ?, ?, ?)""",
                        [(m["session_id"], m["role"], m["content"],
                          m["timestamp"], m["model"]) for m in messages]
                    )

                    # Calculate inserted message IDs
                    new_ids = list(range(max_id_before + 1, max_id_before + 1 + len(messages)))
                    auto_tag_messages(conn, new_ids)

                total_messages += len(messages)
                total_files += 1

            # Update indexed_files
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """INSERT INTO indexed_files (path, size, byte_offset, indexed_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(path) DO UPDATE SET
                       size = excluded.size,
                       byte_offset = excluded.byte_offset,
                       indexed_at = excluded.indexed_at""",
                (str(filepath), file_size, file_size, now)
            )

        # Auto-tag sessions that had new messages
        for sid in all_session_ids:
            auto_tag_session(conn, sid)

        # Apply workstream tags from session markers
        _apply_session_markers(conn, all_session_ids)

        conn.commit()

    finally:
        conn.close()

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    stats = {
        "files": total_files,
        "messages": total_messages,
        "sessions": len(all_session_ids),
        "skipped": total_skipped,
        "duration_seconds": round(elapsed, 2),
    }
    logger.info(
        f"Indexing complete: {stats['files']} files processed, "
        f"{stats['skipped']} unchanged, "
        f"{stats['messages']} messages, "
        f"{stats['sessions']} sessions in {stats['duration_seconds']}s"
    )
    return stats


def _upsert_session(conn: sqlite3.Connection, meta: dict) -> None:
    """Insert or update a session record, merging timestamp ranges."""
    existing = conn.execute(
        "SELECT * FROM sessions WHERE session_id = ?",
        (meta["session_id"],)
    ).fetchone()

    if existing is None:
        conn.execute(
            """INSERT INTO sessions
               (session_id, project_dir, slug, first_timestamp, last_timestamp,
                message_count, git_branch, cwd)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (meta["session_id"], meta["project_dir"], meta["slug"],
             meta["first_timestamp"], meta["last_timestamp"],
             meta["message_count"], meta["git_branch"], meta["cwd"])
        )
    else:
        # Merge: expand timestamp range, accumulate message count, update latest fields
        first_ts = meta["first_timestamp"]
        if existing["first_timestamp"] and first_ts:
            first_ts = min(existing["first_timestamp"], first_ts)
        elif existing["first_timestamp"]:
            first_ts = existing["first_timestamp"]

        last_ts = meta["last_timestamp"]
        if existing["last_timestamp"] and last_ts:
            last_ts = max(existing["last_timestamp"], last_ts)
        elif existing["last_timestamp"]:
            last_ts = existing["last_timestamp"]

        conn.execute(
            """UPDATE sessions SET
                   project_dir = COALESCE(?, project_dir),
                   slug = COALESCE(?, slug),
                   first_timestamp = ?,
                   last_timestamp = ?,
                   message_count = message_count + ?,
                   git_branch = COALESCE(?, git_branch),
                   cwd = COALESCE(?, cwd)
               WHERE session_id = ?""",
            (meta["project_dir"], meta["slug"], first_ts, last_ts,
             meta["message_count"], meta["git_branch"], meta["cwd"],
             meta["session_id"])
        )


def _get_marker_dir() -> Path:
    """Return the session markers directory path."""
    return Path(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    ) / "context-flow" / "session-markers"


def _read_and_apply_marker(conn: sqlite3.Connection, marker_path: Path, sid: str) -> None:
    """Read a single session marker file and apply its workstream tag."""
    # Validate session ID format to prevent path traversal
    if not _UUID_RE.match(sid):
        return
    try:
        with open(marker_path) as f:
            data = json.load(f)
        workstream = data.get("workstream")
        if workstream:
            conn.execute(
                "INSERT OR IGNORE INTO session_tags (session_id, tag, source) VALUES (?, ?, ?)",
                (sid, f"workstream:{workstream}", "auto"),
            )
    except (json.JSONDecodeError, OSError):
        logger.warning(f"Failed to read session marker: {marker_path}")


def _apply_session_markers(conn: sqlite3.Connection, session_ids: set[str]) -> None:
    """Read workstream marker files and apply session tags."""
    marker_dir = _get_marker_dir()
    if not marker_dir.exists():
        return

    for sid in session_ids:
        marker_path = marker_dir / f"{sid}.json"
        if marker_path.exists():
            _read_and_apply_marker(conn, marker_path, sid)


def _apply_all_session_markers(conn: sqlite3.Connection) -> None:
    """Scan all session markers and apply tags. Used during full reindex."""
    marker_dir = _get_marker_dir()
    if not marker_dir.exists():
        return

    for marker_path in marker_dir.glob("*.json"):
        sid = marker_path.stem
        # Only tag sessions that exist in the DB
        exists = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (sid,)
        ).fetchone()
        if exists:
            _read_and_apply_marker(conn, marker_path, sid)


def reindex(db_path: Path | str, transcript_root: Path | str | None = None) -> dict:
    """Force a full re-index by clearing all data and rebuilding."""
    conn = get_connection(db_path)
    try:
        # Clear all message tags (message IDs change on re-insert, so manual
        # message tags become orphaned). Session tags preserve manual entries
        # since session_id is a stable UUID.
        conn.execute("DELETE FROM message_tags")
        conn.execute("DELETE FROM session_tags WHERE source = 'auto'")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM indexed_files")
        # Rebuild FTS index
        conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
        conn.commit()
    finally:
        conn.close()

    stats = index_all(db_path, transcript_root)

    # Apply all session markers after full reindex
    conn = get_connection(db_path)
    try:
        _apply_all_session_markers(conn)
        conn.commit()
    finally:
        conn.close()

    return stats

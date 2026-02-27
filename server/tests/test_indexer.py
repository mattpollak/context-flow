"""Tests for the JSONL indexer."""

import json
import tempfile
from pathlib import Path

from context_flow_server.db import ensure_schema, get_connection
from context_flow_server.indexer import _extract_from_entry, _parse_file, _UUID_RE, index_all


# --- Entry extraction tests ---


def test_extract_user_text():
    entry = {
        "type": "user",
        "timestamp": "2026-01-01T00:00:00Z",
        "message": {"content": "Hello world"},
    }
    results = _extract_from_entry(entry)
    assert len(results) == 1
    assert results[0]["role"] == "user"
    assert results[0]["content"] == "Hello world"


def test_extract_user_tool_result_skipped():
    """User entries with array content (tool_result) should be skipped."""
    entry = {
        "type": "user",
        "timestamp": "2026-01-01T00:00:00Z",
        "message": {"content": [{"type": "tool_result", "content": "result"}]},
    }
    results = _extract_from_entry(entry)
    assert len(results) == 0


def test_extract_assistant_text_and_tools():
    entry = {
        "type": "assistant",
        "timestamp": "2026-01-01T00:00:00Z",
        "message": {
            "model": "claude-opus-4-6",
            "content": [
                {"type": "text", "text": "Let me check that."},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/test.py"}},
            ],
        },
    }
    results = _extract_from_entry(entry)
    assert len(results) == 2
    text_msg = next(r for r in results if r["role"] == "assistant")
    assert text_msg["content"] == "Let me check that."
    assert text_msg["model"] == "claude-opus-4-6"
    tool_msg = next(r for r in results if r["role"] == "tool_summary")
    assert "[Read] /tmp/test.py" in tool_msg["content"]


def test_extract_plan_content():
    entry = {
        "type": "user",
        "timestamp": "2026-01-01T00:00:00Z",
        "message": {"content": "approve the plan"},
        "planContent": "## Phase 1\nDo the thing",
    }
    results = _extract_from_entry(entry)
    assert len(results) == 2
    plan = next(r for r in results if r["role"] == "plan")
    assert "Phase 1" in plan["content"]


def test_extract_skips_progress_type():
    entry = {"type": "progress", "timestamp": "2026-01-01T00:00:00Z"}
    assert _extract_from_entry(entry) == []


def test_extract_handles_corrupted_assistant():
    """Non-list content blocks should be handled gracefully."""
    entry = {
        "type": "assistant",
        "timestamp": "2026-01-01T00:00:00Z",
        "message": {"content": "not a list"},
    }
    assert _extract_from_entry(entry) == []


# --- File parsing tests ---


def _write_jsonl(tmpdir: str, project_dir: str, entries: list[dict]) -> Path:
    """Write entries to a JSONL file in the expected directory structure."""
    project_path = Path(tmpdir) / project_dir
    project_path.mkdir(parents=True, exist_ok=True)
    filepath = project_path / "transcript.jsonl"
    with open(filepath, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return filepath


def test_parse_file_basic():
    with tempfile.TemporaryDirectory() as tmpdir:
        entries = [
            {
                "type": "user",
                "sessionId": "session-1",
                "timestamp": "2026-01-01T10:00:00Z",
                "slug": "test-convo",
                "message": {"content": "Hi there"},
            },
            {
                "type": "assistant",
                "sessionId": "session-1",
                "timestamp": "2026-01-01T10:01:00Z",
                "message": {
                    "content": [{"type": "text", "text": "Hello!"}],
                },
            },
        ]
        filepath = _write_jsonl(tmpdir, "-test-project", entries)
        messages, session_metas = _parse_file(filepath)

        assert len(messages) == 2
        assert "session-1" in session_metas
        meta = session_metas["session-1"]
        assert meta["slug"] == "test-convo"
        assert meta["message_count"] == 2


def test_parse_file_handles_corruption():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "-test"
        project_path.mkdir(parents=True)
        filepath = project_path / "bad.jsonl"
        with open(filepath, "w") as f:
            f.write("not json\n")
            f.write("{invalid json too\n")
            f.write(json.dumps({
                "type": "user", "sessionId": "s1",
                "timestamp": "2026-01-01T00:00:00Z",
                "message": {"content": "valid line"},
            }) + "\n")

        messages, metas = _parse_file(filepath)
        assert len(messages) == 1  # Only the valid line


def test_parse_file_byte_offset():
    """Parsing from an offset should only return messages after that point."""
    with tempfile.TemporaryDirectory() as tmpdir:
        entries = [
            {"type": "user", "sessionId": "s1", "timestamp": "2026-01-01T10:00:00Z",
             "message": {"content": "First"}},
            {"type": "user", "sessionId": "s1", "timestamp": "2026-01-01T10:01:00Z",
             "message": {"content": "Second"}},
        ]
        filepath = _write_jsonl(tmpdir, "-test", entries)

        # Parse full file to get offset after first line
        first_line_size = len(json.dumps(entries[0]).encode()) + 1  # +1 for newline

        messages, _ = _parse_file(filepath, byte_offset=first_line_size)
        assert len(messages) == 1
        assert messages[0]["content"] == "Second"


# --- UUID validation ---


def test_uuid_regex_valid():
    assert _UUID_RE.match("70620f58-abcd-1234-ef56-789012345678")
    assert _UUID_RE.match("abc123")


def test_uuid_regex_rejects_traversal():
    assert not _UUID_RE.match("../../etc/passwd")
    assert not _UUID_RE.match("../something")
    assert not _UUID_RE.match("")


# --- Full index_all integration ---


def test_index_all_basic():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)

        # Create a fake transcript
        transcript_root = Path(tmpdir) / "projects"
        project_dir = transcript_root / "-test-project"
        project_dir.mkdir(parents=True)
        filepath = project_dir / "convo.jsonl"
        entries = [
            {"type": "user", "sessionId": "s1", "timestamp": "2026-01-01T10:00:00Z",
             "slug": "test-slug", "message": {"content": "Hello"}},
            {"type": "assistant", "sessionId": "s1", "timestamp": "2026-01-01T10:01:00Z",
             "message": {"content": [{"type": "text", "text": "Hi!"}]}},
        ]
        with open(filepath, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        stats = index_all(db_path, transcript_root)
        assert stats["files"] == 1
        assert stats["messages"] == 2
        assert stats["sessions"] == 1

        # Verify data in DB
        conn = get_connection(db_path)
        try:
            session = conn.execute("SELECT * FROM sessions WHERE session_id = 's1'").fetchone()
            assert session is not None
            assert session["slug"] == "test-slug"

            msgs = conn.execute("SELECT * FROM messages ORDER BY timestamp").fetchall()
            assert len(msgs) == 2

            # FTS should work
            fts = conn.execute(
                "SELECT * FROM messages_fts WHERE messages_fts MATCH 'Hello'"
            ).fetchall()
            assert len(fts) == 1
        finally:
            conn.close()


def test_index_all_incremental():
    """Running index_all twice should skip unchanged files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)

        transcript_root = Path(tmpdir) / "projects"
        project_dir = transcript_root / "-test"
        project_dir.mkdir(parents=True)
        filepath = project_dir / "convo.jsonl"
        with open(filepath, "w") as f:
            f.write(json.dumps({
                "type": "user", "sessionId": "s1",
                "timestamp": "2026-01-01T10:00:00Z",
                "message": {"content": "Hello"},
            }) + "\n")

        stats1 = index_all(db_path, transcript_root)
        assert stats1["files"] == 1
        assert stats1["skipped"] == 0

        stats2 = index_all(db_path, transcript_root)
        assert stats2["files"] == 0
        assert stats2["skipped"] == 1  # Same file, same size

"""Tests for the JSONL indexer."""

import json
import tempfile
from pathlib import Path

from relay_server.db import ensure_schema, get_connection
from relay_server.indexer import _extract_from_entry, _parse_file, _UUID_RE, index_all, _index_session_hints


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


# --- Session hints indexing tests ---


def _insert_dummy_session(conn, session_id):
    """Insert a minimal session row so FK constraints pass."""
    conn.execute(
        """INSERT OR IGNORE INTO sessions
           (session_id, project_dir, first_timestamp, last_timestamp, message_count)
           VALUES (?, '/tmp', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 0)""",
        (session_id,),
    )


def test_index_session_hints_basic():
    """Hint files should be indexed into session_hints table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)
        conn = get_connection(db_path)

        # Create a hint file
        hints_dir = Path(tmpdir) / "hints"
        hints_dir.mkdir()
        hint = {
            "session_id": "abc-123",
            "workstream": "squadkeeper",
            "summary": ["Built feature X", "Added 5 tests"],
            "decisions": ["Used pattern Y"],
        }
        hint_file = hints_dir / "2026-03-05T043956Z-abc-123.json"
        hint_file.write_text(json.dumps(hint))

        try:
            _insert_dummy_session(conn, "abc-123")
            count = _index_session_hints(conn, hints_dir)
            conn.commit()
            assert count == 1

            rows = conn.execute(
                "SELECT * FROM session_hints WHERE session_id = 'abc-123'"
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["workstream"] == "squadkeeper"
            assert rows[0]["source_file"] == "2026-03-05T043956Z-abc-123.json"
            assert rows[0]["timestamp"] == "2026-03-05T04:39:56Z"
            assert json.loads(rows[0]["summary"]) == ["Built feature X", "Added 5 tests"]
            assert json.loads(rows[0]["decisions"]) == ["Used pattern Y"]
        finally:
            conn.close()


def test_index_session_hints_idempotent():
    """Re-indexing the same hint file should not create duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)
        conn = get_connection(db_path)

        hints_dir = Path(tmpdir) / "hints"
        hints_dir.mkdir()
        hint = {"session_id": "abc-123", "workstream": "ws", "summary": ["bullet"]}
        (hints_dir / "2026-03-05T000000Z-abc-123.json").write_text(json.dumps(hint))

        try:
            _insert_dummy_session(conn, "abc-123")
            count1 = _index_session_hints(conn, hints_dir)
            conn.commit()
            count2 = _index_session_hints(conn, hints_dir)
            conn.commit()
            assert count1 == 1
            assert count2 == 0  # Skipped — already indexed

            rows = conn.execute("SELECT COUNT(*) as cnt FROM session_hints").fetchone()
            assert rows["cnt"] == 1
        finally:
            conn.close()


def test_index_session_hints_multiple_segments():
    """Multiple hint files for the same session should create multiple rows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)
        conn = get_connection(db_path)

        hints_dir = Path(tmpdir) / "hints"
        hints_dir.mkdir()
        hint1 = {"session_id": "abc-123", "workstream": "ws1", "summary": ["segment 1"]}
        hint2 = {"session_id": "abc-123", "workstream": "ws2", "summary": ["segment 2"]}
        (hints_dir / "2026-03-05T100000Z-abc-123.json").write_text(json.dumps(hint1))
        (hints_dir / "2026-03-05T140000Z-abc-123.json").write_text(json.dumps(hint2))

        try:
            _insert_dummy_session(conn, "abc-123")
            count = _index_session_hints(conn, hints_dir)
            conn.commit()
            assert count == 2

            rows = conn.execute(
                "SELECT * FROM session_hints WHERE session_id = 'abc-123' ORDER BY timestamp"
            ).fetchall()
            assert len(rows) == 2
            assert rows[0]["workstream"] == "ws1"
            assert rows[1]["workstream"] == "ws2"
        finally:
            conn.close()


def test_index_session_hints_skips_malformed():
    """Malformed or incomplete hint files should be skipped without error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)
        conn = get_connection(db_path)

        hints_dir = Path(tmpdir) / "hints"
        hints_dir.mkdir()
        # Malformed JSON
        (hints_dir / "2026-03-05T000000Z-bad1.json").write_text("not json")
        # Missing required fields
        (hints_dir / "2026-03-05T000000Z-bad2.json").write_text(json.dumps({"session_id": "x"}))
        # Valid
        valid = {"session_id": "good", "workstream": "ws", "summary": ["ok"]}
        (hints_dir / "2026-03-05T000000Z-good.json").write_text(json.dumps(valid))

        try:
            _insert_dummy_session(conn, "good")
            count = _index_session_hints(conn, hints_dir)
            conn.commit()
            assert count == 1  # Only the valid one
        finally:
            conn.close()


def test_index_session_hints_skips_unknown_session():
    """Hints for sessions not in the DB should be skipped gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)
        conn = get_connection(db_path)

        hints_dir = Path(tmpdir) / "hints"
        hints_dir.mkdir()
        hint = {"session_id": "nonexistent-session", "workstream": "ws", "summary": ["test"]}
        (hints_dir / "2026-03-05T000000Z-nonexistent.json").write_text(json.dumps(hint))

        try:
            count = _index_session_hints(conn, hints_dir)
            conn.commit()
            assert count == 0  # Skipped — session doesn't exist
        finally:
            conn.close()

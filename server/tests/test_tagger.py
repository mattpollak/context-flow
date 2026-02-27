"""Tests for auto-tagging rules."""

import sqlite3
import tempfile
from pathlib import Path

from context_flow_server.db import ensure_schema, get_connection
from context_flow_server.tagger import (
    _check_decision,
    _check_has_browser,
    _check_has_planning,
    _check_has_tests,
    _check_insight,
    _check_plan,
    _check_review_ux,
    auto_tag_messages,
    auto_tag_session,
)


# --- Message-level rule tests ---


def test_review_ux_requires_substantial_content():
    short = "Quick UX review looks good."
    assert not _check_review_ux("assistant", short)

    long = "UX review " + "x" * 600
    assert _check_review_ux("assistant", long)


def test_review_ux_requires_assistant_role():
    content = "UX review " + "x" * 600
    assert not _check_review_ux("user", content)


def test_plan_detects_plan_role():
    assert _check_plan("plan", "any content here")


def test_plan_detects_phase_implementation_pattern():
    content = "## Phase 1\nDo stuff\n## Implementation\nBuild it" + "x" * 500
    assert _check_plan("assistant", content)


def test_plan_rejects_missing_pattern():
    content = "Just a normal message about planning" + "x" * 500
    assert not _check_plan("assistant", content)


def test_insight_detects_marker():
    assert _check_insight("assistant", "Here is the answer\n★ Insight\nSomething cool")


def test_insight_requires_assistant():
    assert not _check_insight("user", "★ Insight something")


def test_decision_detects_phrases():
    content = "After analysis, decided to use Redis for caching" + "x" * 500
    assert _check_decision("assistant", content)


def test_decision_requires_substantial():
    assert not _check_decision("assistant", "decided to use it")


# --- Session-level rule tests ---


def test_has_browser_detects_playwright():
    msgs = [{"role": "tool_summary", "content": "[browser_snapshot] captured page"}]
    assert _check_has_browser(msgs)


def test_has_browser_ignores_non_tool():
    msgs = [{"role": "assistant", "content": "browser_snapshot is a tool"}]
    assert not _check_has_browser(msgs)


def test_has_tests_detects_pytest():
    msgs = [{"role": "tool_summary", "content": "[Bash] pytest tests/ -v"}]
    assert _check_has_tests(msgs)


def test_has_planning_detects_plan_role():
    msgs = [
        {"role": "assistant", "content": "Let me plan this out"},
        {"role": "plan", "content": "## Phase 1"},
    ]
    assert _check_has_planning(msgs)


# --- Integration: auto_tag_messages ---


def _make_db():
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"
    ensure_schema(db_path)
    conn = get_connection(db_path)
    # Insert a session
    conn.execute(
        "INSERT INTO sessions (session_id, project_dir, message_count) VALUES (?, ?, ?)",
        ("test-session", "/test", 0),
    )
    return conn, db_path


def test_auto_tag_messages_tags_insight():
    conn, _ = _make_db()
    try:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("test-session", "assistant", "Here is a ★ Insight about something", "2026-01-01T00:00:00Z"),
        )
        msg_id = conn.execute("SELECT MAX(id) FROM messages").fetchone()[0]
        count = auto_tag_messages(conn, [msg_id])
        assert count >= 1
        tags = conn.execute(
            "SELECT tag FROM message_tags WHERE message_id = ?", (msg_id,)
        ).fetchall()
        tag_names = {r[0] for r in tags}
        assert "insight" in tag_names
    finally:
        conn.close()


def test_auto_tag_session_optimized_query():
    """auto_tag_session only fetches tool_summary and plan roles."""
    conn, _ = _make_db()
    try:
        # Insert a plan message and a tool_summary with pytest
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("test-session", "plan", "## Phase 1\nPlan content", "2026-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("test-session", "tool_summary", "[Bash] pytest tests/ -v", "2026-01-01T00:01:00Z"),
        )
        count = auto_tag_session(conn, "test-session")
        assert count >= 2  # has:planning + has:tests
        tags = conn.execute(
            "SELECT tag FROM session_tags WHERE session_id = ?", ("test-session",)
        ).fetchall()
        tag_names = {r[0] for r in tags}
        assert "has:planning" in tag_names
        assert "has:tests" in tag_names
    finally:
        conn.close()

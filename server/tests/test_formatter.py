"""Tests for the markdown formatter."""

from context_flow_server.formatter import _is_noise, _truncate, format_conversation


def test_truncate_short_content():
    assert _truncate("hello", 100) == "hello"


def test_truncate_long_content():
    content = "x" * 600
    result = _truncate(content, 500)
    assert result.startswith("x" * 500)
    assert "100 more chars" in result


def test_is_noise_empty():
    assert _is_noise({"content": ""})
    assert _is_noise({"content": "   "})


def test_is_noise_system_reminder():
    assert _is_noise({"content": "<system-reminder>some internal stuff</system-reminder>"})


def test_is_noise_command():
    assert _is_noise({"content": "<command-name>compact</command-name>"})


def test_is_noise_normal_message():
    assert not _is_noise({"content": "Here is a real assistant response."})


def test_format_conversation_basic():
    sessions = [{
        "session_id": "abc-123",
        "slug": "test-slug",
        "project_dir": "/home/matt/project",
        "git_branch": "main",
        "first_timestamp": "2026-01-01T10:00:00Z",
        "last_timestamp": "2026-01-01T11:00:00Z",
    }]
    messages = [
        {"session_id": "abc-123", "role": "user", "content": "Hello",
         "timestamp": "2026-01-01T10:00:00Z", "id": 1},
        {"session_id": "abc-123", "role": "assistant", "content": "Hi there!",
         "timestamp": "2026-01-01T10:01:00Z", "id": 2},
    ]
    result = format_conversation(sessions, messages)
    assert "## test-slug" in result
    assert "**User**" in result
    assert "**Assistant**" in result
    assert "Hello" in result
    assert "Hi there!" in result


def test_format_conversation_filters_noise():
    sessions = [{
        "session_id": "abc-123",
        "slug": "test-slug",
        "project_dir": "",
        "git_branch": "",
        "first_timestamp": "2026-01-01T10:00:00Z",
        "last_timestamp": "2026-01-01T10:00:00Z",
    }]
    messages = [
        {"session_id": "abc-123", "role": "user", "content": "Hello",
         "timestamp": "2026-01-01T10:00:00Z", "id": 1},
        {"session_id": "abc-123", "role": "assistant",
         "content": "<system-reminder>internal</system-reminder>",
         "timestamp": "2026-01-01T10:00:01Z", "id": 2},
    ]
    result = format_conversation(sessions, messages)
    assert "Hello" in result
    assert "system-reminder" not in result


def test_format_conversation_multi_session():
    sessions = [
        {"session_id": "s1", "slug": "multi-slug", "project_dir": "", "git_branch": "",
         "first_timestamp": "2026-01-01T10:00:00Z", "last_timestamp": "2026-01-01T10:30:00Z"},
        {"session_id": "s2", "slug": "multi-slug", "project_dir": "", "git_branch": "",
         "first_timestamp": "2026-01-01T11:00:00Z", "last_timestamp": "2026-01-01T11:30:00Z"},
    ]
    messages = [
        {"session_id": "s1", "role": "user", "content": "First session",
         "timestamp": "2026-01-01T10:00:00Z", "id": 1},
        {"session_id": "s2", "role": "user", "content": "Second session",
         "timestamp": "2026-01-01T11:00:00Z", "id": 2},
    ]
    result = format_conversation(sessions, messages)
    assert "(2 sessions)" in result
    assert "Session 1 of 2" in result
    assert "Session 2 of 2" in result

"""Auto-tagging rules for messages and sessions."""

import re
import sqlite3
from collections.abc import Callable

# Minimum content length to be considered "substantial"
SUBSTANTIAL_THRESHOLD = 500


# --- Message-level tag rules ---

def _check_review_ux(role: str, content: str) -> bool:
    if role != "assistant" or len(content) < SUBSTANTIAL_THRESHOLD:
        return False
    lower = content.lower()
    return any(phrase in lower for phrase in [
        "ux review", "usability review", "user experience review",
        "user experience audit",
    ])


def _check_review_architecture(role: str, content: str) -> bool:
    if role != "assistant" or len(content) < SUBSTANTIAL_THRESHOLD:
        return False
    lower = content.lower()
    return any(phrase in lower for phrase in [
        "architecture review", "system design review",
        "architectural review", "architecture audit",
    ])


def _check_review_code(role: str, content: str) -> bool:
    if role != "assistant" or len(content) < SUBSTANTIAL_THRESHOLD:
        return False
    lower = content.lower()
    return any(phrase in lower for phrase in [
        "code review", "code quality review",
    ])


def _check_review_security(role: str, content: str) -> bool:
    if role != "assistant" or len(content) < SUBSTANTIAL_THRESHOLD:
        return False
    lower = content.lower()
    return any(phrase in lower for phrase in [
        "security review", "security audit", "vulnerability assessment",
    ])


def _check_plan(role: str, content: str) -> bool:
    if role == "plan":
        return True
    if role != "assistant" or len(content) < SUBSTANTIAL_THRESHOLD:
        return False
    return bool(
        re.search(r"##\s+Phase\s", content)
        and re.search(r"##\s+Implementation", content)
    )


def _check_decision(role: str, content: str) -> bool:
    if role != "assistant" or len(content) < SUBSTANTIAL_THRESHOLD:
        return False
    lower = content.lower()
    return any(phrase in lower for phrase in [
        "decided to ", "decision:", "the approach is",
        "chose ", " over ", "trade-off",
    ])


def _check_investigation(role: str, content: str) -> bool:
    if role != "assistant" or len(content) < SUBSTANTIAL_THRESHOLD:
        return False
    lower = content.lower()
    return any(phrase in lower for phrase in [
        "root cause", "the issue was", "found the bug",
        "the problem was", "debugging revealed",
    ])


def _check_insight(role: str, content: str) -> bool:
    if role != "assistant":
        return False
    return "★ Insight" in content


# Tag name -> check function
MESSAGE_TAG_RULES: list[tuple[str, Callable[[str, str], bool]]] = [
    ("review:ux", _check_review_ux),
    ("review:architecture", _check_review_architecture),
    ("review:code", _check_review_code),
    ("review:security", _check_review_security),
    ("plan", _check_plan),
    ("decision", _check_decision),
    ("investigation", _check_investigation),
    ("insight", _check_insight),
]


# --- Session-level tag rules ---

def _check_has_browser(messages: list[dict]) -> bool:
    for m in messages:
        if m["role"] == "tool_summary":
            content = m["content"]
            if "[browser_" in content or "playwright" in content.lower():
                return True
    return False


def _check_has_tests(messages: list[dict]) -> bool:
    for m in messages:
        if m["role"] == "tool_summary":
            content = m["content"].lower()
            if any(kw in content for kw in [
                "pytest", "vitest", "npm run test", "npm run check",
            ]):
                return True
    return False


def _check_has_deploy(messages: list[dict]) -> bool:
    for m in messages:
        if m["role"] == "tool_summary":
            content = m["content"].lower()
            if any(kw in content for kw in [
                "ssh ", "docker ", "deploy", "rsync",
            ]):
                return True
    return False


def _check_has_planning(messages: list[dict]) -> bool:
    return any(m["role"] == "plan" for m in messages)


SESSION_TAG_RULES: list[tuple[str, Callable[[list[dict]], bool]]] = [
    ("has:browser", _check_has_browser),
    ("has:tests", _check_has_tests),
    ("has:deploy", _check_has_deploy),
    ("has:planning", _check_has_planning),
]


def auto_tag_messages(conn: sqlite3.Connection, message_ids: list[int]) -> int:
    """Apply auto-tags to newly inserted messages. Returns count of tags added."""
    if not message_ids:
        return 0

    placeholders = ",".join("?" * len(message_ids))
    rows = conn.execute(
        f"SELECT id, role, content FROM messages WHERE id IN ({placeholders})",
        message_ids,
    ).fetchall()

    tags_to_insert = []
    for row in rows:
        msg_id = row["id"]
        role = row["role"]
        content = row["content"]
        for tag, check_fn in MESSAGE_TAG_RULES:
            if check_fn(role, content):
                tags_to_insert.append((msg_id, tag, "auto"))

    if tags_to_insert:
        conn.executemany(
            "INSERT OR IGNORE INTO message_tags (message_id, tag, source) VALUES (?, ?, ?)",
            tags_to_insert,
        )

    return len(tags_to_insert)


def auto_tag_session(conn: sqlite3.Connection, session_id: str) -> int:
    """Apply auto-tags to a session based on its messages. Returns count of tags added."""
    # Only fetch roles that session rules actually inspect (tool_summary + plan)
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? AND role IN ('tool_summary', 'plan')",
        (session_id,),
    ).fetchall()
    messages = [dict(r) for r in rows]

    tags_to_insert = []
    for tag, check_fn in SESSION_TAG_RULES:
        if check_fn(messages):
            tags_to_insert.append((session_id, tag, "auto"))

    if tags_to_insert:
        conn.executemany(
            "INSERT OR IGNORE INTO session_tags (session_id, tag, source) VALUES (?, ?, ?)",
            tags_to_insert,
        )

    return len(tags_to_insert)

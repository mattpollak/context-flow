# Session Hints Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Shift summarization from expensive read-time conversation fetching to near-free write-time metadata, with database-backed assembly.

**Architecture:** Claude writes small JSON hint files at save/park/switch time. The MCP server indexer picks them up and stores them in a `session_hints` table. A new `get_session_summaries` tool assembles hints by session ID in one query. The summarize skill reads hints instead of full conversations. A backfill skill generates hints for existing sessions.

**Tech Stack:** Python (MCP server), SQLite, bash scripts, markdown skills

---

### Task 1: Add `session_hints` table to database schema

**Files:**
- Modify: `server/relay_server/db.py:7-67` (SCHEMA string)
- Test: `server/tests/test_db.py` (new test)

**Step 1: Write the failing test**

Add to the end of `server/tests/test_db.py`:

```python
def test_session_hints_table_exists():
    """session_hints table should be created by ensure_schema."""
    import tempfile
    from pathlib import Path
    from relay_server.db import ensure_schema, get_connection

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)
        conn = get_connection(db_path)
        try:
            # Table exists and accepts inserts
            conn.execute(
                """INSERT INTO session_hints
                   (session_id, timestamp, source_file, workstream, summary)
                   VALUES ('test-id', '2026-03-05T00:00:00Z', 'test.json', 'ws', '["bullet"]')"""
            )
            # Unique constraint on source_file
            try:
                conn.execute(
                    """INSERT INTO session_hints
                       (session_id, timestamp, source_file, workstream, summary)
                       VALUES ('test-id', '2026-03-05T00:00:00Z', 'test.json', 'ws', '["bullet"]')"""
                )
                assert False, "Should have raised IntegrityError"
            except Exception:
                pass  # Expected — unique constraint on source_file

            # Multiple segments per session allowed (different source_file)
            conn.execute(
                """INSERT INTO session_hints
                   (session_id, timestamp, source_file, workstream, summary, decisions)
                   VALUES ('test-id', '2026-03-05T01:00:00Z', 'test2.json', 'ws', '["b2"]', '["d1"]')"""
            )
            rows = conn.execute(
                "SELECT * FROM session_hints WHERE session_id = 'test-id' ORDER BY timestamp"
            ).fetchall()
            assert len(rows) == 2
            assert rows[1]["decisions"] == '["d1"]'
        finally:
            conn.close()
```

**Step 2: Run test to verify it fails**

Run: `cd /home/matt/src/personal/relay/server && uv run pytest tests/test_db.py::test_session_hints_table_exists -v`
Expected: FAIL — `no such table: session_hints`

**Step 3: Write minimal implementation**

In `server/relay_server/db.py`, add to the end of the `SCHEMA` string (before the closing `"""`), after the session_tags index:

```sql
CREATE TABLE IF NOT EXISTS session_hints (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source_file TEXT NOT NULL UNIQUE,
    workstream TEXT NOT NULL,
    summary TEXT NOT NULL,
    decisions TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
CREATE INDEX IF NOT EXISTS idx_session_hints_session ON session_hints(session_id);
CREATE INDEX IF NOT EXISTS idx_session_hints_workstream ON session_hints(workstream);
```

**Step 4: Run test to verify it passes**

Run: `cd /home/matt/src/personal/relay/server && uv run pytest tests/test_db.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
cd /home/matt/src/personal/relay && git add server/relay_server/db.py server/tests/test_db.py
git commit -m "feat: add session_hints table to schema"
```

---

### Task 2: Add hint file indexing to the indexer

**Files:**
- Modify: `server/relay_server/indexer.py` (add `_get_hints_dir`, `_index_session_hints`, `_index_all_session_hints`)
- Modify: `server/relay_server/indexer.py:213` (call from `index_all`)
- Modify: `server/relay_server/indexer.py:458` (call from `reindex`)
- Test: `server/tests/test_indexer.py` (new tests)

**Step 1: Write the failing tests**

Add to the end of `server/tests/test_indexer.py`:

```python
from relay_server.indexer import _index_session_hints, _index_all_session_hints


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
            count = _index_session_hints(conn, hints_dir)
            conn.commit()
            assert count == 1

            rows = conn.execute(
                "SELECT * FROM session_hints WHERE session_id = 'abc-123'"
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["workstream"] == "squadkeeper"
            assert rows[0]["source_file"] == "2026-03-05T043956Z-abc-123.json"
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
            count = _index_session_hints(conn, hints_dir)
            conn.commit()
            assert count == 1  # Only the valid one
        finally:
            conn.close()
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/matt/src/personal/relay/server && uv run pytest tests/test_indexer.py::test_index_session_hints_basic -v`
Expected: FAIL — `cannot import name '_index_session_hints'`

**Step 3: Write implementation**

Add to `server/relay_server/indexer.py`, after the `_get_marker_dir()` function (line 409):

```python
def _get_hints_dir() -> Path:
    """Return the session hints directory path."""
    return Path(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    ) / "relay" / "session-hints"


def _parse_hint_file(hint_path: Path) -> dict | None:
    """Parse a session hint JSON file. Returns dict or None if invalid."""
    try:
        with open(hint_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning(f"Failed to parse hint file: {hint_path}")
        return None

    # Validate required fields
    if not isinstance(data, dict):
        return None
    session_id = data.get("session_id")
    workstream = data.get("workstream")
    summary = data.get("summary")
    if not session_id or not workstream or not summary:
        logger.warning(f"Hint file missing required fields: {hint_path}")
        return None
    if not isinstance(summary, list):
        return None

    # Extract timestamp from filename: 2026-03-05T043956Z-<session_id>.json
    filename = hint_path.name
    timestamp = filename.split("-", 1)[0] if "-" in filename else ""
    # Reformat: 2026-03-05T043956Z -> 2026-03-05T04:39:56Z
    if len(timestamp) >= 18 and "T" in timestamp:
        t = timestamp
        timestamp = f"{t[:13]}:{t[13:15]}:{t[15:]}"

    return {
        "session_id": session_id,
        "timestamp": timestamp,
        "source_file": filename,
        "workstream": workstream,
        "summary": json.dumps(summary),
        "decisions": json.dumps(data["decisions"]) if data.get("decisions") else None,
    }


def _index_session_hints(conn: sqlite3.Connection, hints_dir: Path | None = None) -> int:
    """Index session hint files into the session_hints table.

    Returns count of newly indexed hints.
    """
    if hints_dir is None:
        hints_dir = _get_hints_dir()
    if not hints_dir.exists():
        return 0

    count = 0
    for hint_path in sorted(hints_dir.glob("*.json")):
        # Check if already indexed (by source_file unique constraint)
        existing = conn.execute(
            "SELECT 1 FROM session_hints WHERE source_file = ?",
            (hint_path.name,)
        ).fetchone()
        if existing:
            continue

        parsed = _parse_hint_file(hint_path)
        if parsed is None:
            continue

        conn.execute(
            """INSERT INTO session_hints
               (session_id, timestamp, source_file, workstream, summary, decisions)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (parsed["session_id"], parsed["timestamp"], parsed["source_file"],
             parsed["workstream"], parsed["summary"], parsed["decisions"]),
        )
        count += 1

    return count


def _index_all_session_hints(conn: sqlite3.Connection) -> int:
    """Re-index all session hints. Used during full reindex."""
    conn.execute("DELETE FROM session_hints")
    return _index_session_hints(conn)
```

Now wire it into `index_all` — add after `_apply_session_markers(conn, all_session_ids)` (around line 334):

```python
        # Index session hint files
        hints_indexed = _index_session_hints(conn)
        if hints_indexed:
            logger.info(f"Indexed {hints_indexed} new session hints")
```

Wire it into `reindex` — add a line to clear session_hints in the DELETE block (after line 468, the `DELETE FROM session_tags` line):

```python
        conn.execute("DELETE FROM session_hints")
```

And call `_index_all_session_hints` after `_apply_all_session_markers` in the reindex function (around line 483):

```python
        _index_all_session_hints(conn)
```

Update the import in `server/tests/test_indexer.py` line 8:

```python
from relay_server.indexer import _extract_from_entry, _parse_file, _UUID_RE, index_all, _index_session_hints
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/matt/src/personal/relay/server && uv run pytest tests/test_indexer.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `cd /home/matt/src/personal/relay/server && uv run pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
cd /home/matt/src/personal/relay && git add server/relay_server/indexer.py server/tests/test_indexer.py
git commit -m "feat: index session hint files into session_hints table"
```

---

### Task 3: Add `get_session_summaries` MCP tool

**Files:**
- Modify: `server/relay_server/server.py` (new tool, after `list_tags`)
- Test: `server/tests/test_session_addressing.py` (or new test file)

**Step 1: Write the failing tests**

Create `server/tests/test_session_summaries.py`:

```python
"""Tests for get_session_summaries tool logic."""

import json
import tempfile
from pathlib import Path

from relay_server.db import ensure_schema, get_connection


def _setup_db_with_hints(tmpdir):
    """Create a test DB with sessions and hints."""
    db_path = Path(tmpdir) / "test.db"
    ensure_schema(db_path)
    conn = get_connection(db_path)

    # Insert test sessions
    conn.execute(
        """INSERT INTO sessions
           (session_id, project_dir, slug, first_timestamp, last_timestamp, message_count)
           VALUES ('s1', '/test', 'slug-1', '2026-03-05T00:00:00Z', '2026-03-05T01:00:00Z', 50)"""
    )
    conn.execute(
        """INSERT INTO sessions
           (session_id, project_dir, slug, first_timestamp, last_timestamp, message_count)
           VALUES ('s2', '/test', 'slug-2', '2026-03-05T02:00:00Z', '2026-03-05T03:00:00Z', 30)"""
    )
    conn.execute(
        """INSERT INTO sessions
           (session_id, project_dir, slug, first_timestamp, last_timestamp, message_count)
           VALUES ('s3', '/test', 'slug-3', '2026-03-05T04:00:00Z', '2026-03-05T05:00:00Z', 10)"""
    )

    # Insert hints for s1 (two segments) and s2 (one segment). No hints for s3.
    conn.execute(
        """INSERT INTO session_hints
           (session_id, timestamp, source_file, workstream, summary, decisions)
           VALUES ('s1', '2026-03-05T01:00:00Z', 'h1.json', 'squadkeeper',
                   ?, ?)""",
        (json.dumps(["Built feature X", "Added tests"]), json.dumps(["Used pattern Y"])),
    )
    conn.execute(
        """INSERT INTO session_hints
           (session_id, timestamp, source_file, workstream, summary)
           VALUES ('s1', '2026-03-05T02:00:00Z', 'h2.json', 'relay',
                   ?)""",
        (json.dumps(["Switched to relay work"]),),
    )
    conn.execute(
        """INSERT INTO session_hints
           (session_id, timestamp, source_file, workstream, summary)
           VALUES ('s2', '2026-03-05T03:00:00Z', 'h3.json', 'squadkeeper',
                   ?)""",
        (json.dumps(["Fixed bug Z"]),),
    )
    conn.commit()
    return db_path, conn


def test_get_summaries_with_hints():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, conn = _setup_db_with_hints(tmpdir)
        try:
            from relay_server.server import _get_session_summaries_from_db
            results = _get_session_summaries_from_db(conn, ["s1", "s2"])
            assert len(results) == 2

            s1 = next(r for r in results if r["session_id"] == "s1")
            assert s1["hints_available"] is True
            assert len(s1["segments"]) == 2
            assert s1["segments"][0]["workstream"] == "squadkeeper"
            assert s1["segments"][1]["workstream"] == "relay"

            s2 = next(r for r in results if r["session_id"] == "s2")
            assert s2["hints_available"] is True
            assert len(s2["segments"]) == 1
        finally:
            conn.close()


def test_get_summaries_missing_hints():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, conn = _setup_db_with_hints(tmpdir)
        try:
            from relay_server.server import _get_session_summaries_from_db
            results = _get_session_summaries_from_db(conn, ["s3"])
            assert len(results) == 1
            assert results[0]["hints_available"] is False
            assert results[0]["segments"] == []
        finally:
            conn.close()


def test_get_summaries_mixed():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, conn = _setup_db_with_hints(tmpdir)
        try:
            from relay_server.server import _get_session_summaries_from_db
            results = _get_session_summaries_from_db(conn, ["s1", "s3"])
            s1 = next(r for r in results if r["session_id"] == "s1")
            s3 = next(r for r in results if r["session_id"] == "s3")
            assert s1["hints_available"] is True
            assert s3["hints_available"] is False
        finally:
            conn.close()


def test_get_summaries_empty_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, conn = _setup_db_with_hints(tmpdir)
        try:
            from relay_server.server import _get_session_summaries_from_db
            results = _get_session_summaries_from_db(conn, [])
            assert results == []
        finally:
            conn.close()
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/matt/src/personal/relay/server && uv run pytest tests/test_session_summaries.py -v`
Expected: FAIL — `cannot import name '_get_session_summaries_from_db'`

**Step 3: Write implementation**

Add to `server/relay_server/server.py`, after the `list_tags` tool (around line 553):

```python
def _get_session_summaries_from_db(
    conn: sqlite3.Connection,
    session_ids: list[str],
) -> list[dict]:
    """Query session hints from DB. Extracted for testability."""
    if not session_ids:
        return []

    placeholders = ",".join("?" * len(session_ids))
    rows = conn.execute(
        f"""SELECT session_id, timestamp, workstream, summary, decisions
            FROM session_hints
            WHERE session_id IN ({placeholders})
            ORDER BY session_id, timestamp ASC""",
        session_ids,
    ).fetchall()

    # Group by session_id
    hints_by_session: dict[str, list[dict]] = {}
    for row in rows:
        sid = row["session_id"]
        if sid not in hints_by_session:
            hints_by_session[sid] = []
        segment = {
            "workstream": row["workstream"],
            "timestamp": row["timestamp"],
            "summary": json.loads(row["summary"]),
        }
        if row["decisions"]:
            segment["decisions"] = json.loads(row["decisions"])
        hints_by_session[sid].append(segment)

    # Build results for all requested session_ids
    results = []
    for sid in session_ids:
        segments = hints_by_session.get(sid, [])
        results.append({
            "session_id": sid,
            "hints_available": len(segments) > 0,
            "segments": segments,
        })
    return results


@mcp.tool()
def get_session_summaries(
    session_ids: list[str],
    ctx: Context[ServerSession, AppContext],
) -> list[dict]:
    """Get pre-written session summaries for efficient summarization.

    Returns all hint segments for the given sessions, ordered by timestamp.
    Sessions without hints return an entry with hints_available: false.

    Args:
        session_ids: List of session UUIDs to fetch summaries for
    """
    db_path = _get_db_path(ctx)
    conn = get_connection(db_path)
    try:
        return _get_session_summaries_from_db(conn, session_ids)
    finally:
        conn.close()
```

Add `import json` to the top of `server/relay_server/server.py` if not already present.

**Step 4: Run tests to verify they pass**

Run: `cd /home/matt/src/personal/relay/server && uv run pytest tests/test_session_summaries.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `cd /home/matt/src/personal/relay/server && uv run pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
cd /home/matt/src/personal/relay && git add server/relay_server/server.py server/tests/test_session_summaries.py
git commit -m "feat: add get_session_summaries MCP tool"
```

---

### Task 4: Update save/park/switch skills to write hint files

**Files:**
- Modify: `skills/save/SKILL.md`
- Modify: `skills/park/SKILL.md`
- Modify: `skills/switch/SKILL.md`

**Step 1: Update the save skill**

Add a new step between the current Step 4 (complete-save.sh) and Step 5 (confirm). Insert as new **Step 5**, and renumber the old Step 5 to Step 6:

```markdown
5. **Write session hint.** Write a session hint file summarizing what was accomplished in this session segment. The hint is a small JSON file that the relay indexer will pick up for efficient summarization later.

   Generate a UTC timestamp for the filename: `date -u +%Y-%m-%dT%H%M%SZ` (e.g. `2026-03-05T163000Z`).

   Get the current session ID from the `CLAUDE_SESSION_ID` environment variable. If not available, skip this step silently.

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/write-data-file.sh" "session-hints/<timestamp>-<session_id>.json" << 'EOF'
   {
     "session_id": "<session_id>",
     "workstream": "<active workstream name>",
     "summary": [
       "<3-6 bullets describing what was accomplished>",
       "<focus on capabilities added, features built, decisions made>",
       "<not task counts or commit hashes>"
     ],
     "decisions": [
       "<key architectural or design decisions, if any>",
       "<omit this field if no notable decisions were made>"
     ]
   }
   EOF
   ```

   **Hint writing guidelines:**
   - Summary bullets should be **what changed**, not how much work happened. "Added broadcast messaging with recipient snapshots" not "completed 13 tasks"
   - Include specific outcomes: features, capabilities, fixes, design decisions
   - If the session spanned multiple workstreams, write one hint per workstream segment
   - Keep each bullet to one line, no sub-bullets
   - Omit the `decisions` field entirely if no notable decisions were made
```

**Step 2: Update the park skill**

The park skill calls save as Step 2. Add the same hint-writing step after the save completes. Insert as new **Step 3** (between save and park-registry), renumber accordingly:

```markdown
3. **Write session hint.** Write a session hint file (same format as in `/relay:save` Step 5). Use the same timestamp + session_id filename pattern. If the save step already wrote a hint, skip this — don't write duplicate hints for the same segment.
```

**Step 3: Update the switch skill**

The switch skill saves current workstream as Step 3. Add hint writing after the save completes. Insert as new **Step 4** (between save and activate target), renumber accordingly:

```markdown
4. **Write session hint.** Write a session hint file for the workstream being switched away from (same format as in `/relay:save` Step 5). Use the same timestamp + session_id filename pattern.
```

**Step 4: Commit**

```bash
cd /home/matt/src/personal/relay && git add skills/save/SKILL.md skills/park/SKILL.md skills/switch/SKILL.md
git commit -m "feat: save/park/switch skills write session hint files"
```

---

### Task 5: Update PreCompact hook instructions to include hint writing

**Files:**
- Modify: `scripts/pre-compact-save.sh`

**Step 1: Update the script**

In `scripts/pre-compact-save.sh`, update the `cat <<EOF` block (lines 26-45) to also instruct Claude to write a session hint. Add after the existing instructions about writing state.md:

```bash
cat <<EOF
IMPORTANT: Context compaction is imminent. You MUST save the active workstream '${ACTIVE_NAME}' state NOW.

Write an updated state file to: ${STATE_FILE}

Use atomic overwrite:
1. Write content to ${STATE_FILE}.new
2. command mv ${STATE_FILE} ${STATE_FILE}.bak (if exists)
3. command mv ${STATE_FILE}.new ${STATE_FILE}

The state file must be under 80 lines and include:
- Current status (what was being worked on)
- Key decisions made
- Next steps
- Any blockers or important context that would be lost

Then write a session hint file for efficient summarization:
bash "\${CLAUDE_PLUGIN_ROOT}/scripts/write-data-file.sh" "session-hints/\$(date -u +%Y-%m-%dT%H%M%SZ)-\${CLAUDE_SESSION_ID}.json" << 'HINTEOF'
{
  "session_id": "\${CLAUDE_SESSION_ID}",
  "workstream": "${ACTIVE_NAME}",
  "summary": ["<3-6 bullets: what was accomplished in this session segment>"],
  "decisions": ["<key decisions, if any — omit field if none>"]
}
HINTEOF

Then update the registry and reset the context monitor:
bash "\${CLAUDE_PLUGIN_ROOT}/scripts/update-registry.sh" "${ACTIVE_NAME}"
bash "\${CLAUDE_PLUGIN_ROOT}/scripts/reset-counter.sh"
EOF
```

**Step 2: Commit**

```bash
cd /home/matt/src/personal/relay && git add scripts/pre-compact-save.sh
git commit -m "feat: PreCompact hook instructs Claude to write session hints"
```

---

### Task 6: Update the summarize skill to use hints

**Files:**
- Modify: `skills/summarize/SKILL.md`

**Step 1: Rewrite the summarize skill**

Replace the contents of `skills/summarize/SKILL.md`. The new version uses `get_session_summaries` instead of `get_conversation`:

```markdown
---
name: summarize
description: >
  Summarize recent activity grouped by workstream. Use for standup prep, brag books, or catching up after time away.
  Trigger phrases: "summarize activity", "what did I work on", "standup summary", "brag book".
argument-hint: "<time-range: 48h, 7d, since Monday, 2026-03-01>"
---

# Summarize Activity

Generate a summary of recent Claude Code sessions grouped by workstream.

**Argument:** `$ARGUMENTS` is a natural-language time expression. If empty, default to 24h.

## Steps

1. **Parse time argument.** Interpret `$ARGUMENTS` as a time range and convert to an ISO date (`YYYY-MM-DD`). Examples:
   - `48h` → 2 days before today
   - `7d` or `1w` → 7 days before today
   - `since Monday` → last Monday's date
   - `2026-03-01` → literal date
   - Empty → 1 day before today (24h default)

   Store the computed date as `DATE_FROM` for the next step.

2. **Fetch sessions.** Use the `list_sessions` MCP tool:
   ```
   list_sessions(date_from=DATE_FROM, limit=100)
   ```
   If no sessions are found, tell the user there's no activity in that range and stop.

3. **Fetch summaries.** Collect all session IDs from step 2 and call:
   ```
   get_session_summaries(session_ids=[...])
   ```
   This returns pre-written summary hints for each session. Sessions with `hints_available: true` have structured bullets ready to use.

4. **Map sessions without hints to workstreams.** For sessions with `hints_available: false`, read the session marker file to find the workstream:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/read-data-file.sh" "session-markers/<session_id>.json"
   ```
   Sessions without markers or hints go into an "Other" group.

5. **Generate summary.** Output grouped by workstream, ordered by most sessions first.

   - For sessions **with hints**: use the summary bullets directly. If a session has multiple segments (different workstreams), list each segment under its respective workstream group.
   - For sessions **without hints**: show basic metadata only — date, slug, project, message count. Add a note: *"Run `/relay:backfill` to generate summaries for older sessions."*

   Format:

   ```
   ## Activity Summary: <start date> – <end date>

   ### <workstream-name> (<N> sessions)

   **Session <number>** — `<slug>` (<date>)
   - <bullet from hint>
   - <bullet from hint>

   **Session <number>** — `<slug>` (<date>)
   - <bullet from hint>

   ### <other-workstream> (<N> sessions)
   ...

   ---
   *Use `get_conversation("<slug>")` to drill into any session.*
   ```

   Include the slug in each session header so the user (or Claude) can easily drill in later.

## Notes

- Prioritize **breadth over depth** — mention every session, even if briefly.
- Sessions with hints are the fast path — no conversation reading needed.
- Sessions without hints degrade gracefully to metadata-only entries.
- The `decisions` field from hints can be included as sub-bullets when the detail level warrants it (≤ 3 day ranges).
```

**Step 2: Commit**

```bash
cd /home/matt/src/personal/relay && git add skills/summarize/SKILL.md
git commit -m "feat: summarize skill uses session hints instead of full conversation reads"
```

---

### Task 7: Create the backfill skill

**Files:**
- Create: `skills/backfill/SKILL.md`

**Step 1: Create the skill**

```markdown
---
name: backfill
description: >
  Generate session hints for older sessions that don't have them. Interactive — Claude reads conversations and writes structured summaries.
  Trigger phrases: "backfill hints", "generate summaries", "backfill sessions".
argument-hint: "<time-range: 7d, 30d, all>"
---

# Backfill Session Hints

Generate session hint files for sessions that don't have them yet. This reads conversation content and writes structured summaries — a one-time cost that makes future `/relay:summarize` calls nearly free.

**Argument:** `$ARGUMENTS` is a time range. If empty, default to 7d.

## Steps

1. **Parse time argument.** Same as `/relay:summarize` — convert `$ARGUMENTS` to an ISO date for `DATE_FROM`.

2. **Fetch sessions.** Use the `list_sessions` MCP tool:
   ```
   list_sessions(date_from=DATE_FROM, limit=100)
   ```
   If no sessions found, tell the user and stop.

3. **Check which sessions need hints.** Call:
   ```
   get_session_summaries(session_ids=[...])
   ```
   Filter to sessions where `hints_available` is `false`. If all sessions have hints, tell the user "All sessions in this range already have hints" and stop.

   Report: "Found N sessions without hints (M already have hints). Proceeding with backfill."

4. **For each session without hints:**

   a. **Read the session marker** to find the workstream:
      ```bash
      bash "${CLAUDE_PLUGIN_ROOT}/scripts/read-data-file.sh" "session-markers/<session_id>.json"
      ```
      If no marker, use "other" as the workstream.

   b. **Read the conversation:**
      ```
      get_conversation(session_id, roles=["user", "assistant"], limit=50, format="markdown")
      ```

   c. **Write the hint file.** Based on the conversation content, write a hint:
      ```bash
      bash "${CLAUDE_PLUGIN_ROOT}/scripts/write-data-file.sh" "session-hints/<timestamp>-<session_id>.json" << 'EOF'
      {
        "session_id": "<session_id>",
        "workstream": "<workstream from marker>",
        "summary": [
          "<3-6 bullets describing what was accomplished>",
          "<focus on capabilities, features, decisions — not counts>"
        ],
        "decisions": [
          "<key decisions, if any>"
        ]
      }
      EOF
      ```
      Use the session's `last_timestamp` (converted to filename format) as the timestamp.

   d. **Report progress:** "Wrote hint for session `<slug>` (<date>)"

   e. If the session clearly spans multiple workstreams (e.g., user switched workstreams mid-session), write separate hint files for each segment — use different timestamps in the filenames.

5. **Summary.** Report: "Backfill complete. Generated hints for N sessions."

## Notes

- This is intentionally interactive — Claude reads and synthesizes. It costs tokens but produces high-quality hints.
- Skip sessions with very few messages (< 5) — they're usually session starts or quick checks, not worth summarizing.
- For sessions that had context compaction, the conversation may be incomplete — do your best with what's available.
- If a session is an execution session (user messages are mostly "continue", "yes", "1"), focus on the assistant's outcome messages for the summary bullets.
```

**Step 2: Commit**

```bash
cd /home/matt/src/personal/relay && git add skills/backfill/SKILL.md
git commit -m "feat: add backfill skill for generating hints from older sessions"
```

---

### Task 8: Update version, changelog, and README

**Files:**
- Modify: `.claude-plugin/plugin.json` — bump `0.7.0` → `0.8.0`
- Modify: `.claude-plugin/marketplace.json` — bump version
- Modify: `CHANGELOG.md` — add 0.8.0 entry
- Modify: `README.md` — add `/relay:backfill` to slash commands table and natural language triggers

**Step 1: Bump versions**

In `.claude-plugin/plugin.json`, change `"version": "0.7.0"` to `"version": "0.8.0"`.

In `.claude-plugin/marketplace.json`, update the version field similarly.

**Step 2: Add changelog entry**

Add at the top of CHANGELOG.md (after the `# Changelog` heading):

```markdown
## [0.8.0] - 2026-03-05

### Added
- **Session hints** — Write-time metadata for efficient summarization. Claude writes small JSON hint files at save/park/switch/compact time. The MCP server indexes them into a `session_hints` table for fast assembly. Reduces summarize token cost by 10x+.
- **`get_session_summaries` MCP tool** — Fetches pre-written session summaries from the database in one query. Returns structured segments with summary bullets and decisions.
- **`/relay:backfill` skill** — Generate session hints for older sessions interactively. Reads conversations and writes structured summaries as a one-time cost.

### Changed
- **`/relay:summarize`** — Now reads pre-written hints instead of fetching full conversation content. Sessions without hints degrade gracefully to metadata-only entries.
- **`/relay:save`, `/relay:park`, `/relay:switch`** — Now write session hint files after saving state.
- **PreCompact hook** — Now instructs Claude to write a session hint before context compression.
- **Indexer** — Scans `session-hints/` directory on startup and indexes hint files into `session_hints` table.
```

**Step 3: Update README**

Add `/relay:backfill` to the slash commands table and natural language triggers section. Also add a brief section about session hints in the architecture/data storage area if one exists.

**Step 4: Commit**

```bash
cd /home/matt/src/personal/relay && git add .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md README.md
git commit -m "chore: bump to v0.8.0, update changelog and README for session hints"
```

---

### Task 9: Run full test suite and verify

**Step 1: Run all tests**

Run: `cd /home/matt/src/personal/relay/server && uv run pytest -v`
Expected: ALL PASS (previous 78 + new tests from tasks 1-3)

**Step 2: Verify hint file flow manually**

1. Start a Claude Code session with the plugin
2. Run `/relay:save` — verify a hint file appears in `~/.config/relay/session-hints/`
3. Restart Claude Code — verify the indexer picks it up (check startup log)
4. Run `/relay:summarize` — verify it uses the hint instead of fetching full conversation

**Step 3: Tag release**

```bash
cd /home/matt/src/personal/relay && git tag v0.8.0
```

---

Plan complete and saved to `docs/plans/2026-03-05-session-hints-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

Which approach?
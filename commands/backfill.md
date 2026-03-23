---
description: Generate session hints for older sessions that don't have them. Interactive — Claude reads conversations and writes structured summaries.
argument-hint: "<time-range: 7d, 30d, all>"
---

# Backfill Session Hints

Generate session hints for sessions that don't have them yet. This reads conversation content and writes structured summaries — a one-time cost that makes future `/relay:summarize` calls nearly free.

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

   a. **Determine the workstream.** Use the session's `project_dir` or tags to infer which workstream. If unclear, use "other".

   b. **Read the conversation:**
      ```
      get_conversation(session_id, roles=["user", "assistant"], limit=50, format="markdown")
      ```

   c. **Write the hint.** Based on the conversation content, call:
      ```
      write_session_hint(
        session_id="<full-uuid-from-list_sessions>",
        workstream="<workstream>",
        summary=["<3-6 bullets describing what was accomplished>"],
        decisions=["<key decisions, if any>"]
      )
      ```

   d. **Report progress:** "Wrote hint for session `<slug>` (<date>)"

   e. If the session clearly spans multiple workstreams, write separate hints for each segment.

5. **Summary.** Report: "Backfill complete. Generated hints for N sessions."

## Notes

- This is intentionally interactive — Claude reads and synthesizes. It costs tokens but produces high-quality hints.
- Skip sessions with very few messages (< 5) — they're usually session starts or quick checks, not worth summarizing.
- For sessions that had context compaction, the conversation may be incomplete — do your best with what's available.
- If a session is an execution session (user messages are mostly "continue", "yes", "1"), focus on the assistant's outcome messages for the summary bullets.

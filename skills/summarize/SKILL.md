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

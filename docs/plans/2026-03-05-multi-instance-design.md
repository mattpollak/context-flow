# Multi-Instance Support Design

**Date:** 2026-03-05
**Status:** Approved

## Problem

Users run multiple Claude Code instances in parallel (e.g., one per git worktree). The current design assumes a single "active" workstream — two instances fight over it, and `/relay:switch` in one instance parks the other's workstream.

## Design

Allow multiple workstreams to be `"active"` simultaneously. Each Claude session attaches to one workstream via its session marker. Parking is an explicit action, not a side effect of switching.

### Session Start Behavior

| Active count | Behavior |
|---|---|
| 0 | List parked workstreams, suggest `/relay:switch` or `/relay:new` (unchanged) |
| 1 | Auto-attach, inject state, write marker (unchanged) |
| 2+ | List active workstreams in context, instruct Claude to ask user which one, then attach |

For the 2+ case, the hook can't prompt interactively. It outputs instructions for Claude to ask the user and then call `attach-workstream.sh`.

### Attachment

New script `attach-workstream.sh <name> <session_id>`:
1. Validates workstream exists and is active
2. Writes session marker (`session-markers/<session_id>.json`)
3. Outputs the state file content

This replaces the ad-hoc "read state + write marker" instructions. One script, one step — less room for Claude to skip something.

### Same-Workstream Warning

At attach time, check if another live session is using the same workstream:
- Scan counter files (`/tmp/relay-*.count`) for other session IDs
- Check their session markers for matching workstream
- If found: output advisory warning — not blocking

### Script Changes

| Script | Change |
|---|---|
| `session-start.sh` | Multi-active detection, same-workstream warning, call attach for 1-active |
| `session-end.sh` | Use session marker (not `status == "active"`) to find workstream |
| `pre-compact-save.sh` | Use session marker (not `status == "active"`) to find workstream |
| `attach-workstream.sh` | **New** — writes marker + reads state in one step |

### Skill Changes

| Skill | Change |
|---|---|
| `/relay:new` | Remove auto-park step. New workstream created active alongside existing active ones. |
| `/relay:switch` | Detach from old, attach to new. Both stay active. Update session marker. Don't park old. |
| `/relay:park` | Unchanged — explicitly parks a named workstream. |
| `/relay:save` | Unchanged — already knows workstream from session context. |
| `/relay:status` | Show attached workstream from context. Mention if others are also active. |
| `/relay:list` | Unchanged — already groups by status. |

### Data Integrity Analysis

| Data flow | Multi-instance safe? | Notes |
|---|---|---|
| Session markers | Yes | Per-session, written at attach time |
| Session hints | Yes | Per-session, carry own workstream field |
| SQLite index | Yes | WAL mode + busy_timeout handles concurrent access |
| Summarize | Yes | Hints carry workstream; markers are fallback only |
| State files | Last-write-wins | Acceptable — both snapshots are valid. Warning mitigates. |
| Registry (`workstreams.json`) | Rare race window | Writes are infrequent and fast. Atomic rename prevents corruption. Lost write would only be `last_touched`. |

### What Doesn't Change

- Registry schema — no new fields
- Session hints and markers format
- Indexer, DB, MCP server
- Counter files (already per-session)
- `/relay:backfill`, `/relay:summarize`, `/relay:idea`

### Edge Cases

- **Session crashes without cleanup:** Counter file stays in `/tmp`, eventually cleaned by OS. Stale same-workstream warning is advisory only.
- **Two sessions save same workstream:** Last-write-wins on `state.md`. Both are valid snapshots. Session hints capture both sessions' work independently.
- **Park from wrong session:** User parks a workstream another instance is using. Other instance can still save (file write doesn't check registry status). Next session won't auto-load the parked workstream.

### Post-Implementation

- Update plugin README and MCP server README for consistency with new multi-active behavior.

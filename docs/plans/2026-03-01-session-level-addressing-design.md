# Session-Level Addressing for relay-search

**Date:** 2026-03-01
**Status:** Approved

## Problem

When a slug spans multiple sessions (via "continue"), there is no way to address individual sessions. Callers must guess timestamps to window into the right part of a conversation, and search results don't indicate which session a hit belongs to. This makes it difficult to hand off conversation references to other Claude instances or retrieve specific parts of long conversations.

## Design

Enhance three existing MCP tools in `server.py`. No new tools, no schema changes.

### 1. `get_conversation` — new `session` parameter

**Parameter:** `session: str | None = None`

Accepts a session range string after slug resolution:
- `"4"` — single session
- `"4-5"` — inclusive range
- `"1,3,5"` — specific sessions (comma-separated, each element can be a number or range)

After resolving a slug to its session chain (ordered by `first_timestamp`), the `session` parameter slices that list to only the requested sessions before querying messages.

**Behavior:**
- Ignored when `session_id_or_slug` resolves to a single session (exact UUID match)
- Out-of-range indices return an error: `"Session 7 out of range (1-6)"`
- Compatible with `around_timestamp` — session filtering happens first, then timestamp windowing applies within the filtered sessions
- Compatible with `roles` and `limit` — these apply after session filtering

### 2. `list_sessions` — new `slug` parameter

**Parameter:** `slug: str | None = None`

When provided:
- Filters to `WHERE slug = ?`
- Adds a `session_number` field (1-based) to each result
- Orders by `first_timestamp ASC` (chronological) instead of `last_timestamp DESC` (recency)

`session_number` is only present when `slug` is provided (meaningless in global context).

When `slug` is provided alongside `project`, the `slug` filter takes precedence (a slug already implies a project). `date_from`, `date_to`, and `tags` still apply as additional filters.

### 3. `search_history` — `session_number` in results

Each search result gains a `session_number` field indicating the hit's position within its slug chain.

**Implementation:** Post-processing after the existing FTS query. Collect unique slugs from results, query their session chains in bulk, build a `{session_id: session_number}` lookup, annotate each result. One extra query, bounded by result set size (max 500).

### Shared utility

`_parse_session_range(session_str: str, total: int) -> list[int]`

Parses a session range string into a sorted list of 0-based indices. Validates bounds against `total`. Raises `ValueError` on invalid input.

Examples:
- `_parse_session_range("4", 6)` → `[3]`
- `_parse_session_range("4-5", 6)` → `[3, 4]`
- `_parse_session_range("1,3,5", 6)` → `[0, 2, 4]`
- `_parse_session_range("7", 6)` → ValueError

### Tests

- Unit tests for `_parse_session_range` (valid ranges, edge cases, errors)
- Integration-style tests using an in-memory DB with a multi-session slug:
  - `get_conversation` with session filtering
  - `list_sessions` with slug parameter
  - `search_history` session number annotation

# Changelog

## [0.3.0] - 2026-02-27

### Added
- **`read-data-file.sh`** — generic helper script to read files from the data directory, eliminating `${XDG_CONFIG_HOME:-...}` parameter substitution prompts

### Changed
- **List skill** — uses `read-data-file.sh` instead of inline `$DATA_DIR` with `${}`-based default, removing permission prompts
- **README copyediting** — clarified wording in intro, tag filtering example, and migration section

## [0.2.0] - 2026-02-26

Security hardening, architecture improvements, and workflow polish based on security + architecture reviews.

### Added
- **Test suite** — 49 tests across 5 files (db, tagger, formatter, indexer, server)
- **`complete-save.sh`** — single script for state file rotation, registry update, and counter reset
- **Helper scripts** — `update-registry.sh`, `switch-registry.sh`, `park-registry.sh`, `new-registry.sh`, `reset-counter.sh` to avoid inline jq/for in skills (which triggered permission prompts)
- **Permission pattern docs** in README — recommended `Bash(bash */context-flow/*/scripts/*:*)` for frictionless saves
- **Update instructions** in README
- **Schema versioning** — `workstreams.json` includes `"version": 1` for future migrations
- **Dev dependencies** — `pytest>=8.0` as optional dependency

### Changed
- **Context monitor resets on save/switch/park** — counter goes to 0 after saving, stopping repeated warnings
- **`command mv` everywhere** — bypasses shell `mv -i` aliases without the aggressive `-f` flag
- **`auto_tag_session` optimization** — only fetches `tool_summary` + `plan` roles instead of all messages
- **MCP dependency pinned** — `mcp[cli]>=1.0.0,<2.0.0` to prevent breaking changes
- **Skills use script calls** — all registry operations go through helper scripts instead of inline shell commands

### Security
- **DB directory permissions** — created with `mode=0o700`
- **`PRAGMA foreign_keys=ON`** — enforced on every connection
- **UUID validation** — regex check at all trust boundaries (hooks + indexer) to prevent path traversal
- **Workstream name validation** — `[a-z0-9-]` enforced in shell scripts
- **FTS5 error handling** — `sqlite3.OperationalError` caught with helpful syntax hint
- **Input bounds** — limit clamping (`MAX_LIMIT=500`), tag count/length limits, format/scope parameter validation
- **Type hints** — `callable` → `Callable` from `collections.abc`

## [0.1.0] - 2026-02-26

### Added
- Initial release
- 5 core skills: `/context-flow:new`, `/context-flow:switch`, `/context-flow:park`, `/context-flow:list`, `/context-flow:save`
- MCP conversation search server — indexes Claude Code JSONL transcripts into SQLite FTS5
- Slug chain support — `get_conversation` by slug returns all sessions chronologically
- Auto-tagging — messages tagged by content type (reviews, plans, decisions), sessions by activity (tests, deploy, browser)
- Manual tagging — `tag_message`, `tag_session`, `list_tags` tools
- Tag filtering on `search_history` and `list_sessions`
- Markdown formatter — `get_conversation` returns readable markdown by default
- SessionStart hook: auto-loads active workstream state, writes session markers
- PostToolUse hook: context exhaustion monitor with graduated warnings
- PreCompact hook: prompts Claude to save state before context compression
- SessionEnd hook: cleanup and timestamp update
- Migration script from manual workstream system
- JSON registry (`workstreams.json`) with `jq` parsing
- Atomic state saves with one-deep `.bak` backup

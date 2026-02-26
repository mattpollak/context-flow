# Changelog

## [0.1.0] - 2026-02-26

### Added
- Initial release
- 5 core skills: `/context-flow:new`, `/context-flow:switch`, `/context-flow:park`, `/context-flow:list`, `/context-flow:save`
- SessionStart hook: auto-loads active workstream state
- PostToolUse hook: context exhaustion monitor with graduated warnings
- PreCompact hook: prompts Claude to save state before context compression
- SessionEnd hook: cleanup and timestamp update
- Migration script from manual workstream system
- JSON registry (`workstreams.json`) with `jq` parsing
- Atomic state saves with one-deep `.bak` backup

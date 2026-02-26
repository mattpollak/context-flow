# context-flow

A Claude Code plugin for workstream management, context persistence, and session continuity.

Tracks what you're working on across Claude Code sessions. Auto-loads your context on session start, warns when context is running low, and saves state before compaction. Switch between projects without losing your place.

## Features

- **Auto-load** — SessionStart hook injects your active workstream's state into every new session
- **Context monitoring** — PostToolUse hook counts tool calls and warns at ~80 (approaching limit) and ~100 (critical)
- **Auto-save on compaction** — PreCompact hook instructs Claude to save state before context compression
- **5 slash commands** — `/context-flow:new`, `/context-flow:switch`, `/context-flow:park`, `/context-flow:list`, `/context-flow:save`
- **Atomic saves** — State files use write-to-temp + rename with a one-deep `.bak` backup
- **JSON registry** — `workstreams.json` parsed with `jq` for reliable cross-platform operation

## Prerequisites

- **Claude Code** v2.1.0+ (plugin system support)
- **`jq`** — JSON parser, required for hook scripts
  ```bash
  # Ubuntu/Debian
  sudo apt install jq

  # macOS
  brew install jq

  # Other: https://jqlang.github.io/jq/download/
  ```

## Installation

```bash
# Clone the repo
git clone https://github.com/mattpollak/context-flow.git

# Install as a local plugin
claude plugin add ./context-flow
```

Or test without installing:
```bash
claude --plugin-dir ./context-flow
```

## Usage

### Create a workstream
```
/context-flow:new api-refactor Modernizing the REST API layer
```

### List workstreams
```
/context-flow:list
```

### Save current state
```
/context-flow:save
```

### Switch to a different workstream
```
/context-flow:switch auth-migration
```

### Park current workstream
```
/context-flow:park
```

### Natural language triggers

The skills also respond to natural language:
- "new workstream", "start workstream", "create workstream"
- "switch to X", "resume workstream", "load workstream", "work on X"
- "save context", "save state", "save session", "persist context"
- "park this", "park workstream", "pause workstream", "shelve this"
- "list workstreams", "show workstreams"

## Data Storage

Data is stored at `${XDG_CONFIG_HOME:-$HOME/.config}/context-flow/`:

```
~/.config/context-flow/
├── workstreams.json          # Central registry
├── workstreams/
│   ├── api-refactor/
│   │   ├── state.md          # ~80 lines, auto-loaded on session start
│   │   ├── state.md.bak      # One-deep backup (previous version)
│   │   ├── plan.md           # Optional, loaded on /switch
│   │   └── architecture.md   # Optional, loaded on /switch
│   └── ...
└── parking-lot.md            # Cross-project ideas
```

## How It Works

### Hooks

| Hook | Event | What it does |
|---|---|---|
| `session-start.sh` | SessionStart | Reads registry, injects active workstream's `state.md` into context |
| `context-monitor.sh` | PostToolUse | Counts tool calls, warns at 80 and 100 |
| `pre-compact-save.sh` | PreCompact | Instructs Claude to save state before compression |
| `session-end.sh` | SessionEnd | Cleans up temp files, updates `last_touched` timestamp |

### State files

State files (`state.md`) are kept under 80 lines and contain:
- Current status
- Key decisions
- Next steps
- Recent session summaries (if space permits)

Saves use an atomic three-step process: write new content to a temp file (`state.md.new`), back up the current file (`state.md` → `state.md.bak`, overwriting any previous backup), then rename the temp file into place (`state.md.new` → `state.md`). Each step overwrites its target, so stale files from a previous interrupted save are cleaned up automatically.

## Complementary Systems

context-flow handles **session state** (what you're working on, where you left off). It complements, not replaces, Claude Code's built-in systems:

| System | Purpose | Example |
|---|---|---|
| Auto-memory (`MEMORY.md`) | Learnings about the codebase | "Use TypeORM migrations for schema changes" |
| `CLAUDE.md` | Instructions for Claude | "Run tests with `npm test` before committing" |
| **context-flow** | Session state + task switching | "Working on auth migration, next: add OAuth" |

## Future Plans

- **`/context-flow:complete`** — Mark a workstream as completed
- **`/context-flow:search`** — Search past session conversations
- **MCP server** — Python-based conversation indexer + semantic search (installable via `uvx`)

## Inspired By

- [Episodic Memory](https://github.com/obra/episodic-memory) — conversation archival and search
- [Get Shit Done](https://github.com/gsd-build/get-shit-done) — context monitoring and lean state files
- [CASS Memory System](https://github.com/Dicklesworthstone/cass_memory_system) — structured knowledge accumulation

See [ATTRIBUTION.md](./ATTRIBUTION.md) for details.

## License

MIT — see [LICENSE](./LICENSE).

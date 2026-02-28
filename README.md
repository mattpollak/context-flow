# context-flow

A Claude Code plugin for workstream management, context persistence, and conversation history search.

**The problem:** Claude Code sessions are stateless. Every new session starts from scratch — you re-explain what you're working on, re-describe your architecture, and repeat decisions you already made. If you juggle multiple projects, context-switching means writing notes by hand or hoping you remember where you left off. And all that knowledge Claude helped you build? Buried in transcript files with no way to find it again.

**context-flow fixes this.** It tracks what you're working on across sessions, auto-loads your most recent context at startup, and indexes every conversation you've ever had with Claude Code — making it all searchable. Switch between projects without losing your place. Find that UX review from last week. Pick up exactly where you left off.

## What You Get

- **Auto-loaded context** — Every session starts with your active workstream's state already in context. No more "let me catch you up on what we're doing."
- **One-command project switching** — `/context-flow:switch auth-migration` saves your current work, loads the new project's state, and you're coding in seconds.
- **Context exhaustion warnings** — Get warned at ~80 tool calls (approaching limit) and ~100 (critical) so you can save before compaction hits.
- **Auto-save before compaction** — PreCompact hook ensures Claude saves your state before context is compressed.
- **Full conversation history search** — MCP server indexes all your Claude Code transcripts into searchable SQLite FTS5. Find that architecture decision from two weeks ago.
- **Auto-tagging** — Messages are automatically tagged by content type (UX reviews, plans, decisions, investigations) so high-value content is discoverable without remembering exact phrases.

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
- **Python 3.10+** and **`uv`** — Required for the MCP conversation search server

## Installation

```bash
# Add the marketplace
claude plugin marketplace add mattpollak/context-flow

# Install the plugin
claude plugin install context-flow@context-flow
```

To verify it's installed:
```bash
claude plugin list
```

Start a new Claude Code session — you should see the SessionStart hook fire. If no workstreams exist yet, it will prompt you to create one.

### Permissions

When you save, switch, or park a workstream, Claude runs helper scripts bundled with the plugin (e.g., `complete-save.sh` to atomically rotate state files). A bundled `PreToolUse` hook automatically approves these commands — **no manual permission setup is needed.**

The hook (`scripts/approve-scripts.sh`) checks whether each Bash command targets a script inside the plugin's own `scripts/` directory. Only exact matches against `${CLAUDE_PLUGIN_ROOT}/scripts/` are approved; all other commands go through the normal permission flow.

> **If you're upgrading from ≤0.4.0**, you can remove the old `Bash(bash */context-flow/*/scripts/*:*)` rule from `~/.claude/settings.json` — that glob pattern never actually worked because `*` doesn't match across `/` directory separators in Claude Code's permission system.

### Updating

```bash
# Pull latest from the marketplace
claude plugin marketplace update context-flow

# Update the plugin
claude plugin update context-flow@context-flow
```

Restart Claude Code after updating to apply changes.

### Testing without installing

```bash
claude --plugin-dir /path/to/context-flow
```

## Usage

### Slash commands

| Command | What it does |
|---|---|
| `/context-flow:new api-refactor Modernizing the REST API` | Create a new workstream |
| `/context-flow:list` | List all workstreams grouped by status |
| `/context-flow:save` | Save current workstream state to disk |
| `/context-flow:switch auth-migration` | Save current, load a different workstream |
| `/context-flow:park` | Save and deactivate the current workstream |

### Natural language

The skills also respond to natural language:
- "new workstream", "start workstream", "create workstream"
- "switch to X", "resume workstream", "work on X"
- "save context", "save state", "save session"
- "park this", "park workstream", "pause workstream"
- "list workstreams", "show workstreams"

### Conversation search

The MCP server provides tools that Claude can use directly during your session:

| Tool | What it does |
|---|---|
| `search_history` | Full-text search across all conversations (FTS5: AND, OR, NOT, "phrases") |
| `get_conversation` | Retrieve messages from a session by UUID or slug. Slug chains (via "continue") return all sessions combined chronologically. |
| `list_sessions` | List recent sessions with metadata, filterable by project, date, and tags |
| `tag_message` | Manually tag a message for future discoverability |
| `tag_session` | Manually tag a session (e.g., associate with a workstream) |
| `list_tags` | List all tags with counts — see what's been auto-detected |
| `reindex` | Force a complete re-index from scratch |

**Tag filtering:** Both `search_history` and `list_sessions` accept an optional `tags` parameter to narrow results. For example, searching for "splash page" with `tags: ["review:ux"]` returns only UX review messages that mention splash page.

**Auto-tags applied during indexing:**

| Tag | What it detects |
|---|---|
| `review:ux` | Substantial UX/usability review content |
| `review:architecture` | Architecture or system design reviews |
| `review:code` | Code quality reviews |
| `review:security` | Security reviews or audits |
| `plan` | Implementation plans (plan-mode messages or structured phase/implementation docs) |
| `decision` | Architectural or approach decisions |
| `investigation` | Root cause analysis and debugging findings |
| `insight` | Messages with `★ Insight` markers |
| `has:browser` | Session used browser/Playwright tools |
| `has:tests` | Session ran tests (pytest, vitest, etc.) |
| `has:deploy` | Session involved deployment (ssh, docker, etc.) |
| `has:planning` | Session used Claude Code's plan mode |

## Data Storage

Data is stored at `${XDG_CONFIG_HOME:-$HOME/.config}/context-flow/`:

```
~/.config/context-flow/
├── workstreams.json              # Central registry
├── parking-lot.md                # Cross-project ideas
├── session-markers/              # Links session IDs to workstreams (auto)
│   └── <session-id>.json
└── workstreams/
    ├── api-refactor/
    │   ├── state.md              # ~80 lines, auto-loaded on session start
    │   ├── state.md.bak          # One-deep backup (previous version)
    │   ├── plan.md               # Optional, loaded on /switch
    │   └── architecture.md       # Optional, loaded on /switch
    └── ...
```

The conversation search index lives at `~/.local/share/context-flow/index.db` (SQLite, WAL mode).

## How It Works

### Hooks

| Hook | Event | What it does |
|---|---|---|
| `session-start.sh` | SessionStart | Reads registry, injects active workstream's `state.md` into context. Writes session marker linking session ID to active workstream. |
| `context-monitor.sh` | PostToolUse | Counts tool calls, warns at 80 and 100 |
| `pre-compact-save.sh` | PreCompact | Instructs Claude to save state before compression |
| `session-end.sh` | SessionEnd | Cleans up temp files, updates `last_touched` timestamp |
| `approve-scripts.sh` | PreToolUse | Auto-approves Bash commands targeting plugin scripts (no user prompt) |

### State files

State files (`state.md`) are kept under 80 lines and contain:
- Current status
- Key decisions
- Next steps
- Recent session summaries (if space permits)

Saves use an atomic three-step process: write new content to a temp file (`state.md.new`), back up the current file (`state.md` → `state.md.bak`, overwriting any previous backup), then rename the temp file into place (`state.md.new` → `state.md`). Each step overwrites its target, so stale files from a previous interrupted save are cleaned up automatically.

### MCP server

On startup, the server scans `~/.claude/projects/` for JSONL transcript files and incrementally indexes them into SQLite FTS5. First run takes 3-5 seconds; subsequent runs process only new/modified files (~0.01s). Auto-tagging runs during indexing — keyword heuristics classify messages by content type (reviews, plans, decisions, etc.) and sessions by activity (testing, deployment, browser usage).

## Complementary Systems

context-flow handles **session state** (what you're working on, where you left off). It complements, not replaces, Claude Code's built-in systems:

| System | Purpose | Example |
|---|---|---|
| Auto-memory (`MEMORY.md`) | Learnings about the codebase | "Use TypeORM migrations for schema changes" |
| `CLAUDE.md` | Instructions for Claude | "Run tests with `npm test` before committing" |
| **context-flow** | Session state + task switching + history search | "Working on auth migration, next: add OAuth" |

## Migrating from Manual Workstreams

If you have - and you almost certainly don't, unless you're me - an existing manual workstream system with a `WORKSTREAMS.md` registry:

```bash
# Preview what the migration will do
bash /path/to/context-flow/scripts/migrate-from-workstreams.sh --dry-run

# Run the migration
bash /path/to/context-flow/scripts/migrate-from-workstreams.sh
```

The migration is non-destructive — it copies files to the new location without deleting originals.

## Inspired By

- [Episodic Memory](https://github.com/obra/episodic-memory) — conversation archival and search
- [Get Shit Done](https://github.com/gsd-build/get-shit-done) — context monitoring and lean state files
- [CASS Memory System](https://github.com/Dicklesworthstone/cass_memory_system) — structured knowledge accumulation

See [ATTRIBUTION.md](./ATTRIBUTION.md) for details.

## License

MIT — see [LICENSE](./LICENSE).

# context-flow-server

MCP server for searching Claude Code conversation history. Indexes JSONL transcript files and provides full-text search via SQLite FTS5.

## Tools

- **search_history** — Full-text search across all indexed conversations
- **get_conversation** — Retrieve messages from a specific session
- **list_sessions** — List recent sessions with metadata
- **reindex** — Force a complete re-index from scratch

## Usage

```bash
# Run directly (starts stdio MCP server)
cd server && uv run context-flow-server

# Or via python -m
cd server && uv run python -m context_flow_server
```

## How it works

On startup, the server scans `~/.claude/projects/` for JSONL transcript files. It incrementally indexes new/modified files into a SQLite database at `~/.local/share/context-flow/index.db`. Subsequent startups only process new or grown files.

The index stores:
- **User messages** — actual human input (not tool results)
- **Assistant text** — Claude's responses (not thinking blocks)
- **Tool summaries** — what tools were called and with what arguments
- **Plans** — `planContent` from plan-mode entries

Messages are searchable via FTS5 full-text search with support for AND, OR, NOT, and phrase queries.

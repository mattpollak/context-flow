# Attribution

relay was designed by studying several existing Claude Code memory
and workflow management systems. While no code was copied from these projects,
their architectural ideas and patterns were instrumental in shaping this plugin.

## Inspirations

### Episodic Memory
- **Repository:** https://github.com/obra/episodic-memory
- **Author:** Jesse Vincent
- **License:** MIT
- **Ideas adopted:** Conversation archival and semantic search via MCP server;
  subagent-based recall to protect main context window; SessionStart hook
  for automatic context loading.

### Get Shit Done (GSD)
- **Repository:** https://github.com/gsd-build/get-shit-done
- **Author:** GSD Build
- **License:** MIT
- **Ideas adopted:** PostToolUse context exhaustion monitoring with graduated
  warnings; wave-based parallel subagent execution; lean state files (STATE.md
  kept under 100 lines); explicit pause/resume lifecycle with handoff files.

### CASS Memory System
- **Repository:** https://github.com/Dicklesworthstone/cass_memory_system
- **Author:** Jeff Emanuel
- **License:** MIT
- **Ideas adopted:** Structured knowledge accumulation with confidence tracking
  and decay; anti-pattern recording ("we tried X and it failed because Y");
  evidence-based rule validation. These concepts informed our approach to
  state file design and future knowledge accumulation features.

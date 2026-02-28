# relay Data Formats

## workstreams.json

Central registry of all workstreams. Parsed with `jq` by hook scripts.

```json
{
  "workstreams": {
    "<name>": {
      "status": "active" | "parked" | "completed",
      "description": "Short description",
      "created": "YYYY-MM-DD",
      "last_touched": "YYYY-MM-DD",
      "project_dir": "/absolute/path/to/project"  // optional
    }
  }
}
```

### Status values
- **active**: Currently being worked on. At most one workstream should be active.
- **parked**: Paused, can be resumed later.
- **completed**: Done. Kept for reference.

### Fields
- **status** (required): One of active/parked/completed
- **description** (required): Human-readable summary
- **created** (required): ISO date when created
- **last_touched** (required): ISO date of last activity
- **project_dir** (optional): Absolute path to the project's code directory

## state.md

Per-workstream state file. Target: ~80 lines max. Atomic overwrite with `.bak` backup.

### Required sections
```markdown
# <Workstream Name>

## Metadata
- **Description:** ...
- **Created:** YYYY-MM-DD
- **Project dir:** /path/to/project (if applicable)

## Current Status
What's happening right now. 2-3 sentences.

## Key Decisions
Bullet list of important choices made.

## Next Steps
Numbered list of what to do next.
```

### Optional sections
- **Architecture Notes** — inline notes (or pointer to architecture.md)
- **Blockers** — anything preventing progress
- **Recent Sessions** — last 2-3 sessions in condensed form (one line each)

## parking-lot.md

Cross-project ideas and future work. Simple bullet list.

```markdown
# Parking Lot

- **Project: Feature name** — description
- Standalone idea — description
- ~~Completed item~~ — DONE (when/where)
```

## Companion files (optional, per-workstream)

- **plan.md** — Implementation plan. Not auto-loaded; read on explicit `/relay:switch`.
- **architecture.md** — Architecture notes. Not auto-loaded; read on explicit `/relay:switch`.

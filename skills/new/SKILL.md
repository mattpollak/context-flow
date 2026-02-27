---
name: new
description: >
  Create a new workstream for tracking a project or task.
  Trigger phrases: "new workstream", "start workstream", "create workstream".
argument-hint: "<name> [description]"
---

# Create New Workstream

Create a new context-flow workstream with the name and description provided in `$ARGUMENTS`.

## Data directory

```
DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
```

## Steps

1. **Parse arguments.** The first word of `$ARGUMENTS` is the workstream name. Everything after is the description. If no arguments were provided, ask the user for a name and description before proceeding.

2. **Validate name.** Must match `^[a-z0-9][a-z0-9-]*$` (lowercase, hyphens, no leading/trailing hyphens). If invalid, tell the user and ask for a corrected name.

3. **Initialize data directory.** Run:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/init-data-dir.sh"
   ```

4. **Check for duplicates.** Read `$DATA_DIR/workstreams.json` and check if a workstream with this name already exists. If it does, tell the user and stop.

5. **Auto-park active workstream.** If any workstream has `"status": "active"`, set it to `"parked"` and update its `last_touched` to today. Tell the user you're parking it.

6. **Create workstream directory and state file.** Create `$DATA_DIR/workstreams/<name>/state.md` using the template at `${CLAUDE_PLUGIN_ROOT}/templates/state.md`. Replace `{{NAME}}` with the name, `{{DESCRIPTION}}` with the description, `{{DATE}}` with today's date (YYYY-MM-DD), and `{{PROJECT_DIR}}` with the current working directory.

7. **Update registry.** Add the new workstream to `$DATA_DIR/workstreams.json` using jq:
   ```bash
   jq --arg name "<name>" \
      --arg desc "<description>" \
      --arg date "$(date +%Y-%m-%d)" \
      --arg dir "$(pwd)" \
      '.workstreams[$name] = {status: "active", description: $desc, created: $date, last_touched: $date, project_dir: $dir}' \
      "$DATA_DIR/workstreams.json" > "$DATA_DIR/workstreams.json.tmp" && \
   command mv "$DATA_DIR/workstreams.json.tmp" "$DATA_DIR/workstreams.json"
   ```

8. **Confirm.** Tell the user the workstream was created and is now active. Show the path to the state file.

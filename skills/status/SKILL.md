---
name: status
description: >
  Show current workstream status and available commands.
  Trigger phrases: "relay status", "workstream status", "what workstream", "what am I working on".
---

# Workstream Status

Show this session's attached workstream status, plus a summary of other workstreams and available commands.

## Steps

1. **Read registry.** Run the helper script to read the registry:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/read-data-file.sh" "workstreams.json"
   ```
   If the output is `NOT_FOUND`, tell the user no workstreams exist yet and suggest `/relay:new`.

2. **Identify attached workstream.** Check the `relay:` line in your session context for the workstream name. If none, check the registry for active workstreams.

3. **If an attached/active workstream exists:**
   a. Read its state file:
      ```bash
      bash "${CLAUDE_PLUGIN_ROOT}/scripts/read-data-file.sh" "workstreams/<name>/state.md"
      ```
   b. Display a status summary:
      ```
      ## Attached: <name>
      **Description:** <description>
      **Project:** <project_dir or "none">
      **Last touched:** <last_touched>

      ### Current Status
      <Current Status section from state.md, or "(no state file)" if NOT_FOUND>

      ### Next Steps
      <Next Steps section from state.md, if present>
      ```

4. **If no attached workstream:** Say "No workstream attached to this session." and skip to step 5.

5. **Show other workstreams.** From the registry, list other active, parked, and completed workstreams:
   ```
   **Other active:** name1, name2 (or "none")
   **Parked:** name1, name2 (or "none")
   **Completed:** name1, name2 (or "none")
   ```

6. **Show commands.** End with:
   ```
   **Commands:** `/relay:new` · `/relay:switch <name>` · `/relay:save` · `/relay:park` · `/relay:list`
   ```

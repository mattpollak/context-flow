---
name: status
description: >
  Show current workstream status and available commands.
  Trigger phrases: "relay status", "workstream status", "what workstream", "what am I working on".
---

# Workstream Status

Show this session's attached workstream status, plus a summary of other workstreams and available commands.

## Steps

1. **Fetch data.** Call `list_workstreams` to get all workstreams grouped by status.

2. **Identify attached workstream.** Check the `relay:` line in your session context for the workstream name. If none, check the active workstreams from the response.

3. **If an attached/active workstream exists:** Display:
   ```
   ## Attached: <name>
   **Description:** <description>
   **Project:** <project_dir or "none">
   **Last touched:** <last_touched>
   ```
   Then call `switch_workstream(to_name="<name>")` to get the current state content (this is a read-only operation -- if already attached, it just returns the state without saving anything). Display the Current Status and Next Steps sections from the state.

   **Alternative:** If the workstream state was already loaded in session context (from session start), just display it directly without an extra MCP call.

4. **If no attached workstream:** Say "No workstream attached to this session."

5. **Show other workstreams.** From the `list_workstreams` response:
   ```
   **Other active:** name1, name2 (or "none")
   **Parked:** name1, name2 (or "none")
   **Completed:** name1, name2 (or "none")
   ```

6. **Show commands.** End with:
   ```
   **Commands:** `/relay:new` · `/relay:switch <name>` · `/relay:save` · `/relay:park` · `/relay:list`
   ```

---
name: new
description: >
  Create a new workstream for tracking a project or task.
  Trigger phrases: "new workstream", "start workstream", "create workstream".
argument-hint: "<name> [description]"
---

# Create New Workstream

Create a new workstream with the name and description provided in `$ARGUMENTS`.

## Steps

1. **Parse arguments.** The first word of `$ARGUMENTS` is the workstream name. Everything after is the description. If no arguments provided, ask the user.

2. **Validate name.** Must match `^[a-z0-9][a-z0-9-]*$`. If invalid, ask for correction.

3. **Create workstream.** Call `create_workstream`:
   ```
   create_workstream(name="<name>", description="<desc>", project_dir="<cwd>")
   ```
   If it returns an error (duplicate), tell the user.

4. **Check for matching ideas.** Call `manage_idea(action="list")`. If any idea's text closely matches the new workstream's name or description, ask the user if they'd like to remove it. If yes, call `manage_idea(action="remove", idea_id=<id>)`.

5. **Confirm.** Tell the user the workstream was created and is now active.

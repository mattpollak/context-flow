---
name: idea
description: >
  Capture an idea for future work, or promote one to a workstream. Displayed by /relay:list.
  Trigger phrases: "add idea", "jot down", "remember this idea", "idea promote".
argument-hint: "<idea text> | promote <id>"
---

# Capture or Promote Ideas

Ideas are things you want to track but haven't started working on yet. They are displayed by `/relay:list`. When you're ready to work on one, promote it to a full workstream.

**Argument:** `$ARGUMENTS` is either idea text to capture, or `promote <id>` to turn an idea into a workstream.

## Subcommand: promote

If `$ARGUMENTS` starts with `promote`, extract the idea ID (the number after "promote").

1. **Find the idea.** Call `manage_idea(action="list")`. Find the idea with the matching ID. If not found, list all ideas with their IDs and stop.

2. **Remove the idea.** Call `manage_idea(action="remove", idea_id=<id>)`.

3. **Create workstream.** Tell the user the idea has been removed, then invoke `/relay:new` using the idea text as context. Ask the user for a workstream name and description (suggest based on the idea text).

## Subcommand: add (default)

If `$ARGUMENTS` does not start with `promote`, treat it as idea text.

1. **Get the idea.** The idea text is `$ARGUMENTS`. If empty, ask the user what they want to capture and stop.

2. **Add.** Call `manage_idea(action="add", text="<idea text>")`.

3. **Confirm.** Tell the user the idea was captured with its ID. Mention `/relay:list` to see all ideas and `/relay:idea promote <id>` when ready.

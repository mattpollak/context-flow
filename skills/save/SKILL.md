---
name: save
description: >
  Save the current workstream's state to disk.
  Trigger phrases: "save context", "save state", "save session", "persist context", "update context".
---

# Save Workstream State

Save the current session's context to the active workstream's state file.

## Steps

1. **Find active workstream.** Call `list_workstreams` to find which workstream is active. If none is active, tell the user and suggest `/relay:new` or `/relay:switch`.

2. **Save.** Call `save_workstream` with the state content and session hint:
   ```
   save_workstream(
     name="<active workstream>",
     state_content="<80-line state markdown>",
     session_id="<from relay-session-id context>",
     hint_summary=["<3-6 bullets>"],
     hint_decisions=["<decisions if any>"]
   )
   ```

3. **Confirm.** Tell the user the state was saved. Mention backup at `state.md.bak`.

## State File Content

The state file MUST stay under 80 lines. Include these sections:

```markdown
# <Workstream Name>

## Metadata
- **Description:** ...
- **Created:** YYYY-MM-DD
- **Project dir:** /path (if applicable)

## Current Status
2-3 sentences on what's happening right now.

## Key Decisions
- Bullet list of important choices made (accumulated across sessions)

## Next Steps
1. Numbered list of what to do next

## Recent Sessions (optional, if space permits)
- YYYY-MM-DD: One-line summary
```

**Priority if space is tight:** Current Status > Next Steps > Key Decisions > Recent Sessions.

## Hint Writing Guidelines

- Summary bullets should be **what changed**, not how much work happened
- Include specific outcomes: features, capabilities, fixes, design decisions
- If the session spanned multiple workstreams, write one hint per workstream segment
- Keep each bullet to one line, no sub-bullets
- Omit the `hint_decisions` parameter if no notable decisions were made

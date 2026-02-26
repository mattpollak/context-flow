---
name: list
description: >
  List all workstreams grouped by status.
  Trigger phrases: "list workstreams", "show workstreams".
---

# List Workstreams

Display all workstreams from the registry, grouped by status.

## Data directory

```
DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
```

## Steps

1. **Read registry.** Read `$DATA_DIR/workstreams.json`. If it doesn't exist, tell the user no workstreams have been created yet and suggest `/context-flow:new`.

2. **Display grouped by status.** Format the output as a table grouped by status. Show active workstreams first, then parked, then completed:

   ```
   ## Active
   | Workstream | Description | Last Touched |
   |---|---|---|
   | name | description | date |

   ## Parked
   | Workstream | Description | Last Touched |
   |---|---|---|
   | name | description | date |

   ## Completed
   | Workstream | Description | Completed |
   |---|---|---|
   | name | description | date |
   ```

   If a group has no entries, skip it entirely.

3. **Show parking lot.** If `$DATA_DIR/parking-lot.md` exists, read and display its contents under a "## Parking Lot" heading.

4. **Quick tips.** After the listing, show:
   ```
   **Commands:** `/context-flow:new` · `/context-flow:switch <name>` · `/context-flow:park` · `/context-flow:save`
   ```

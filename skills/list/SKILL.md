---
name: list
description: >
  List all workstreams grouped by status.
  Trigger phrases: "list workstreams", "show workstreams".
---

# List Workstreams

Display all workstreams from the registry, grouped by status.

## Steps

1. **Fetch data.** Call `list_workstreams`. Returns `active`, `parked`, `completed` arrays and `ideas`.

2. **Display grouped by status.** Format as tables, showing active first, then parked, then completed:

   ```
   ## Active
   | Workstream | Description | Last Touched |
   |---|---|---|
   | name | description | date |

   ## Parked
   | Workstream | Description | Last Touched |
   |---|---|---|
   | name | description | date |
   ```

   If a group has no entries, skip it entirely.

3. **Show ideas.** If the `ideas` array is non-empty, display:
   ```
   ## Ideas
   1. idea text *(date)*

   `/relay:idea promote <id>` to start working on one.
   ```

4. **Quick tips.** Show:
   ```
   **Commands:** `/relay:status` · `/relay:new` · `/relay:switch <name>` · `/relay:save` · `/relay:park` · `/relay:idea`
   ```

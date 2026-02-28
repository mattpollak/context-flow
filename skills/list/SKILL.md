---
name: list
description: >
  List all workstreams grouped by status.
  Trigger phrases: "list workstreams", "show workstreams".
---

# List Workstreams

Display all workstreams from the registry, grouped by status.

## Steps

1. **Read registry.** Run the helper script to read the registry:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/read-data-file.sh" "workstreams.json"
   ```
   If the output is `NOT_FOUND`, tell the user no workstreams have been created yet and suggest `/relay:new`.

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

3. **Show parking lot.** Read the parking lot file:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/read-data-file.sh" "parking-lot.md"
   ```
   If the output is NOT `NOT_FOUND`, display its contents under a "## Parking Lot" heading.

4. **Quick tips.** After the listing, show:
   ```
   **Commands:** `/relay:new` · `/relay:switch <name>` · `/relay:park` · `/relay:save`
   ```

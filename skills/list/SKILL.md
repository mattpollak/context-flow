---
name: list
description: >
  List all workstreams grouped by status.
  Trigger phrases: "list workstreams", "show workstreams".
---

# List Workstreams

Display all workstreams from the registry, grouped by status.

## Steps

1. **Fetch data.** Call `list_workstreams`. The response includes a `formatted` field with ready-to-display markdown.

2. **Display.** Output the `formatted` field directly — it contains grouped tables, ideas, and command hints. Do not reformat or restructure it.

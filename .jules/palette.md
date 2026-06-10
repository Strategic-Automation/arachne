## 2026-05-25 - Screen reader spam with CLI ASCII art
**Learning:** Typer `@app.callback(invoke_without_command=True)` affects all subcommands. Outputting large ASCII art indiscriminately across all CLI commands spams screen readers with useless "block block block" readings, wasting both accessibility device time and terminal space.
**Action:** Only display ASCII banners when explicitly invoking the base command (`ctx.invoked_subcommand is None`) or when it adds specific contextual value (like displaying available tools with `--list-tools`).

## 2026-05-25 - Actionable Error Messages
**Learning:** Providing actionable guidance in error messages and empty states significantly reduces user friction. When a user queries a non-existent ID, giving them the exact command to find the correct ID is an immediate UX win.
**Action:** Always append hints to "not found" or "empty" states that point the user to the correct command or workflow.
## 2026-05-25 - Actionable Error Messages for Empty States
**Learning:** Empty states in CLIs (like "No sessions found") can be frustrating dead-ends. Providing actionable guidance using existing console styles (e.g., `Run a goal with arachne run first.`) transforms an error into a helpful workflow suggestion without needing new dependencies.
**Action:** Always append hints to "not found" or "empty" states that point the user to the correct command or workflow, keeping changes under 50 lines.
## 2024-05-18 - CLI Empty State Handling
**Learning:** Users can encounter empty states (like listing sessions or graphs) even if the parent directory structure exists. Showing a completely empty table is visually confusing and doesn't tell the user what to do next. Providing actionable error/empty messages is much better UX.
**Action:** Always verify that a directory actually contains valid entries (like `.json` files or subdirectories) before attempting to iterate and render a UI component (like a table). Fall back to a helpful, actionable empty state message.

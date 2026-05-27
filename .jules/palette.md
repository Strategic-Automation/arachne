## 2026-05-25 - Screen reader spam with CLI ASCII art
**Learning:** Typer `@app.callback(invoke_without_command=True)` affects all subcommands. Outputting large ASCII art indiscriminately across all CLI commands spams screen readers with useless "block block block" readings, wasting both accessibility device time and terminal space.
**Action:** Only display ASCII banners when explicitly invoking the base command (`ctx.invoked_subcommand is None`) or when it adds specific contextual value (like displaying available tools with `--list-tools`).

## 2026-05-25 - Actionable Error Messages
**Learning:** Providing actionable guidance in error messages and empty states significantly reduces user friction. When a user queries a non-existent ID, giving them the exact command to find the correct ID is an immediate UX win.
**Action:** Always append hints to "not found" or "empty" states that point the user to the correct command or workflow.

## 2026-05-27 - Actionable Empty States
**Learning:** Empty tables in CLI outputs with headers but no data are confusing and give the impression something is broken or loading. Explicitly catching empty conditions and displaying clear, helpful guidance ("No sessions found. Run a goal with arachne run first.") provides a much better experience.
**Action:** Always intercept empty list states before rendering tables, displaying descriptive text and guiding users to the next sensible action.

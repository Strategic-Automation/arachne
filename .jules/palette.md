## 2026-05-25 - Screen reader spam with CLI ASCII art
**Learning:** Typer `@app.callback(invoke_without_command=True)` affects all subcommands. Outputting large ASCII art indiscriminately across all CLI commands spams screen readers with useless "block block block" readings, wasting both accessibility device time and terminal space.
**Action:** Only display ASCII banners when explicitly invoking the base command (`ctx.invoked_subcommand is None`) or when it adds specific contextual value (like displaying available tools with `--list-tools`).

## 2026-05-25 - Actionable Error Messages
**Learning:** Providing actionable guidance in error messages and empty states significantly reduces user friction. When a user queries a non-existent ID, giving them the exact command to find the correct ID is an immediate UX win.
**Action:** Always append hints to "not found" or "empty" states that point the user to the correct command or workflow.

## 2026-06-06 - Empty State Directory Safety
**Learning:** Adding helpful hints to empty states (e.g. `arachne cat`) can cause unexpected regressions if the underlying code assumes the storage directory already exists. Iterating over `base.iterdir()` without first checking `base.exists()` throws a `FileNotFoundError` on fresh installs where no sessions exist yet.
**Action:** Always wrap directory iteration in an `.exists()` check when building "not found" or "empty" states, especially in CLI tools that manage local file structures.

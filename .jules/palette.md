## 2026-05-25 - Screen reader spam with CLI ASCII art
**Learning:** Typer `@app.callback(invoke_without_command=True)` affects all subcommands. Outputting large ASCII art indiscriminately across all CLI commands spams screen readers with useless "block block block" readings, wasting both accessibility device time and terminal space.
**Action:** Only display ASCII banners when explicitly invoking the base command (`ctx.invoked_subcommand is None`) or when it adds specific contextual value (like displaying available tools with `--list-tools`).

## 2026-05-25 - Actionable Error Messages
**Learning:** Providing actionable guidance in error messages and empty states significantly reduces user friction. When a user queries a non-existent ID, giving them the exact command to find the correct ID is an immediate UX win.
**Action:** Always append hints to "not found" or "empty" states that point the user to the correct command or workflow.
## 2026-05-26 - Screen Reader Accessibility in CLI Interfaces
**Learning:** Large ASCII art banners in global CLI callbacks spam screen readers with unintelligible characters on every sub-command execution, drastically degrading accessibility.
**Action:** Replace complex ASCII art with simple, clean, screen-reader-friendly text strings for CLI banners.

## 2026-05-26 - Actionable CLI Empty States
**Learning:** CLI users often reach dead ends when empty states simply declare "No data found." Adding hints on what command to run next significantly improves the developer experience.
**Action:** Ensure all "list" or "show" commands provide actionable next steps (e.g., "Run a goal with arachne run first") when returning empty data.

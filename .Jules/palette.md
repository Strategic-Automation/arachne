## 2024-05-22 - Handling UI cancellations
**Learning:** `questionary` CLI prompts return `None` when a user interrupts the process via Ctrl+C. Failing to capture this in interactive flows (like confirm/select boxes) causes the program to bypass cancellation and continue execution, frustrating users who expect `Ctrl+C` to cleanly abort.
**Action:** Created a wrapper `_safe_ask` that explicitly captures `None` returns from `.ask()` and translates them to `KeyboardInterrupt` to correctly interrupt standard flows.
## 2024-05-23 - Empty State Copy Improvements in CLI Tools
**Learning:** Found that CLI commands lacking empty states can be confusing and create dead-ends for users. Instead of a generic "No sessions found", adding context-specific messages ("No sessions found to clean") and actionable advice ("Run a goal with arachne run first.") improves the overall user experience.
**Action:** When implementing CLI commands that list or manage resources, always ensure empty states are descriptive and provide a clear next step for the user.

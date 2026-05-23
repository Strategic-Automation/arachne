## 2024-05-22 - Handling UI cancellations
**Learning:** `questionary` CLI prompts return `None` when a user interrupts the process via Ctrl+C. Failing to capture this in interactive flows (like confirm/select boxes) causes the program to bypass cancellation and continue execution, frustrating users who expect `Ctrl+C` to cleanly abort.
**Action:** Created a wrapper `_safe_ask` that explicitly captures `None` returns from `.ask()` and translates them to `KeyboardInterrupt` to correctly interrupt standard flows.

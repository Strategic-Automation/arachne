## 2026-06-07 - [Path Traversal in System File Tools]
**Vulnerability:** The system file reading and writing tools (`read_file` and `write_local_file`) blindly constructed paths without verifying if they broke out of the active session outputs directory or current working directory.
**Learning:** Agent execution environments lacking boundary restrictions allow for dangerous Path Traversal where the agent can interact with or expose files outside the intended sandbox (e.g., `/etc/passwd`).
**Prevention:** Always perform strict boundary checks using `Path.resolve().is_relative_to(boundary_path.resolve())` within system file operation wrappers before interacting with the file. Also, ensure security checks fail closed inside a `try...except` block in case path resolution throws.

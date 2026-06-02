## 2025-05-18 - Path Traversal in File Tools
**Vulnerability:** `read_file` and `write_file` tools were vulnerable to path traversal (e.g. `../../../../etc/passwd`). The implementation only checked `os.path.realpath` but failed to enforce boundary restrictions.
**Learning:** `os.path.realpath` alone normalizes paths but does not prevent escaping the intended workspace directory if malicious relative paths are provided.
**Prevention:** Use `Path.resolve().is_relative_to()` to strictly constrain resolved paths to expected boundaries like `Path.cwd()` or the active session's `outputs` directory.

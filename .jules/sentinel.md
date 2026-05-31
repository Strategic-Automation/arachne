## 2024-05-31 - Path Traversal Vulnerability in System Tools
**Vulnerability:** System tools `file_read` and `file_write` lacked proper validation for absolute paths, enabling an arbitrary file read/write through path traversal (`../../` or absolute path inputs) if exploited by a compromised or malicious agent.
**Learning:** `os.path.realpath` without an explicit bounds check does not restrict paths, it only canonicalizes them. File operations in agent tools must be strictly constrained to their designated workspace to prevent agents from reading or modifying external/system files.
**Prevention:** Always use `Path.resolve().is_relative_to()` with a known safe root directory (like `Path.cwd()` or a session-specific outputs directory) before executing any file operations.

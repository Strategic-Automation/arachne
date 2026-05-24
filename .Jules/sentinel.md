## 2024-05-24 - Path Traversal in file read/write tools
**Vulnerability:** Path traversal existed in `read_file` and `write_local_file` because the `realpath` check is insufficient to verify boundaries.
**Learning:** `os.path.realpath` simply resolves symlinks and absolute paths but does not restrict where a file can be accessed from. An attacker could still provide an absolute path to a sensitive file or use `../` to access unintended directories.
**Prevention:** Always verify that the fully resolved absolute path is relative to an explicitly allowed base directory (e.g., `Path.cwd()` or the session output directory) using `resolved.is_relative_to(allowed_dir)`.

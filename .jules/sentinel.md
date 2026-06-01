## 2024-06-01 - Path Traversal in File Tools
**Vulnerability:** Found a path traversal vulnerability in `read_file` and `write_local_file` where absolute paths and relative paths `../../` can escape the intended sandbox bounds, potentially leaking sensitive system files like `/etc/passwd`.
**Learning:** `os.path.realpath` is insufficient if the path is not validated against a bounded root directory.
**Prevention:** Use `Path.resolve()` to get an absolute, canonical path, and explicitly verify bounds using `resolved_path.is_relative_to(bounded_dir)` before performing any file operations.

## 2025-05-29 - Path Traversal in File Operations
**Vulnerability:** Path traversal vulnerabilities identified in `read_file` and `write_local_file` tools. The tools accepted file paths (including ones starting with `../../`) without checking if the target file resolved to a location inside `Path.cwd()` or the current active session outputs.
**Learning:** Checking `os.path.realpath` or `p.resolve()` is not enough to prevent path traversal on its own. We must constrain the resolved path strictly within permitted boundaries using `is_relative_to`.
**Prevention:** Used `Path.resolve().is_relative_to(Path.cwd().resolve())` along with similar checks for session output directories to strictly enforce operational boundaries on all file paths handled by system tools.

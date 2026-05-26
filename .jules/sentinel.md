## 2024-05-24 - Path Traversal Vulnerability in File Operations
**Vulnerability:** Found arbitrary path traversal vulnerabilities in `read_file` and `write_local_file` tools (`src/arachne/tools/system/file_read.py` and `src/arachne/tools/system/file_write.py`).
**Learning:** File access operations were lacking strict validation against specific allowed boundaries. The project requires confining file interactions to `Path.cwd()` and the active session's outputs directory.
**Prevention:** Use `Path.resolve().is_relative_to()` to strictly enforce boundaries on resolved paths against an allowlist of directories (`[Path.cwd().resolve(), (sess_path / "outputs").resolve()]`). Always enforce this pattern for any file system related tools.

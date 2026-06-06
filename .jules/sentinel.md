## 2026-06-06 - Fix Path Traversal in File Tools
**Vulnerability:** Path traversal vulnerabilities allowed reading/writing arbitrary files outside the session directory and cwd.
**Learning:** Path boundaries must be explicitly validated using resolved absolute paths to prevent symlink bypasses or relative payload attacks.
**Prevention:** Use `Path.resolve().is_relative_to(boundary.resolve())` for all file operations that accept user input.

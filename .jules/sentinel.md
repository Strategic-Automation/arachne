## $(date +%Y-%m-%d) - Prevent Path Traversal in File Tools
**Vulnerability:** File read/write tools allowed reading and writing arbitrary files outside the current working directory or session outputs directory.
**Learning:** Using `os.path.realpath()` only normalizes paths but does not check if the resolved path is within an acceptable boundary. It's critical to enforce boundaries, especially on user-provided inputs in LLM agents.
**Prevention:** Use `Path.resolve()` and `Path.is_relative_to()` to ensure the final path is strictly constrained to `Path.cwd()` or the active session's outputs directory. Fail closed by default.

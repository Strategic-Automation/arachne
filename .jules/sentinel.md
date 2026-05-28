## 2024-05-28 - Path Traversal Vulnerability in File Read/Write Tools
**Vulnerability:** The built-in file read (`read_file`) and write (`write_local_file`) tools were vulnerable to path traversal. They failed to validate whether the requested file paths (like `../../../../etc/passwd`) stayed within allowed bounds.
**Learning:** Security features like this project's sandbox bypass when standard Python tools fail to enforce path boundaries. `realpath` by itself is insufficient without also enforcing that the resolved path originates from a safe root context (e.g. `is_relative_to()`).
**Prevention:** Always restrict file system operations within agent tools to the current working directory (`Path.cwd()`) or the active session's directory to prevent LLM-driven path traversal.

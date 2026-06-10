
## 2024-06-10 - Agent Tool Path Traversal
**Vulnerability:** System read/write tools (`read_file`, `write_local_file`) did not adequately resolve and restrict paths, allowing `os.path.realpath` to process relative traversal characters (`../../../`) which bypassed basic non-absolute checks.
**Learning:** Agentic tool calls accessing the filesystem natively must defensively isolate user inputs. Basic `is_absolute()` checks are insufficient when `realpath` subsequently resolves traversal tokens.
**Prevention:** Always fully resolve the user input string into a `Path.resolve()` instance, and strictly use `is_relative_to()` against allowed boundary paths (e.g., `Path.cwd().resolve()`, active session directories) to reliably enforce directory boundaries.

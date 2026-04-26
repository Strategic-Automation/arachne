# Contributing to Arachne

Thank you for considering contributing to Arachne! We welcome contributions from the community.

## How to Contribute

### Reporting Issues
- Use the [issue template](../.github/ISSUE_TEMPLATE/bug_report.md) for bug reports
- Use the [feature template](../.github/ISSUE_TEMPLATE/feature_request.md) for feature requests
- Clearly describe the problem, steps to reproduce, and expected behavior
- Include relevant logs, screenshots, or code snippets

### Development Workflow

1. **Fork the repository**
2. **Create a feature branch**: Use the naming convention `issue/{number}-{short-description}`
   - Example: `issue/123-add-user-authentication`
3. **Make your changes** following our coding standards
4. **Write tests** for any new functionality
5. **Run tests and linting** before committing
6. **Commit your changes** using conventional commits
7. **Push to your fork** and open a Pull Request

### Branch Naming
All branches must follow the format: `issue/{number}-{description}`
- `{number}`: The GitHub issue number this branch addresses
- `{description}`: Short, hyphen-separated description of the work
- Examples:
  - `issue/45-add-mcp-validation`
  - `issue/102-fix-shell-exec-security`
  - `issue/88-update-documentation`

### Commit Messages
We follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes
- `style`: Formatting, missing semi-colons, etc.
- `refactor`: Code restructuring without changing behavior
- `test`: Adding or modifying tests
- `chore`: Build process or auxiliary tool changes

Format: `type(scope): description`
- Examples:
  - `feat(topologies): add MCP command validation`
  - `fix(tools): remove shell=True from shell_exec`
  - `docs(readme): add quick start guide`

### Pull Request Process
1. **Ensure your PR targets the `main` branch**
2. **Link to the issue**: Use `Fixes #issue-number` or `Closes #issue-number` in your description
3. **Request review** from at least one maintainer
4. **Pass all checks**: Tests must pass, linting must be clean
5. **Address review feedback** promptly
6. **Once approved**, maintainers will merge your PR

### Coding Standards
- **Package Manager**: Use `uv` for all Python execution and package management
- **Linting**: Run `uv run ruff check --fix` before committing
- **Formatting**: Run `uv run ruff format` before committing
- **Testing**: Write tests alongside new code using `pytest`
- **Type Hints**: Add type hints to all function signatures
- **Strings**: Always use f-strings (`f"hello {name}"`), never `.format()` or `%`-style
- **File Size**: Keep files under 200 lines when practical; split large files
- **Security**: 
  - Never use `shell=True` in subprocess calls
  - Validate MCP server commands against allowed list
  - Never commit `.env` files or secrets
- **Documentation**: Add docstrings to all public functions and classes

### Testing Guidelines
- Write unit tests for all new functionality
- Use mock LLM responses in tests (never real API calls)
- Maintain >60% test coverage (configured in pyproject.toml)
- Use `pytest-asyncio` with `@pytest.mark.asyncio` for async tests
- Integration tests requiring real credentials should use the `integration` marker

### Getting Started
1. Fork and clone the repository
2. Install dependencies: `uv sync`
3. Install pre-commit hooks: `uv run pre-commit install`
4. Run tests: `uv run pytest`
5. Start coding!

### Questions?
Feel free to ask questions in your issue or pull request. We're happy to help!

Thank you for contributing to Arachne!
"""Session introspection tools."""

from arachne.sessions.manager import active_session_path


def read_session_file(relative_path: str) -> str:
    """Read a file from the current session folder by relative path."""
    sess_path = active_session_path.get()
    if not sess_path:
        return "No active session."
    p = sess_path / relative_path

    try:
        resolved_path = p.resolve()
        if not resolved_path.is_relative_to(sess_path.resolve()):
            return f"Security Error: Access to {relative_path} is restricted to session folder."
    except Exception as e:
        return f"Error resolving path {relative_path}: {e}"

    if not p.exists():
        return f"File not found: {relative_path}"
    try:
        content = p.read_text()
        if len(content) > 50000:
            content = content[:25000] + "\n... [TRUNCATED - file too large] ...\n" + content[-25000:]
        return content
    except Exception as e:
        return f"Error reading {relative_path}: {e}"

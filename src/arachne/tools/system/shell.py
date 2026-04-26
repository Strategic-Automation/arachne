"""Execute shell commands safely."""

import shlex
import subprocess


def shell_exec(command: str | list[str]) -> str:
    """Execute a shell command and return stdout+stderr. Max 30s timeout.

    SECURITY: This function does NOT use shell=True to prevent command injection.
    Commands should be passed as a list of arguments when possible.

    Args:
        command: Either a string command or list of command arguments

    Returns:
        Command output as string (stdout+stderr, truncated to 4000 chars)
    """
    try:
        command_list = shlex.split(command) if isinstance(command, str) else command
        r = subprocess.run(command_list, shell=False, capture_output=True, text=True, timeout=30)
        out = (r.stdout + r.stderr).strip()
        return out[:4000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "(command timed out after 30s)"
    except Exception as e:
        return f"Error: {e}"

"""Local Python Sandbox."""

import contextlib
import os
import subprocess
import tempfile


def python_sandbox(code: str, timeout_seconds: int = 30) -> str:
    """Execute Python code in a local subprocess with a timeout.

    WARNING: This executes code directly on the local machine. It uses a subprocess
    to isolate crashes and timeouts, but it does NOT provide network or filesystem
    isolation. Do not use this for untrusted code.

    Args:
        code: The Python code to execute.
        timeout_seconds: Maximum time to allow the code to run (default 30s).

    Returns:
        The standard output and standard error from the script execution.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_file = f.name

    try:
        # Run the script in a new Python subprocess
        result = subprocess.run(
            ["python3", temp_file], capture_output=True, text=True, timeout=timeout_seconds, check=False
        )

        output = result.stdout
        if result.stderr:
            output += f"\n--- STDERR ---\n{result.stderr}"

        if not output.strip():
            return "(Execution completed with no output)"

        # Truncate output if it's too massive
        if len(output) > 10000:
            return output[:5000] + "\n... [TRUNCATED] ...\n" + output[-5000:]

        return output.strip()

    except subprocess.TimeoutExpired:
        return f"Error: Script execution timed out after {timeout_seconds} seconds."
    except Exception as e:
        return f"Error executing script: {e!s}"
    finally:
        # Clean up the temporary file
        with contextlib.suppress(OSError):
            os.remove(temp_file)

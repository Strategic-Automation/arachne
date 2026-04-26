import subprocess
from unittest.mock import MagicMock, patch

from arachne.tools.execution.python_sandbox import python_sandbox


def test_python_sandbox_happy_path():
    """Test successful execution of valid Python code."""
    mock_result = MagicMock()
    mock_result.stdout = "Hello World\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = python_sandbox("print('Hello World')")

        assert result == "Hello World"
        mock_run.assert_called_once()
        _args, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == 30


def test_python_sandbox_with_stderr():
    """Test execution that produces both stdout and stderr."""
    mock_result = MagicMock()
    mock_result.stdout = "Normal output"
    mock_result.stderr = "Warning message"

    with patch("subprocess.run", return_value=mock_result):
        result = python_sandbox("print('test')")

        assert "Normal output" in result
        assert "--- STDERR ---" in result
        assert "Warning message" in result


def test_python_sandbox_timeout():
    """Test handling of subprocess timeout."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="python3", timeout=5)):
        result = python_sandbox("while True: pass", timeout_seconds=5)

        assert "timed out after 5 seconds" in result


def test_python_sandbox_no_output():
    """Test script that runs successfully but produces no output."""
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        result = python_sandbox("x = 1")
        assert result == "(Execution completed with no output)"


def test_python_sandbox_massive_output():
    """Test that massive outputs are safely truncated."""
    mock_result = MagicMock()
    # Create 15,000 character output
    mock_result.stdout = "A" * 15000
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        result = python_sandbox("print('A' * 15000)")

        assert len(result) < 15000
        assert "[TRUNCATED]" in result
        assert result.startswith("A" * 5000)
        assert result.endswith("A" * 5000)

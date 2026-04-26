import subprocess
from unittest.mock import MagicMock, patch

from arachne.tools.system.file_read import read_file
from arachne.tools.system.file_write import write_local_file
from arachne.tools.system.shell import shell_exec
from arachne.tools.system.system_time import get_current_time


# --- Shell Tests ---
def test_shell_exec_happy_path():
    """Test successful shell execution."""
    mock_result = MagicMock()
    mock_result.stdout = "hello\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = shell_exec("echo hello")

        assert result == "hello"
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        # Should be properly shlex split
        assert args[0] == ["echo", "hello"]
        assert kwargs.get("shell") is False


def test_shell_exec_timeout():
    """Test handling of shell timeout."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sleep 100", timeout=30)):
        result = shell_exec("sleep 100")
        assert "(command timed out after 30s)" in result


def test_shell_exec_truncation():
    """Test that massive output is truncated to 4000 chars."""
    mock_result = MagicMock()
    mock_result.stdout = "A" * 5000
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        result = shell_exec("echo lots")
        assert len(result) == 4000
        assert result == "A" * 4000


# --- System Time Tests ---
def test_get_current_time_valid_tz():
    """Test getting time in a valid timezone."""
    with patch("arachne.tools.system.system_time.datetime") as mock_datetime, \
         patch("arachne.tools.system.system_time.ZoneInfo") as mock_zoneinfo:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "Current Date and Time: Monday, January 01, 2024 at 12:00:00 PM UTC"
        mock_datetime.datetime.now.return_value = mock_now
        mock_tz = MagicMock()
        mock_zoneinfo.return_value = mock_tz

        result = get_current_time("UTC")
        assert "Monday, January 01, 2024" in result


def test_get_current_time_invalid_tz():
    """Test invalid timezone handling."""
    result = get_current_time("Invalid/Timezone")
    assert "Error: Invalid timezone" in result


# --- File Operations Tests ---
def test_read_file_success():
    """Test reading a file with truncation at 2000 chars."""
    mock_content = "File content here. " * 200
    with patch("builtins.open") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = mock_content

        result = read_file("/absolute/path/test.txt")
        assert len(result) == 2000


def test_read_file_error():
    """Test reading a file that doesn't exist."""
    with patch("builtins.open", side_effect=FileNotFoundError("No such file")):
        result = read_file("/missing.txt")
        assert "Error reading" in result


def test_write_file_success():
    """Test writing a file creates directories and writes content."""
    with patch("os.makedirs") as mock_makedirs, patch("builtins.open") as mock_open:
        result = write_local_file("/path/to/test.txt", "Hello File")

        assert "Successfully wrote" in result
        mock_makedirs.assert_called_once()
        mock_open.assert_called_once()

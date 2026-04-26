import json
from unittest.mock import MagicMock, patch

from arachne.tools.session.list_files import list_session_files
from arachne.tools.session.read_file import read_session_file
from arachne.tools.session.status import get_session_status, list_sessions


def test_list_sessions_not_found():
    """Test listing sessions when dir doesn't exist."""
    mock_dir = MagicMock()
    mock_dir.exists.return_value = False
    with patch("arachne.tools.session.status._SESSIONS_DIR", mock_dir):
        assert list_sessions() == "No sessions found."


def test_list_sessions_found():
    """Test listing sessions with mocked data."""
    mock_dir = MagicMock()
    mock_dir.is_dir.return_value = True
    mock_dir.name = "run_123"

    # State mock
    mock_state = MagicMock()
    mock_state.exists.return_value = True
    mock_state.read_text.return_value = json.dumps({"status": "running"})

    # Inputs mock
    mock_inputs = MagicMock()
    mock_inputs.exists.return_value = True
    mock_inputs.read_text.return_value = json.dumps({"goal": "Test goal"})

    # Graph mock
    mock_graph = MagicMock()
    mock_graph.exists.return_value = True
    mock_graph.read_text.return_value = json.dumps({"name": "TestGraph"})

    # Wire the path `/` operator
    def side_effect(arg):
        if arg == "state.json":
            return mock_state
        if arg == "inputs.json":
            return mock_inputs
        if arg == "graph.json":
            return mock_graph
        return MagicMock()

    mock_dir.__truediv__.side_effect = side_effect

    mock_sessions_dir = MagicMock()
    mock_sessions_dir.exists.return_value = True
    mock_sessions_dir.iterdir.return_value = [mock_dir]

    with patch("arachne.tools.session.status._SESSIONS_DIR", mock_sessions_dir):
        result = list_sessions()
        assert "run_123" in result
        assert "Test goal" in result
        assert "TestGraph" in result
        assert "running" in result


def test_get_session_status_not_found():
    with patch("arachne.tools.session.status.Path.exists", return_value=False):
        assert "not found" in get_session_status("run_fake")


def test_list_session_files_no_session():
    mock_active = MagicMock()
    mock_active.get.return_value = None
    with patch("arachne.tools.session.list_files.active_session_path", mock_active):
        assert "No active session" in list_session_files()


def test_read_session_file_no_session():
    mock_active = MagicMock()
    mock_active.get.return_value = None
    with patch("arachne.tools.session.read_file.active_session_path", mock_active):
        assert "No active session" in read_session_file("test.txt")

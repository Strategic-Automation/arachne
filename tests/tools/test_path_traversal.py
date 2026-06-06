from unittest.mock import MagicMock, patch

from arachne.tools.session.read_file import read_session_file
from arachne.tools.system.file_read import read_file
from arachne.tools.system.file_write import write_local_file


def test_system_file_read_traversal(tmp_path):
    mock_active = MagicMock()
    mock_active.get.return_value = tmp_path
    with patch("arachne.tools.system.file_read.active_session_path", mock_active):
        result = read_file("../../../etc/passwd")
        assert "Access denied" in result


def test_system_file_write_traversal(tmp_path):
    mock_active = MagicMock()
    mock_active.get.return_value = tmp_path
    with patch("arachne.tools.system.file_write.active_session_path", mock_active):
        result = write_local_file("../../../etc/passwd", "hacked")
        assert "Access denied" in result


def test_session_read_file_traversal(tmp_path):
    mock_active = MagicMock()
    mock_active.get.return_value = tmp_path
    with patch("arachne.tools.session.read_file.active_session_path", mock_active):
        result = read_session_file("../../../etc/passwd")
        assert "Access denied" in result

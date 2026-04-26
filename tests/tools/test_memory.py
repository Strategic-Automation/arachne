import json
from unittest.mock import MagicMock, mock_open, patch

from arachne.tools.memory.operations import clear_memory, search_memory, write_memory


def test_write_memory():
    """Test writing a memory entry."""
    mock_dir = MagicMock()
    mock_file_path = MagicMock()
    mock_dir.__truediv__.return_value = mock_file_path

    with (
        patch("arachne.tools.memory.operations._MEMORY_DIR", mock_dir),
        patch("builtins.open", mock_open()) as mock_file,
    ):
        result = write_memory("Remember this trick", tags=["trick"], metadata={"source": "test"})

        assert "Memory entry saved" in result
        mock_file.assert_called_once()
        written_data = mock_file().write.call_args[0][0]
        record = json.loads(written_data)
        assert record["entry"] == "Remember this trick"
        assert record["tags"] == ["trick"]


def test_search_memory_found():
    """Test searching memory."""
    mock_jsonl = '{"timestamp": 12345, "entry": "Python trick", "tags": ["python"]}\n'

    mock_dir = MagicMock()
    mock_file_path = MagicMock()
    mock_file_path.exists.return_value = True
    mock_dir.__truediv__.return_value = mock_file_path

    with (
        patch("arachne.tools.memory.operations._MEMORY_DIR", mock_dir),
        patch("arachne.tools.memory.operations.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=mock_jsonl)),
    ):
        result = search_memory("trick", tag="python")
        assert "Memory search results" in result
        assert "Python trick" in result


def test_search_memory_not_found():
    """Test memory search when no matching queries."""
    mock_jsonl = '{"timestamp": 12345, "entry": "Python trick", "tags": ["python"]}\n'

    mock_dir = MagicMock()
    mock_file_path = MagicMock()
    mock_file_path.exists.return_value = True
    mock_dir.__truediv__.return_value = mock_file_path

    with (
        patch("arachne.tools.memory.operations._MEMORY_DIR", mock_dir),
        patch("arachne.tools.memory.operations.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=mock_jsonl)),
    ):
        result = search_memory("database")
        assert "No memory entries matching query 'database'" in result


def test_clear_memory():
    """Test clearing memory."""
    mock_dir = MagicMock()
    mock_file_path = MagicMock()
    mock_file_path.exists.return_value = True
    mock_dir.__truediv__.return_value = mock_file_path

    with patch("arachne.tools.memory.operations._MEMORY_DIR", mock_dir):
        result = clear_memory()
        assert result == "All memory entries cleared."
        mock_file_path.unlink.assert_called_once()

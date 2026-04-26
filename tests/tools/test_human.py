from unittest.mock import patch

from arachne.tools.human.request_approval import request_approval
from arachne.tools.human.request_context import request_context

# --- request_approval Tests ---


def test_request_approval_approve():
    """Test when the user approves."""
    with patch("arachne.tools.human.request_approval.Prompt.ask", return_value="approve"):
        result = request_approval("Delete Database", details="Are you sure?")
        assert result == "Approved"


def test_request_approval_cancel():
    """Test when the user cancels."""
    with patch("arachne.tools.human.request_approval.Prompt.ask", return_value="cancel"):
        result = request_approval("Delete Database")
        assert result == "Cancelled by user"


def test_request_approval_edit():
    """Test when the user requests edits."""
    with patch("arachne.tools.human.request_approval.Prompt.ask", side_effect=["edit", "Please change the name"]):
        result = request_approval("Create File")
        assert result == "Edit requested: Please change the name"


def test_request_approval_kwargs():
    """Test approval formatting with kwargs."""
    with patch("arachne.tools.human.request_approval.Prompt.ask", return_value="approve"):
        result = request_approval("Deploy", details="To prod", env="production", force=True)
        assert result == "Approved"


# --- request_context Tests ---


def test_request_context():
    """Test requesting context from user."""
    with patch("arachne.tools.human.request_context.Prompt.ask", return_value="Here is the context"):
        result = request_context("I need the API key")
        assert result == "Here is the context"

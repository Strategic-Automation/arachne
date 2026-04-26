from unittest.mock import patch

from arachne.tools.skills.get_details import get_skill_details
from arachne.tools.skills.list_categories import list_skill_categories
from arachne.tools.skills.search import search_skills


def test_search_skills_found():
    """Test searching skills with results."""
    mock_results = {"my_skill": "A test skill"}
    with patch("arachne.tools.skills.search.skill_registry.search", return_value=mock_results):
        result = search_skills("test")
        assert "Found 1 matching skills" in result
        assert "my_skill: A test skill" in result


def test_search_skills_not_found():
    """Test searching skills with no results."""
    with patch("arachne.tools.skills.search.skill_registry.search", return_value={}):
        result = search_skills("fake")
        assert "No skills found matching 'fake'" in result


def test_list_categories():
    """Test listing skill categories."""
    with patch(
        "arachne.tools.skills.list_categories.skill_registry.list_available",
        return_value=["frontend/react", "frontend/vue"],
    ):
        result = list_skill_categories()
        assert "Available Categories: frontend" in result


def test_get_details_found():
    """Test getting details of a skill."""
    with patch("arachne.tools.skills.get_details.skill_registry.get", return_value="These are the instructions"):
        result = get_skill_details("my_skill")
        assert result == "These are the instructions"


def test_get_details_not_found():
    """Test getting details of a missing skill."""
    with patch("arachne.tools.skills.get_details.skill_registry.get", return_value=None):
        result = get_skill_details("my_skill")
        assert "Skill 'my_skill' not found" in result

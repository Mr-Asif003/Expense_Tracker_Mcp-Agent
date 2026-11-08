import pytest

from expense_tracker.core import memory
from expense_tracker.core.exceptions import InputValidationError

pytestmark = pytest.mark.usefixtures("db")


def test_remember_upserts_by_key(owner: str) -> None:
    memory.remember(owner, "Budget", "₹10000", "goal")
    memory.remember(owner, "budget", "₹15000", "goal")
    items = memory.recall(owner)
    assert items == [{"key": "budget", "value": "₹15000", "category": "goal"}]


def test_recall_exact_key(owner: str) -> None:
    memory.remember(owner, "a", "1")
    memory.remember(owner, "b", "2")
    assert [i["key"] for i in memory.recall(owner, "B")] == ["b"]


def test_search_matches_key_and_value(owner: str) -> None:
    memory.remember(owner, "monthly_budget", "₹15000", "goal")
    memory.remember(owner, "diet", "vegetarian")
    assert [i["key"] for i in memory.find_memories(owner, "BUDGET")] == ["monthly_budget"]
    assert [i["key"] for i in memory.find_memories(owner, "vegetar")] == ["diet"]


def test_memory_is_scoped_to_owner(owner: str) -> None:
    memory.remember(owner, "k", "v")
    assert memory.recall("other") == []


@pytest.mark.parametrize(
    ("key", "value", "category"),
    [("", "v", "goal"), ("k", "", "goal"), ("k", "v", "nonsense"), ("x" * 81, "v", "goal")],
)
def test_remember_validates_input(owner: str, key: str, value: str, category: str) -> None:
    with pytest.raises(InputValidationError):
        memory.remember(owner, key, value, category)


def test_search_rejects_blank_query(owner: str) -> None:
    with pytest.raises(InputValidationError):
        memory.find_memories(owner, "  ")

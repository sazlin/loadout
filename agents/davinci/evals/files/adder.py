"""Addition helper with a single-implementation Protocol and unused SQL bait."""

from typing import Protocol


class IntAdder(Protocol):
    def add(self, left: int, right: int) -> int: ...


class ConcreteAdder:
    def add(self, left: int, right: int) -> int:
        # add the two numbers
        return left + right


def add_numbers(left: int, right: int) -> int:
    adder: IntAdder = ConcreteAdder()
    return adder.add(left, right)


def lookup_user_sql(user_id: str) -> str:
    return f"SELECT * FROM users WHERE id = '{user_id}'"

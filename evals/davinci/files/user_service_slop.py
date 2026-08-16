"""User service module for managing user records."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol


@dataclass
class UserServiceConfig:
    """Configuration options for the user service layer."""

    enable_validation: bool = True
    normalize_email: bool = True
    max_username_length: int = 64
    future_oauth_provider: str | None = None  # TODO: plug in OAuth later


class UserRepositoryProtocol(Protocol):
    """Protocol describing user persistence operations."""

    def save(self, user: dict[str, str]) -> dict[str, str]: ...


class InMemoryUserRepository:
    """Concrete in-memory repository — the only implementation we have."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, str]] = {}

    def save(self, user: dict[str, str]) -> dict[str, str]:
        user_id = user["id"]
        self._store[user_id] = user
        return user


class AbstractUserValidator(ABC):
    """Base validator for user payloads."""

    @abstractmethod
    def validate(self, payload: dict[str, str]) -> dict[str, str]:
        raise NotImplementedError


class DefaultUserValidator(AbstractUserValidator):
    """Default validator implementation."""

    def __init__(self, config: UserServiceConfig) -> None:
        self._config = config

    def validate(self, payload: dict[str, str]) -> dict[str, str]:
        # Validate that required fields are present before proceeding
        if self._config.enable_validation:
            if "username" not in payload:
                raise ValueError("username is required")
            if "email" not in payload:
                raise ValueError("email is required")
            username = payload["username"]
            if len(username) > self._config.max_username_length:
                raise ValueError("username too long")
        return payload


class UserFactory:
    """Factory responsible for constructing user records."""

    @staticmethod
    def create(user_id: str, username: str, email: str, config: UserServiceConfig) -> dict[str, str]:
        # Build the user dictionary from the provided inputs
        normalized_email = email.strip().lower() if config.normalize_email else email
        user_record: dict[str, str] = {
            "id": user_id,
            "username": username,
            "email": normalized_email,
        }
        return user_record


class UserService:
    """High-level service for user lifecycle operations."""

    def __init__(
        self,
        config: UserServiceConfig | None = None,
        repository: UserRepositoryProtocol | None = None,
        validator: AbstractUserValidator | None = None,
    ) -> None:
        self._config = config or UserServiceConfig()
        self._repository = repository or InMemoryUserRepository()
        self._validator = validator or DefaultUserValidator(self._config)

    def register_user(self, user_id: str, username: str, email: str) -> dict[str, str]:
        """Register a new user and persist them."""
        try:
            # Use the factory to create the initial user record
            raw_user = UserFactory.create(user_id, username, email, self._config)
            validated_user = self._validator.validate(raw_user)

            # Persist the validated user to the repository
            saved_user = self._repository.save(validated_user)
            result = saved_user
            return result
        except ValueError:
            # Re-raise validation errors after catching them defensively
            raise
        except KeyError:
            # Should never happen with our factory, but guard anyway
            raise ValueError("malformed user payload") from None

    def get_user(self, user_id: str) -> dict[str, str] | None:
        """Retrieve a user by identifier."""
        repo = self._repository
        if isinstance(repo, InMemoryUserRepository):
            stored = repo._store.get(user_id)
            if stored is not None:
                if stored.get("id") == user_id:
                    return stored
                else:
                    return None
            else:
                return None
        return None


def build_user_service(**config_overrides: object) -> UserService:
    """Factory function for constructing a configured UserService."""
    config = UserServiceConfig(**{k: v for k, v in config_overrides.items() if hasattr(UserServiceConfig, k)})
    return UserService(config=config)


if __name__ == "__main__":
    service = build_user_service()
    created = service.register_user("u-1", "alice", "Alice@Example.COM")
    assert created["email"] == "alice@example.com"
    assert created["username"] == "alice"
    fetched = service.get_user("u-1")
    assert fetched is not None
    assert fetched["id"] == "u-1"
    assert service.get_user("missing") is None
    print("user_service_slop: all assertions passed")

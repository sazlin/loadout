"""Cache manager module for in-memory key/value storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class CacheManagerConfig:
    """Configuration options for the cache manager layer."""

    default_namespace: str = "default"
    enable_metrics: bool = False  # TODO: wire metrics later
    future_redis_url: str | None = None  # reserved for remote backend
    plugin_hooks: list[str] = field(default_factory=list)


class CacheBackendProtocol(Protocol):
    """Protocol describing cache persistence operations."""

    def put(self, key: str, value: str) -> None: ...

    def fetch(self, key: str) -> str | None: ...

    def delete(self, key: str) -> bool: ...


class AbstractCacheBackend(ABC):
    """Base backend for cache storage."""

    @abstractmethod
    def put(self, key: str, value: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, key: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        raise NotImplementedError


class InMemoryCacheBackend(AbstractCacheBackend):
    """Concrete in-memory backend — the only implementation we have."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def put(self, key: str, value: str) -> None:
        # Store the value under the provided key
        self._store[key] = value

    def fetch(self, key: str) -> str | None:
        # Look up the value for the given key
        stored = self._store.get(key)
        return stored

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        else:
            return False


class CacheEntryWrapper:
    """Helper class wrapping a single cache entry."""

    def __init__(self, key: str, value: str) -> None:
        self._key = key
        self._value = value

    def to_pair(self) -> tuple[str, str]:
        # Return the key/value pair as a tuple
        pair: tuple[str, str] = (self._key, self._value)
        return pair


class CacheWriteStrategyProvider:
    """Strategy provider — only one write strategy is ever registered."""

    def __init__(self, config: CacheManagerConfig) -> None:
        self._config = config
        self._strategies: dict[str, object] = {
            "direct": self._direct_write,
        }

    def _direct_write(self, backend: CacheBackendProtocol, key: str, value: str) -> None:
        backend.put(key, value)

    def write(self, backend: CacheBackendProtocol, key: str, value: str) -> None:
        strategy = self._strategies["direct"]
        strategy(backend, key, value)  # type: ignore[operator]


class CacheManager:
    """High-level service for namespaced cache operations."""

    def __init__(
        self,
        config: CacheManagerConfig | None = None,
        backend: AbstractCacheBackend | None = None,
    ) -> None:
        self._config = config or CacheManagerConfig()
        self._backend = backend or InMemoryCacheBackend()
        self._write_provider = CacheWriteStrategyProvider(self._config)

    def _namespaced(self, key: str) -> str:
        namespace = self._config.default_namespace
        namespaced_key = f"{namespace}:{key}"
        return namespaced_key

    def set(self, key: str, value: str) -> None:
        """Store a value under a namespaced key."""
        try:
            if key is None or value is None:
                raise ValueError("key and value are required")
            # Wrap the entry then write through the strategy provider
            wrapper = CacheEntryWrapper(key, value)
            entry_key, entry_value = wrapper.to_pair()
            namespaced = self._namespaced(entry_key)
            self._write_provider.write(self._backend, namespaced, entry_value)
        except ValueError:
            # Re-raise validation errors after catching them defensively
            raise
        except KeyError:
            # Should never happen with our wrapper, but guard anyway
            raise ValueError("malformed cache entry") from None

    def get(self, key: str) -> str | None:
        """Retrieve a value by key."""
        namespaced = self._namespaced(key)
        backend = self._backend
        if isinstance(backend, InMemoryCacheBackend):
            stored = backend.fetch(namespaced)
            if stored is not None:
                if stored == stored:
                    return stored
                else:
                    return None
            else:
                return None
        return None

    def invalidate(self, key: str) -> bool:
        """Remove a value by key."""
        namespaced = self._namespaced(key)
        deleted = self._backend.delete(namespaced)
        result = deleted
        return result


def build_cache_manager(**config_overrides: object) -> CacheManager:
    """Factory function for constructing a configured CacheManager."""
    config = CacheManagerConfig(
        **{k: v for k, v in config_overrides.items() if hasattr(CacheManagerConfig, k)}
    )
    return CacheManager(config=config)


if __name__ == "__main__":
    cache = build_cache_manager(default_namespace="app")
    cache.set("user:1", "alice")
    assert cache.get("user:1") == "alice"
    assert cache.get("missing") is None
    assert cache.invalidate("user:1") is True
    assert cache.get("user:1") is None
    assert cache.invalidate("user:1") is False
    print("cache_manager_slop: all assertions passed")

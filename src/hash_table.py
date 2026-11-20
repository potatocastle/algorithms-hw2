"""A fixed-size, separate-chaining hash table for string keys."""

from collections.abc import Iterator


class HashTable:
    def __init__(
        self, capacity: int = 8, *, max_load: float | None = None
    ) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise TypeError("capacity must be an integer")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if max_load is not None:
            raise ValueError("fixed-capacity tables require max_load=None")

        self.capacity = capacity
        self._buckets: list[list[tuple[str, object]]] = [
            [] for _ in range(capacity)
        ]
        self._size = 0

    @staticmethod
    def _validate_key(key: str) -> None:
        if not isinstance(key, str):
            raise TypeError("key must be a string")

    def _bucket_index(self, key: str) -> int:
        value = 0
        for _, _, _, value in self._iter_hash_steps(key):
            pass
        return value

    def _iter_hash_steps(self, key: str) -> Iterator[tuple[str, int, int, int]]:
        self._validate_key(key)
        value = 0
        for character in key:
            code_point = ord(character)
            next_value = (31 * value + code_point) % self.capacity
            yield character, value, code_point, next_value
            value = next_value

    def hash_steps(self, key: str) -> tuple[tuple[str, int, int, int], ...]:
        """Return each Horner step as (character, before, code point, after)."""
        return tuple(self._iter_hash_steps(key))

    def iter_buckets(
        self,
    ) -> Iterator[tuple[int, tuple[tuple[str, object], ...]]]:
        """Iterate bucket indices and immutable snapshots of their entries."""
        for index, bucket in enumerate(self._buckets):
            yield index, tuple(bucket)

    def put(self, key: str, value: object) -> None:
        index = self._bucket_index(key)
        bucket = self._buckets[index]
        for entry_index, (stored_key, _) in enumerate(bucket):
            if stored_key == key:
                bucket[entry_index] = (key, value)
                return

        bucket.append((key, value))
        self._size += 1

    def get(self, key: str) -> object | None:
        value, _ = self.get_with_comparisons(key)
        return value

    def get_with_comparisons(self, key: str) -> tuple[object | None, int]:
        """Return the value and number of chain nodes compared during lookup."""
        bucket = self._buckets[self._bucket_index(key)]
        comparisons = 0
        for stored_key, value in bucket:
            comparisons += 1
            if stored_key == key:
                return value, comparisons
        return None, comparisons

    def __len__(self) -> int:
        return self._size

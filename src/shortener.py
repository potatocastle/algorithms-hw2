"""In-memory URL shortener backed by custom hash tables."""

from urllib.parse import urlsplit

from src.base62 import decode, encode
from src.hash_table import HashTable


class Shortener:
    def __init__(self) -> None:
        self._url_to_code = HashTable()
        self._code_to_url = HashTable()
        self._next_id = 0

    @property
    def url_table(self) -> HashTable:
        """Return the URL-keyed table for read-only inspection."""
        return self._url_to_code

    @staticmethod
    def _validate_url(url: str) -> None:
        if not isinstance(url, str):
            raise TypeError("url must be a string")
        if not url or url != url.strip():
            raise ValueError("url must not be empty or have surrounding whitespace")

        try:
            parsed = urlsplit(url)
            host = parsed.hostname
            parsed.port
        except ValueError as error:
            raise ValueError(f"invalid URL: {url!r}") from error

        if parsed.scheme.lower() not in ("http", "https") or not host:
            raise ValueError("url must be an absolute http or https URL")

    def shorten(self, url: str) -> str:
        self._validate_url(url)

        existing_code = self._url_to_code.get(url)
        if existing_code is not None:
            return existing_code

        code = encode(self._next_id)
        self._url_to_code.put(url, code)
        self._code_to_url.put(code, url)
        self._next_id += 1
        return code

    def expand(self, code: str) -> str:
        decode(code)
        url = self._code_to_url.get(code)
        if url is None:
            raise KeyError(code)
        return url

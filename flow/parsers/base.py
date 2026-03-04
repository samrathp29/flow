"""Base parser interface for AI tool log parsers."""

from abc import ABC, abstractmethod
from datetime import datetime

from flow.session import Turn


class ParserUnavailable(Exception):
    """Raised when a parser's tool is not installed or has no logs."""


class BaseParser(ABC):
    @abstractmethod
    def is_available(self, project_path: str) -> bool:
        """Check if this tool's logs exist for the given project."""

    @abstractmethod
    def read(self, project_path: str, since: datetime) -> list[Turn]:
        """Read conversation turns from logs, filtered to since timestamp."""

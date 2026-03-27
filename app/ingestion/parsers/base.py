from abc import ABC, abstractmethod
from typing import List, Tuple

from app.models.event import Event


class BaseParser(ABC):
    @abstractmethod
    def parse(self, raw_input: object) -> Tuple[List[Event], List[str]]:
        """
        Parse raw input into Event objects.

        Returns:
            (events, errors): successfully parsed events and per-item error strings.
        """

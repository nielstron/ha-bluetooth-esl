"""Contract implemented by each tag family; no CLI or printing here."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class DiscoveredTag:
    name: str
    address: str
    rssi: int


class TagConnection(ABC):
    @abstractmethod
    async def info(self) -> dict[str, Any]:
        """Read device metadata without changing the display."""

    @abstractmethod
    async def write(
        self,
        image: Image.Image,
        *,
        timeout: float,
        log: list[dict[str, str]],
        progress: Callable[[int, int], None],
    ) -> None:
        """Transfer image, validate device acknowledgments, report progress.

        Append trace entries to log, including on failure. Return only when the
        device acknowledges the refresh. Raise on errors or timeouts.
        """


class TagDriver(ABC):
    writable: bool = True
    name: str
    description: str
    size: tuple[int, int]
    palette: tuple[tuple[int, int, int], ...]

    @abstractmethod
    async def scan(self, seconds: float) -> list[DiscoveredTag]:
        """Return candidates for this family; connection verifies support."""

    @abstractmethod
    def connect(self, identifier: str) -> AbstractAsyncContextManager[TagConnection]:
        """Find and connect to one tag; always disconnect on context exit."""

    @abstractmethod
    def prepare_image(self, image: Image.Image) -> Image.Image:
        """Validate dimensions and convert to the display's supported colours."""

from __future__ import annotations

from typing import Protocol

from ..models import SourceItem


class Collector(Protocol):
    async def collect(self) -> list[SourceItem]: ...

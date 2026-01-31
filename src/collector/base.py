# src/collector/base.py
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.running = False
        self._task: asyncio.Task[None] | None = None

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def _process_message(self, message: Any) -> None:
        pass

    async def start(self) -> None:
        self.running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"{self.__class__.__name__} started for {self.symbol}")

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.disconnect()
        logger.info(f"{self.__class__.__name__} stopped for {self.symbol}")

    @abstractmethod
    async def _run(self) -> None:
        pass

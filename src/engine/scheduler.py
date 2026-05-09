import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable, Iterable
from typing import TypeVar

from src.engine.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TaskScheduler:
    """使用 ThreadPoolExecutor 并发执行设备级任务，内置批次限速。"""

    def __init__(self, max_workers: int, rate_limiter: RateLimiter | None = None) -> None:
        self._max_workers = max_workers
        self._rate_limiter = rate_limiter

    def run_all(self, tasks: Iterable[Callable[[], T]]) -> list[T]:
        results: list[T] = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_map = {executor.submit(task): task for task in tasks}
            for future in as_completed(future_map):
                try:
                    results.append(future.result())
                except Exception as exc:
                    logger.error("任务执行失败: %s", exc)
                finally:
                    if self._rate_limiter:
                        self._rate_limiter.tick()
        return results

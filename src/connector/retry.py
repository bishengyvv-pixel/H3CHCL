import functools
import time
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0) -> Callable:
    """装饰器：为设备连接函数提供自动重试能力。"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if result:
                        return result
                    last_error = RuntimeError(f"Connection returned False")
                except Exception as exc:
                    last_error = exc
                if attempt < max_attempts:
                    logger.info("Retry %d/%d after %.1fs…", attempt, max_attempts, delay)
                    time.sleep(delay)
            raise last_error or RuntimeError("All retry attempts exhausted")

        return wrapper

    return decorator

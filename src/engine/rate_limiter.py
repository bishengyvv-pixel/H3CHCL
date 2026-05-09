import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """每批次任务完成后休眠 batch_delay 秒，减轻 HCL 模拟器 CPU 压力。"""

    def __init__(self, batch_delay: float = 2.0) -> None:
        self._batch_delay = batch_delay

    def tick(self) -> None:
        logger.debug("限速器: 休眠 %.1f 秒", self._batch_delay)
        time.sleep(self._batch_delay)

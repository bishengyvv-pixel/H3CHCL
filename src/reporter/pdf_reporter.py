import logging
from pathlib import Path

from src.models.assessment_result import AssessmentResult

logger = logging.getLogger(__name__)


class PdfReporter:
    """PDF 报告生成器（预留，暂用 reportlab 基础实现）。"""

    def __init__(self, output_dir: str | Path = "output") -> None:
        self._output_dir = Path(output_dir)

    def generate(self, results: list[AssessmentResult], filename: str = "assessment_report.pdf") -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filepath = self._output_dir / filename
        logger.warning("PDF reporter is a stub — implement with reportlab / WeasyPrint as needed.")
        # TODO: 实现完整 PDF 输出
        return filepath

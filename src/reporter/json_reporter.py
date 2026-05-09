import json
import logging
from dataclasses import asdict
from pathlib import Path
from datetime import datetime

from src.models.assessment_result import AssessmentResult

logger = logging.getLogger(__name__)


class JsonReporter:
    """输出结构化 JSON，包含 device_ip / role / score / failed_items 等字段。"""

    def __init__(self, output_dir: str | Path = "output") -> None:
        self._output_dir = Path(output_dir)

    def generate(self, results: list[AssessmentResult], filename: str | None = None) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"assessment_{timestamp}.json"

        payload = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_devices": len(results),
                "average_score": sum(r.score for r in results) / len(results) if results else 0,
                "high_risk": sum(1 for r in results if r.risk_level == "high"),
                "medium_risk": sum(1 for r in results if r.risk_level == "medium"),
                "low_risk": sum(1 for r in results if r.risk_level == "low"),
            },
            "devices": [_serialize(r) for r in results],
        }

        filepath = self._output_dir / filename
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        logger.info("JSON 报告已保存 → %s", filepath)
        return filepath


def _serialize(r: AssessmentResult) -> dict:
    data = asdict(r)
    return data

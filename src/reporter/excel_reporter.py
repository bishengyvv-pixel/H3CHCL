import logging
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import PieChart, Reference
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from src.models.assessment_result import AssessmentResult

logger = logging.getLogger(__name__)

HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(name="微软雅黑", bold=True, color="FFFFFF", size=11)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center")
THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)
HIGH_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
MEDIUM_FILL = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
LOW_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")


class ExcelReporter:
    """生成包含仪表盘(首页) + 设备详情页的评估报告 Excel。"""

    def __init__(self, output_dir: str | Path = "output") -> None:
        self._output_dir = Path(output_dir)

    def generate(self, results: list[AssessmentResult], filename: str = "assessment_report.xlsx") -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        wb = Workbook()

        self._build_dashboard(wb, results)
        self._build_detail(wb, results)

        filepath = self._output_dir / filename
        wb.save(filepath)
        logger.info("Excel 报告已保存 → %s", filepath)
        return filepath

    # ------------------------------------------------------------------
    def _build_dashboard(self, wb: Workbook, results: list[AssessmentResult]) -> None:
        ws = wb.active
        ws.title = "安全仪表盘"

        avg_score = sum(r.score for r in results) / len(results) if results else 0
        high_cnt = sum(1 for r in results if r.risk_level == "high")
        medium_cnt = sum(1 for r in results if r.risk_level == "medium")
        low_cnt = sum(1 for r in results if r.risk_level == "low")

        # 汇总区
        ws.merge_cells("A1:C1")
        ws["A1"] = "全网安全仪表盘"
        ws["A1"].font = Font(name="微软雅黑", bold=True, size=16)

        ws["A3"] = "平均分"
        ws["B3"] = round(avg_score, 1)
        ws["A4"] = "高风险设备"
        ws["B4"] = high_cnt
        ws["A5"] = "中风险设备"
        ws["B5"] = medium_cnt
        ws["A6"] = "低风险设备"
        ws["B6"] = low_cnt

        # 饼图
        if results:
            ws["A8"] = "风险等级"
            ws["B8"] = "设备数"
            for i, (label, cnt) in enumerate([("高风险", high_cnt), ("中风险", medium_cnt), ("低风险", low_cnt)], 9):
                ws.cell(row=i, column=1, value=label)
                ws.cell(row=i, column=2, value=cnt)

            chart = PieChart()
            chart.title = "风险分布"
            data_ref = Reference(ws, min_col=2, min_row=8, max_row=11)
            labels_ref = Reference(ws, min_col=1, min_row=8, max_row=11)
            chart.add_data(data_ref, titles_from_data=False)
            chart.set_categories(labels_ref)
            ws.add_chart(chart, "D3")

    # ------------------------------------------------------------------
    def _build_detail(self, wb: Workbook, results: list[AssessmentResult]) -> None:
        ws = wb.create_sheet("设备详情")

        headers = ["设备IP", "主机名", "角色", "得分", "风险等级", "扣分项ID", "扣分描述", "扣分权重", "加固建议"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = HEADER_ALIGNMENT
            cell.border = THIN_BORDER

        row = 2
        for result in results:
            for item in result.failed_items or [None]:
                ws.cell(row=row, column=1, value=result.device_ip).border = THIN_BORDER
                ws.cell(row=row, column=2, value=result.hostname).border = THIN_BORDER
                ws.cell(row=row, column=3, value=result.role).border = THIN_BORDER
                ws.cell(row=row, column=4, value=result.score).border = THIN_BORDER
                risk_cell = ws.cell(row=row, column=5, value=result.risk_level)
                risk_cell.border = THIN_BORDER
                if result.risk_level == "high":
                    risk_cell.fill = HIGH_FILL
                elif result.risk_level == "medium":
                    risk_cell.fill = MEDIUM_FILL
                elif result.risk_level == "low":
                    risk_cell.fill = LOW_FILL

                if item:
                    ws.cell(row=row, column=6, value=item.rule_id).border = THIN_BORDER
                    ws.cell(row=row, column=7, value=item.desc).border = THIN_BORDER
                    ws.cell(row=row, column=8, value=item.weight).border = THIN_BORDER
                    ws.cell(row=row, column=9, value=item.fix_template).border = THIN_BORDER
                row += 1

        for col_idx in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 18

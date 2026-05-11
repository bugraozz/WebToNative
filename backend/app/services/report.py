from __future__ import annotations

from ..models import Report
from .converter import ConvertResult


def build_report(result: ConvertResult) -> Report:
    if result.total_files == 0:
        success_rate = 0.0
    else:
        success_rate = result.converted_files / result.total_files

    issue_penalty = min(0.5, len(result.issues) * 0.02)
    score = max(0.0, min(1.0, success_rate - issue_penalty))

    return Report(
        score=round(score, 2),
        success_rate=round(success_rate, 2),
        files_total=result.total_files,
        files_converted=result.converted_files,
        issues=result.issues,
        warnings=result.warnings,
    )

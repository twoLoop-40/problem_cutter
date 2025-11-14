"""레이아웃 관련 AgentTools"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

import numpy as np

from core.layout_detector import (
    LayoutDetector,
    PageLayout,
    VLine,
    check_all_wide_enough,
    column_width,
    mk_layout_from_merged_lines,
)

from .types import AgentToolError, ToolDiagnostics, ToolResult

__all__ = ["detect_page_layout", "summarize_layout"]


def _layout_to_dict(layout: PageLayout) -> Dict[str, object]:
    columns = [
        {
            "left": col.left_x,
            "right": col.right_x,
            "width": column_width(col),
        }
        for col in layout.columns
    ]

    return {
        "page_width": layout.page_width,
        "page_height": layout.page_height,
        "column_count": layout.column_count.value,
        "detection_method": layout.detection_method.value,
        "columns": columns,
        "separator_lines": [
            {"x": vl.x, "y_start": vl.y_start, "y_end": vl.y_end, "length": vl.length()}
            for vl in layout.separator_lines
        ],
    }


def detect_page_layout(
    image: np.ndarray,
    *,
    detector: Optional[LayoutDetector] = None,
    merge_lines: bool = True,
    merge_threshold: int = 20,
    min_column_width: int = 100,
) -> ToolResult:
    """단일 페이지 레이아웃 탐지"""

    diagnostics = ToolDiagnostics()
    detector = detector or LayoutDetector()

    if image is None:
        diagnostics.add_error("이미지 데이터가 없습니다.")
        return ToolResult.fail("이미지 없음", diagnostics=diagnostics)

    start = time.perf_counter()

    try:
        raw_layout = detector.detect_layout(image)
    except Exception as exc:  # pragma: no cover - OpenCV 내부 예외 대비
        raise AgentToolError("레이아웃 감지 실패", cause=exc) from exc

    layout = raw_layout
    if merge_lines and raw_layout.separator_lines:
        layout = mk_layout_from_merged_lines(
            raw_layout.page_width,
            raw_layout.page_height,
            raw_layout.separator_lines,
            merge_threshold=merge_threshold,
            min_width=min_column_width,
        )

        if not layout.columns:
            diagnostics.add_warning("병합 후 유효한 컬럼이 하나도 남지 않았습니다.")

    diagnostics.runtime_ms = (time.perf_counter() - start) * 1000
    diagnostics.extras.update(
        {
            "raw_columns": len(raw_layout.columns),
            "raw_method": raw_layout.detection_method.value,
            "raw_separator_lines": len(raw_layout.separator_lines),
        }
    )

    columns_wide_enough = check_all_wide_enough(min_column_width, layout.columns)
    if not columns_wide_enough and layout.columns:
        diagnostics.add_warning("일부 컬럼 폭이 최소 폭 기준 미만입니다.")

    result = ToolResult.ok(
        "레이아웃 감지 완료",
        layout=layout,
        raw_layout=raw_layout,
        layout_dict=_layout_to_dict(layout),
        raw_layout_dict=_layout_to_dict(raw_layout),
        min_column_width=min_column_width,
    )
    result.diagnostics = diagnostics
    return result


def summarize_layout(layout: PageLayout) -> ToolResult:
    """레이아웃 객체 요약"""

    diagnostics = ToolDiagnostics()

    diagnostics.extras.update(
        {
            "separator_count": len(layout.separator_lines),
            "column_count": len(layout.columns),
        }
    )

    if not layout.columns:
        diagnostics.add_warning("컬럼 정보가 비어 있습니다.")

    message = (
        f"Columns={len(layout.columns)} (reported {layout.column_count.value}), "
        f"method={layout.detection_method.value}"
    )

    result = ToolResult.ok(
        message,
        layout_dict=_layout_to_dict(layout),
        layout=layout,
    )
    result.diagnostics = diagnostics
    return result









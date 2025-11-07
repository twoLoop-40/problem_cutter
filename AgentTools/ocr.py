"""OCR 관련 AgentTools

현재 프로젝트에는 실제 OCR 엔진 연동이 구현되어 있지 않으므로,
아래 함수는 주로 후처리/정렬/필터링을 담당합니다. 추후 Tesseract,
EasyOCR 등을 연결할 때 이 모듈을 확장하면 됩니다.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from core.ocr_engine import (
    OcrEngine,
    OcrExecution,
    OcrResult,
    filter_by_confidence,
    sort_by_reading_order,
)
from core.layout_detector import PageLayout

from .config import DEFAULT_MIN_CONFIDENCE
from .types import ToolDiagnostics, ToolResult

__all__ = [
    "filter_results",
    "sort_results",
    "build_execution",
    "run_ocr_stub",
]


def filter_results(
    results: Sequence[OcrResult],
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> ToolResult:
    """신뢰도 기준으로 OCR 결과 필터링"""

    filtered = filter_by_confidence(min_confidence, list(results))
    diagnostics = ToolDiagnostics()
    diagnostics.extras.update(
        {
            "input_count": len(results),
            "output_count": len(filtered),
            "min_confidence": min_confidence,
        }
    )

    if len(filtered) < len(results):
        diagnostics.add_warning("일부 OCR 결과가 낮은 신뢰도로 제거되었습니다.")

    result = ToolResult.ok(
        "OCR 결과 필터링 완료",
        filtered_results=filtered,
    )
    result.diagnostics = diagnostics
    return result


def sort_results(layout: PageLayout, results: Sequence[OcrResult]) -> ToolResult:
    """레이아웃을 고려해 읽기 순서대로 정렬"""

    if not layout.columns:
        diagnostics = ToolDiagnostics()
        diagnostics.add_warning("레이아웃 컬럼 정보가 없어 기본 정렬을 수행합니다.")
        sorted_results = sorted(results, key=lambda r: (r.bbox.top_left.y, r.bbox.top_left.x))
        result = ToolResult.ok("컬럼 정보 없음 - 기본 정렬", sorted_results=sorted_results)
        result.diagnostics = diagnostics
        return result

    sorted_results = sort_by_reading_order(layout, list(results))
    diagnostics = ToolDiagnostics()
    diagnostics.extras.update(
        {
            "input_count": len(results),
            "columns": len(layout.columns),
        }
    )

    result = ToolResult.ok("읽기 순서 정렬 완료", sorted_results=sorted_results)
    result.diagnostics = diagnostics
    return result


def build_execution(
    engine: OcrEngine,
    input_region,
    results: Iterable[OcrResult],
    languages: Optional[Iterable[str]] = None,
) -> ToolResult:
    """OCR 실행 결과 객체 생성"""

    execution = OcrExecution(
        engine=engine,
        input_region=input_region,
        languages=list(languages or []),
        results=list(results),
    )

    diagnostics = ToolDiagnostics()
    diagnostics.extras.update(
        {
            "engine": engine.value,
            "result_count": len(execution.results),
        }
    )

    result = ToolResult.ok("OCR 실행 객체 생성", execution=execution)
    result.diagnostics = diagnostics
    return result


def run_ocr_stub(engine: OcrEngine) -> ToolResult:
    """미구현 OCR 엔진에 대한 기본 응답"""

    diagnostics = ToolDiagnostics()
    diagnostics.add_warning("현재 프로젝트에는 OCR 엔진이 통합되어 있지 않습니다.")

    result = ToolResult.fail(
        f"OCR 엔진 '{engine.value}' 실행 미구현",
        diagnostics=diagnostics,
        engine=engine.value,
    )
    return result




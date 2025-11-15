"""워크플로우 제어 AgentTools"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from core.workflow import WorkflowResult, execute_pdf_extraction

from .config import DEFAULT_DPI, DEFAULT_MARGIN
from .layout import detect_page_layout
from .pdf import load_pdf_images, summarize_pdf
from .types import ToolDiagnostics, ToolResult

__all__ = [
    "run_layout_stage",
    "run_full_workflow_stub",
]


def run_layout_stage(
    pdf_path: str,
    *,
    page_index: int = 0,
    dpi: int = DEFAULT_DPI,
) -> ToolResult:
    """PDF 로딩 후 첫 페이지 레이아웃 탐지까지 수행"""

    pdf_summary = summarize_pdf(pdf_path, dpi=dpi)
    if not pdf_summary.success:
        return pdf_summary

    load_result = load_pdf_images(pdf_path, dpi=dpi, page_numbers=[page_index], limit_pages=1)
    if not load_result.success:
        return load_result

    images = load_result.data.get("images", [])
    if not images:
        diagnostics = ToolDiagnostics()
        diagnostics.add_error("지정한 페이지 이미지를 가져오지 못했습니다.")
        return ToolResult.fail("이미지 로드 실패", diagnostics=diagnostics)

    layout_result = detect_page_layout(images[0])
    layout_result.data["pdf_summary"] = pdf_summary.data
    layout_result.diagnostics.warnings.extend(pdf_summary.diagnostics.warnings)
    layout_result.diagnostics.errors.extend(pdf_summary.diagnostics.errors)
    return layout_result


def run_full_workflow_stub(
    pdf_path: str,
    *,
    output_format: str = "png",
) -> ToolResult:
    """기존 `execute_pdf_extraction` 래핑"""

    start = time.perf_counter()

    workflow_result: WorkflowResult = execute_pdf_extraction(pdf_path, output_format=output_format)

    diagnostics = ToolDiagnostics()
    diagnostics.runtime_ms = (time.perf_counter() - start) * 1000

    if not workflow_result.success:
        diagnostics.add_error(workflow_result.message)
        return ToolResult.fail(
            workflow_result.message,
            diagnostics=diagnostics,
            state=workflow_result.state.value,
        )

    result = ToolResult.ok(
        workflow_result.message,
        state=workflow_result.state.value,
        output_path=str(workflow_result.output_path) if workflow_result.output_path else None,
    )
    result.diagnostics = diagnostics
    return result










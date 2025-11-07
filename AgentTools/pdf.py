"""PDF 관련 AgentTools"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from core.pdf_converter import get_pdf_page_count, pdf_to_images
from core.result_validator import load_expected_problems

from .config import DEFAULT_DPI
from .types import AgentToolError, ToolDiagnostics, ToolResult

__all__ = [
    "load_pdf_images",
    "summarize_pdf",
]


def _select_pages(
    images: Sequence, page_numbers: Optional[Iterable[int]] = None, limit: Optional[int] = None
) -> tuple[List, List[int]]:
    if page_numbers is not None:
        indices = sorted({max(0, int(p)) for p in page_numbers})
    else:
        indices = list(range(len(images)))

    if limit is not None:
        indices = indices[:limit]

    selected = [images[i] for i in indices if 0 <= i < len(images)]
    return selected, indices


def load_pdf_images(
    pdf_path: str,
    *,
    dpi: int = DEFAULT_DPI,
    page_numbers: Optional[Iterable[int]] = None,
    limit_pages: Optional[int] = None,
) -> ToolResult:
    """PDF를 이미지 목록으로 변환"""

    pdf_file = Path(pdf_path)
    diagnostics = ToolDiagnostics()

    if not pdf_file.exists():
        diagnostics.add_error("파일을 찾을 수 없습니다.")
        return ToolResult.fail(
            f"PDF 미존재: {pdf_path}", diagnostics=diagnostics, pdf_path=str(pdf_file)
        )

    start = time.perf_counter()

    try:
        images = pdf_to_images(str(pdf_file), dpi=dpi)
    except ImportError as exc:
        diagnostics.add_error(str(exc))
        diagnostics.runtime_ms = (time.perf_counter() - start) * 1000
        return ToolResult.fail(
            "pdf2image 또는 PyMuPDF 미설치", diagnostics=diagnostics, pdf_path=str(pdf_file)
        )
    except Exception as exc:  # pragma: no cover - 외부 라이브러리 오류 방지용
        raise AgentToolError("PDF → 이미지 변환 실패", cause=exc) from exc

    selected, indices = _select_pages(images, page_numbers, limit_pages)

    diagnostics.runtime_ms = (time.perf_counter() - start) * 1000
    diagnostics.extras.update(
        {
            "total_pages": len(images),
            "selected_indices": indices,
            "dpi": dpi,
        }
    )

    result = ToolResult.ok(
        "PDF 페이지 로드 완료",
        images=selected,
        page_indices=indices,
        total_pages=len(images),
        dpi=dpi,
    )
    result.diagnostics = diagnostics
    return result


def summarize_pdf(pdf_path: str, *, dpi: int = DEFAULT_DPI) -> ToolResult:
    """PDF 메타데이터 요약"""

    pdf_file = Path(pdf_path)
    diagnostics = ToolDiagnostics()

    if not pdf_file.exists():
        diagnostics.add_error("파일을 찾을 수 없습니다.")
        return ToolResult.fail(
            f"PDF 미존재: {pdf_path}", diagnostics=diagnostics, pdf_path=str(pdf_file)
        )

    try:
        page_count = get_pdf_page_count(str(pdf_file))
    except Exception as exc:  # pragma: no cover - 외부 라이브러리 오류 방지용
        raise AgentToolError("PDF 페이지 수 확인 실패", cause=exc) from exc

    expected = load_expected_problems(str(pdf_file))
    if expected is None:
        diagnostics.add_warning("예상 문제 번호 정보를 찾지 못했습니다.")

    diagnostics.extras.update({"expected_source": "ground_truth" if expected else "unknown"})

    result = ToolResult.ok(
        "PDF 요약 정보",
        pdf_path=str(pdf_file),
        page_count=page_count,
        default_dpi=dpi,
        expected_problems=expected or [],
    )
    result.diagnostics = diagnostics
    return result




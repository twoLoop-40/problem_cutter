"""
Tesseract OCR Plugin

Idris2 명세: Specs/System/Ocr/Interface.idr (OcrEngineInterface 구현)
"""

import time
from typing import List
import cv2

from core.ocr_engine import run_tesseract_ocr as legacy_tesseract
from .interface import (
    OcrEngineInterface,
    OcrInput,
    OcrOutput,
    TextBlock,
)


class TesseractEngine(OcrEngineInterface):
    """Tesseract OCR 플러그인 (무료, 빠름, 정확도 중간)"""

    def name(self) -> str:
        return "Tesseract OCR"

    def execute(self, input_data: OcrInput) -> OcrOutput:
        start_time = time.time()

        # 이미지 로드
        image = cv2.imread(input_data.image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {input_data.image_path}")

        # 언어 설정
        lang = "+".join(input_data.languages)

        # Tesseract OCR 실행
        ocr_results = legacy_tesseract(image, lang=lang)

        # OcrOutput 형식으로 변환
        blocks: List[TextBlock] = []
        total_confidence = 0.0

        for result in ocr_results:
            # BBox는 (x, y, width, height) → (x1, y1, x2, y2)로 변환
            x1 = result.bbox.x
            y1 = result.bbox.y
            x2 = x1 + result.bbox.width
            y2 = y1 + result.bbox.height

            blocks.append(TextBlock(
                text=result.text,
                bbox=(x1, y1, x2, y2),
                confidence=result.confidence.value,
                detected_language=None,
            ))
            total_confidence += result.confidence.value

        avg_confidence = total_confidence / len(blocks) if blocks else 0.0
        execution_time = int(time.time() - start_time)

        return OcrOutput(
            blocks=blocks,
            execution_time=execution_time,
            average_confidence=avg_confidence,
            engine_name=self.name(),
        )

    def is_available(self) -> bool:
        try:
            import pytesseract
            return True
        except ImportError:
            return False

    def estimated_cost(self, input_data: OcrInput) -> int:
        return 0  # 무료

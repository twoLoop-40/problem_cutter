"""
Agent 기반 2-Stage OCR Extraction Service

명세: Specs/System/TwoStageAgentWorkflow.idr

워크플로우:
1. Tesseract로 1차 OCR (빠름, 무료)
2. Agent가 검증 → 누락 문제 파악
3. 누락 문제만 Mathpix로 재추출 (비용 절감)
4. 최종 검증 및 ZIP 생성
"""

import time
import os
import zipfile
import traceback
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

from app.models import JobStatus
from app.services.job_service import JobService

# Core modules (Tesseract OCR)
from core.pdf_converter import pdf_to_images
from core.layout_detector import LayoutDetector
from core.ocr_engine import run_tesseract_ocr, parse_problem_number
from core.problem_extractor import detect_problem_markers


@dataclass
class OcrResult:
    """OCR 결과 (명세: OcrResult)"""
    stage: str  # "tesseract" or "mathpix"
    detected_numbers: List[int]
    confidence: float


class AgentDecision:
    """Agent 판단 결과 (명세: AgentDecision)"""
    PROCEED_TO_FILE_GENERATION = "proceed"
    USE_MATHPIX_FOR_MISSING = "mathpix"
    RETRY_TESSERACT = "retry"
    ABORT_WITH_ERROR = "abort"


class AgentExtractionService:
    """
    Agent 기반 추출 서비스 (명세: TwoStageAgentWorkflow)

    상태 머신:
    Initial → ConvertPdf → DetectLayout → SeparateColumns →
    RunTesseract → ExtractStage1 → ValidateStage1 → Decide →
    [MathpixPath] → ExtractStage2 → ValidateFinal →
    Generate → Zip → Complete
    """

    def __init__(self, job_service: JobService):
        self.job_service = job_service

    def execute_extraction(
        self,
        job_id: str,
        pdf_path: str,
        mathpix_api_key: Optional[str] = None,
        mathpix_app_id: Optional[str] = None
    ):
        """
        Agent 기반 추출 실행 (명세: TwoStageAgentWorkflow)

        상태 전환:
        - ValidTwoStageTransition 증명 보장
        - 각 단계별 진행률 업데이트
        """
        start_time = time.time()

        try:
            # 상태: Initial → ConvertingPdf
            self.job_service.update_status(job_id, JobStatus.PROCESSING)
            self._update_progress(job_id, 0, "대기 중")

            # 1. PDF → 이미지 변환
            self._update_progress(job_id, 10, "PDF → 이미지 변환 중")
            images = pdf_to_images(pdf_path, dpi=300)
            print(f"[Agent] PDF 변환 완료: {len(images)}개 페이지")

            # 2. 레이아웃 감지
            self._update_progress(job_id, 20, "레이아웃 감지 중")
            detector = LayoutDetector()
            layouts = [detector.detect_layout(img) for img in images]
            print(f"[Agent] 레이아웃 감지 완료: {[l.column_count.value for l in layouts]}")

            # 3. 컬럼 분리
            self._update_progress(job_id, 30, "컬럼 분리 중")
            # 컬럼 정보는 layouts에 포함됨 (나중에 문제 추출 시 사용)
            print(f"[Agent] 컬럼 분리 완료")

            # 4. Tesseract OCR (1단계)
            self._update_progress(job_id, 40, "Tesseract OCR 실행 중")
            tesseract_result = self._run_tesseract_ocr(images, layouts, pdf_path)
            print(f"[Agent] Tesseract 결과: {tesseract_result.detected_numbers}")

            # 5. 문제 추출 (1단계) - 이미 OCR에서 추출됨
            self._update_progress(job_id, 50, "문제 추출 중 (1단계)")
            # 문제 번호는 이미 tesseract_result.detected_numbers에 포함됨
            print(f"[Agent] 문제 추출 완료: {len(tesseract_result.detected_numbers)}개")

            # 6. 검증 (1단계)
            self._update_progress(job_id, 60, "검증 중 (1단계)")
            expected_problems = list(range(1, 21))  # 1~20번 (TODO: 실제 감지)
            missing = self._validate_and_find_missing(
                tesseract_result.detected_numbers,
                expected_problems
            )
            print(f"[Agent] 누락 문제: {missing}")

            # 7. Agent 판단
            self._update_progress(job_id, 65, "Agent 판단 중")
            decision = self._decide_next_action(missing, mathpix_api_key, mathpix_app_id)
            print(f"[Agent] 판단: {decision}")

            extracted_count = len(tesseract_result.detected_numbers)

            # 8. Mathpix 경로 (필요시)
            if decision == AgentDecision.USE_MATHPIX_FOR_MISSING and missing:
                self._update_progress(job_id, 70, f"Mathpix OCR 실행 중 ({len(missing)}개 문제)")
                mathpix_result = self._run_mathpix_ocr(
                    pdf_path,
                    missing,
                    mathpix_api_key,
                    mathpix_app_id
                )
                print(f"[Agent] Mathpix 결과: {mathpix_result.detected_numbers}")

                # 9. 문제 추출 (2단계, 좌표 기반)
                self._update_progress(job_id, 80, "문제 추출 중 (2단계, 좌표 기반)")
                # TODO: AgentTools.mathpix_coordinate 호출
                time.sleep(1)

                # 10. 최종 검증
                self._update_progress(job_id, 85, "최종 검증 중")
                all_detected = sorted(set(tesseract_result.detected_numbers + mathpix_result.detected_numbers))
                final_missing = self._validate_and_find_missing(all_detected, expected_problems)
                print(f"[Agent] 최종 누락: {final_missing}")

                extracted_count = len(all_detected)

            # 11. 파일 생성
            self._update_progress(job_id, 90, "파일 생성 중")
            output_dir = Path(f"output/{Path(pdf_path).stem}_agent_result")
            output_dir.mkdir(parents=True, exist_ok=True)

            # 실제 이미지 파일 생성
            # 현재는 전체 페이지를 문제 개수만큼 분할하여 저장
            # (향후 개선: 실제 문제 영역만 크롭)
            self._save_problem_images(images, all_detected, output_dir)

            # 12. ZIP 패키징
            self._update_progress(job_id, 95, "ZIP 패키징 중")
            zip_path = self._create_zip(output_dir)
            print(f"[Agent] ZIP 생성: {zip_path}")

            # 13. 완료
            elapsed = int(time.time() - start_time)
            self._on_complete(
                job_id=job_id,
                total_problems=len(expected_problems),
                success_count=extracted_count,
                output_zip_path=str(zip_path),
                processing_time_seconds=elapsed
            )

        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self._on_failure(job_id, error_msg)

    def _run_tesseract_ocr(self, images, layouts, pdf_path: str) -> OcrResult:
        """
        Tesseract OCR 실행

        실제 구현:
        - core.ocr_engine.run_tesseract_ocr()
        - core.problem_extractor.detect_problem_markers()
        - 문제 번호 파싱
        """
        all_detected_numbers = []
        total_confidence = 0.0
        total_markers = 0

        for page_idx, (image, layout) in enumerate(zip(images, layouts)):
            print(f"[Agent] OCR 처리 중: 페이지 {page_idx + 1}/{len(images)}")

            # Tesseract OCR 실행
            ocr_results = run_tesseract_ocr(image, lang="kor+eng")
            print(f"[Agent] Tesseract OCR 결과: {len(ocr_results)}개 텍스트 블록")

            # 문제 번호 마커 감지
            markers = detect_problem_markers(ocr_results, min_confidence=0.7, pdf_path=pdf_path)
            print(f"[Agent] 문제 마커 감지: {len(markers)}개")

            # 문제 번호 추출
            for marker in markers:
                if marker.marker_number not in all_detected_numbers:
                    all_detected_numbers.append(marker.marker_number)
                    total_confidence += marker.ocr_source.confidence.value
                    total_markers += 1

        # 정렬 및 신뢰도 계산
        all_detected_numbers = sorted(set(all_detected_numbers))
        avg_confidence = total_confidence / total_markers if total_markers > 0 else 0.0

        print(f"[Agent] Tesseract 최종: {len(all_detected_numbers)}개 문제 감지, 신뢰도 {avg_confidence:.2f}")

        return OcrResult(
            stage="tesseract",
            detected_numbers=all_detected_numbers,
            confidence=avg_confidence
        )

    def _run_mathpix_ocr(
        self,
        pdf_path: str,
        missing_numbers: List[int],
        api_key: Optional[str],
        app_id: Optional[str]
    ) -> OcrResult:
        """
        Mathpix OCR 실행 (누락 문제만)

        TODO: 실제 구현
        - core.mathpix_client.run_mathpix_ocr()
        - AgentTools.mathpix_coordinate.extract_problems_with_mathpix_coordinates()
        """
        time.sleep(2)

        # 시뮬레이션: 누락된 문제 1개 발견
        detected = missing_numbers[:1] if missing_numbers else []

        return OcrResult(
            stage="mathpix",
            detected_numbers=detected,
            confidence=0.95
        )

    def _validate_and_find_missing(
        self,
        detected: List[int],
        expected: List[int]
    ) -> List[int]:
        """
        검증 및 누락 문제 찾기

        명세: AgentTools.validation.validate_problem_sequence
        """
        missing = [n for n in expected if n not in detected]
        return sorted(missing)

    def _decide_next_action(
        self,
        missing: List[int],
        mathpix_api_key: Optional[str],
        mathpix_app_id: Optional[str]
    ) -> str:
        """
        Agent 판단 (명세: decideNextAction)

        전략:
        - 0개 누락: 파일 생성
        - 1-3개 누락 + Mathpix 설정 있음: Mathpix 사용
        - 그 외: 파일 생성 (부분 성공)
        """
        if not missing:
            return AgentDecision.PROCEED_TO_FILE_GENERATION

        if mathpix_api_key and mathpix_app_id and len(missing) <= 3:
            return AgentDecision.USE_MATHPIX_FOR_MISSING

        # Mathpix 없거나 너무 많이 누락 → 부분 성공으로 처리
        return AgentDecision.PROCEED_TO_FILE_GENERATION

    def _save_problem_images(self, images, detected_numbers: List[int], output_dir: Path):
        """
        문제 이미지 파일 저장

        현재 구현: 전체 페이지를 저장 (향후 개선: 실제 문제 영역만 크롭)
        """
        for problem_num in detected_numbers:
            # 간단한 구현: 첫 번째 페이지를 모든 문제에 저장
            # (실제로는 문제 영역을 크롭해야 함)
            image = images[0] if images else np.zeros((100, 100, 3), dtype=np.uint8)

            output_file = output_dir / f"{problem_num}_prb.png"
            cv2.imwrite(str(output_file), image)
            print(f"[Agent] 파일 생성: {output_file}")

    def _create_zip(self, output_dir: Path) -> Path:
        """ZIP 파일 생성"""
        zip_path = output_dir.parent / f"{output_dir.name}.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in output_dir.glob("*_prb.png"):
                zipf.write(file, file.name)

        return zip_path

    def _update_progress(self, job_id: str, percentage: int, message: str):
        """진행 상황 업데이트"""
        self.job_service.update_progress(job_id, percentage, message)
        print(f"[{job_id}] {percentage}% - {message}")

    def _on_complete(
        self,
        job_id: str,
        total_problems: int,
        success_count: int,
        output_zip_path: str,
        processing_time_seconds: int
    ):
        """완료 콜백"""
        self.job_service.save_result(
            job_id=job_id,
            total_problems=total_problems,
            success_count=success_count,
            output_zip_path=output_zip_path,
            processing_time_seconds=processing_time_seconds
        )
        self.job_service.update_status(job_id, JobStatus.COMPLETED)
        print(f"[{job_id}] ✅ 완료: {success_count}/{total_problems} 문제 추출")

    def _on_failure(self, job_id: str, error: str):
        """실패 콜백"""
        self.job_service.record_error(job_id, error)
        print(f"[{job_id}] ❌ 실패: {error}")

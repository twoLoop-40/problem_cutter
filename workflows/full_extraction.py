#!/usr/bin/env python3
"""
Complete PDF problem extraction workflow

Based on directions/view.md:
1. 파일 분석 (문제 개수, 번호 파악)
2. 타입명세 작성 (예상 문제 목록)
3. 단 분리 → 1단으로 변환
4. 세로 추적하면서 각 문제 잘라내기
5. 타입명세와 비교 검증
6. 전체 파일과 비교 확인
7. 문제 파일 생성 + 여백 정리
8. ZIP으로 합치기
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from core.pdf_converter import pdf_to_images, get_pdf_page_count
from core.layout_detector import LayoutDetector, mk_layout_from_merged_lines
from core.ocr_engine import run_tesseract_ocr, sort_by_reading_order
from core.problem_extractor import extract_problems, detect_problem_markers
from core.image_cropper import crop_image, visualize_boundaries
from core.result_validator import validate_results, ValidationFeedback
from PIL import Image as PILImage
import numpy as np


def step1_analyze_pdf(pdf_path: str) -> Dict[str, Any]:
    """Step 1: 파일 분석 - 문제 개수, 번호 파악"""
    print("\n" + "="*60)
    print("Step 1: PDF 파일 분석")
    print("="*60)

    page_count = get_pdf_page_count(pdf_path)
    print(f"  → 총 페이지 수: {page_count}")

    # Quick OCR scan to detect problem numbers
    images = pdf_to_images(pdf_path, dpi=200)
    all_problem_numbers = set()

    for page_num, image in enumerate(images, start=1):
        print(f"  → 페이지 {page_num} 스캔 중...")

        # Simple OCR
        detector = LayoutDetector()
        raw_layout = detector.detect_layout(image)
        ocr_results = run_tesseract_ocr(image, lang="kor+eng")

        # Detect problem markers
        markers = detect_problem_markers(ocr_results, min_confidence=0.6)
        page_problems = [m.marker_number for m in markers]
        all_problem_numbers.update(page_problems)

        print(f"     감지된 문제: {sorted(page_problems)}")

    problem_list = sorted(all_problem_numbers)

    metadata = {
        "pdf_path": pdf_path,
        "page_count": page_count,
        "detected_problems": problem_list,
        "problem_count": len(problem_list),
        "analysis_date": datetime.now().isoformat()
    }

    print(f"\n  ✓ 총 {len(problem_list)}개 문제 감지: {problem_list}")
    return metadata


def step2_create_spec(metadata: Dict[str, Any], output_dir: Path) -> Path:
    """Step 2: 타입명세 작성"""
    print("\n" + "="*60)
    print("Step 2: 타입명세 작성")
    print("="*60)

    spec = {
        "pdf": metadata["pdf_path"],
        "expected_problems": metadata["detected_problems"],
        "expected_count": metadata["problem_count"],
        "created_at": metadata["analysis_date"]
    }

    spec_path = output_dir / "expected_spec.json"
    with open(spec_path, 'w', encoding='utf-8') as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)

    print(f"  ✓ 명세 저장: {spec_path}")
    print(f"  → 예상 문제: {spec['expected_problems']}")

    return spec_path


def step3_extract_problems(pdf_path: str, output_dir: Path) -> List[Dict[str, Any]]:
    """Step 3-4: 단 분리 및 문제 추출"""
    print("\n" + "="*60)
    print("Step 3-4: 레이아웃 감지 및 문제 추출")
    print("="*60)

    images = pdf_to_images(pdf_path, dpi=200)
    all_extracted = []

    for page_num, image in enumerate(images, start=1):
        print(f"\n페이지 {page_num} 처리 중...")

        # Detect layout
        detector = LayoutDetector()
        raw_layout = detector.detect_layout(image)

        if raw_layout.separator_lines:
            layout = mk_layout_from_merged_lines(
                raw_layout.page_width,
                raw_layout.page_height,
                raw_layout.separator_lines
            )
        else:
            layout = raw_layout

        print(f"  → 레이아웃: {layout.column_count.value}단")

        # Run OCR
        raw_ocr_results = run_tesseract_ocr(image, lang="kor+eng")
        ocr_results = sort_by_reading_order(layout, raw_ocr_results)
        print(f"  → OCR: {len(ocr_results)}개 텍스트 블록")

        # Extract problems
        all_boxes = [result.bbox for result in ocr_results]
        problems = extract_problems(
            pdf_path=pdf_path,
            page_num=page_num,
            layout=layout,
            ocr_results=ocr_results,
            all_boxes=all_boxes
        )

        print(f"  → 추출: {len(problems)}개 문제")

        # Visualize boundaries
        vis_dir = output_dir / "visualizations"
        vis_dir.mkdir(exist_ok=True)

        boundaries = [(p.number, p.region) for p in problems]
        vis_path = vis_dir / f"page{page_num}_boundaries.png"
        visualize_boundaries(image, boundaries, str(vis_path))
        print(f"  → 시각화: {vis_path.name}")

        # Save problem images
        problems_dir = output_dir / "problems"
        problems_dir.mkdir(exist_ok=True)

        for problem in problems:
            cropped = crop_image(image, problem.region)
            pil_image = PILImage.fromarray(cropped)

            problem_file = problems_dir / f"{page_num}_{problem.number:02d}_prb.png"
            pil_image.save(problem_file)

            all_extracted.append({
                "page": page_num,
                "number": problem.number,
                "file": str(problem_file),
                "bbox": {
                    "x": problem.region.top_left.x,
                    "y": problem.region.top_left.y,
                    "width": problem.region.width,
                    "height": problem.region.height
                }
            })

            print(f"  ✓ 문제 {problem.number:2d} → {problem_file.name}")

    return all_extracted


def step5_validate(extracted: List[Dict[str, Any]],
                   spec_path: Path,
                   output_dir: Path) -> ValidationFeedback:
    """Step 5: 타입명세와 비교 검증"""
    print("\n" + "="*60)
    print("Step 5: 타입명세 검증")
    print("="*60)

    # Load spec
    with open(spec_path, 'r', encoding='utf-8') as f:
        spec = json.load(f)

    expected = spec["expected_problems"]
    detected = sorted(list(set(item["number"] for item in extracted)))

    # Validate
    feedback = validate_results(
        pdf_path=spec["pdf"],
        detected_problems=detected,
        expected_problems=expected
    )

    # Save validation report
    report_path = output_dir / "validation_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("문제 번호 검증 결과\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"예상 문제: {expected}\n")
        f.write(f"추출 문제: {detected}\n\n")
        f.write(f"정확도: {feedback.accuracy:.1%}\n")
        f.write(f"성공: {feedback.success}\n\n")

        if feedback.missing_problems:
            f.write(f"누락된 문제: {feedback.missing_problems}\n")
        if feedback.false_positives:
            f.write(f"잘못 추출된 문제: {feedback.false_positives}\n")

        f.write(f"\n메시지: {feedback.message}\n")

    print(f"  ✓ 검증 결과: {feedback.message}")
    print(f"  → 정확도: {feedback.accuracy:.1%}")
    print(f"  → 보고서: {report_path}")

    return feedback


def step7_create_zip(output_dir: Path) -> Path:
    """Step 7-8: ZIP으로 합치기"""
    print("\n" + "="*60)
    print("Step 7-8: ZIP 파일 생성")
    print("="*60)

    problems_dir = output_dir / "problems"
    if not problems_dir.exists():
        print("  ⚠️  문제 디렉토리가 없습니다.")
        return None

    zip_path = output_dir / "extracted.zip"

    # Create ZIP
    shutil.make_archive(
        str(zip_path.with_suffix('')),
        'zip',
        str(problems_dir)
    )

    # Get file count and size
    problem_files = list(problems_dir.glob("*.png"))
    zip_size = zip_path.stat().st_size / 1024  # KB

    print(f"  ✓ ZIP 생성: {zip_path}")
    print(f"  → 파일 수: {len(problem_files)}개")
    print(f"  → 크기: {zip_size:.1f} KB")

    return zip_path


def create_final_report(output_dir: Path,
                       metadata: Dict[str, Any],
                       extracted: List[Dict[str, Any]],
                       feedback: ValidationFeedback):
    """최종 보고서 생성"""
    report_path = output_dir / "report.txt"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("PDF 문제 추출 최종 보고서\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"PDF: {metadata['pdf_path']}\n")
        f.write(f"페이지 수: {metadata['page_count']}\n")
        f.write(f"처리 일시: {metadata['analysis_date']}\n\n")

        f.write("=" * 60 + "\n")
        f.write("추출 결과\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"예상 문제: {metadata['detected_problems']}\n")
        f.write(f"추출 문제: {sorted(list(set(item['number'] for item in extracted)))}\n")
        f.write(f"추출 파일 수: {len(extracted)}개\n\n")

        f.write("=" * 60 + "\n")
        f.write("검증 결과\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"정확도: {feedback.accuracy:.1%}\n")
        f.write(f"성공: {feedback.success}\n")
        f.write(f"메시지: {feedback.message}\n\n")

        if feedback.missing_problems:
            f.write(f"⚠️  누락된 문제: {feedback.missing_problems}\n")
        if feedback.false_positives:
            f.write(f"⚠️  잘못 추출: {feedback.false_positives}\n")

        f.write("\n" + "=" * 60 + "\n")
        f.write("출력 파일\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"- 문제 이미지: {output_dir / 'problems'}/\n")
        f.write(f"- 경계 시각화: {output_dir / 'visualizations'}/\n")
        f.write(f"- ZIP 파일: {output_dir / 'extracted.zip'}\n")
        f.write(f"- 메타데이터: {output_dir / 'metadata.json'}\n")

    print(f"\n  ✓ 최종 보고서: {report_path}")


def main():
    """전체 워크플로우 실행"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python run_full_extraction.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    pdf_name = Path(pdf_path).stem
    output_dir = Path("output") / pdf_name
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*60)
    print("PDF 문제 추출 워크플로우")
    print("="*60)
    print(f"입력: {pdf_path}")
    print(f"출력: {output_dir}/")

    # Step 1: Analyze PDF
    metadata = step1_analyze_pdf(pdf_path)

    # Save metadata
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Step 2: Create spec
    spec_path = step2_create_spec(metadata, output_dir)

    # Step 3-4: Extract problems
    extracted = step3_extract_problems(pdf_path, output_dir)

    # Step 5: Validate
    feedback = step5_validate(extracted, spec_path, output_dir)

    # Step 7-8: Create ZIP
    step7_create_zip(output_dir)

    # Final report
    create_final_report(output_dir, metadata, extracted, feedback)

    print("\n" + "="*60)
    print("✓ 전체 워크플로우 완료!")
    print("="*60)
    print(f"\n결과물 위치: {output_dir}/")
    print("\n생성된 파일:")
    print(f"  - metadata.json (메타데이터)")
    print(f"  - expected_spec.json (타입명세)")
    print(f"  - problems/ ({len(extracted)}개 문제 이미지)")
    print(f"  - visualizations/ (경계 시각화)")
    print(f"  - extracted.zip (압축 파일)")
    print(f"  - report.txt (최종 보고서)")
    print(f"  - validation_report.txt (검증 보고서)")
    print()


if __name__ == "__main__":
    main()

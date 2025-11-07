"""
실제 샘플 PDF들을 이용한 레이아웃 감지 테스트

결과를 output/layout_results/ 폴더에 저장
"""

import sys
import cv2
from pathlib import Path

from core.pdf_converter import pdf_to_images
from core.layout_detector import LayoutDetector


def test_sample_pdfs():
    """샘플 PDF들로 레이아웃 감지 테스트"""
    
    # 샘플 PDF 경로
    samples_dir = Path(__file__).parent.parent / "samples"
    output_dir = Path(__file__).parent / "output" / "layout_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*70}")
    print(f"PDF 레이아웃 감지 테스트")
    print(f"{'='*70}\n")
    
    # 샘플 PDF 파일들
    sample_files = list(samples_dir.glob("*.pdf"))
    
    if not sample_files:
        print(f"❌ 샘플 PDF를 찾을 수 없습니다: {samples_dir}")
        print(f"   절대 경로: {samples_dir.absolute()}")
        return
    
    print(f"📁 샘플 디렉토리: {samples_dir}")
    print(f"📂 결과 저장 위치: {output_dir}\n")
    print(f"발견된 샘플: {len(sample_files)}개\n")
    
    # 레이아웃 감지기 생성
    detector = LayoutDetector(
        min_line_length=100,
        line_thickness_threshold=5,
        gap_threshold=50
    )
    
    total_pages = 0
    results = []
    
    # 각 PDF 처리
    for pdf_idx, pdf_path in enumerate(sorted(sample_files), 1):
        print(f"\n{'─'*70}")
        print(f"[{pdf_idx}/{len(sample_files)}] 📄 {pdf_path.name}")
        print(f"{'─'*70}")
        
        try:
            # PDF를 이미지로 변환
            print(f"🔄 PDF → 이미지 변환 중 (DPI: 200)...")
            images = pdf_to_images(str(pdf_path), dpi=200)
            print(f"✅ {len(images)} 페이지 변환 완료")
            
            # 각 페이지 처리
            for page_num, image in enumerate(images, 1):
                total_pages += 1
                print(f"\n  📑 페이지 {page_num}/{len(images)}")
                
                # 레이아웃 감지
                layout = detector.detect_layout(image)
                
                # 결과 출력
                print(f"     감지 방법: {layout.detection_method.value}")
                print(f"     컬럼 수: {layout.column_count.value}단")
                print(f"     페이지 크기: {layout.page_width}x{layout.page_height}px")
                
                if layout.separator_lines:
                    print(f"     구분선: {len(layout.separator_lines)}개")
                    for i, vline in enumerate(layout.separator_lines, 1):
                        print(f"       - 선 {i}: x={vline.x}, 길이={vline.length()}px")
                
                print(f"     컬럼 경계:")
                for i, col in enumerate(layout.columns, 1):
                    width = col.right_x - col.left_x
                    print(f"       - 컬럼 {i}: x=[{col.left_x}, {col.right_x}], 폭={width}px")
                
                # 시각화
                vis = detector.visualize_layout(image, layout)
                
                # 파일명 생성 (안전한 파일명)
                safe_name = pdf_path.stem.replace(" ", "_")
                output_filename = f"{safe_name}_page{page_num}.jpg"
                output_path = output_dir / output_filename
                
                # 저장
                cv2.imwrite(str(output_path), vis)
                print(f"     💾 저장: {output_filename}")
                
                # 결과 기록
                results.append({
                    'pdf': pdf_path.name,
                    'page': page_num,
                    'columns': layout.column_count.value,
                    'method': layout.detection_method.value,
                    'output': output_filename
                })
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
    
    # 최종 요약
    print(f"\n{'='*70}")
    print(f"테스트 완료!")
    print(f"{'='*70}\n")
    
    print(f"📊 처리 결과:")
    print(f"   - 총 PDF: {len(sample_files)}개")
    print(f"   - 총 페이지: {total_pages}개")
    print(f"   - 결과 파일: {len(results)}개")
    
    # 컬럼 분포
    from collections import Counter
    column_counts = Counter(r['columns'] for r in results)
    print(f"\n📈 컬럼 분포:")
    for cols, count in sorted(column_counts.items()):
        print(f"   - {cols}단: {count}개 페이지")
    
    # 감지 방법 분포
    method_counts = Counter(r['method'] for r in results)
    print(f"\n🔍 감지 방법:")
    for method, count in sorted(method_counts.items()):
        print(f"   - {method}: {count}개 페이지")
    
    print(f"\n✅ 모든 결과가 저장되었습니다:")
    print(f"   📂 {output_dir.absolute()}\n")
    
    # 결과 파일 리스트
    print(f"생성된 파일:")
    for result in results:
        print(f"   - {result['output']}")
    
    return results


if __name__ == "__main__":
    test_sample_pdfs()


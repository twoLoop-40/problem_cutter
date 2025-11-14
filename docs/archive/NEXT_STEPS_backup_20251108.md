# 다음 단계 (Next Steps)

**작성일**: 2025-11-08
**현재 상태**: Mathpix 통합 완료, 명세 작성 완료, 파일 정리 완료

---

## 🎯 최우선 과제 (Phase 1)

### 1. Mathpix 발견 후 이미지 재추출 구현 ⭐⭐⭐

**현재 상태**: Mathpix가 문제 번호를 발견하지만 이미지 추출 안됨

**구현 필요**:
```python
# AgentTools/mathpix_validator.py 수정
async def verify_missing_problems_with_mathpix(...):
    # 현재: 문제 번호만 반환
    # 필요: 문제 번호 + 재추출 트리거

    if found_numbers:
        # 새로운 로직 추가
        for num in found_numbers:
            # Option 1: Tesseract 파라미터 조정 후 재실행
            adjusted_config = adjustConfigForMathpixFinding(config, finding)
            re_extract_with_tesseract(column_image, num, adjusted_config)

            # Option 2: Mathpix 텍스트 위치로 영역 추정
            estimate_region_from_position(column_image, finding.textPosition)
```

**예상 작업 시간**: 2-3시간

**완료 기준**:
- [ ] Mathpix가 발견한 문제 3번 이미지 추출 성공
- [ ] 문제 4번도 감지 및 추출 시도
- [ ] 테스트 통과: 20/20 문제 번호 + 20/20 이미지 추출

---

## 🚀 핵심 기능 (Phase 2)

### 2. LangGraph 병렬 처리 워크플로우 구현 ⭐⭐⭐

**기반**: `.specs/System/LangGraphWorkflow.idr` 명세 완성됨

**구현 계획**:
```python
# workflows/langgraph_parallel.py (신규 생성)

from langgraph.graph import StateGraph
from typing import TypedDict, List

class PdfExtractionState(TypedDict):
    pdf_path: str
    total_pages: int
    page_states: List[PageState]
    overall_success: bool

# 노드 정의
def convert_pdf_node(state): ...
def separate_columns_node(state): ...  # 페이지별 병렬
def detect_problems_node(state): ...   # 컬럼별 병렬
def validate_node(state): ...          # 컬럼별 병렬
def mathpix_node(state): ...           # 컬럼별 병렬

# 그래프 구성
graph = StateGraph(PdfExtractionState)
graph.add_node("convert", convert_pdf_node)
graph.add_node("separate", separate_columns_node)
graph.add_node("detect", detect_problems_node)
graph.add_node("validate", validate_node)
graph.add_node("mathpix", mathpix_node)

# 조건부 엣지
graph.add_conditional_edges(
    "validate",
    lambda state: "mathpix" if has_missing(state) else "finalize"
)
```

**예상 성능 향상**:
- 현재: 4페이지 순차 처리 ~8분
- 목표: 4페이지 병렬 처리 ~2분 (4배 속도)

**예상 작업 시간**: 4-6시간

**완료 기준**:
- [ ] LangGraph 그래프 정의 완료
- [ ] 페이지별 병렬 실행 확인
- [ ] 컬럼별 병렬 실행 확인
- [ ] 성능 측정: 최소 2배 이상 속도 향상

---

### 3. 파일 재구성 Phase 1 실행 ⭐⭐

**참고**: `REORGANIZATION_PLAN.md`

**실행 순서**:
```bash
# 1. workflows/ 디렉토리 생성
mkdir -p workflows

# 2. 메인 실행 파일 이동
git mv test_biology_with_mathpix.py workflows/with_mathpix.py
git mv test_biology_with_agent.py workflows/with_agent.py
git mv test_biology.py workflows/tesseract_only.py
git mv run_full_extraction.py workflows/full_extraction.py

# 3. __init__.py 생성
cat > workflows/__init__.py << 'EOF'
"""PDF Problem Extraction Workflows

Available workflows:
- tesseract_only: Tesseract OCR only
- with_agent: Tesseract with Agent auto-retry
- with_mathpix: 2-stage OCR (Tesseract → Mathpix)
- langgraph_parallel: LangGraph parallel execution
"""
EOF

# 4. import 경로 수정
# 각 파일에서 상대 import를 절대 import로 변경
```

**예상 작업 시간**: 1-2시간

**완료 기준**:
- [ ] workflows/ 디렉토리 생성 및 파일 이동
- [ ] 모든 import 경로 수정
- [ ] 테스트 실행 확인
- [ ] README.md 업데이트 (실행 방법)

---

## 🔧 개선 과제 (Phase 3)

### 4. 문제 4번 감지 개선

**현재 상태**: Tesseract, Mathpix 모두 실패

**시도할 방법**:
1. **이미지 전처리**:
   - 대비 증가 (contrast enhancement)
   - 노이즈 제거 (denoising)
   - 이진화 임계값 조정

2. **OCR 파라미터 조정**:
   ```python
   # max_x_position을 더 크게
   max_x_position = 500  # 기본 300 → 500

   # PSM 모드 변경
   config='--psm 6'  # 단일 블록 → 전체 페이지
   ```

3. **Claude Vision API 백업**:
   - Tesseract, Mathpix 모두 실패 시 Claude Vision 사용

**예상 작업 시간**: 2-3시간

---

### 5. 테스트 커버리지 확대

**현재**: 단위 테스트 일부만 존재

**추가 필요**:
```bash
# tests/ 디렉토리에 추가
tests/
├── test_mathpix_validator.py      # NEW
├── test_validation.py              # NEW
├── test_extraction_workflow.py    # NEW
└── test_langgraph_workflow.py     # NEW (Phase 2 후)
```

**목표 커버리지**: 80% 이상

**예상 작업 시간**: 3-4시간

---

### 6. 문서화 개선

**필요 문서**:
1. **API 문서**: AgentTools, core 모듈 docstring
2. **사용 가이드**: 각 워크플로우 실행 방법
3. **개발 가이드**: 새 워크플로우 추가 방법
4. **Idris2 명세 해설**: 비개발자를 위한 설명

**예상 작업 시간**: 2-3시간

---

## 📦 배포 준비 (Phase 4)

### 7. 패키지화

```bash
# pyproject.toml 업데이트
[project]
name = "problem-cutter"
version = "2.1.0"
description = "PDF Problem Extraction with Formal Specifications"

[project.scripts]
problem-cutter = "workflows.with_mathpix:main"
problem-cutter-parallel = "workflows.langgraph_parallel:main"
```

**예상 작업 시간**: 1-2시간

---

### 8. CI/CD 설정

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install uv
      - run: uv sync
      - run: uv run pytest tests/ --cov

  idris2:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: idris-lang/setup-idris2@v1
      - run: idris2 --build problem_cutter.ipkg
```

**예상 작업 시간**: 1-2시간

---

## 🎓 고급 기능 (Phase 5)

### 9. 웹 UI 추가

- FastAPI 백엔드
- React 프론트엔드
- 실시간 진행 상태 표시
- 수동 검수 인터페이스

**예상 작업 시간**: 1-2주

---

### 10. 클라우드 배포

- Docker 컨테이너화
- AWS Lambda / Cloud Run 배포
- S3 결과 저장
- API Gateway

**예상 작업 시간**: 1주

---

## 📅 권장 실행 순서

### Week 1 (핵심 기능 완성)
- Day 1-2: **Task 1** - Mathpix 이미지 재추출
- Day 3-4: **Task 3** - 파일 재구성 Phase 1
- Day 5: **Task 4** - 문제 4번 감지 개선

### Week 2 (병렬 처리 구현)
- Day 1-3: **Task 2** - LangGraph 워크플로우
- Day 4-5: **Task 5** - 테스트 커버리지

### Week 3 (완성도 향상)
- Day 1-2: **Task 6** - 문서화
- Day 3-4: **Task 7, 8** - 패키지화, CI/CD

---

## 🔗 관련 파일

- **명세**: `.specs/System/ExtractionWorkflow.idr`, `LangGraphWorkflow.idr`
- **구현**: `AgentTools/mathpix_validator.py`, `test_biology_with_mathpix.py`
- **계획**: `REORGANIZATION_PLAN.md`
- **결과**: `output/final_results/MATHPIX_TEST_SUMMARY.md`

---

## ✅ 완료된 작업

- ✅ Idris2 명세 작성 (Mathpix 재추출, LangGraph 병렬)
- ✅ AgentTools 모듈 구현 (validation, mathpix_validator)
- ✅ 2단계 OCR 워크플로우 구현 (Tesseract → Mathpix)
- ✅ 테스트 실행 및 검증 (20/20 문제 번호 감지)
- ✅ 파일 재구성 계획 작성

---

**우선순위**: Task 1 → Task 3 → Task 2 순으로 진행 권장

**최종 목표**: 완전 자동화된 PDF 문제 추출 시스템 (95%+ 정확도, 4배 빠른 속도)

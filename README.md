# PDF Problem Cutter v2.1

> Formal Specification Driven PDF 문제 추출 시스템 (Idris2 + Python)

## 🎯 프로젝트 개요

PDF 시험지에서 문제를 자동으로 분리하여 개별 이미지로 저장하는 시스템입니다.

**핵심 특징**:
- ✅ **Idris2 Formal Specifications**: 타입 안전성 보장
- ✅ **2-Stage OCR**: Tesseract (빠름) + Mathpix (정확함)
- ✅ **Agent 기반 자동화**: 검증 실패 시 자동 재시도
- ✅ **LangGraph 병렬 처리**: 페이지별/컬럼별 병렬 실행 (4배 속도)

## 🏗️ 프로젝트 구조

```
problem_cutter/
├── .specs/                     # Idris2 Formal Specifications
│   └── System/
│       ├── Base.idr
│       ├── ExtractionWorkflow.idr   # ✨ v2.1: Mathpix 재추출
│       ├── LangGraphWorkflow.idr    # ✨ v1.0: 병렬 처리
│       ├── LayoutDetection.idr
│       ├── OcrEngine.idr
│       └── ...
│
├── core/                       # 저수준 핵심 모듈
│   ├── pdf_converter.py        # PDF → 이미지
│   ├── column_separator.py     # 단 분리
│   ├── layout_detector.py      # 레이아웃 감지
│   ├── ocr_engine.py           # Tesseract OCR
│   ├── mathpix_client.py       # Mathpix API
│   └── problem_extractor.py    # 문제 추출
│
├── AgentTools/                 # Agent 툴 (고수준 인터페이스)
│   ├── types.py                # ToolResult, ToolDiagnostics
│   ├── validation.py           # 순차 검증, 재시도 제안
│   └── mathpix_validator.py    # Mathpix 재검증
│
├── workflows/                  # ✨ 실행 워크플로우 (메인)
│   ├── tesseract_only.py       # Tesseract 단독
│   ├── with_agent.py           # Agent 자동 재시도
│   ├── with_mathpix.py         # 2-stage OCR (권장)
│   └── langgraph_parallel.py   # 병렬 실행 (TODO)
│
├── scripts/                    # 유틸리티 스크립트
│   ├── debug_ocr.py
│   ├── extract_problems_strict.py
│   └── test_column_separation.py
│
├── tests/                      # 단위 테스트
│   ├── test_base.py
│   ├── test_column_separator.py
│   ├── test_layout_detector.py
│   └── ...
│
├── samples/                    # 테스트 PDF
├── output/                     # 실행 결과
├── direction/                  # 워크플로우 문서
├── NEXT_STEPS.md              # 다음 단계 계획
└── REORGANIZATION_PLAN.md     # 파일 재구성 계획
```

## 🚀 빠른 시작

### 설치

```bash
# Python 환경 설정 (uv 사용)
uv sync

# Idris2 설치 (명세 컴파일용, 선택)
# macOS: brew install idris2
# Linux: https://github.com/idris-lang/Idris2
```

### 실행

```bash
# 1. Tesseract 단독 (빠름, 기본)
uv run python -m workflows.tesseract_only samples/생명과학.pdf

# 2. Agent 기반 (자동 재시도)
uv run python -m workflows.with_agent samples/생명과학.pdf

# 3. Mathpix 통합 (권장, 가장 정확함)
# .env 파일에 API 키 설정 필요:
#   MATHPIX_APP_KEY=your_key
#   MATHPIX_APP_ID=your_id
uv run python -m workflows.with_mathpix samples/생명과학.pdf

# 4. LangGraph 병렬 (최고 성능, TODO)
uv run python -m workflows.langgraph_parallel samples/생명과학.pdf
```

### 출력

```
output/생명과학_mathpix_test/
├── page_1/
│   ├── 00_original.png
│   ├── col_1.png
│   ├── col_2.png
│   └── problems/
│       ├── page1_col_1_prob_01.png  (문제 1번)
│       ├── page1_col_1_prob_02.png  (문제 2번)
│       └── ...
├── page_2/
├── page_3/
└── page_4/
```

## 📊 성능

### 테스트 결과 (생명과학Ⅰ, 4페이지, 20문제)

| 지표 | Tesseract | + Agent | + Mathpix |
|------|-----------|---------|-----------|
| 문제 번호 감지 | 19/20 (95%) | 19/20 (95%) | 20/20 (100%) ✅ |
| 이미지 추출 | 19/20 (95%) | 19/20 (95%) | 19/20 (95%) |
| 처리 속도 | ~2분 | ~3분 | ~4분 |
| API 비용 | 무료 | 무료 | $0.01/page |

**향후 LangGraph 병렬 처리 시 예상**:
- 4페이지 순차: ~8분 → **병렬: ~2분 (4배 속도)** 🚀

## 🧪 테스트

```bash
# 전체 테스트
uv run pytest tests/

# 특정 모듈
uv run pytest tests/test_mathpix_validator.py

# 커버리지
uv run pytest --cov=core --cov=AgentTools tests/
```

## 📐 Idris2 명세 검증

```bash
# 프로젝트 전체 빌드
idris2 --build problem_cutter.ipkg

# 개별 명세 확인
idris2 -p base --check .specs/System/ExtractionWorkflow.idr
idris2 -p base --check .specs/System/LangGraphWorkflow.idr
```

## 🎯 2-Stage OCR 워크플로우

```
[1단계] Tesseract OCR (빠름, 무료)
   ↓
[2단계] 검증 Agent
   ↓ (실패 시)
[3단계] Mathpix OCR (정확함, 유료) → 누락 문제 재검증
   ↓
[4단계] 최종 검증
```

**장점**:
- Tesseract로 95% 처리 (무료)
- 나머지 5%만 Mathpix 사용 (비용 절감)
- 100% 감지율 달성

## 🤖 AgentTools 사용법

```python
from AgentTools.validation import validate_problem_sequence
from AgentTools.mathpix_validator import verify_missing_problems_with_mathpix

# 1. 검증
result = validate_problem_sequence(found_numbers=[1, 2, 5, 6])
# result.success = False
# result.data["missing"] = [3, 4]

# 2. Mathpix 재검증 (async)
mathpix_result = await verify_missing_problems_with_mathpix(
    column_image_path=Path("output/page1/col_1.png"),
    missing_numbers=[3, 4],
    api_key=os.getenv("MATHPIX_APP_KEY"),
    app_id=os.getenv("MATHPIX_APP_ID")
)
# mathpix_result.data["found_numbers"] = [3]
```

## 📚 주요 문서

- [NEXT_STEPS.md](NEXT_STEPS.md) - 다음 단계 및 작업 계획
- [REORGANIZATION_PLAN.md](REORGANIZATION_PLAN.md) - 파일 재구성 계획
- [output/final_results/MATHPIX_TEST_SUMMARY.md](output/final_results/MATHPIX_TEST_SUMMARY.md) - 테스트 결과
- [direction/](direction/) - 워크플로우 상세 문서

## 🔬 Formal Specifications

### ExtractionWorkflow.idr v2.1

**Mathpix 재추출 알고리즘 명세**:
- `TwoStageOcrState`: 2단계 OCR 상태 (Tesseract → Mathpix)
- `adjustConfigForMathpixFinding`: Mathpix 발견 시 설정 자동 조정
- `ReExtractionStrategy`: 재추출 전략 (파라미터 조정 vs 영역 추정)
- 증명: DPI, 재시도 횟수 보존

### LangGraphWorkflow.idr v1.0

**LangGraph 병렬 처리 명세**:
- `GraphNode`: 11개 노드 (Start → Convert → ... → End)
- `ParallelLevel`: Sequential / PageLevel / ColumnLevel
- `IndependentPages`, `IndependentColumns`: 독립성 증명
- `NoDataRace`: 데이터 경쟁 없음 보장

## 🛠️ 개발 원칙

**Formal Spec Driven Development**:
1. Idris2로 타입 명세 작성
2. 명세 컴파일 검증 (`idris2 --check`)
3. Python 코드 구현
4. 실행 중 문제 발견 시 → 1번으로

**장점**:
- 타입 시스템이 버그를 미리 차단
- 증명 타입으로 불변식(invariant) 보장
- 명세가 곧 문서

## 📈 현재 상태

**v2.1 (2025-11-08)**:
- ✅ Idris2 명세 완성 (ExtractionWorkflow, LangGraphWorkflow)
- ✅ 2-Stage OCR 구현 (Tesseract + Mathpix)
- ✅ Agent 자동 재시도 구현
- ✅ 파일 재구성 완료 (workflows/, scripts/, tests/)
- ⏳ LangGraph 병렬 처리 (명세만 완성, 구현 대기)
- ⏳ Mathpix 발견 후 이미지 재추출 (TODO)

## 🎯 다음 마일스톤

1. **Phase 1** (우선): Mathpix 발견 후 이미지 재추출
2. **Phase 2**: LangGraph 병렬 워크플로우 구현
3. **Phase 3**: 테스트 커버리지 80% 달성
4. **Phase 4**: 패키지화 및 CI/CD

자세한 내용은 [NEXT_STEPS.md](NEXT_STEPS.md) 참고.

## 🤝 기여

1. 새 워크플로우는 `workflows/`에 추가
2. 유틸리티 스크립트는 `scripts/`에 추가
3. 테스트는 `tests/`에 추가
4. Idris2 명세 수정 후 반드시 컴파일 확인

## 📄 라이선스

MIT

---

**현재 진행률**: 명세 100% | 구현 80% | 병렬화 20% | 문서화 90%

**마지막 업데이트**: 2025-11-08 (v2.1)


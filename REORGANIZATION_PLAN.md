# 프로젝트 파일 재구성 계획

**작성일**: 2025-11-08
**목적**: 기능과 성격에 맞게 파일 정리 및 구조 개선

---

## 현재 문제점

1. **중복 파일**: `core/` 와 `AgentTools/` 에 유사 기능 중복
2. **테스트 파일 분산**: 루트에 `test_*.py` 파일들이 산재
3. **실행 스크립트 혼재**: 테스트, 예시, 실제 실행 스크립트가 구분 안됨
4. **명확하지 않은 진입점**: 어느 파일을 실행해야 할지 불명확

---

## 재구성 목표

1. ✅ **기능별 명확한 분리**: core (저수준), AgentTools (고수준), workflows (통합)
2. ✅ **테스트 파일 통합**: `tests/` 디렉토리로 일원화
3. ✅ **실행 스크립트 분리**: `scripts/` (유틸리티), `workflows/` (메인 실행)
4. ✅ **예시 코드 분리**: `examples/` 에 데모 코드 모음

---

## 신규 디렉토리 구조

```
problem_cutter/
├── .specs/                      # Idris2 명세 (현재 그대로)
│   └── System/
│       ├── Base.idr
│       ├── ExtractionWorkflow.idr   # ✨ NEW: Mathpix 재추출 명세
│       ├── LangGraphWorkflow.idr    # ✨ NEW: LangGraph 병렬 처리 명세
│       └── ...
│
├── core/                        # 저수준 핵심 모듈 (라이브러리처럼 사용)
│   ├── __init__.py
│   ├── base.py                  # 공통 타입, 유틸리티
│   ├── pdf_converter.py         # PDF → 이미지
│   ├── column_separator.py      # 단 분리
│   ├── layout_detector.py       # 레이아웃 감지
│   ├── ocr_engine.py            # OCR 엔진 (Tesseract)
│   ├── mathpix_client.py        # Mathpix API 클라이언트
│   ├── problem_extractor.py     # 문제 추출
│   ├── result_validator.py      # 결과 검증
│   └── output_generator.py      # 결과 출력
│
├── AgentTools/                  # Agent 툴 모듈 (Agent 전용 인터페이스)
│   ├── __init__.py
│   ├── types.py                 # ToolResult, ToolDiagnostics
│   ├── validation.py            # 순차 검증 툴
│   ├── mathpix_validator.py     # Mathpix 재검증 툴
│   └── config.py                # 설정 조정 전략
│
├── workflows/                   # ✨ NEW: 실행 워크플로우 (메인 실행 파일)
│   ├── __init__.py
│   ├── tesseract_only.py        # Tesseract 단독 실행
│   ├── with_mathpix.py          # Mathpix 통합 실행 (현재 test_biology_with_mathpix.py)
│   ├── with_agent.py            # Agent 기반 실행 (현재 test_biology_with_agent.py)
│   └── langgraph_parallel.py    # ✨ TODO: LangGraph 병렬 실행
│
├── scripts/                     # 유틸리티 스크립트 (디버그, 도구)
│   ├── debug_ocr.py             # OCR 디버깅
│   ├── analyze_layout.py        # 레이아웃 분석 (현재 examples/detect_layout.py)
│   └── test_column_separation.py # 단 분리 테스트
│
├── examples/                    # 데모 및 예시 코드
│   ├── simple_extraction.py     # 간단한 추출 예시
│   └── column_separation_demo.py # 단 분리 데모
│
├── tests/                       # 단위 테스트 (pytest)
│   ├── __init__.py
│   ├── test_base.py
│   ├── test_pdf_converter.py
│   ├── test_column_separator.py
│   ├── test_layout_detector.py
│   ├── test_ocr_engine.py
│   ├── test_mathpix_client.py
│   ├── test_problem_extractor.py
│   ├── test_validation.py
│   └── test_mathpix_validator.py
│
├── samples/                     # 테스트용 PDF 샘플
│   └── *.pdf
│
├── output/                      # 실행 결과 (gitignore)
│   ├── final_results/
│   └── ...
│
├── direction/                   # 워크플로우 문서 (현재 그대로)
│   └── *.md
│
├── pyproject.toml               # Python 프로젝트 설정 (uv)
├── problem_cutter.ipkg          # Idris2 프로젝트 설정
├── README.md
└── REORGANIZATION_PLAN.md       # 이 파일
```

---

## 파일 이동 계획

### Phase 1: 워크플로우 파일 이동 (우선순위 높음)

| 현재 위치 | 새 위치 | 이유 |
|----------|--------|------|
| `test_biology_with_mathpix.py` | `workflows/with_mathpix.py` | 메인 실행 워크플로우 |
| `test_biology_with_agent.py` | `workflows/with_agent.py` | Agent 기반 워크플로우 |
| `test_biology.py` | `workflows/tesseract_only.py` | Tesseract 단독 워크플로우 |
| `run_full_extraction.py` | `workflows/full_extraction.py` | 전체 추출 워크플로우 |

### Phase 2: 스크립트 파일 정리

| 현재 위치 | 새 위치 | 이유 |
|----------|--------|------|
| `scripts/debug_ocr.py` | 유지 | 이미 올바른 위치 |
| `examples/detect_layout.py` | `scripts/analyze_layout.py` | 디버그 도구 성격 |
| `examples/separate_columns_demo.py` | 유지 | 예시 코드 성격 유지 |
| `test_column_separation_samples.py` | `scripts/test_column_separation.py` | 디버그 도구 |

### Phase 3: 테스트 파일 통합

| 현재 위치 | 새 위치 | 이유 |
|----------|--------|------|
| `test_extract_problems.py` | `tests/test_problem_extraction.py` | 단위 테스트 통합 |
| `test_problem_detection.py` | `tests/test_problem_detection.py` | 단위 테스트 통합 |
| `test_new_extraction.py` | `tests/test_extraction_workflow.py` | 단위 테스트 통합 |
| `test_samples.py` | 삭제 or `tests/test_samples.py` | 중복 기능 확인 필요 |

### Phase 4: core/ 파일 정리 (중복 제거)

| 파일 | 상태 | 조치 |
|-----|------|------|
| `core/problem_analyzer.py` | 🔍 검토 | AgentTools와 중복 확인 |
| `core/problem_cutter.py` | 🔍 검토 | problem_extractor.py와 통합 고려 |
| `core/column_linearizer.py` | ✅ 유지 | 고유 기능 |
| `core/image_cropper.py` | ✅ 유지 | 고유 기능 |
| `core/pdf_text_search.py` | ✅ 유지 | 고유 기능 |
| `core/problem_boundary.py` | ✅ 유지 | 고유 기능 |
| `core/workflow.py` | 🔍 검토 | workflows/ 와 중복 확인 |

### Phase 5: AgentTools/ 파일 정리

| 파일 | 상태 | 조치 |
|-----|------|------|
| `AgentTools/extraction.py` | 🔍 검토 | core와 중복 확인 |
| `AgentTools/layout.py` | 🔍 검토 | core와 중복 확인 |
| `AgentTools/ocr.py` | 🔍 검토 | core와 중복 확인 |
| `AgentTools/pdf.py` | 🔍 검토 | core와 중복 확인 |
| `AgentTools/workflow.py` | 🔍 검토 | workflows/ 와 중복 확인 |
| `AgentTools/types.py` | ✅ 유지 | 고유 기능 (ToolResult) |
| `AgentTools/validation.py` | ✅ 유지 | 고유 기능 |
| `AgentTools/mathpix_validator.py` | ✅ 유지 | 고유 기능 |
| `AgentTools/config.py` | ✅ 유지 | 고유 기능 |

---

## 실행 후 결과

### 명확한 진입점

```bash
# Tesseract 단독 실행
uv run python -m workflows.tesseract_only samples/생명과학.pdf

# Mathpix 통합 실행 (2단계 OCR)
uv run python -m workflows.with_mathpix samples/생명과학.pdf

# Agent 기반 실행 (자동 재시도)
uv run python -m workflows.with_agent samples/생명과학.pdf

# LangGraph 병렬 실행 (최대 성능)
uv run python -m workflows.langgraph_parallel samples/생명과학.pdf
```

### 테스트 실행

```bash
# 전체 테스트
uv run pytest tests/

# 특정 모듈 테스트
uv run pytest tests/test_mathpix_validator.py

# 커버리지 확인
uv run pytest --cov=core --cov=AgentTools tests/
```

### 디버그/분석 도구

```bash
# OCR 디버깅
uv run python scripts/debug_ocr.py output/page_1/col_1.png

# 레이아웃 분석
uv run python scripts/analyze_layout.py samples/생명과학.pdf

# 단 분리 테스트
uv run python scripts/test_column_separation.py samples/
```

---

## 실행 순서

1. ✅ **Phase 1 먼저 실행** (workflows/ 생성 및 메인 파일 이동)
2. ✅ Phase 2, 3 실행 (스크립트 및 테스트 정리)
3. ✅ Phase 4, 5는 코드 검토 후 신중하게 진행 (중복 제거)

---

## 주의사항

1. **git 이력 보존**: `git mv` 사용하여 이동 이력 유지
2. **import 경로 수정**: 파일 이동 후 import 문 전부 수정 필요
3. **테스트 확인**: 각 Phase 완료 후 전체 테스트 실행
4. **문서 업데이트**: README.md, CLAUDE.md 업데이트

---

## 예상 효과

1. ✅ **명확한 구조**: 초보자도 어떤 파일을 실행해야 할지 명확함
2. ✅ **유지보수 용이**: 기능별 분리로 코드 수정 영향 범위 최소화
3. ✅ **테스트 용이**: 테스트 파일 통합으로 CI/CD 설정 단순화
4. ✅ **확장 가능**: 새 워크플로우 추가 시 `workflows/` 에만 파일 추가

---

**다음 단계**: Phase 1 실행 (workflows/ 디렉토리 생성 및 파일 이동)

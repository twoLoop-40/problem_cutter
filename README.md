# PDF Problem Cutter v3.0

> Formal Specification Driven PDF 문제 추출 시스템 (Idris2 + FastAPI + Streamlit)

## 🎯 프로젝트 개요

PDF 시험지에서 문제를 자동으로 분리하여 개별 이미지로 저장하는 웹 애플리케이션입니다.

**핵심 특징**:
- ✅ **Idris2 Formal Specifications**: 타입 안전성 보장
- ✅ **FastAPI 백엔드**: 비동기 처리, RESTful API
- ✅ **SQLite 데이터베이스**: 작업 관리 및 진행률 추적
- ✅ **Streamlit UI**: 웹 기반 사용자 인터페이스
- ✅ **2-Stage OCR**: Tesseract (빠름) + Mathpix (정확함)
- ✅ **실시간 진행률**: 작업 상태 모니터링

## 🏗️ 프로젝트 구조

```
problem_cutter/
├── api/                        # ✨ FastAPI 백엔드
│   └── main.py                 #    REST API 엔드포인트
│
├── app/                        # ✨ 애플리케이션 계층
│   ├── models/                 #    SQLAlchemy 모델
│   │   └── job.py              #    Job Entity
│   ├── repositories/           #    데이터 접근 계층
│   │   └── job_repository.py
│   ├── services/               #    비즈니스 로직
│   │   ├── job_service.py
│   │   └── extraction_service.py
│   └── database.py             #    SQLite 설정
│
├── ui/                         # ✨ 사용자 인터페이스
│   └── streamlit/
│       └── app.py              #    Streamlit 웹 UI
│
├── Specs/                      # Idris2 Formal Specifications
│   └── System/
│       ├── AppArchitecture.idr # ✨ v3.0: 웹 앱 아키텍처
│       ├── Base.idr
│       ├── ExtractionWorkflow.idr
│       └── ...
│
├── core/                       # 저수준 핵심 모듈
│   ├── pdf_converter.py
│   ├── layout_detector.py
│   └── ...
│
├── AgentTools/                 # 고수준 인터페이스
│   ├── mathpix_coordinate.py   # Mathpix 좌표 추출
│   └── types.py
│
├── workflows/                  # 도메인 로직
│   ├── with_mathpix.py         # 2-stage OCR
│   └── ...
│
├── docs/                       # 📚 문서
│   ├── QUICKSTART.md           #    빠른 시작 가이드
│   ├── APP_ARCHITECTURE.md     #    아키텍처 설계
│   └── ...
│
├── tests/                      # 테스트
├── samples/                    # 샘플 PDF
└── uploads/                    # 업로드된 파일
```

## 🚀 빠른 시작 (웹 앱)

### 설치

```bash
# Python 환경 설정
uv sync

# 또는
pip install -r requirements.txt
```

### 실행

```bash
# 터미널 1: FastAPI 백엔드 시작
python -m api.main
# → http://localhost:8000

# 터미널 2: Streamlit UI 시작
streamlit run ui/streamlit/app.py
# → http://localhost:8501
```

### 사용 방법

1. Streamlit UI 열기 (http://localhost:8501)
2. PDF 파일 업로드
3. (선택) Mathpix API 키 입력
4. "추출 시작" 클릭
5. 진행 상황 모니터링 (실시간)
6. 완료 후 결과 다운로드 (ZIP)

### 결과물

```
result.zip
├── 1_prb.png  (문제 1번)
├── 2_prb.png  (문제 2번)
├── 3_prb.png  (문제 3번)
└── ...
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

- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** - 빠른 시작 가이드 (웹 앱)
- **[docs/APP_ARCHITECTURE.md](docs/APP_ARCHITECTURE.md)** - 아키텍처 설계 문서
- [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md) - 다음 단계 및 작업 계획
- [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md) - 테스트 결과

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

**v3.0 (2025-11-14)** - 웹 앱 Phase 1 완료:
- ✅ FastAPI 백엔드 구현 (RESTful API)
- ✅ SQLite 데이터베이스 (Job 관리)
- ✅ Streamlit UI (웹 인터페이스)
- ✅ 실시간 진행률 추적
- ✅ Idris2 명세 (AppArchitecture.idr)
- ✅ Mathpix 좌표 추출 (CoordinateScaler)
- ⏳ workflows 통합 (TODO)
- ⏳ LangGraph 병렬 처리 (TODO)

## 🎯 다음 마일스톤

1. **Phase 1.1**: workflows/with_mathpix.py 로직을 ExtractionService에 통합
2. **Phase 1.2**: 실제 ZIP 파일 생성 및 다운로드
3. **Phase 2**: LangGraph 워크플로우 통합
4. **Phase 3**: Next.js UI로 마이그레이션 (선택)

자세한 내용은 [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md) 참고.

## 🤝 기여

1. 새 워크플로우는 `workflows/`에 추가
2. 유틸리티 스크립트는 `scripts/`에 추가
3. 테스트는 `tests/`에 추가
4. Idris2 명세 수정 후 반드시 컴파일 확인

## 📄 라이선스

MIT

---

**현재 진행률**: 명세 100% | 웹 앱 Phase 1 완료 | 워크플로우 통합 대기

**마지막 업데이트**: 2025-11-14 (v3.0)


# PDF Problem Cutter - 앱 아키텍처 설계

**작성일**: 2025-11-08
**버전**: 3.0 (App Migration)
**Formal Spec**: `.specs/System/AppArchitecture.idr`

---

## 📋 목차

1. [현재 프로젝트 기능별 정리](#1-현재-프로젝트-기능별-정리)
2. [전체 아키텍처](#2-전체-아키텍처)
3. [계층별 역할](#3-계층별-역할)
4. [디렉토리 구조](#4-디렉토리-구조)
5. [데이터 흐름](#5-데이터-흐름)
6. [기술 스택](#6-기술-스택)
7. [마이그레이션 계획](#7-마이그레이션-계획)

---

## 1. 현재 프로젝트 기능별 정리

### 1.1 핵심 기능 (Domain Logic)

#### **PDF 처리 파이프라인**

```
PDF 입력 → 이미지 변환 → 레이아웃 감지 → 컬럼 분리 → OCR → 검증 → 문제 추출 → ZIP 생성
```

**구현 위치**:
- `core/pdf_converter.py` - PDF → 이미지 변환 (DPI=200)
- `core/layout_detector.py` - 레이아웃 감지 (1/2/3단)
- `core/column_separator.py` - 컬럼 분리
- `core/ocr_engine.py` - Tesseract OCR
- `core/mathpix_client.py` - Mathpix API 클라이언트
- `core/problem_extractor.py` - 문제 영역 추출
- `core/output_generator.py` - ZIP 생성

#### **OCR 전략 (3가지)**

| 전략 | 설명 | 성능 | 정확도 |
|------|------|------|--------|
| `tesseract_only` | Tesseract 단독 | ⚡ 빠름 (2분) | 70-80% |
| `with_mathpix` | Tesseract + Mathpix 2단계 | ⚡ 중간 (3-5분) | 95-100% |
| `with_agent` | Agent 자동 재시도 | 🐌 느림 (5-10분) | 90-95% |

**구현 위치**:
- `workflows/tesseract_only.py` - 전략 1
- `workflows/with_mathpix.py` - 전략 2 (권장) ⭐
- `workflows/with_agent.py` - 전략 3 (미완성)

#### **검증 시스템**

**Idris2 명세 기반 검증**:
- `.specs/System/Base.idr` - BBox, Region 타입
- `.specs/System/ExtractionWorkflow.idr` - 워크플로우 상태
- `.specs/System/MathpixCoordinateExtraction.idr` - 좌표 추출

**Python 구현**:
- `AgentTools/validation.py` - 순차 검증
- `AgentTools/mathpix_validator.py` - Mathpix 검증
- `AgentTools/mathpix_coordinate.py` - 좌표 기반 추출 (최신)

### 1.2 지원 기능

#### **이미지 처리**
- `core/image_cropper.py` - 이미지 자르기
- `core/problem_boundary.py` - 문제 경계 감지
- `core/column_linearizer.py` - 다단 → 단일 변환

#### **유틸리티**
- `AgentTools/pdf.py` - PDF 요약
- `AgentTools/layout.py` - 레이아웃 요약
- `AgentTools/types.py` - 공통 타입 (ToolResult)

### 1.3 테스트

```
tests/
├── test_base.py                 # 기본 타입 테스트
├── test_layout_detector.py      # 레이아웃 감지
├── test_column_separator.py     # 컬럼 분리
├── test_ocr_engine.py           # OCR
├── test_problem_extraction.py   # 문제 추출
└── test_extraction_workflow.py  # 전체 워크플로우
```

**커버리지**: 약 60% (코어 로직 중심)

---

## 2. 전체 아키텍처

### 2.1 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                       UI Layer                              │
│  ┌──────────────┐                    ┌──────────────┐      │
│  │  Streamlit   │  ← Phase 1         │   Next.js    │      │
│  │  (간단 UI)   │                    │ (프로덕션 UI) │      │
│  └──────┬───────┘                    └──────┬───────┘      │
│         │                                    │              │
│         └────────────────┬───────────────────┘              │
└──────────────────────────┼──────────────────────────────────┘
                           │ HTTP/WebSocket
┌──────────────────────────┼──────────────────────────────────┐
│                    API Layer (FastAPI)                      │
│                                                              │
│  POST /api/extract       GET /api/status/{job_id}          │
│  GET  /api/download      WS  /ws/{job_id}                  │
│                                                              │
└──────────────────────────┼──────────────────────────────────┘
                           │ Service Call
┌──────────────────────────┼──────────────────────────────────┐
│                   Service Layer                             │
│                                                              │
│  ┌────────────────┐     ┌────────────────┐                │
│  │  JobService    │     │ExtractionService│                │
│  │ (작업 관리)     │     │  (PDF 처리)     │                │
│  └────────┬───────┘     └────────┬───────┘                │
│           │                       │                         │
│           └───────────┬───────────┘                         │
└───────────────────────┼─────────────────────────────────────┘
                        │ Domain Call
┌───────────────────────┼─────────────────────────────────────┐
│                  Domain Layer                               │
│                                                              │
│  ┌────────────────────────────────────────────┐            │
│  │       LangGraph Workflow                   │            │
│  │                                             │            │
│  │  Analyze → Separate → Tesseract → Validate │            │
│  │              ↓            ↑                 │            │
│  │           Mathpix  ←──────┘                │            │
│  │              ↓                              │            │
│  │          Finalize                           │            │
│  └────────────────────────────────────────────┘            │
│                                                              │
│  기존 workflows/ (재사용)                                    │
└───────────────────────┼─────────────────────────────────────┘
                        │ Infrastructure Call
┌───────────────────────┼─────────────────────────────────────┐
│             Infrastructure Layer                            │
│                                                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ PDF I/O   │  │ OCR APIs  │  │ Job Queue │              │
│  │ (파일)     │  │(Tesseract)│  │ (Redis)   │              │
│  │           │  │ (Mathpix) │  │           │              │
│  └───────────┘  └───────────┘  └───────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 계층 의존성 규칙

**명세**: `.specs/System/AppArchitecture.idr` - `LayerDependency`

```idris
data LayerDependency : AppLayer -> AppLayer -> Type where
  ApiToService : LayerDependency ApiLayer ServiceLayer
  ServiceToDomain : LayerDependency ServiceLayer DomainLayer
  DomainToInfra : LayerDependency DomainLayer InfraLayer
```

**규칙**:
- ✅ 상위 계층 → 하위 계층 의존 가능
- ❌ 하위 계층 → 상위 계층 의존 불가
- ❌ 계층 건너뛰기 의존 불가 (API → Domain 직접 X)

---

## 3. 계층별 역할

### 3.1 API Layer (FastAPI)

**역할**: HTTP 엔드포인트, 요청/응답 처리

**책임**:
- 요청 유효성 검증
- 인증/인가 (미래)
- 응답 직렬화
- 에러 핸들링

**엔드포인트**:

```python
# api/main.py

@app.post("/api/extract")
async def extract_problems(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    api_key: str,
    app_id: str,
    strategy: str = "with_mathpix"
) -> UploadResponse:
    """PDF 업로드 및 작업 생성"""
    ...

@app.get("/api/status/{job_id}")
async def get_status(job_id: str) -> StatusResponse:
    """작업 상태 조회"""
    ...

@app.get("/api/download/{job_id}")
async def download_result(job_id: str) -> FileResponse:
    """결과 ZIP 다운로드"""
    ...

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """실시간 진행 상황 (WebSocket)"""
    ...
```

**구현 위치**: `api/main.py` (신규)

---

### 3.2 Service Layer

**역할**: 비즈니스 로직, 상태 관리

#### **JobService** (작업 관리)

```python
# app/services/job_service.py

class JobService:
    """작업 생성, 조회, 상태 업데이트"""

    def create_job(self, pdf_path: str, config: UploadRequest) -> str:
        """작업 생성 → job_id 반환"""

    def get_job(self, job_id: str) -> Optional[Job]:
        """작업 조회"""

    def update_status(self, job_id: str, status: JobStatus):
        """상태 업데이트"""

    def update_progress(self, job_id: str, progress: JobProgress):
        """진행 상황 업데이트"""

    def save_result(self, job_id: str, result: JobResult):
        """결과 저장"""
```

#### **ExtractionService** (PDF 처리)

```python
# app/services/extraction_service.py

class ExtractionService:
    """실제 PDF → 문제 이미지 추출"""

    async def execute(
        self,
        job_id: str,
        pdf_path: str,
        config: UploadRequest
    ) -> JobResult:
        """
        비동기 PDF 처리

        1. LangGraph 워크플로우 실행
        2. 진행 상황을 JobService에 전달
        3. 결과 반환
        """
```

**구현 위치**: `app/services/` (신규)

---

### 3.3 Domain Layer

**역할**: 핵심 도메인 로직 (기존 workflows/ 재사용)

#### **LangGraph Workflow** (신규)

```python
# app/domain/langgraph_workflow.py

from langgraph.graph import StateGraph

class ExtractionGraph:
    """LangGraph 기반 PDF 추출 워크플로우"""

    def __init__(self):
        self.graph = StateGraph(LangGraphState)
        self._build_graph()

    def _build_graph(self):
        # 노드 추가
        self.graph.add_node("analyze", self._analyze_node)
        self.graph.add_node("separate", self._separate_node)
        self.graph.add_node("tesseract", self._tesseract_node)
        self.graph.add_node("validate", self._validate_node)
        self.graph.add_node("mathpix", self._mathpix_node)
        self.graph.add_node("finalize", self._finalize_node)

        # 엣지 추가
        self.graph.add_edge("analyze", "separate")
        self.graph.add_edge("separate", "tesseract")
        self.graph.add_edge("tesseract", "validate")

        # 조건부 엣지
        self.graph.add_conditional_edges(
            "validate",
            self._should_retry_with_mathpix,
            {
                True: "mathpix",   # 검증 실패 → Mathpix
                False: "finalize"  # 검증 성공 → 최종화
            }
        )
        self.graph.add_edge("mathpix", "validate")

    async def execute(self, initial_state: LangGraphState) -> LangGraphState:
        """워크플로우 실행"""
        return await self.graph.ainvoke(initial_state)
```

#### **기존 워크플로우 재사용**

```python
# app/domain/extraction.py

from workflows.with_mathpix import extract_problems as _extract_legacy

def extract_problems(pdf_path: str, config: dict) -> dict:
    """
    기존 workflows/with_mathpix.py를 래핑

    점진적으로 LangGraph로 마이그레이션
    """
    return _extract_legacy(pdf_path, **config)
```

**구현 위치**: `app/domain/` (신규, 기존 workflows/ 래핑)

---

### 3.4 Infrastructure Layer

**역할**: 외부 의존성 (DB, OCR, File I/O)

```python
# app/infrastructure/

├── storage/
│   ├── file_storage.py      # 파일 저장소 (로컬/S3)
│   └── job_repository.py    # 작업 저장소 (메모리/Redis/DB)
│
├── ocr/
│   ├── tesseract_client.py  # 기존 core/ocr_engine.py 래핑
│   └── mathpix_client.py    # 기존 core/mathpix_client.py 래핑
│
└── queue/
    └── job_queue.py         # Redis 기반 작업 큐
```

**구현 위치**: `app/infrastructure/` (신규)

---

## 4. 디렉토리 구조

### 4.1 최종 구조 (Phase 2 완료 후)

```
problem_cutter/
│
├── .specs/                      # Idris2 Formal Specifications
│   └── System/
│       ├── AppArchitecture.idr  # ✨ 앱 아키텍처 (NEW)
│       ├── Base.idr
│       ├── ExtractionWorkflow.idr
│       ├── MathpixCoordinateExtraction.idr
│       └── ...
│
├── api/                         # ✨ API Layer (NEW)
│   ├── __init__.py
│   ├── main.py                  # FastAPI 앱
│   ├── routes/
│   │   ├── extract.py           # POST /api/extract
│   │   ├── status.py            # GET /api/status/{job_id}
│   │   └── download.py          # GET /api/download/{job_id}
│   └── schemas/
│       ├── request.py           # Request 모델
│       └── response.py          # Response 모델
│
├── app/                         # ✨ Application Core (NEW)
│   │
│   ├── services/                # Service Layer
│   │   ├── job_service.py       # 작업 관리
│   │   └── extraction_service.py # PDF 처리
│   │
│   ├── domain/                  # Domain Layer
│   │   ├── langgraph_workflow.py # LangGraph 워크플로우
│   │   └── extraction.py        # 기존 workflows/ 래핑
│   │
│   └── infrastructure/          # Infrastructure Layer
│       ├── storage/
│       │   ├── file_storage.py
│       │   └── job_repository.py
│       ├── ocr/
│       │   ├── tesseract_client.py
│       │   └── mathpix_client.py
│       └── queue/
│           └── job_queue.py
│
├── ui/                          # ✨ UI Layer (NEW)
│   │
│   ├── streamlit/               # Phase 1: Streamlit
│   │   └── app.py
│   │
│   └── nextjs/                  # Phase 2: Next.js (미래)
│       ├── app/
│       ├── components/
│       └── package.json
│
├── core/                        # 기존 Low-level 모듈 (유지)
│   ├── pdf_converter.py
│   ├── layout_detector.py
│   ├── column_separator.py
│   ├── ocr_engine.py
│   ├── mathpix_client.py
│   └── ...
│
├── AgentTools/                  # 기존 Agent 툴 (유지)
│   ├── types.py
│   ├── validation.py
│   ├── mathpix_validator.py
│   ├── mathpix_coordinate.py
│   └── ...
│
├── workflows/                   # 기존 워크플로우 (Phase 1에서 재사용)
│   ├── tesseract_only.py
│   ├── with_mathpix.py
│   └── with_agent.py
│
├── tests/                       # 테스트
│   ├── unit/                    # 단위 테스트
│   ├── integration/             # 통합 테스트
│   └── e2e/                     # E2E 테스트 (NEW)
│
├── scripts/                     # 유틸리티
├── samples/                     # 테스트 PDF
├── output/                      # 결과 (gitignore)
│
├── pyproject.toml
├── requirements.txt
├── .env.example
├── docker-compose.yml           # ✨ NEW
├── Dockerfile                   # ✨ NEW
│
├── README.md
├── APP_ARCHITECTURE.md          # ✨ 이 문서 (NEW)
└── NEXT_STEPS.md
```

### 4.2 마이그레이션 단계별 구조

#### **Phase 0: 현재 (v2.1)**
```
problem_cutter/
├── core/
├── AgentTools/
├── workflows/
└── tests/
```

#### **Phase 1: FastAPI + Streamlit (v3.0)**
```
problem_cutter/
├── api/                 # NEW
├── app/services/        # NEW
├── app/infrastructure/  # NEW
├── ui/streamlit/        # NEW
├── core/                # 재사용
├── AgentTools/          # 재사용
└── workflows/           # 재사용 (domain에서 래핑)
```

#### **Phase 2: LangGraph 통합 (v3.1)**
```
problem_cutter/
├── api/                        # 유지
├── app/
│   ├── services/               # 유지
│   ├── domain/
│   │   └── langgraph_workflow.py  # NEW
│   └── infrastructure/         # 유지
└── ...
```

#### **Phase 3: Next.js (v4.0)**
```
problem_cutter/
├── api/                 # 유지 (변경 없음!)
├── app/                 # 유지 (변경 없음!)
├── ui/
│   ├── streamlit/       # 유지 (레거시)
│   └── nextjs/          # NEW
└── ...
```

---

## 5. 데이터 흐름

### 5.1 작업 생성 흐름

```
사용자 (UI)
    ↓ POST /api/extract (PDF + API keys)
FastAPI (api/main.py)
    ↓ 파일 저장 + 요청 검증
JobService.create_job()
    ↓ job_id 생성 + DB 저장
JobQueue.enqueue(job_id)
    ↓ Redis에 작업 추가
Background Worker
    ↓ 큐에서 작업 가져오기
ExtractionService.execute()
    ↓ PDF 처리 시작
LangGraph Workflow
    ↓ 각 노드 실행
    ├→ Analyze
    ├→ Separate Columns
    ├→ Tesseract OCR
    ├→ Validate
    ├→ Mathpix (필요시)
    └→ Finalize
JobService.save_result()
    ↓ 결과 저장
WebSocket 알림
    ↓ 진행 상황 전송
사용자 (UI)
    ↓ 완료 알림 수신
Download ZIP
```

### 5.2 실시간 진행 상황 전송

```
Worker (ExtractionService)
    ↓ 진행 상황 업데이트
JobService.update_progress(job_id, {progress: 50, message: "OCR 중..."})
    ↓ Redis Pub/Sub
WebSocket Handler
    ↓ 연결된 클라이언트에게 전송
UI (Streamlit/Next.js)
    ↓ 진행률 바 업데이트
```

---

## 6. 기술 스택

### 6.1 백엔드

| 계층 | 기술 | 버전 | 역할 |
|------|------|------|------|
| **API** | FastAPI | 0.104+ | HTTP 서버, 비동기 |
| **Service** | Python | 3.13 | 비즈니스 로직 |
| **Domain** | LangGraph | 0.0.40+ | 워크플로우 오케스트레이션 |
| **Infrastructure** | Redis | 7.0+ | 작업 큐, Pub/Sub |
|  | PostgreSQL | 15+ | 작업 메타데이터 (선택) |

### 6.2 프론트엔드

| Phase | 기술 | 버전 | 용도 |
|-------|------|------|------|
| **Phase 1** | Streamlit | 1.28+ | 빠른 프로토타입 |
| **Phase 2** | Next.js | 14+ | 프로덕션 UI |
|  | React | 18+ | 컴포넌트 |
|  | TypeScript | 5+ | 타입 안전성 |

### 6.3 OCR

| 엔진 | 용도 | 비용 |
|------|------|------|
| **Tesseract** | 1차 OCR (빠름) | 무료 |
| **Mathpix** | 2차 검증 (정확함) | 유료 (API) |

### 6.4 배포

| 도구 | 용도 |
|------|------|
| **Docker** | 컨테이너화 |
| **Docker Compose** | 로컬 개발 |
| **AWS ECS / Cloud Run** | 프로덕션 배포 (미래) |

---

## 7. 마이그레이션 계획

### Phase 1: FastAPI + Streamlit (2-3주) ⭐ 우선

**목표**: 동작하는 웹 앱 (MVP)

**작업**:
1. ✅ Idris2 명세 작성 (완료)
2. ⏳ FastAPI 백엔드 구현
   - `api/main.py` - 엔드포인트
   - `app/services/` - JobService, ExtractionService
   - `app/infrastructure/` - FileStorage, JobRepository (메모리)
3. ⏳ Streamlit UI
   - `ui/streamlit/app.py` - 파일 업로드, 진행 상황, 다운로드
4. ⏳ 기존 workflows/ 래핑
   - `app/domain/extraction.py` - `workflows/with_mathpix.py` 호출

**완료 기준**:
- [ ] PDF 업로드 → 작업 생성 → 비동기 처리
- [ ] 실시간 진행 상황 확인
- [ ] ZIP 다운로드
- [ ] 2개 이상 동시 작업 처리 가능

**예상 시간**: 2-3주

---

### Phase 2: LangGraph 통합 (1-2주)

**목표**: 병렬 처리, 성능 최적화

**작업**:
1. ⏳ LangGraph 워크플로우 구현
   - `app/domain/langgraph_workflow.py`
   - 노드별 병렬 실행
2. ⏳ Redis 큐 통합
   - `app/infrastructure/queue/job_queue.py`
3. ⏳ 성능 벤치마크
   - 순차 vs 병렬 비교

**완료 기준**:
- [ ] 4페이지 PDF 처리 시간: 8분 → 2분 (4배 향상)
- [ ] 페이지별/컬럼별 병렬 실행
- [ ] 동시 10개 작업 처리 가능

**예상 시간**: 1-2주

---

### Phase 3: Next.js 프론트 (2-3주, 선택)

**목표**: 프로덕션급 UI/UX

**작업**:
1. ⏳ Next.js 프로젝트 초기화
   - `ui/nextjs/`
2. ⏳ 컴포넌트 개발
   - Upload, Progress, Download, History
3. ⏳ API 연동
   - FastAPI 엔드포인트 호출 (변경 없음!)

**완료 기준**:
- [ ] 반응형 UI
- [ ] SEO 최적화
- [ ] 작업 히스토리 관리

**예상 시간**: 2-3주

---

## 8. 다음 단계

**즉시 시작**:
1. ✅ Idris2 명세 작성 (완료)
2. ⏳ FastAPI 백엔드 구현 (api/main.py)
3. ⏳ Streamlit UI 프로토타입 (ui/streamlit/app.py)

**세부 계획**: [NEXT_STEPS.md](NEXT_STEPS.md) 참고

---

**최종 업데이트**: 2025-11-08
**다음 작업**: FastAPI 백엔드 구현

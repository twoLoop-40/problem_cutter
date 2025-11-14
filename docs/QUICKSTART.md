# 빠른 시작 가이드 (FastAPI + Streamlit)

## 🚀 Phase 1: SQLite + FastAPI + Streamlit

### 1. 의존성 설치

```bash
# Python 패키지 설치
uv sync

# 또는
pip install -r requirements.txt
```

### 2. FastAPI 백엔드 실행

```bash
# 터미널 1
cd problem_cutter
python -m api.main

# 또는 uvicorn 직접 실행
uvicorn api.main:app --reload --port 8000
```

서버가 시작되면:
- API 문서: http://localhost:8000/docs
- 루트: http://localhost:8000

### 3. Streamlit UI 실행

```bash
# 터미널 2
cd problem_cutter
streamlit run ui/streamlit/app.py
```

브라우저가 자동으로 열립니다:
- Streamlit UI: http://localhost:8501

### 4. 사용 방법

1. **PDF 업로드**:
   - Streamlit UI에서 PDF 파일 선택
   - (선택) Mathpix API 키 입력
   - "추출 시작" 버튼 클릭

2. **진행 상황 모니터링**:
   - 자동으로 진행률 표시 (0% → 100%)
   - 실시간 상태 업데이트

3. **결과 다운로드**:
   - 완료 후 "결과 다운로드" 버튼 클릭
   - ZIP 파일 다운로드 (개별 문제 이미지들)

---

## 📊 아키텍처 개요

```
┌─────────────────┐
│  Streamlit UI   │  (http://localhost:8501)
│  (프론트엔드)    │
└────────┬────────┘
         │ HTTP (requests)
         ↓
┌─────────────────┐
│   FastAPI       │  (http://localhost:8000)
│  (백엔드 API)    │
└────────┬────────┘
         │
    ┌────┴────┬────────────┬──────────┐
    ↓         ↓            ↓          ↓
┌────────┐ ┌──────┐ ┌──────────┐ ┌─────────┐
│ SQLite │ │ Jobs │ │Extraction│ │workflows│
│ (DB)   │ │Service│ │ Service  │ │ (Domain)│
└────────┘ └──────┘ └──────────┘ └─────────┘
```

---

## 🔍 API 엔드포인트

### POST /upload
PDF 업로드 및 추출 시작

**Request:**
```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@sample.pdf" \
  -F "mathpix_api_key=your_key" \
  -F "mathpix_app_id=your_id"
```

**Response:**
```json
{
  "job_id": "abc-123-def-456",
  "message": "작업이 시작되었습니다"
}
```

### GET /status/{job_id}
작업 상태 조회

**Response:**
```json
{
  "job_id": "abc-123-def-456",
  "status": "processing",
  "progress": {
    "percentage": 50,
    "message": "OCR 실행 중",
    "estimated_remaining": 30
  },
  "result": null,
  "error": null
}
```

### GET /download/{job_id}
결과 다운로드 (ZIP)

### DELETE /jobs/{job_id}
작업 삭제

### GET /jobs
모든 작업 조회

---

## 📁 디렉토리 구조

```
problem_cutter/
├── api/
│   └── main.py              # FastAPI 엔드포인트
├── app/
│   ├── models/
│   │   └── job.py           # SQLAlchemy 모델
│   ├── repositories/
│   │   └── job_repository.py
│   ├── services/
│   │   ├── job_service.py
│   │   └── extraction_service.py
│   └── database.py          # SQLite 설정
├── ui/
│   └── streamlit/
│       └── app.py           # Streamlit UI
├── workflows/               # 기존 추출 로직
├── core/                    # 저수준 모듈
├── AgentTools/              # 고수준 인터페이스
├── Specs/                   # Idris2 명세
├── uploads/                 # 업로드된 PDF
├── output/                  # 추출 결과
├── jobs.db                  # SQLite 데이터베이스
└── requirements.txt
```

---

## 🧪 테스트

### 1. API 테스트 (curl)

```bash
# 1. 업로드
curl -X POST http://localhost:8000/upload \
  -F "file=@samples/생명과학.pdf" \
  > response.json

# job_id 추출
JOB_ID=$(cat response.json | jq -r '.job_id')

# 2. 상태 조회
curl http://localhost:8000/status/$JOB_ID

# 3. 결과 다운로드
curl -O http://localhost:8000/download/$JOB_ID
```

### 2. Python 테스트

```python
import requests

# 업로드
with open("samples/생명과학.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/upload",
        files={"file": f}
    )
    job_id = response.json()["job_id"]

# 상태 폴링
import time
while True:
    status = requests.get(f"http://localhost:8000/status/{job_id}").json()
    print(f"{status['progress']['percentage']}% - {status['progress']['message']}")

    if status['status'] in ['completed', 'failed']:
        break

    time.sleep(2)

# 다운로드
if status['status'] == 'completed':
    result = requests.get(f"http://localhost:8000/download/{job_id}")
    with open("result.zip", "wb") as f:
        f.write(result.content)
```

---

## 🔧 설정

### 환경 변수 (.env)

```bash
# Mathpix API (선택)
MATHPIX_APP_KEY=your_app_key
MATHPIX_APP_ID=your_app_id

# 데이터베이스 (기본값: SQLite)
DATABASE_URL=sqlite:///./jobs.db

# API 서버
API_HOST=0.0.0.0
API_PORT=8000
```

---

## 📈 다음 단계 (Phase 2)

- [ ] LangGraph 워크플로우 통합
- [ ] 실제 workflows/with_mathpix.py 로직 연결
- [ ] WebSocket을 통한 실시간 진행률 업데이트
- [ ] Redis 추가 (선택)
- [ ] Next.js UI로 마이그레이션 (선택)
- [ ] Docker 컨테이너화
- [ ] CI/CD 파이프라인

---

## 🐛 문제 해결

### SQLite 락 오류
```bash
# 동시 쓰기가 너무 많을 경우
# → Redis로 마이그레이션 고려
```

### FastAPI 서버가 안 열림
```bash
# 포트 충돌 확인
lsof -i :8000

# 다른 포트 사용
uvicorn api.main:app --port 8001
```

### Streamlit 연결 실패
```bash
# API 서버가 실행 중인지 확인
curl http://localhost:8000

# API_BASE_URL 수정 (ui/streamlit/app.py)
API_BASE_URL = "http://localhost:8000"
```

---

**현재 진행률**: Phase 1 구현 완료 (FastAPI + SQLite + Streamlit) ✅

**마지막 업데이트**: 2025-11-14

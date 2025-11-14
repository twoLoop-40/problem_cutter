"""
FastAPI 메인 애플리케이션

명세: Specs/System/AppArchitecture.idr
- ApiEndpoint: POST /upload, GET /status/{job_id}, GET /download/{job_id}, DELETE /jobs/{job_id}
"""

import os
import shutil
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db, init_db
from app.models import JobStatus
from app.repositories import JobRepository
from app.services import JobService, ExtractionService

# FastAPI 앱 생성
app = FastAPI(
    title="PDF Problem Cutter API",
    description="PDF 시험지 문제 자동 추출 API (Formal Spec Driven)",
    version="1.0.0"
)

# 업로드 디렉토리
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ============================================================================
# Request/Response Models
# ============================================================================

class UploadResponse(BaseModel):
    """업로드 응답 (명세: UploadResponse)"""
    job_id: str
    message: str


class StatusResponse(BaseModel):
    """상태 조회 응답 (명세: StatusResponse)"""
    job_id: str
    status: str
    progress: dict
    result: Optional[dict]
    error: Optional[str]


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
def startup_event():
    """앱 시작 시 데이터베이스 초기화"""
    init_db()
    print("✅ 데이터베이스 초기화 완료")


# ============================================================================
# API Endpoints (명세: apiEndpoints)
# ============================================================================

@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mathpix_api_key: Optional[str] = None,
    mathpix_app_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    PDF 업로드 및 추출 작업 시작

    명세: POST /upload
    - Request: UploadRequest (pdfFile, mathpixApiKey, mathpixAppId)
    - Response: UploadResponse (jobId, message)
    """
    # 1. 파일 저장
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 2. Job 생성
    repo = JobRepository(db)
    job_service = JobService(repo)

    job = job_service.create_job(
        pdf_path=str(file_path),
        mathpix_api_key=mathpix_api_key,
        mathpix_app_id=mathpix_app_id
    )

    # 3. 백그라운드 작업 시작
    extraction_service = ExtractionService(job_service)

    background_tasks.add_task(
        extraction_service.execute_extraction,
        job_id=job.id,
        pdf_path=str(file_path),
        mathpix_api_key=mathpix_api_key,
        mathpix_app_id=mathpix_app_id
    )

    return UploadResponse(
        job_id=job.id,
        message=f"작업이 시작되었습니다. job_id: {job.id}"
    )


@app.get("/status/{job_id}", response_model=StatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    작업 상태 조회

    명세: GET /status/{job_id}
    - Response: StatusResponse
    """
    repo = JobRepository(db)
    job_service = JobService(repo)

    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")

    return StatusResponse(
        job_id=job.id,
        status=job.status,
        progress={
            "percentage": job.progress_percentage,
            "message": job.progress_message,
            "estimated_remaining": job.estimated_remaining
        },
        result=job.result,
        error=job.error
    )


@app.get("/download/{job_id}")
def download_result(job_id: str, db: Session = Depends(get_db)):
    """
    결과 다운로드

    명세: GET /download/{job_id}
    - Response: FileResponse (ZIP)
    """
    repo = JobRepository(db)
    job_service = JobService(repo)

    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")

    if job.status != JobStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail=f"작업이 완료되지 않았습니다. 현재 상태: {job.status}")

    if not job.result or "output_zip_path" not in job.result:
        raise HTTPException(status_code=500, detail="결과 파일 경로를 찾을 수 없습니다")

    zip_path = Path(job.result["output_zip_path"])
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail=f"결과 파일이 존재하지 않습니다: {zip_path}")

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=zip_path.name
    )


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)):
    """
    작업 삭제

    명세: DELETE /jobs/{job_id}
    """
    repo = JobRepository(db)
    job_service = JobService(repo)

    if not job_service.delete_job(job_id):
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")

    return {"message": f"작업이 삭제되었습니다: {job_id}"}


@app.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    """모든 작업 조회"""
    repo = JobRepository(db)
    job_service = JobService(repo)

    jobs = job_service.get_all_jobs()
    return [job.to_dict() for job in jobs]


@app.get("/")
def root():
    """API 루트"""
    return {
        "message": "PDF Problem Cutter API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "POST /upload - PDF 업로드",
            "GET /status/{job_id} - 작업 상태 조회",
            "GET /download/{job_id} - 결과 다운로드",
            "DELETE /jobs/{job_id} - 작업 삭제",
            "GET /jobs - 모든 작업 조회"
        ]
    }


# ============================================================================
# 실행
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

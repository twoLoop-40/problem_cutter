"""
Mathpix API 비동기 클라이언트
Idris2 명세 (.specs/MathpixApi.idr)를 기반으로 구현
"""

import asyncio
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import aiohttp
from dotenv import load_dotenv

load_dotenv()


# ============================================================================
# Idris2 명세에서 정의한 타입들을 Python으로 구현
# ============================================================================

class ApiStatus(Enum):
    """API 상태 (MathpixApi.idr의 ApiStatus)"""
    RECEIVED = "received"
    LOADED = "loaded"
    SPLIT = "split"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ConversionFormat(Enum):
    """변환 포맷 (MathpixApi.idr의 ConversionFormat)"""
    MD = ".md"             # Markdown
    DOCX = ".docx"         # Word
    TEX_ZIP = ".tex.zip"   # LaTeX (zip)
    HTML = ".html"         # HTML
    LINES_JSON = ".lines.json"  # 구조화된 JSON


@dataclass
class Progress:
    """진행 상황 (MathpixApi.idr의 Progress)"""
    num_pages: int
    num_pages_completed: int
    percent_done: int  # 0-100

    def is_valid(self) -> bool:
        """isValidProgress: 진행률이 유효한가?"""
        return 0 <= self.percent_done <= 100


@dataclass
class UploadRequest:
    """업로드 요청 (MathpixApi.idr의 UploadRequest)"""
    pdf_path: str
    formats: List[ConversionFormat]


@dataclass
class UploadResponse:
    """업로드 응답 (MathpixApi.idr의 UploadResponse)"""
    pdf_id: str
    status: ApiStatus


@dataclass
class StatusResponse:
    """상태 확인 응답 (MathpixApi.idr의 StatusResponse)"""
    pdf_id: str
    status: ApiStatus
    progress: Progress


@dataclass
class DownloadResult:
    """다운로드 결과 (MathpixApi.idr의 DownloadResult)"""
    pdf_id: str
    format: ConversionFormat
    content: str


@dataclass
class RetryConfig:
    """재시도 설정 (MathpixApi.idr의 RetryConfig)"""
    max_retries: int
    current_retry: int = 0

    def can_retry(self) -> bool:
        """canRetry: 재시도 가능한가?"""
        return self.current_retry < self.max_retries

    def increment(self) -> 'RetryConfig':
        """incrementRetry: 재시도 횟수 증가"""
        return RetryConfig(self.max_retries, self.current_retry + 1)


# ============================================================================
# 상태 전환 검증 (MathpixApi.idr의 ValidTransition)
# ============================================================================

VALID_TRANSITIONS = {
    ApiStatus.RECEIVED: [ApiStatus.LOADED, ApiStatus.ERROR],
    ApiStatus.LOADED: [ApiStatus.SPLIT, ApiStatus.ERROR],
    ApiStatus.SPLIT: [ApiStatus.PROCESSING, ApiStatus.COMPLETED, ApiStatus.ERROR],  # SPLIT->COMPLETED 가능
    ApiStatus.PROCESSING: [ApiStatus.COMPLETED, ApiStatus.ERROR, ApiStatus.PROCESSING],
}


def is_valid_transition(old: ApiStatus, new: ApiStatus) -> bool:
    """updateStatus: 유효한 상태 전환인가?"""
    if old == new:
        return True
    return new in VALID_TRANSITIONS.get(old, [])


def is_terminal(status: ApiStatus) -> bool:
    """isTerminal: 완료 상태인가?"""
    return status in [ApiStatus.COMPLETED, ApiStatus.ERROR]


def is_downloadable(status: ApiStatus) -> bool:
    """isDownloadable: 다운로드 가능한가?"""
    return status == ApiStatus.COMPLETED


def needs_polling(status: ApiStatus) -> bool:
    """needsPolling: 폴링이 계속 필요한가?"""
    return not is_terminal(status)


# ============================================================================
# Mathpix API 클라이언트
# ============================================================================

class MathpixClient:
    """
    Mathpix API 비동기 클라이언트

    Idris2 명세의 워크플로우를 구현:
    1. UploadResult (PDF 업로드)
    2. PollResult (상태 폴링)
    3. DownloadOutcome (결과 다운로드)
    """

    BASE_URL = "https://api.mathpix.com/v3"

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_key: Optional[str] = None,
        poll_interval: float = 2.0,
        timeout: int = 300
    ):
        self.app_id = app_id or os.getenv('MATHPIX_APP_ID')
        self.app_key = app_key or os.getenv('MATHPIX_APP_KEY')
        self.poll_interval = poll_interval
        self.timeout = timeout

        if not self.app_id or not self.app_key:
            raise ValueError("Mathpix API credentials not found")

        self.headers = {
            'app_id': self.app_id,
            'app_key': self.app_key
        }

    async def upload_pdf(self, request: UploadRequest) -> UploadResponse:
        """
        1단계: PDF 업로드 (UploadResult)

        명세 보장: 성공 시 status = RECEIVED

        Note: Mathpix API는 두 가지 방식을 지원:
        1. JSON with URL - URL로 PDF 전달
        2. Multipart form - 파일 직접 업로드

        여기서는 multipart form 방식 사용
        """
        pdf_path = Path(request.pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # 변환 포맷 준비
        import json
        conversion_formats = {}
        for fmt in request.formats:
            # .tex.zip -> tex.zip, .md -> md
            key = fmt.value.lstrip('.')
            conversion_formats[key] = True

        url = f"{self.BASE_URL}/pdf"

        async with aiohttp.ClientSession() as session:
            with open(pdf_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=pdf_path.name, content_type='application/pdf')

                # conversion_formats를 JSON 문자열이 아닌 개별 필드로 추가
                for fmt, enabled in conversion_formats.items():
                    data.add_field(f'conversion_formats[{fmt}]', str(enabled).lower())

                async with session.post(url, headers=self.headers, data=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Upload failed: {resp.status} - {error_text}")

                    result = await resp.json()
                    print(f"Debug - API response: {result}")
                    pdf_id = result.get('pdf_id')
                    status_str = result.get('status', 'received')

                    # 상태 파싱
                    status = ApiStatus(status_str)

                    # 명세 검증: 업로드 성공 시 RECEIVED 상태여야 함
                    if status != ApiStatus.RECEIVED:
                        print(f"Warning: Expected RECEIVED but got {status}")

                    return UploadResponse(pdf_id=pdf_id, status=status)

    async def check_status(self, pdf_id: str) -> StatusResponse:
        """
        상태 확인
        """
        url = f"{self.BASE_URL}/pdf/{pdf_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Status check failed: {resp.status} - {error_text}")

                result = await resp.json()

                # 상태 파싱
                status_str = result.get('status', 'processing')
                status = ApiStatus(status_str) if status_str != 'error' else ApiStatus.ERROR

                # 진행 상황 파싱
                progress = Progress(
                    num_pages=result.get('num_pages', 0),
                    num_pages_completed=result.get('num_pages_completed', 0),
                    percent_done=result.get('percent_done', 0)
                )

                # 진행률 검증
                if not progress.is_valid():
                    print(f"Warning: Invalid progress {progress.percent_done}%")

                return StatusResponse(
                    pdf_id=pdf_id,
                    status=status,
                    progress=progress
                )

    async def poll_until_complete(
        self,
        pdf_id: str,
        retry_config: Optional[RetryConfig] = None
    ) -> StatusResponse:
        """
        2단계: 상태 폴링 (PollResult)

        완료될 때까지 폴링하고 최종 StatusResponse 반환
        명세 보장: 반환 시 status = COMPLETED 또는 ERROR
        """
        if retry_config is None:
            retry_config = RetryConfig(max_retries=int(self.timeout / self.poll_interval))

        start_time = asyncio.get_event_loop().time()
        last_status = None

        while retry_config.can_retry():
            # 타임아웃 체크
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.timeout:
                raise TimeoutError(f"Polling timeout after {self.timeout}s")

            try:
                status_resp = await self.check_status(pdf_id)

                # 상태 전환 검증
                if last_status and not is_valid_transition(last_status, status_resp.status):
                    print(f"Warning: Invalid transition {last_status} -> {status_resp.status}")

                last_status = status_resp.status

                # 진행 상황 출력
                p = status_resp.progress
                print(f"[{pdf_id[:8]}] {status_resp.status.value}: "
                      f"{p.num_pages_completed}/{p.num_pages} pages ({p.percent_done}%)")

                # 완료 상태 체크
                if is_terminal(status_resp.status):
                    if status_resp.status == ApiStatus.COMPLETED:
                        print(f"✅ Processing completed!")
                        return status_resp
                    else:
                        raise Exception(f"Processing failed: {status_resp.status}")

                # 다음 폴링까지 대기
                await asyncio.sleep(self.poll_interval)
                retry_config = retry_config.increment()

            except Exception as e:
                if not retry_config.can_retry():
                    raise
                print(f"Polling error (retrying): {e}")
                retry_config = retry_config.increment()
                await asyncio.sleep(self.poll_interval)

        raise Exception(f"Max retries exceeded")

    async def download_result(
        self,
        pdf_id: str,
        format: ConversionFormat
    ) -> DownloadResult:
        """
        3단계: 결과 다운로드 (DownloadOutcome)

        명세 보장: COMPLETED 상태에서만 호출되어야 함
        """
        url = f"{self.BASE_URL}/pdf/{pdf_id}{format.value}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Download failed: {resp.status} - {error_text}")

                # zip 파일은 바이너리로 읽기
                if 'zip' in format.value:
                    content = await resp.read()  # bytes
                    content_str = f"<binary content: {len(content)} bytes>"
                else:
                    content_str = await resp.text()  # str
                    content = content_str.encode('utf-8')

                return DownloadResult(
                    pdf_id=pdf_id,
                    format=format,
                    content=content_str if 'zip' not in format.value else content
                )

    async def download_lines_json(self, pdf_id: str) -> Dict[str, Any]:
        """
        .lines.json 포맷 다운로드 및 파싱

        명세: MathpixCoordinateExtraction.Implementation.parseMathpixJson

        Returns:
            {
                "pages": [
                    {
                        "page": 1,
                        "page_width": 1000,
                        "page_height": 3000,
                        "lines": [
                            {
                                "text": "3. 다음은...",
                                "region": {
                                    "top_left_x": 245,
                                    "top_left_y": 2374,
                                    "width": 25,
                                    "height": 27
                                },
                                "confidence": 0.95,
                                "line": 10,
                                "column": 1
                            }
                        ]
                    }
                ]
            }
        """
        result = await self.download_result(pdf_id, ConversionFormat.LINES_JSON)

        # JSON 파싱
        import json
        try:
            lines_data = json.loads(result.content)
            return lines_data
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse .lines.json: {e}")

    async def process_pdf(
        self,
        pdf_path: str,
        formats: Optional[List[ConversionFormat]] = None
    ) -> Dict[ConversionFormat, DownloadResult]:
        """
        전체 워크플로우 실행 (OcrWorkflow)

        1. 업로드 (UploadResult)
        2. 폴링 (PollResult)
        3. 다운로드 (DownloadOutcome)

        명세 검증: 각 단계의 상태 보장
        """
        if formats is None:
            formats = [ConversionFormat.MD]

        # 1. 업로드
        print(f"📤 Uploading: {pdf_path}")
        upload_req = UploadRequest(pdf_path=pdf_path, formats=formats)
        upload_resp = await self.upload_pdf(upload_req)
        print(f"✅ Uploaded: {upload_resp.pdf_id} (status: {upload_resp.status.value})")

        # 2. 폴링
        print(f"⏳ Polling for completion...")
        final_resp = await self.poll_until_complete(upload_resp.pdf_id)

        # 3. 다운로드 (명세 검증: COMPLETED 상태인지 확인)
        if not is_downloadable(final_resp.status):
            raise Exception(f"Cannot download: status is {final_resp.status}")

        print(f"⬇️  Downloading results...")
        results = {}
        for fmt in formats:
            result = await self.download_result(upload_resp.pdf_id, fmt)
            results[fmt] = result
            print(f"✅ Downloaded: {fmt.value} ({len(result.content)} chars)")

        return results


# ============================================================================
# 예제 사용법
# ============================================================================

async def example_usage():
    """사용 예제"""
    client = MathpixClient()

    # 샘플 PDF 처리
    pdf_path = "samples/고3_사회탐구_사회문화_1p.pdf"

    results = await client.process_pdf(
        pdf_path=pdf_path,
        formats=[ConversionFormat.MD, ConversionFormat.TEX_ZIP]
    )

    # 결과 저장 (샘플명 기반 디렉토리)
    sample_name = Path(pdf_path).stem
    output_dir = Path(f"output/{sample_name}")
    output_dir.mkdir(parents=True, exist_ok=True)

    for fmt, result in results.items():
        # mathpix_raw.md, result.tex.zip 등
        if fmt == ConversionFormat.MD:
            output_path = output_dir / "mathpix_raw.md"
        else:
            output_path = output_dir / f"result{fmt.value}"

        # zip 파일은 바이너리로 저장
        if isinstance(result.content, bytes):
            output_path.write_bytes(result.content)
        else:
            output_path.write_text(result.content, encoding='utf-8')

        print(f"💾 Saved: {output_path}")


if __name__ == '__main__':
    asyncio.run(example_usage())

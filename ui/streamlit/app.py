"""
Streamlit UI for PDF Problem Cutter

명세: Specs/System/AppArchitecture.idr
Phase 1: Streamlit (빠른 프로토타이핑)
Phase 2: Next.js로 마이그레이션 (선택)
"""

import time
import requests
import streamlit as st
from pathlib import Path

# API 서버 주소
API_BASE_URL = "http://localhost:8000"


def check_backend_connection():
    """백엔드 서버 연결 상태 확인"""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=2)
        if response.status_code == 200:
            st.success("✅ 백엔드 서버 연결됨")
            return True
    except requests.exceptions.ConnectionError:
        st.error("❌ 백엔드 서버에 연결할 수 없습니다")
        st.warning(f"서버가 실행 중인지 확인하세요: `uv run python -m api.main`")
        st.info(f"서버 주소: {API_BASE_URL}")
        return False
    except requests.exceptions.Timeout:
        st.warning("⚠️ 백엔드 서버 응답 시간 초과")
        return False
    except Exception as e:
        st.error(f"❌ 연결 오류: {e}")
        return False


def main():
    st.set_page_config(
        page_title="PDF Problem Cutter",
        page_icon="✂️",
        layout="centered",  # "wide"에서 "centered"로 변경
        initial_sidebar_state="expanded"
    )

    st.title("✂️ PDF Problem Cutter")
    st.markdown("PDF 시험지에서 문제를 자동으로 추출합니다")
    st.caption("Powered by Formal Spec Driven Development (Idris2)")

    # 백엔드 연결 상태 확인
    check_backend_connection()

    # 사이드바: 설정
    with st.sidebar:
        st.header("⚙️ 설정")

        use_mathpix = st.checkbox("Mathpix 사용 (더 정확)", value=False)

        mathpix_api_key = None
        mathpix_app_id = None

        if use_mathpix:
            mathpix_api_key = st.text_input(
                "Mathpix API Key",
                type="password",
                help="Mathpix API 키를 입력하세요"
            )
            mathpix_app_id = st.text_input(
                "Mathpix App ID",
                type="password",
                help="Mathpix App ID를 입력하세요"
            )

        st.divider()
        st.markdown("### 📊 작업 현황")

        # 모든 작업 조회
        if st.button("🔄 새로고침"):
            st.rerun()

        try:
            response = requests.get(f"{API_BASE_URL}/jobs")
            if response.status_code == 200:
                jobs = response.json()
                st.metric("전체 작업", len(jobs))

                pending = sum(1 for j in jobs if j["status"] == "pending")
                processing = sum(1 for j in jobs if j["status"] == "processing")
                completed = sum(1 for j in jobs if j["status"] == "completed")
                failed = sum(1 for j in jobs if j["status"] == "failed")

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("대기", pending)
                    st.metric("처리 중", processing)
                with col2:
                    st.metric("완료", completed)
                    st.metric("실패", failed)
        except Exception as e:
            st.error(f"API 연결 실패: {e}")

    # 메인 영역: 업로드
    st.header("📤 PDF 업로드")

    uploaded_file = st.file_uploader(
        "PDF 파일을 선택하세요",
        type=["pdf"],
        help="시험지 PDF 파일 (단일 페이지 또는 다중 페이지)"
    )

    if uploaded_file:
        st.success(f"✅ 파일 선택됨: {uploaded_file.name}")

        if st.button("🚀 추출 시작", type="primary"):
            with st.spinner("업로드 중..."):
                # API 호출
                files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
                data = {}

                if use_mathpix and mathpix_api_key and mathpix_app_id:
                    data["mathpix_api_key"] = mathpix_api_key
                    data["mathpix_app_id"] = mathpix_app_id

                try:
                    response = requests.post(
                        f"{API_BASE_URL}/upload",
                        files=files,
                        data=data
                    )

                    if response.status_code == 200:
                        result = response.json()
                        job_id = result["job_id"]

                        st.success(f"✅ {result['message']}")
                        st.session_state["current_job_id"] = job_id

                        # 상태 조회 페이지로 전환
                        st.rerun()
                    else:
                        st.error(f"❌ 업로드 실패: {response.text}")

                except Exception as e:
                    st.error(f"❌ 오류: {e}")

    # 작업 상태 모니터링
    if "current_job_id" in st.session_state:
        st.divider()
        show_job_status(st.session_state["current_job_id"])

    # 모든 작업 리스트
    st.divider()
    st.header("📋 작업 목록")
    show_job_list()


def show_job_status(job_id: str):
    """작업 상태 표시"""
    st.subheader(f"📊 작업 상태: {job_id[:8]}...")

    try:
        response = requests.get(f"{API_BASE_URL}/status/{job_id}")

        if response.status_code == 200:
            job = response.json()

            # 상태 표시
            status = job["status"]
            progress = job["progress"]

            col1, col2, col3 = st.columns(3)

            with col1:
                status_emoji = {
                    "pending": "⏳",
                    "processing": "⚙️",
                    "completed": "✅",
                    "failed": "❌"
                }
                st.metric("상태", f"{status_emoji.get(status, '❓')} {status}")

            with col2:
                st.metric("진행률", f"{progress['percentage']}%")

            with col3:
                remaining = progress.get("estimated_remaining")
                if remaining:
                    st.metric("예상 남은 시간", f"{remaining}초")

            # 진행 바
            st.progress(progress["percentage"] / 100)
            st.info(progress["message"])

            # 완료 시 결과 표시
            if status == "completed" and job["result"]:
                st.success("✅ 추출 완료!")

                result = job["result"]
                st.json(result)

                # 다운로드 버튼 (실제 파일 다운로드)
                zip_path = result.get("output_zip_path")
                if zip_path:
                    try:
                        # 직접 ZIP 파일 읽기
                        with open(zip_path, "rb") as f:
                            zip_data = f.read()

                        st.download_button(
                            label="📥 결과 다운로드",
                            data=zip_data,
                            file_name=Path(zip_path).name,
                            mime="application/zip",
                            type="primary"
                        )
                    except FileNotFoundError:
                        st.warning(f"⚠️ 파일을 찾을 수 없습니다: {zip_path}")
                        st.markdown(f"[API 다운로드 시도]({API_BASE_URL}/download/{job_id})")
                else:
                    st.warning("다운로드 경로가 없습니다")

            # 실패 시 에러 표시
            elif status == "failed":
                st.error(f"❌ 추출 실패: {job['error']}")

            # 처리 중이면 자동 새로고침
            elif status in ["pending", "processing"]:
                time.sleep(2)
                st.rerun()

        else:
            st.error(f"작업을 찾을 수 없습니다: {job_id}")

    except Exception as e:
        st.error(f"상태 조회 실패: {e}")


def show_job_list():
    """모든 작업 리스트 표시"""
    try:
        response = requests.get(f"{API_BASE_URL}/jobs")

        if response.status_code == 200:
            jobs = response.json()

            if not jobs:
                st.info("작업이 없습니다")
                return

            for job in jobs[:10]:  # 최근 10개만
                with st.expander(f"{job['job_id'][:8]}... - {job['status']}"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.text(f"PDF: {Path(job['pdf_path']).name}")
                        st.text(f"상태: {job['status']}")
                        st.text(f"진행률: {job['progress']['percentage']}%")

                    with col2:
                        st.text(f"생성: {job['created_at']}")

                        if st.button("📊 상태 보기", key=f"view_{job['job_id']}"):
                            st.session_state["current_job_id"] = job['job_id']
                            st.rerun()

                        if st.button("🗑️ 삭제", key=f"delete_{job['job_id']}"):
                            requests.delete(f"{API_BASE_URL}/jobs/{job['job_id']}")
                            st.success("삭제됨")
                            st.rerun()

    except Exception as e:
        st.error(f"작업 목록 조회 실패: {e}")


if __name__ == "__main__":
    main()

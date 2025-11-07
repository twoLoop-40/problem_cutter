"""PDF Problem Extraction Workflows

Available workflows:
- tesseract_only: Tesseract OCR only (basic)
- with_agent: Tesseract with Agent auto-retry
- with_mathpix: 2-stage OCR (Tesseract → Mathpix) - RECOMMENDED
- langgraph_parallel: LangGraph parallel execution (TODO)

Usage:
    uv run python -m workflows.with_mathpix samples/생명과학.pdf
"""

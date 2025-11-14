||| Project Reorganization Specification (v4.0)
|||
||| 현재 프로젝트 구조 문제점:
||| 1. core/, AgentTools/, workflows/ 간 기능 중복
||| 2. 파일 추출 로직이 parallel_workflow.py에만 있어서 재사용 불가
||| 3. Agent가 사용하기 어려운 구조 (툴 형태 아님)
|||
||| 재구성 목표:
||| 1. AgentTools/ 를 유일한 진입점으로 만들기
||| 2. core/ 는 저수준 구현만 (AgentTools가 사용)
||| 3. app/ 는 FastAPI + LangGraph 통합만
||| 4. 중복/레거시 파일 제거

module System.ProjectReorganization

import Data.List
import System.AppArchitecture
import System.Agent.Tools

%default total

--------------------------------------------------------------------------------
-- 현재 상태 분석
--------------------------------------------------------------------------------

||| 프로젝트 디렉토리 구조
public export
data ProjectDir : Type where
  AgentToolsDir : ProjectDir  -- LLM Agent용 고수준 툴
  CoreDir       : ProjectDir  -- 저수준 구현 (PDF, OCR, OpenCV)
  AppDir        : ProjectDir  -- FastAPI + LangGraph 통합
  ApiDir        : ProjectDir  -- FastAPI 라우터
  UiDir         : ProjectDir  -- Streamlit UI
  WorkflowsDir  : ProjectDir  -- 레거시 (삭제 대상)
  ScriptsDir    : ProjectDir  -- 레거시 (삭제 대상)
  ExamplesDir   : ProjectDir  -- 레거시 (삭제 대상)
  TestsDir      : ProjectDir  -- Pytest 테스트

||| 파일 카테고리
public export
data FileCategory : Type where
  KeepFile   : FileCategory  -- 유지
  MoveFile   : ProjectDir -> FileCategory  -- 다른 디렉토리로 이동
  DeleteFile : String -> FileCategory  -- 삭제 (이유 명시)
  MergeFile  : String -> FileCategory  -- 다른 파일과 병합

--------------------------------------------------------------------------------
-- AgentTools/ 재구성 (Agent 진입점)
--------------------------------------------------------------------------------

||| AgentTools 모듈 구조 (최종)
public export
data AgentToolModule : Type where
  TypesModule      : AgentToolModule  -- types.py (ToolResult, ToolDiagnostics)
  PdfModule        : AgentToolModule  -- pdf.py (summarize_pdf, load_pdf_images)
  LayoutModule     : AgentToolModule  -- layout.py (detect_page_layout)
  OcrModule        : AgentToolModule  -- ocr.py (run_ocr_on_region)
  ExtractionModule : AgentToolModule  -- extraction.py (extract_problems)
  WorkflowModule   : AgentToolModule  -- workflow.py (run_full_workflow)
  ConfigModule     : AgentToolModule  -- config.py (설정 관리)

||| extraction.py 의 기능 정의
public export
record ExtractionTool where
  constructor MkExtractionTool
  ||| 문제 영역 추출 (핵심 기능 - 현재 누락됨!)
  extractProblemRegions : String -> List Nat -> IO (List (Nat, Image))

  ||| 문제 경계 찾기
  findProblemBoundaries : String -> IO (List ProblemMarker)

  ||| 검증
  validateExtraction : List Nat -> List Nat -> IO Bool

--------------------------------------------------------------------------------
-- core/ 재구성 (저수준 구현)
--------------------------------------------------------------------------------

||| core 모듈 구조 (최종)
public export
data CoreModule : Type where
  -- PDF 처리
  PdfConverterModule : CoreModule  -- pdf_converter.py

  -- OCR 엔진
  OcrEngineModule    : CoreModule  -- ocr_engine.py (파서 포함)
  OcrInterfaceModule : CoreModule  -- ocr/interface.py
  OcrTesseractModule : CoreModule  -- ocr/tesseract_plugin.py
  OcrRegistryModule  : CoreModule  -- ocr/registry.py

  -- 레이아웃 감지
  LayoutDetectorModule : CoreModule  -- layout_detector.py

  -- 기본 타입
  BaseModule : CoreModule  -- base.py (Coord, BBox, VLine)

||| 삭제 대상 core 파일들
public export
coreLegacyFiles : List (String, String)
coreLegacyFiles =
  [ ("core/problem_analyzer.py", "기능이 AgentTools/extraction.py 로 통합됨")
  , ("core/problem_boundary.py", "기능이 AgentTools/extraction.py 로 통합됨")
  , ("core/problem_cutter.py", "기능이 AgentTools/extraction.py 로 통합됨")
  , ("core/problem_extractor.py", "기능이 AgentTools/extraction.py 로 통합됨")
  , ("core/column_linearizer.py", "레이아웃 감지로 충분")
  , ("core/result_validator.py", "검증 로직이 AgentTools/extraction.py 로 통합됨")
  , ("core/output_generator.py", "파일 생성은 workflow에서 직접 처리")
  , ("core/workflow.py", "LangGraph로 대체됨")
  ]

--------------------------------------------------------------------------------
-- app/ 재구성 (FastAPI + LangGraph)
--------------------------------------------------------------------------------

||| app 모듈 구조 (최종)
public export
data AppModule : Type where
  -- 서비스
  LangGraphServiceModule : AppModule  -- services/langgraph_service.py
  JobServiceModule       : AppModule  -- services/job_service.py

  -- Agent
  ParallelWorkflowModule : AppModule  -- agents/parallel_workflow.py (수정 필요)
  StateModule            : AppModule  -- agents/state.py

  -- 모델
  ModelsModule : AppModule  -- models.py

||| parallel_workflow.py 수정 필요 사항
public export
record WorkflowRefactoring where
  constructor MkWorkflowRefactoring
  ||| extract_problem_regions() 함수를 AgentTools/extraction.py로 이동
  moveExtractionLogic : Bool

  ||| generate_files_node()는 AgentTools.extraction.extract_problem_regions() 호출
  useAgentTool : Bool

  ||| OCR import를 core.ocr로 통일
  fixOcrImports : Bool

--------------------------------------------------------------------------------
-- workflows/, scripts/, examples/ 삭제
--------------------------------------------------------------------------------

||| 삭제 대상 디렉토리
public export
deleteDirs : List (String, String)
deleteDirs =
  [ ("workflows/", "LangGraph로 대체됨")
  , ("scripts/", "더 이상 사용하지 않음")
  , ("examples/detect_layout.py", "tests/로 이동")
  ]

--------------------------------------------------------------------------------
-- 재구성 계획
--------------------------------------------------------------------------------

||| 재구성 단계
public export
data ReorgStep : Type where
  Step1_MoveExtraction : ReorgStep  -- extract_problem_regions를 AgentTools로
  Step2_DeleteLegacy   : ReorgStep  -- core/problem_*.py 삭제
  Step3_FixImports     : ReorgStep  -- parallel_workflow.py import 수정
  Step4_DeleteDirs     : ReorgStep  -- workflows/, scripts/, examples/ 삭제
  Step5_UpdateTests    : ReorgStep  -- 테스트 경로 수정
  Step6_VerifyBuild    : ReorgStep  -- 전체 테스트 실행

||| Step1: AgentTools/extraction.py 에 추가할 함수
public export
step1_newFunctions : List String
step1_newFunctions =
  [ "extract_problem_regions(image_path, found_problems) -> ToolResult"
  , "  - OCR 실행 (Tesseract)"
  , "  - 문제 번호 파싱"
  , "  - Y 좌표 기준 정렬"
  , "  - 문제 영역 crop"
  , "  - ToolResult 형태로 반환"
  ]

||| Step2: 삭제할 core 파일 목록
public export
step2_deleteFiles : List String
step2_deleteFiles =
  [ "core/problem_analyzer.py"
  , "core/problem_boundary.py"
  , "core/problem_cutter.py"
  , "core/problem_extractor.py"
  , "core/column_linearizer.py"
  , "core/result_validator.py"
  , "core/output_generator.py"
  , "core/workflow.py"
  ]

||| Step3: parallel_workflow.py 수정 사항
public export
step3_fixParallelWorkflow : List String
step3_fixParallelWorkflow =
  [ "from AgentTools.extraction import extract_problem_regions"
  , "from core.ocr.interface import OcrInput, OcrOutput"
  , "from core.ocr.tesseract_plugin import TesseractEngine"
  , "from core.ocr_engine import parse_problem_number"
  , ""
  , "def generate_files_node(state):"
  , "    for col_state in page_states:"
  , "        result = extract_problem_regions("
  , "            image_path=col_state['image_path'],"
  , "            found_problems=col_state['found_problems']"
  , "        )"
  , "        if result.success:"
  , "            for prob_num, img in result.data['regions']:"
  , "                cv2.imwrite(f'{prob_num}_prb.png', img)"
  ]

||| Step4: 삭제할 디렉토리
public export
step4_deleteDirs : List String
step4_deleteDirs =
  [ "workflows/"
  , "scripts/"
  , "examples/"
  ]

||| Step5: 업데이트할 테스트
public export
step5_updateTests : List (String, String)
step5_updateTests =
  [ ("tests/test_problem_extractor.py", "삭제 (core/problem_extractor.py 삭제됨)")
  , ("tests/test_problem_boundary.py", "삭제 (core/problem_boundary.py 삭제됨)")
  , ("examples/detect_layout.py", "tests/manual/test_layout.py로 이동")
  ]

--------------------------------------------------------------------------------
-- 최종 디렉토리 구조
--------------------------------------------------------------------------------

||| 최종 디렉토리 구조
public export
finalStructure : String
finalStructure = """
problem_cutter/
├── Specs/System/           # Idris2 명세 (변경 없음)
│
├── AgentTools/            # 🔥 Agent 진입점 (유일한 고수준 API)
│   ├── __init__.py
│   ├── types.py           # ToolResult, ToolDiagnostics
│   ├── config.py          # 설정 관리
│   ├── pdf.py             # summarize_pdf, load_pdf_images
│   ├── layout.py          # detect_page_layout, summarize_layout
│   ├── ocr.py             # run_ocr_on_region
│   ├── extraction.py      # 🆕 extract_problem_regions, find_boundaries, validate
│   └── workflow.py        # run_full_workflow_stub
│
├── core/                  # 저수준 구현 (AgentTools가 사용)
│   ├── __init__.py
│   ├── base.py            # Coord, BBox, VLine
│   ├── pdf_converter.py   # PDF → 이미지
│   ├── layout_detector.py # 컬럼 감지
│   ├── ocr_engine.py      # parse_problem_number
│   └── ocr/
│       ├── interface.py   # OcrInput, OcrOutput
│       ├── tesseract_plugin.py
│       └── registry.py
│
├── app/                   # FastAPI + LangGraph
│   ├── models.py
│   ├── services/
│   │   ├── langgraph_service.py
│   │   └── job_service.py
│   └── agents/
│       ├── state.py
│       └── parallel_workflow.py  # 🔧 AgentTools 사용하도록 수정
│
├── api/                   # FastAPI 라우터
│   ├── main.py
│   └── routes/
│
├── ui/                    # Streamlit
│   └── streamlit/
│       └── app.py
│
├── tests/                 # Pytest
│   ├── test_base.py
│   ├── test_layout_detector.py
│   ├── test_ocr_engine.py
│   └── manual/            # 수동 테스트
│       └── test_layout.py
│
└── output/                # 결과 (gitignore)
"""

--------------------------------------------------------------------------------
-- 검증 (재구성 후 확인 사항)
--------------------------------------------------------------------------------

||| 재구성 후 검증 체크리스트
public export
data VerificationCheck : Type where
  AgentToolsComplete   : VerificationCheck  -- AgentTools 모든 함수 동작
  NoCoreDuplicates     : VerificationCheck  -- core에 중복 파일 없음
  WorkflowUsesTools    : VerificationCheck  -- parallel_workflow가 AgentTools 사용
  AllTestsPass         : VerificationCheck  -- pytest 전체 통과
  SamplePdfWorks       : VerificationCheck  -- 샘플 PDF 추출 성공
  NoLegacyImports      : VerificationCheck  -- 레거시 import 없음

||| 검증 절차
public export
verificationSteps : List String
verificationSteps =
  [ "1. pytest -v  # 모든 테스트 통과"
  , "2. uv run python test_parallel_workflow.py  # 샘플 추출 성공"
  , "3. grep -r 'from core.problem_' **/*.py  # 레거시 import 없음"
  , "4. grep -r 'import workflows' **/*.py  # workflows import 없음"
  , "5. Streamlit UI에서 전체 플로우 테스트"
  ]

--------------------------------------------------------------------------------
-- 실행 계획
--------------------------------------------------------------------------------

||| 재구성 실행 순서 (안전하게)
public export
executionPlan : List String
executionPlan =
  [ "=== Step 1: AgentTools/extraction.py 구현 ==="
  , "1. extract_problem_regions() 함수 작성"
  , "2. find_problem_boundaries() 함수 작성"
  , "3. validate_extraction() 함수 작성"
  , ""
  , "=== Step 2: parallel_workflow.py 수정 ==="
  , "1. extract_problem_regions()를 AgentTools.extraction에서 import"
  , "2. generate_files_node()에서 새 함수 사용"
  , "3. 테스트: uv run python test_parallel_workflow.py"
  , ""
  , "=== Step 3: 레거시 파일 삭제 ==="
  , "1. core/problem_*.py 파일 8개 삭제"
  , "2. workflows/, scripts/, examples/ 디렉토리 삭제"
  , "3. 테스트: pytest -v"
  , ""
  , "=== Step 4: import 정리 ==="
  , "1. grep으로 레거시 import 찾기"
  , "2. 모두 AgentTools 또는 core로 수정"
  , "3. 최종 테스트: 전체 플로우"
  ]

--------------------------------------------------------------------------------
-- 증명: 재구성이 기능을 보존함
--------------------------------------------------------------------------------

||| 재구성 전후 기능 동일성
||| (모든 기능이 AgentTools로 이동하거나 삭제되거나 둘 중 하나)
public export
functionPreservation : (before : List String) -> (after : List String) -> Type
functionPreservation before after =
  -- 모든 before 기능이 after 또는 AgentTools에 존재
  (f : String) -> Elem f before -> Either (Elem f after) (Elem f agentToolsFunctions)

||| 재구성 후에도 워크플로우가 동작함을 보장
public export
workflowStillWorks : Type
workflowStillWorks =
  (pdf : String) ->
  (beforeResult : ExtractionResult) ->
  (afterResult : ExtractionResult) ->
  beforeResult = afterResult  -- 동일한 결과

||| 파일 추출 버그가 수정됨을 보장
public export
extractionBugFixed : Type
extractionBugFixed =
  (imageFile : String) ->
  (foundProblems : List Nat) ->
  (regions : List (Nat, Image)) ->
  length regions = length foundProblems  -- 0이 아님!
"""
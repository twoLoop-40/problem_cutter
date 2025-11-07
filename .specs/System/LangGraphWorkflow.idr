||| Formal specification for LangGraph-based PDF extraction workflow
||| Version 1.0 - Parallel processing architecture
|||
||| This module defines:
||| 1. LangGraph state graph structure
||| 2. Parallelization strategy (pages and columns)
||| 3. Node definitions and transitions
||| 4. State management

module System.LangGraphWorkflow

import Data.List
import Data.Nat
import System.ExtractionWorkflow

%default total

--------------------------------------------------------------------------------
-- LangGraph State Management
--------------------------------------------------------------------------------

||| 컬럼별 상태 - 각 컬럼은 독립적으로 처리
public export
record ColumnState where
  constructor MkColumnState
  columnIndex : Nat
  imagePath : Maybe String
  foundProblems : List Nat
  extractedCount : Nat
  mathpixVerified : Bool
  success : Bool

||| 페이지별 상태 - 각 페이지는 독립적으로 처리
public export
record PageState where
  constructor MkPageState
  pageNum : Nat
  imagePath : Maybe String
  columnCount : Nat
  columnStates : List ColumnState  -- 컬럼별 상태 (병렬 처리)
  validated : Bool
  completed : Bool

||| LangGraph 상태 - PDF 전체 추출 워크플로우
public export
record PdfExtractionState where
  constructor MkPdfState
  pdfPath : String
  totalPages : Nat
  dpi : Nat
  outputDir : String
  pageStates : List PageState  -- 페이지별 상태 (병렬 처리)
  overallSuccess : Bool
  errors : List String

--------------------------------------------------------------------------------
-- LangGraph Node 타입
--------------------------------------------------------------------------------

||| LangGraph 노드 타입 (각 단계를 나타냄)
public export
data GraphNode : Type where
  StartNode            : GraphNode  -- 시작
  ConvertPdfNode       : GraphNode  -- PDF → 이미지 변환
  SeparateColumnsNode  : GraphNode  -- 단 분리 (페이지별 병렬)
  DetectProblemsNode   : GraphNode  -- 문제 감지 (컬럼별 병렬)
  ExtractProblemsNode  : GraphNode  -- 문제 추출 (컬럼별 병렬)
  ValidateNode         : GraphNode  -- 검증 (컬럼별 병렬)
  MathpixNode          : GraphNode  -- Mathpix 재검증 (필요 시)
  ReExtractNode        : GraphNode  -- 재추출 (Mathpix 발견 시)
  FinalValidationNode  : GraphNode  -- 최종 검증 (페이지별)
  MergeResultsNode     : GraphNode  -- 결과 병합
  EndNode              : GraphNode  -- 종료

--------------------------------------------------------------------------------
-- 병렬 처리 전략
--------------------------------------------------------------------------------

||| 병렬화 가능 여부
public export
data ParallelizableUnit : GraphNode -> Type where
  -- PDF 변환은 순차 (전체 PDF를 한번에)
  SequentialConversion : ParallelizableUnit ConvertPdfNode

  -- 단 분리는 페이지별 병렬
  ParallelByPage : ParallelizableUnit SeparateColumnsNode

  -- 문제 감지는 컬럼별 병렬 (페이지 내)
  ParallelByColumn : ParallelizableUnit DetectProblemsNode

  -- 문제 추출도 컬럼별 병렬
  ParallelExtract : ParallelizableUnit ExtractProblemsNode

  -- 검증도 컬럼별 병렬
  ParallelValidate : ParallelizableUnit ValidateNode

  -- Mathpix도 컬럼별 병렬
  ParallelMathpix : ParallelizableUnit MathpixNode

  -- 재추출도 컬럼별 병렬
  ParallelReExtract : ParallelizableUnit ReExtractNode

  -- 최종 검증은 페이지별 병렬
  ParallelFinalValidation : ParallelizableUnit FinalValidationNode

  -- 결과 병합은 순차
  SequentialMerge : ParallelizableUnit MergeResultsNode

||| 병렬 처리 레벨
public export
data ParallelLevel : Type where
  Sequential : ParallelLevel  -- 순차 처리
  PageLevel  : ParallelLevel  -- 페이지별 병렬
  ColumnLevel : ParallelLevel -- 컬럼별 병렬 (페이지 내)

||| 노드별 병렬 처리 레벨
public export
parallelLevel : GraphNode -> ParallelLevel
parallelLevel StartNode = Sequential
parallelLevel ConvertPdfNode = Sequential
parallelLevel SeparateColumnsNode = PageLevel
parallelLevel DetectProblemsNode = ColumnLevel
parallelLevel ExtractProblemsNode = ColumnLevel
parallelLevel ValidateNode = ColumnLevel
parallelLevel MathpixNode = ColumnLevel
parallelLevel ReExtractNode = ColumnLevel
parallelLevel FinalValidationNode = PageLevel
parallelLevel MergeResultsNode = Sequential
parallelLevel EndNode = Sequential

--------------------------------------------------------------------------------
-- LangGraph Edge 타입 (상태 전환)
--------------------------------------------------------------------------------

||| 노드 간 전환 조건
public export
data EdgeCondition : Type where
  Always         : EdgeCondition  -- 항상 전환
  OnSuccess      : EdgeCondition  -- 성공 시
  OnFailure      : EdgeCondition  -- 실패 시
  OnMissing      : EdgeCondition  -- 누락된 문제 발견 시
  OnMathpixFound : EdgeCondition  -- Mathpix로 문제 발견 시

||| 유효한 그래프 엣지
public export
data ValidEdge : GraphNode -> EdgeCondition -> GraphNode -> Type where
  -- 정상 플로우
  StartToConvert : ValidEdge StartNode Always ConvertPdfNode
  ConvertToSeparate : ValidEdge ConvertPdfNode Always SeparateColumnsNode
  SeparateToDetect : ValidEdge SeparateColumnsNode Always DetectProblemsNode
  DetectToExtract : ValidEdge DetectProblemsNode Always ExtractProblemsNode
  ExtractToValidate : ValidEdge ExtractProblemsNode Always ValidateNode

  -- 검증 성공 → 최종 검증
  ValidateToFinal : ValidEdge ValidateNode OnSuccess FinalValidationNode

  -- 검증 실패 (누락) → Mathpix
  ValidateToMathpix : ValidEdge ValidateNode OnMissing MathpixNode

  -- Mathpix 발견 → 재추출
  MathpixToReExtract : ValidEdge MathpixNode OnMathpixFound ReExtractNode

  -- 재추출 → 최종 검증
  ReExtractToFinal : ValidEdge ReExtractNode Always FinalValidationNode

  -- Mathpix 실패 → 최종 검증 (발견하지 못함)
  MathpixToFinal : ValidEdge MathpixNode OnFailure FinalValidationNode

  -- 최종 검증 → 병합
  FinalToMerge : ValidEdge FinalValidationNode Always MergeResultsNode

  -- 병합 → 종료
  MergeToEnd : ValidEdge MergeResultsNode Always EndNode

--------------------------------------------------------------------------------
-- 실행 계획 (Execution Plan)
--------------------------------------------------------------------------------

||| LangGraph 실행 계획
public export
data ExecutionPlan : GraphNode -> Type where
  EndPlan : ExecutionPlan EndNode

  StepPlan : ValidEdge n1 cond n2 -> ExecutionPlan n2 -> ExecutionPlan n1

||| 정상 플로우 (누락 없음)
public export
normalFlowPlan : ExecutionPlan StartNode
normalFlowPlan =
  StepPlan StartToConvert $
  StepPlan ConvertToSeparate $
  StepPlan SeparateToDetect $
  StepPlan DetectToExtract $
  StepPlan ExtractToValidate $
  StepPlan ValidateToFinal $
  StepPlan FinalToMerge $
  StepPlan MergeToEnd $
  EndPlan

||| Mathpix 플로우 (누락 발견 → 재검증)
public export
mathpixFlowPlan : ExecutionPlan StartNode
mathpixFlowPlan =
  StepPlan StartToConvert $
  StepPlan ConvertToSeparate $
  StepPlan SeparateToDetect $
  StepPlan DetectToExtract $
  StepPlan ExtractToValidate $
  StepPlan ValidateToMathpix $
  StepPlan MathpixToReExtract $
  StepPlan ReExtractToFinal $
  StepPlan FinalToMerge $
  StepPlan MergeToEnd $
  EndPlan

--------------------------------------------------------------------------------
-- 병렬 처리 보장 (Parallelization Guarantees)
--------------------------------------------------------------------------------

||| 페이지 상태들이 독립적임을 보장
public export
data IndependentPages : List PageState -> Type where
  NoPages : IndependentPages []
  SinglePage : (p : PageState) -> IndependentPages [p]
  ConsPages : (p : PageState) -> IndependentPages ps ->
              -- 페이지 번호가 서로 다름을 보장
              (p.pageNum `elem` map pageNum ps = False) ->
              IndependentPages (p :: ps)

||| 컬럼 상태들이 독립적임을 보장
public export
data IndependentColumns : List ColumnState -> Type where
  NoColumns : IndependentColumns []
  SingleColumn : (c : ColumnState) -> IndependentColumns [c]
  ConsColumns : (c : ColumnState) -> IndependentColumns cs ->
                -- 컬럼 인덱스가 서로 다름을 보장
                (c.columnIndex `elem` map columnIndex cs = False) ->
                IndependentColumns (c :: cs)

||| 병렬 실행 시 데이터 경쟁이 없음을 보장
||| (각 페이지/컬럼은 독립적인 상태를 가지며, 공유 자원이 없음)
public export
data NoDataRace : GraphNode -> Type where
  -- 순차 처리는 데이터 경쟁 없음
  SequentialNoRace : NoDataRace ConvertPdfNode

  -- 페이지별 병렬: 각 페이지가 독립적이면 경쟁 없음
  PageLevelNoRace : (pages : List PageState) ->
                    IndependentPages pages ->
                    NoDataRace SeparateColumnsNode

  -- 컬럼별 병렬: 각 컬럼이 독립적이면 경쟁 없음
  ColumnLevelNoRace : (columns : List ColumnState) ->
                      IndependentColumns columns ->
                      NoDataRace DetectProblemsNode

--------------------------------------------------------------------------------
-- LangGraph Tool 맵핑
--------------------------------------------------------------------------------

||| LangGraph 노드에서 사용할 Python 함수
public export
nodeTool : GraphNode -> String
nodeTool StartNode = "initialize_state"
nodeTool ConvertPdfNode = "pdf_to_images"
nodeTool SeparateColumnsNode = "separate_columns_parallel"
nodeTool DetectProblemsNode = "detect_problems_parallel"
nodeTool ExtractProblemsNode = "extract_problems_parallel"
nodeTool ValidateNode = "validate_sequence_parallel"
nodeTool MathpixNode = "mathpix_verify_parallel"
nodeTool ReExtractNode = "re_extract_parallel"
nodeTool FinalValidationNode = "final_validation_parallel"
nodeTool MergeResultsNode = "merge_all_results"
nodeTool EndNode = "finalize_output"

--------------------------------------------------------------------------------
-- 예시: 4페이지 PDF의 실행 플랜
--------------------------------------------------------------------------------

||| 예시: 4페이지 생명과학 PDF
example_biology_pages : Nat
example_biology_pages = 4

||| 예시: 각 페이지당 2개 컬럼
example_columns_per_page : Nat
example_columns_per_page = 2

||| 예시: 총 병렬 작업 수 (페이지 레벨)
example_parallel_pages : Nat
example_parallel_pages = example_biology_pages

||| 예시: 총 병렬 작업 수 (컬럼 레벨)
example_parallel_columns : Nat
example_parallel_columns = example_biology_pages * example_columns_per_page  -- 8개

||| 병렬 처리로 인한 예상 속도 향상
||| - 4 페이지 순차 처리: ~8분 (페이지당 2분)
||| - 4 페이지 병렬 처리: ~2분 (최대 병렬)
||| - 이론적 속도 향상: 4배
example_speedup_factor : Nat
example_speedup_factor = example_biology_pages

--------------------------------------------------------------------------------
-- 증명: 병렬 처리의 안전성
--------------------------------------------------------------------------------

||| 페이지별 병렬 처리는 결과를 보존함
||| (페이지 순서와 무관하게 동일한 문제 집합을 추출)
||| (증명 스킵: 병렬 실행과 순차 실행의 결과 동일성)
export
parallelPagesPreserveResult : (pages : List PageState) ->
                               IndependentPages pages ->
                               Type
parallelPagesPreserveResult pages prf = ()

||| 컬럼별 병렬 처리는 결과를 보존함
||| (증명 스킵: 병렬 실행과 순차 실행의 결과 동일성)
export
parallelColumnsPreserveResult : (columns : List ColumnState) ->
                                 IndependentColumns columns ->
                                 Type
parallelColumnsPreserveResult columns prf = ()

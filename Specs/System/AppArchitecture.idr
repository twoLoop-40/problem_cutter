||| FastAPI + LangGraph + Streamlit 앱 아키텍처 명세
|||
||| 이 명세는 problem_cutter를 웹 애플리케이션으로 전환하는
||| 전체 시스템 아키텍처를 정의합니다.
|||
||| 설계 원칙:
||| 1. 계층 분리: API / Service / Domain
||| 2. 비동기 처리: 동시성 보장
||| 3. 상태 관리: 작업 추적
||| 4. 확장성: Streamlit → Next.js 전환 가능
|||
||| Python 구현: api/, app/, services/

module System.AppArchitecture

import System.Base
import System.ExtractionWorkflow
import Data.List

%default total

-- ============================================================================
-- 계층별 역할 정의
-- ============================================================================

||| 앱 계층 구조
|||
||| 각 계층은 명확한 책임을 가지며 상위 계층만 의존
public export
data AppLayer : Type where
  ||| API 계층: HTTP 엔드포인트, 요청/응답
  ApiLayer : AppLayer

  ||| Service 계층: 비즈니스 로직, 상태 관리
  ServiceLayer : AppLayer

  ||| Domain 계층: 핵심 도메인 로직 (기존 workflows/)
  DomainLayer : AppLayer

  ||| Infrastructure 계층: 외부 의존성 (DB, OCR, File)
  InfraLayer : AppLayer

||| 계층 의존성 규칙
|||
||| 상위 계층만 하위 계층에 의존 가능
public export
data LayerDependency : AppLayer -> AppLayer -> Type where
  ||| API → Service 의존 가능
  ApiToService : LayerDependency ApiLayer ServiceLayer

  ||| Service → Domain 의존 가능
  ServiceToDomain : LayerDependency ServiceLayer DomainLayer

  ||| Domain → Infrastructure 의존 가능
  DomainToInfra : LayerDependency DomainLayer InfraLayer

-- ============================================================================
-- 데이터 모델 (Domain Entities)
-- ============================================================================

||| 작업 ID (UUID)
public export
JobId : Type
JobId = String

||| 작업 상태
public export
data JobStatus : Type where
  ||| 대기 중 (큐에 추가됨)
  Pending : JobStatus

  ||| 처리 중 (워커가 실행 중)
  Processing : JobStatus

  ||| 완료 (결과 사용 가능)
  Completed : JobStatus

  ||| 실패 (오류 발생)
  Failed : JobStatus

||| 작업 진행 상황
public export
record JobProgress where
  constructor MkJobProgress
  ||| 진행률 (0-100)
  percentage : Nat
  ||| 현재 단계 메시지
  message : String
  ||| 예상 남은 시간 (초)
  estimatedRemaining : Maybe Nat

||| 작업 결과
public export
record JobResult where
  constructor MkJobResult
  ||| 총 문제 수
  totalProblems : Nat
  ||| 성공한 문제 수
  successCount : Nat
  ||| 출력 파일 경로
  outputZipPath : String
  ||| 실행 시간 (초)
  processingTimeSeconds : Nat

||| 작업 (Job Entity)
public export
record Job where
  constructor MkJob
  ||| 작업 ID
  jobId : JobId
  ||| PDF 파일 경로
  pdfPath : String
  ||| 작업 상태
  status : JobStatus
  ||| 진행 상황
  progress : JobProgress
  ||| 결과 (완료 시)
  result : Maybe JobResult
  ||| 에러 메시지 (실패 시)
  error : Maybe String
  ||| 생성 시간 (Unix timestamp)
  createdAt : Nat

-- ============================================================================
-- API 계층 (FastAPI Endpoints)
-- ============================================================================

||| HTTP 메서드
public export
data HttpMethod : Type where
  GET : HttpMethod
  POST : HttpMethod
  DELETE : HttpMethod

||| API 엔드포인트
public export
record ApiEndpoint where
  constructor MkEndpoint
  ||| HTTP 메서드
  method : HttpMethod
  ||| URL 경로
  path : String
  ||| 응답 타입 설명
  responseType : String

||| 업로드 요청
public export
record UploadRequest where
  constructor MkUploadRequest
  ||| PDF 파일 (multipart/form-data)
  pdfFile : String  -- file path
  ||| Mathpix API 키 (옵션)
  mathpixApiKey : Maybe String
  ||| Mathpix App ID (옵션)
  mathpixAppId : Maybe String

||| 업로드 응답
public export
record UploadResponse where
  constructor MkUploadResponse
  ||| 생성된 작업 ID
  jobId : JobId
  ||| 응답 메시지
  message : String

||| 상태 조회 응답
public export
record StatusResponse where
  constructor MkStatusResponse
  ||| 작업 ID
  jobId : JobId
  ||| 작업 상태
  status : JobStatus
  ||| 진행 상황
  progress : JobProgress
  ||| 결과 (완료 시)
  result : Maybe JobResult
  ||| 에러 메시지 (실패 시)
  error : Maybe String

-- ============================================================================
-- Service 계층 (Business Logic)
-- ============================================================================

||| Job Service (작업 관리)
public export
record JobService where
  constructor MkJobService
  ||| 새 작업 생성
  createJob : String -> UploadRequest -> JobId
  ||| 작업 조회
  getJob : JobId -> Maybe Job
  ||| 작업 상태 업데이트
  updateStatus : JobId -> JobStatus -> ()
  ||| 진행 상황 업데이트
  updateProgress : JobId -> JobProgress -> ()
  ||| 결과 저장
  saveResult : JobId -> JobResult -> ()
  ||| 에러 기록
  recordError : JobId -> String -> ()

||| Extraction Service (추출 실행)
public export
record ExtractionService where
  constructor MkExtractionService
  ||| 추출 실행 (비동기)
  executeExtraction : JobId -> String -> UploadRequest -> ()
  ||| 진행 상황 콜백
  onProgress : JobId -> JobProgress -> ()
  ||| 완료 콜백
  onComplete : JobId -> JobResult -> ()
  ||| 실패 콜백
  onFailure : JobId -> String -> ()

-- ============================================================================
-- LangGraph Workflow
-- ============================================================================

||| LangGraph 노드
public export
data GraphNode : Type where
  ||| 시작 노드
  Start : GraphNode
  ||| PDF → 이미지 변환
  ConvertPdf : GraphNode
  ||| 레이아웃 감지
  DetectLayout : GraphNode
  ||| 컬럼 분리
  SeparateColumns : GraphNode
  ||| Tesseract OCR
  RunTesseract : GraphNode
  ||| 문제 추출
  ExtractProblems : GraphNode
  ||| 검증
  Validate : GraphNode
  ||| Mathpix 재추출
  RunMathpix : GraphNode
  ||| 파일 생성
  GenerateFiles : GraphNode
  ||| ZIP 패키징
  CreateZip : GraphNode
  ||| 종료 노드
  End : GraphNode

||| LangGraph 엣지 (노드 간 전환)
public export
data GraphEdge : GraphNode -> GraphNode -> Type where
  ||| Start → ConvertPdf
  StartToConvert : GraphEdge Start ConvertPdf
  ||| ConvertPdf → DetectLayout
  ConvertToDetect : GraphEdge ConvertPdf DetectLayout
  ||| DetectLayout → SeparateColumns
  DetectToSeparate : GraphEdge DetectLayout SeparateColumns
  ||| SeparateColumns → RunTesseract
  SeparateToTesseract : GraphEdge SeparateColumns RunTesseract
  ||| RunTesseract → ExtractProblems
  TesseractToExtract : GraphEdge RunTesseract ExtractProblems
  ||| ExtractProblems → Validate
  ExtractToValidate : GraphEdge ExtractProblems Validate
  ||| Validate → GenerateFiles (성공 시)
  ValidateToGenerate : GraphEdge Validate GenerateFiles
  ||| Validate → RunMathpix (실패 시)
  ValidateToMathpix : GraphEdge Validate RunMathpix
  ||| RunMathpix → ExtractProblems (재시도)
  MathpixToExtract : GraphEdge RunMathpix ExtractProblems
  ||| GenerateFiles → CreateZip
  GenerateToZip : GraphEdge GenerateFiles CreateZip
  ||| CreateZip → End
  ZipToEnd : GraphEdge CreateZip End

||| LangGraph 상태
public export
record LangGraphState where
  constructor MkLangGraphState
  ||| 작업 ID
  jobId : JobId
  ||| PDF 경로
  pdfPath : String
  ||| Mathpix 설정
  mathpixConfig : (String, String)  -- (api_key, app_id)
  ||| 현재 노드
  currentNode : GraphNode
  ||| 추출된 문제 수
  extractedCount : Nat
  ||| 검증 통과 여부
  validationPassed : Bool
  ||| 출력 경로
  outputPath : String

-- ============================================================================
-- Infrastructure 계층
-- ============================================================================

||| Job Queue (Redis 기반)
public export
record JobQueue where
  constructor MkJobQueue
  ||| 큐에 작업 추가
  enqueue : JobId -> ()
  ||| 큐에서 작업 가져오기
  dequeue : Maybe JobId
  ||| 큐 크기
  size : Nat

||| Worker Pool (동시 처리)
public export
record WorkerPool where
  constructor MkWorkerPool
  ||| 워커 수
  workerCount : Nat
  ||| 활성 작업 수
  activeJobs : Nat
  ||| 최대 동시 처리 수
  maxConcurrency : Nat

-- ============================================================================
-- 시스템 보장 사항 (Guarantees)
-- ============================================================================

||| 작업 상태 전환의 유효성
|||
||| Pending → Processing → (Completed | Failed)
public export
data ValidJobTransition : JobStatus -> JobStatus -> Type where
  ||| Pending → Processing
  PendingToProcessing : ValidJobTransition Pending Processing

  ||| Processing → Completed
  ProcessingToCompleted : ValidJobTransition Processing Completed

  ||| Processing → Failed
  ProcessingToFailed : ValidJobTransition Processing Failed

||| 계층 분리 보장
|||
||| 하위 계층은 상위 계층에 의존하지 않음
public export
data LayerSeparation : Type where
  MkLayerSeparation :
    (api : AppLayer) ->
    (service : AppLayer) ->
    (domain : AppLayer) ->
    (infra : AppLayer) ->
    LayerDependency api service ->
    LayerDependency service domain ->
    LayerDependency domain infra ->
    LayerSeparation

||| 비동기 처리 보장
|||
||| FastAPI는 여러 요청을 동시에 처리할 수 있음
public export
data ConcurrencySupport : WorkerPool -> Type where
  MkConcurrency :
    (pool : WorkerPool) ->
    ConcurrencySupport pool

-- ============================================================================
-- API 엔드포인트 정의
-- ============================================================================

||| 모든 API 엔드포인트
public export
apiEndpoints : List ApiEndpoint
apiEndpoints =
  [ MkEndpoint POST "/upload" "UploadResponse"
  , MkEndpoint GET "/status/{job_id}" "StatusResponse"
  , MkEndpoint GET "/download/{job_id}" "FileResponse"
  , MkEndpoint DELETE "/jobs/{job_id}" "DeleteResponse"
  ]

-- ============================================================================
-- 워크플로우 실행 보장
-- ============================================================================

||| LangGraph 워크플로우가 Start에서 End로 도달 가능함
public export
data WorkflowReachable : Type where
  MkReachable :
    GraphEdge Start ConvertPdf ->
    GraphEdge ConvertPdf DetectLayout ->
    GraphEdge DetectLayout SeparateColumns ->
    GraphEdge SeparateColumns RunTesseract ->
    GraphEdge RunTesseract ExtractProblems ->
    GraphEdge ExtractProblems Validate ->
    GraphEdge Validate GenerateFiles ->
    GraphEdge GenerateFiles CreateZip ->
    GraphEdge CreateZip End ->
    WorkflowReachable

||| 워크플로우 실행 보장 증명
public export
workflowIsReachable : WorkflowReachable
workflowIsReachable =
  MkReachable
    StartToConvert
    ConvertToDetect
    DetectToSeparate
    SeparateToTesseract
    TesseractToExtract
    ExtractToValidate
    ValidateToGenerate
    GenerateToZip
    ZipToEnd

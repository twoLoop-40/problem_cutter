||| OCR Engine Interface (완전히 독립적인 모듈)
|||
||| OCR 엔진은 입력(이미지)을 받아 출력(텍스트 + 위치)을 반환하는 블랙박스
||| Agent는 OCR 엔진 내부를 모름 (추상 인터페이스만 사용)
|||
||| Python 구현: core/ocr/interface.py
|||
||| 설계 원칙:
||| 1. 입력/출력 표준화 (모든 OCR 엔진이 동일한 인터페이스)
||| 2. 엔진별 세부사항은 플러그인으로 구현
||| 3. 새로운 엔진 추가 = 새로운 플러그인 추가 (명세 변경 없음)

module System.Ocr.Interface

import System.Base
import Data.Nat
import Data.List

%default total

-- =============================================================================
-- OCR Input (표준 입력)
-- =============================================================================

||| OCR 입력 (이미지 경로 + 옵션)
|||
||| 모든 OCR 엔진이 동일한 입력을 받음
public export
record OcrInput where
  constructor MkOcrInput
  ||| 이미지 경로 (또는 Base64 인코딩)
  imagePath : String
  ||| 언어 코드 (예: "kor", "eng", "kor+eng")
  languages : List String
  ||| DPI (이미지 해상도)
  dpi : Nat
  ||| 추가 옵션 (엔진별로 다를 수 있음)
  options : List (String, String)

||| 기본 OCR 입력 생성
public export
defaultOcrInput : String -> OcrInput
defaultOcrInput path = MkOcrInput
  { imagePath = path
  , languages = ["kor", "eng"]
  , dpi = 300
  , options = []
  }

-- =============================================================================
-- OCR Output (표준 출력)
-- =============================================================================

||| 단일 텍스트 블록 결과
|||
||| 모든 OCR 엔진이 동일한 출력 형식 사용
public export
record TextBlock where
  constructor MkTextBlock
  ||| 인식된 텍스트
  text : String
  ||| 위치 (BBox)
  bbox : BBox
  ||| 신뢰도 (0.0 ~ 1.0)
  confidence : Double
  ||| 언어 (감지된 경우)
  detectedLanguage : Maybe String

||| OCR 실행 결과
public export
record OcrOutput where
  constructor MkOcrOutput
  ||| 텍스트 블록 목록
  blocks : List TextBlock
  ||| 전체 실행 시간 (초)
  executionTime : Nat
  ||| 전체 평균 신뢰도
  averageConfidence : Double
  ||| 사용된 엔진 이름 (디버깅용)
  engineName : String

-- =============================================================================
-- OCR Engine Interface (추상 인터페이스)
-- =============================================================================

||| OCR 엔진 추상 인터페이스
|||
||| 모든 OCR 엔진은 이 인터페이스를 구현해야 함
|||
||| Python 구현:
||| ```python
||| class OcrEngine(ABC):
|||     @abstractmethod
|||     def name(self) -> str:
|||         pass
|||
|||     @abstractmethod
|||     def execute(self, input: OcrInput) -> OcrOutput:
|||         pass
|||
|||     @abstractmethod
|||     def is_available(self) -> bool:
|||         pass
|||
|||     @abstractmethod
|||     def estimated_cost(self, input: OcrInput) -> float:
|||         pass
||| ```
public export
record OcrEngineInterface where
  constructor MkOcrEngineInterface
  ||| 엔진 이름 (예: "tesseract", "mathpix", "claude_vision")
  name : String
  ||| 엔진 실행 함수 (실제 구현은 Python)
  execute : OcrInput -> OcrOutput
  ||| 엔진 사용 가능 여부 (API 키 확인 등)
  isAvailable : Bool
  ||| 예상 비용 (센트 단위, 무료는 0)
  estimatedCost : OcrInput -> Nat

-- =============================================================================
-- OCR Engine Registry (플러그인 등록)
-- =============================================================================

||| OCR 엔진 타입 (확장 가능)
|||
||| 새로운 엔진 추가 시 여기에 추가
public export
data OcrEngineType
  = TesseractEngine
  | MathpixEngine
  | ClaudeVisionEngine
  | GPT4VisionEngine
  | PaddleOCREngine
  | EasyOCREngine
  | CustomEngine String  -- 사용자 정의 엔진

||| 엔진 타입을 문자열로 변환
public export
engineTypeName : OcrEngineType -> String
engineTypeName TesseractEngine = "tesseract"
engineTypeName MathpixEngine = "mathpix"
engineTypeName ClaudeVisionEngine = "claude_vision"
engineTypeName GPT4VisionEngine = "gpt4_vision"
engineTypeName PaddleOCREngine = "paddleocr"
engineTypeName EasyOCREngine = "easyocr"
engineTypeName (CustomEngine name) = name

-- =============================================================================
-- OCR Strategy (비용 기반)
-- =============================================================================

||| OCR 전략 카테고리
public export
data OcrCategory
  = FastCategory      -- 빠르고 저렴 (Tesseract, PaddleOCR, EasyOCR)
  | AccurateCategory  -- 느리고 비쌈 (Mathpix, Claude Vision, GPT-4V)

||| 엔진 타입의 카테고리 분류
public export
categorizeEngine : OcrEngineType -> OcrCategory
categorizeEngine TesseractEngine = FastCategory
categorizeEngine PaddleOCREngine = FastCategory
categorizeEngine EasyOCREngine = FastCategory
categorizeEngine MathpixEngine = AccurateCategory
categorizeEngine ClaudeVisionEngine = AccurateCategory
categorizeEngine GPT4VisionEngine = AccurateCategory
categorizeEngine (CustomEngine _) = FastCategory  -- 기본값

||| OCR 실행 전략
|||
||| Agent는 이 전략만 지정하고, 실제 엔진 선택은 런타임에 결정
public export
record OcrStrategy where
  constructor MkOcrStrategy
  ||| 1단계 엔진 (Fast)
  stage1Engine : OcrEngineType
  ||| 2단계 엔진 (Accurate)
  stage2Engine : OcrEngineType
  ||| 최대 재시도 횟수
  maxRetries : Nat
  ||| Fallback 엔진 (실패 시)
  fallbackEngine : Maybe OcrEngineType

||| 기본 OCR 전략 (Tesseract → Mathpix)
public export
defaultOcrStrategy : OcrStrategy
defaultOcrStrategy = MkOcrStrategy
  { stage1Engine = TesseractEngine
  , stage2Engine = MathpixEngine
  , maxRetries = 2
  , fallbackEngine = Just EasyOCREngine
  }

-- =============================================================================
-- OCR Execution Result (Agent가 사용)
-- =============================================================================

||| OCR 실행 결과 (Agent 친화적)
|||
||| Agent는 텍스트 블록 목록이 아니라 "검출된 문제 번호"만 필요함
||| OCR → 문제 번호 파싱은 별도 모듈에서 처리
public export
record OcrExecutionResult where
  constructor MkOcrExecutionResult
  ||| 사용된 엔진
  engine : OcrEngineType
  ||| 검출된 문제 번호 (파싱 완료)
  detectedProblems : List Nat
  ||| 평균 신뢰도
  confidence : Double
  ||| 실행 시간
  executionTime : Nat
  ||| 원본 OCR 출력 (디버깅용)
  rawOutput : Maybe OcrOutput

-- =============================================================================
-- Guarantees (보장 사항)
-- =============================================================================

||| 유효한 OCR 입력
public export
data ValidOcrInput : OcrInput -> Type where
  MkValidInput :
    (input : OcrInput) ->
    (length input.imagePath > 0 = True) ->
    (length input.languages > 0 = True) ->
    (input.dpi > 0 = True) ->
    ValidOcrInput input

||| 유효한 OCR 출력
public export
data ValidOcrOutput : OcrOutput -> Type where
  MkValidOutput :
    (output : OcrOutput) ->
    (0.0 <= output.averageConfidence = True) ->
    (output.averageConfidence <= 1.0 = True) ->
    ValidOcrOutput output

||| 엔진이 카테고리와 일치함을 보장
public export
data EngineMatchesCategory : OcrEngineType -> OcrCategory -> Type where
  MkMatches :
    (engine : OcrEngineType) ->
    (category : OcrCategory) ->
    (categorizeEngine engine = category) ->
    EngineMatchesCategory engine category

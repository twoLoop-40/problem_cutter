||| OCR 결과 → 구조화된 정보 파싱 (확장 가능한 설계)
|||
||| OCR 출력 (텍스트 블록)을 받아 구조화된 정보를 추출하는 모듈
||| Agent와 OCR 엔진 사이의 어댑터 역할
|||
||| Python 구현: core/ocr/parser.py
|||
||| 핵심 설계:
||| 1. **마커 시스템 확장 가능**: 문제 번호, 정답 마커, 배점, 난이도 등
||| 2. **Parser 플러그인 구조**: 새로운 마커 타입 추가 시 플러그인만 추가
||| 3. **Context-aware 파싱**: 주변 텍스트 정보 활용

module System.Ocr.Parser

import System.Ocr.Interface
import System.Base
import Data.Nat
import Data.List

%default total

-- =============================================================================
-- Marker System (확장 가능한 마커 시스템)
-- =============================================================================

||| 마커 타입 (확장 가능)
|||
||| 새로운 마커 타입 추가 시 여기에 추가
public export
data MarkerType
  = ProblemNumberMarker        -- 문제 번호 (1., ①, [1] 등)
  | SolutionMarker             -- 정답/해설 마커 ([정답], [해설])
  | ScoreMarker                -- 배점 ([2점], [1.5점])
  | DifficultyMarker           -- 난이도 (상, 중, 하)
  | CategoryMarker             -- 카테고리/영역 ([문법], [독해])
  | RangeMarker                -- 공통 지문 ([8~9], [10-12])
  | CustomMarker String        -- 사용자 정의 마커

||| 마커 타입 이름
public export
markerTypeName : MarkerType -> String
markerTypeName ProblemNumberMarker = "problem_number"
markerTypeName SolutionMarker = "solution"
markerTypeName ScoreMarker = "score"
markerTypeName DifficultyMarker = "difficulty"
markerTypeName CategoryMarker = "category"
markerTypeName RangeMarker = "range"
markerTypeName (CustomMarker name) = name

||| Eq 구현
public export
Eq MarkerType where
  ProblemNumberMarker == ProblemNumberMarker = True
  SolutionMarker == SolutionMarker = True
  ScoreMarker == ScoreMarker = True
  DifficultyMarker == DifficultyMarker = True
  CategoryMarker == CategoryMarker = True
  RangeMarker == RangeMarker = True
  (CustomMarker a) == (CustomMarker b) = a == b
  _ == _ = False

-- =============================================================================
-- Pattern System (확장 가능한 패턴 시스템)
-- =============================================================================

||| 패턴 매처 인터페이스
|||
||| 각 마커 타입은 여러 패턴을 가질 수 있음
||| Python 구현:
||| ```python
||| class PatternMatcher(ABC):
|||     @abstractmethod
|||     def name(self) -> str:
|||         pass
|||
|||     @abstractmethod
|||     def match(self, text: str) -> Optional[Match]:
|||         pass
|||
|||     @abstractmethod
|||     def extract(self, match: Match) -> Any:
|||         pass
||| ```
public export
record PatternMatcher where
  constructor MkPatternMatcher
  ||| 패턴 이름
  name : String
  ||| 정규식 패턴
  regex : String
  ||| 우선순위 (낮을수록 먼저 시도)
  priority : Nat

||| 문제 번호 패턴들
public export
problemNumberPatterns : List PatternMatcher
problemNumberPatterns =
  [ MkPatternMatcher "dot" "^(\\d+)\\.$" 1              -- "1.", "2."
  , MkPatternMatcher "circled" "^[①-⑳]$" 2            -- "①", "②"
  , MkPatternMatcher "bracket" "^\\[(\\d+)\\]$" 3       -- "[1]", "[2]"
  , MkPatternMatcher "parenthesis" "^\\((\\d+)\\)$" 4   -- "(1)", "(2)"
  , MkPatternMatcher "digit_only" "^(\\d{1,2})$" 10     -- "1", "2" (낮은 우선순위)
  ]

||| 정답 마커 패턴들
public export
solutionMarkerPatterns : List PatternMatcher
solutionMarkerPatterns =
  [ MkPatternMatcher "bracket_answer" "^\\[정답\\]$" 1
  , MkPatternMatcher "bracket_solution" "^\\[해설\\]$" 1
  , MkPatternMatcher "colon_answer" "^정답:$" 2
  , MkPatternMatcher "colon_solution" "^해설:$" 2
  ]

||| 배점 패턴들
public export
scoreMarkerPatterns : List PatternMatcher
scoreMarkerPatterns =
  [ MkPatternMatcher "bracket_score" "^\\[(\\d+(\\.\\d+)?)점\\]$" 1  -- "[2점]", "[1.5점]"
  , MkPatternMatcher "parenthesis_score" "^\\((\\d+(\\.\\d+)?)점\\)$" 2
  ]

||| 범위 패턴들 (공통 지문)
public export
rangeMarkerPatterns : List PatternMatcher
rangeMarkerPatterns =
  [ MkPatternMatcher "bracket_range_tilde" "^\\[(\\d+)~(\\d+)\\]$" 1  -- "[8~9]"
  , MkPatternMatcher "bracket_range_dash" "^\\[(\\d+)-(\\d+)\\]$" 2   -- "[8-9]"
  ]

-- =============================================================================
-- Parser Plugin Interface (확장 가능한 파서)
-- =============================================================================

||| 파서 플러그인 인터페이스
|||
||| 새로운 마커 타입 추가 시 새로운 파서 플러그인 구현
||| Python 구현:
||| ```python
||| class ParserPlugin(ABC):
|||     @abstractmethod
|||     def marker_type(self) -> MarkerType:
|||         pass
|||
|||     @abstractmethod
|||     def patterns(self) -> List[PatternMatcher]:
|||         pass
|||
|||     @abstractmethod
|||     def parse(self, text_block: TextBlock, context: ParsingContext) -> Optional[Marker]:
|||         pass
|||
|||     @abstractmethod
|||     def validate(self, marker: Marker) -> bool:
|||         pass
||| ```
public export
record ParserPlugin where
  constructor MkParserPlugin
  ||| 마커 타입
  markerType : MarkerType
  ||| 패턴 목록
  patterns : List PatternMatcher
  ||| 최소 신뢰도
  minConfidence : Double

-- =============================================================================
-- Parsing Context (문맥 정보)
-- =============================================================================

||| 파싱 문맥 정보
|||
||| 주변 텍스트, 위치 정보 등을 활용한 context-aware 파싱
public export
record ParsingContext where
  constructor MkParsingContext
  ||| 현재 텍스트 블록
  currentBlock : TextBlock
  ||| 이전 블록 (위치 정보 활용)
  previousBlock : Maybe TextBlock
  ||| 다음 블록 (위치 정보 활용)
  nextBlock : Maybe TextBlock
  ||| 페이지 번호
  pageNumber : Nat
  ||| 이미 검출된 마커들 (중복 방지)
  detectedMarkers : List (MarkerType, Nat)

-- =============================================================================
-- Unified Marker (통합 마커)
-- =============================================================================

||| 통합 마커 (모든 마커 타입을 포함)
|||
||| 각 마커 타입별로 다른 데이터를 가질 수 있음
public export
data MarkerData
  = ProblemNumberData Nat                    -- 문제 번호
  | SolutionData String                      -- 정답/해설 타입
  | ScoreData Double                         -- 배점
  | DifficultyData String                    -- 난이도
  | CategoryData String                      -- 카테고리
  | RangeData Nat Nat                        -- 범위 (시작, 끝)
  | CustomData String                        -- 사용자 정의

||| 통합 마커
public export
record Marker where
  constructor MkMarker
  ||| 마커 타입
  markerType : MarkerType
  ||| 마커 데이터 내용
  markerData : MarkerData
  ||| 위치 (BBox)
  position : BBox
  ||| 신뢰도
  confidence : Double
  ||| 매칭된 패턴
  matchedPattern : String
  ||| 원본 텍스트
  originalText : String

-- =============================================================================
-- Parsing Configuration
-- =============================================================================

||| 파싱 설정
public export
record ParserConfig where
  constructor MkParserConfig
  ||| 활성화할 파서 플러그인 목록
  enabledParsers : List ParserPlugin
  ||| 최소 신뢰도 (전역)
  globalMinConfidence : Double
  ||| 최대 문제 번호
  maxProblemNumber : Nat
  ||| 중복 제거 여부
  deduplicate : Bool
  ||| Context window 크기 (전후 몇 개 블록)
  contextWindow : Nat

||| 기본 파싱 설정 (문제 번호만)
public export
defaultParserConfig : ParserConfig
defaultParserConfig = MkParserConfig
  { enabledParsers =
      [ MkParserPlugin ProblemNumberMarker problemNumberPatterns 0.7
      , MkParserPlugin RangeMarker rangeMarkerPatterns 0.7
      ]
  , globalMinConfidence = 0.6
  , maxProblemNumber = 50
  , deduplicate = True
  , contextWindow = 2
  }

||| 확장된 파싱 설정 (모든 마커)
public export
fullParserConfig : ParserConfig
fullParserConfig = MkParserConfig
  { enabledParsers =
      [ MkParserPlugin ProblemNumberMarker problemNumberPatterns 0.7
      , MkParserPlugin SolutionMarker solutionMarkerPatterns 0.7
      , MkParserPlugin ScoreMarker scoreMarkerPatterns 0.6
      , MkParserPlugin RangeMarker rangeMarkerPatterns 0.7
      ]
  , globalMinConfidence = 0.6
  , maxProblemNumber = 50
  , deduplicate = True
  , contextWindow = 3
  }

-- =============================================================================
-- Parsing Result
-- =============================================================================

||| 파싱 결과
public export
record ParsingResult where
  constructor MkParsingResult
  ||| 검출된 모든 마커
  allMarkers : List Marker
  ||| 문제 번호 마커만
  problemMarkers : List Marker
  ||| 검출된 문제 번호 (중복 제거)
  problemNumbers : List Nat
  ||| 파싱 성공률
  successRate : Double

-- =============================================================================
-- Parser Interface
-- =============================================================================

||| OCR 결과 → 마커 파싱 함수
|||
||| Python 구현:
||| ```python
||| def parse_markers(
|||     ocr_output: OcrOutput,
|||     config: ParserConfig
||| ) -> ParsingResult:
|||     all_markers = []
|||
|||     for i, block in enumerate(ocr_output.blocks):
|||         if block.confidence < config.global_min_confidence:
|||             continue
|||
|||         # Build context
|||         context = ParsingContext(
|||             current_block=block,
|||             previous_block=ocr_output.blocks[i-1] if i > 0 else None,
|||             next_block=ocr_output.blocks[i+1] if i < len(blocks)-1 else None,
|||             page_number=calculate_page(block),
|||             detected_markers=[(m.marker_type, extract_id(m)) for m in all_markers]
|||         )
|||
|||         # Try each enabled parser
|||         for parser in config.enabled_parsers:
|||             if block.confidence < parser.min_confidence:
|||                 continue
|||
|||             marker = parser.parse(block, context)
|||             if marker and parser.validate(marker):
|||                 all_markers.append(marker)
|||                 break  # 첫 번째 매칭된 파서만 사용
|||
|||     # Extract problem numbers
|||     problem_markers = [m for m in all_markers if m.marker_type == MarkerType.PROBLEM_NUMBER]
|||     problem_numbers = [extract_number(m.data) for m in problem_markers]
|||
|||     if config.deduplicate:
|||         problem_numbers = sorted(set(problem_numbers))
|||
|||     return ParsingResult(
|||         all_markers=all_markers,
|||         problem_markers=problem_markers,
|||         problem_numbers=problem_numbers,
|||         success_rate=len(all_markers) / len(ocr_output.blocks)
|||     )
||| ```
public export
parseMarkers :
  (output : OcrOutput) ->
  (config : ParserConfig) ->
  ParsingResult

-- =============================================================================
-- Helper Functions
-- =============================================================================

||| 범위 마커 확장 ([8~9] → [8, 9])
public export
expandRangeMarkers : List Marker -> List Nat
expandRangeMarkers markers =
  concat [expandSingle m | m <- markers, isRangeMarker m]
  where
    isRangeMarker : Marker -> Bool
    isRangeMarker m = m.markerType == RangeMarker

    expandSingle : Marker -> List Nat
    expandSingle m = case m.markerData of
      RangeData start end => [start .. end]
      _ => []

||| OCR 결과 → OcrExecutionResult 변환
public export
ocrOutputToExecutionResult :
  (output : OcrOutput) ->
  (engine : OcrEngineType) ->
  (config : ParserConfig) ->
  OcrExecutionResult
ocrOutputToExecutionResult output engine config =
  let parsing = parseMarkers output config
  in MkOcrExecutionResult
    { engine = engine
    , detectedProblems = parsing.problemNumbers
    , confidence = output.averageConfidence
    , executionTime = output.executionTime
    , rawOutput = Just output
    }

-- =============================================================================
-- Guarantees
-- =============================================================================

||| 유효한 마커
public export
data ValidMarker : Marker -> Type where
  MkValidMarker :
    (marker : Marker) ->
    (0.0 <= marker.confidence = True) ->
    (marker.confidence <= 1.0 = True) ->
    (length marker.originalText > 0 = True) ->
    ValidMarker marker

|||마커 타입과 데이터가 일치함
public export
data MarkerDataMatches : MarkerType -> MarkerData -> Type where
  MatchProblemNumber :
    (n : Nat) ->
    MarkerDataMatches ProblemNumberMarker (ProblemNumberData n)

  MatchSolution :
    (s : String) ->
    MarkerDataMatches SolutionMarker (SolutionData s)

  MatchScore :
    (score : Double) ->
    MarkerDataMatches ScoreMarker (ScoreData score)

  MatchRange :
    (start : Nat) ->
    (end : Nat) ->
    MarkerDataMatches RangeMarker (RangeData start end)

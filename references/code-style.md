# 코드 스타일 (code-style)

> **목적:** 이 프로젝트의 Python·pandas 작성 규칙. 재무 데이터의 정확성·추적성을 지키기 위한 최소 규약이며, 과도한 형식주의는 지양한다. (안전 규칙 전반은 `references/safety-rules.md`.)

## 일반
- Python 3.10+. `snake_case` 함수·변수, 모듈명은 `docs/PLAN.md`의 파이프라인 이름을 따른다.
- 타입 힌트와 짧은 docstring을 붙인다. 공개 함수의 입력/출력 형태를 명확히.
- **순수 함수 우선.** 계산 로직과 I/O(API·파일)를 분리한다. 부수효과는 얇은 경계 계층에 모은다.
- 의존성은 최소로: `requests`, `pandas`, `pyyaml`, `xlsxwriter`, `python-dotenv` 수준. 새 의존성은 리뷰에서 정당화한다.
- 임계값·경로·연도 등은 **코드 리터럴이 아니라 `config/settings.yaml`**에서 읽는다.

## pandas — 행 의미·원본 추적 보존
- **행 식별자를 잃지 않는다.** `reset_index`로 식별 컬럼을 버리지 말 것. merge/join 후에는 **행 수와 키 유일성**을 검증한다.
- `groupby`/`pivot` 시 원본 키(`corp_code`, `rcept_no` 등)를 결과에 유지한다.
- **명시적 컬럼 선택**(이름 기반). 위치 인덱싱·암묵적 브로드캐스트에 의존하지 않는다.
- 원본 프레임을 in-place로 변형하지 않는다. 변형 전 `.copy()`를 명시하고, chained assignment(`df[a][b] = ...`)를 쓰지 않는다.
- `dtype`을 명시한다. 특히 `corp_code`·`stock_code`·`rcept_no`는 **문자열**(앞자리 0 보존).
- **금액은 부동소수(float)를 피하고** `Decimal`로 다룬다. 비율 계산 시에만 명시적으로 변환한다.
- **결정적(deterministic) 정렬**을 사용한다. dict/set/파일 순서에 의존하지 않는다.
- 분위수(quantile) 계산은 interpolation 방식을 고정해 버전 간 재현성을 확보한다.

## 결측·오류
- `NaN`/결측을 **명시적으로** 처리한다. `dropna` 남용 금지 — 무엇을, 왜 버렸는지 로그로 남긴다.
- 분모 ≤ 0, 계정 누락 등은 예외로 죽이지 말고 `NOT_COMPUTABLE`로 표시하고 분포에서 제외한다(→ `references/methodology.md`).
- `inf`/`NaN`이 통계로 새어 들어가지 않게 한다.

## 로깅·재현성
- 조용한 실패 금지. 버린 행·재시도·폴백은 로그로 남긴다.
- 실행 파라미터·타임스탬프를 기록해 결과를 재현·감사할 수 있게 한다.
- 파일 쓰기는 **임시 파일 → 원자적 교체**로 하고, 기존 출력은 `--overwrite` 없이 덮지 않는다.

## 테스트
- 위험 경로 위주(벤치마크 수식, NOT_COMPUTABLE 가드, dedup 결정성, no-clobber 쓰기). 자명한 코드의 테스트는 만들지 않는다.

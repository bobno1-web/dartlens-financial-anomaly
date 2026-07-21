# CLAUDE.md — 프로젝트 라우터

OpenDART 연결 재무제표 산업 이상징후 도구. 이 문서는 **핵심 라우터**다.
상세 규칙·설계는 `references/` 아래 문서에 있고, 여기서는 요약과 링크만 유지한다.

MVP · 로컬 Python 스크립트 · **웹앱 아님**. 감사가능성(auditability)과 안전이 최우선.

## 문서 라우팅

| 알고 싶은 것 | 문서 |
|---|---|
| 무엇을 왜 만드는가, 범위, 주장/비주장 | `references/project-goal.md` |
| 데이터 모델(엔티티·필드) | `references/data-model.md` |
| 분석 방법론·라벨 | `references/methodology.md` |
| 코드 스타일·pandas 규칙 | `references/code-style.md` |
| 안전 규칙(데이터 보호) | `references/safety-rules.md` |
| 리뷰 절차(cr1) | `references/review-protocol.md` |
| MVP 로드맵·5대 교정 | `docs/PLAN.md` |
| 확정 결정·미결 질문 | `docs/DECISIONS.md` |
| 웹 UI(로컬 Flask 앱, 엔진 미변경; 초기 Streamlit→Loop 20 Flask 재구축) | `docs/WEB_UI_PLAN.md` |

각 주제의 **정본은 위 문서**다. 이 라우터는 요약만 담고, 세부 내용을 중복 서술하지 않는다.

## 절대 규칙 (요약 — 상세·근거는 `references/safety-rules.md`)

1. **회사별 하드코딩 금지.** 회사명·`corp_code`·종목코드·계정별 특수분기를 코드에 넣지 않는다. 그런 값은 데이터·`config/settings.yaml`·`mappings/`에서 온다.
2. **원본(raw) 덮어쓰기 금지.** `data/raw/`는 verbatim append-only 감사 계층이다. `parsed`는 항상 raw에서 재생성 가능해야 한다.
3. **조용한 데이터 손실 금지.** 버려진 행·누락 계정·API 실패·계산불가 비율은 기록하고 표면화한다.
4. **승인 전 구현 금지.** `docs/`의 해당 계획이 승인되기 전에는 비즈니스 로직을 작성하지 않는다. 구조/스캐폴딩은 허용된다.
5. **출력 파일 덮어쓰기 금지** — 명시적 `--overwrite` 플래그 없이는 기존 `.xlsx`를 덮지 않는다.

## 작업 워크플로우 (상세는 `references/review-protocol.md`)

- **주요 변경 전 `cr1` 리뷰**를 받는다: 데이터 로딩, dataframe 변환, 비율/벤치마크/이상탐지 로직, Excel 출력, 설계 결정. `cr1`은 리뷰만 하고 파일을 수정하지 않는다.
- **작고 감사가능한 증분 변경**을 선호한다(대규모 재작성 지양).
- 임계값·파라미터는 코드가 아니라 `config/settings.yaml`에 둔다.
- 모든 출력값은 `rcept_no` / `account_id` / 원본 filing으로 **역추적** 가능해야 한다.
- 테스트는 **실용적으로**(위험 경로 위주), 과도하지 않게 작성한다.

## 지금 단계에서 하지 말 것

- OpenDART API 호출·비즈니스 로직 구현 (계획 승인 전).
- hooks · skills · plugin · MCP 생성.
- 실제 API 키·`.env` 커밋.
- 웹앱화.
- 확인 없는 파괴적 명령(대량 삭제·강제 덮어쓰기).

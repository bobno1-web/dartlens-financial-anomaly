# WEB_UI_PLAN.md — Ralph Loop 4: Streamlit UI MVP (이력 문서)

> **📌 이력 문서 안내**: 이 문서는 **Loop 4 당시의 Streamlit 기반 웹 UI 계획**을 기록한 것이다.
> Loop 20에서 웹 UI는 **엔진을 한 줄도 바꾸지 않고 Flask로 재구축**되었다. 아래 본문의
> `Streamlit`·`app.py`·`streamlit run` 언급은 **당시 계획의 이력**이며 현재 구현이 아니다.
> 현재 실행·구조는 `README.md`와 `app_flask.py` 를 참조한다.
> 매핑: `app.py`(Streamlit) → `app_flask.py`(Flask), `python -m streamlit run app.py` → `python app_flask.py`.

> **당시(Loop 4) 상태**: Loop 4는 승인된 로컬 Streamlit UI wrapper 단계였다. 웹 UI는 분석 엔진(benchmark/compare/
> ratio/accounts/pipeline)을 변경하지 않는 wrapper이며, 산출물 Excel을 읽어 표시하거나 기존 pipeline을
> 호출만 한다. Loop 4-A에서 report/debug **동일 timestamp 쌍 가드**를 추가했다.

## 1. Loop 4 목적
검증 완료된 Loop 1~3-B **분석 엔진을 변경하지 않고** 로컬 Streamlit 웹 UI로 감싸는 MVP.
- 분석 로직(benchmark/compare/ratio/account mapping/판정 기준) **변경 없음**.
- 흐름: **사용자 입력 → 분석 실행(또는 최근 결과 불러오기) → 요약/비율/Peer/제외사유 표시 → Excel 다운로드**.
- 엔진은 신규 `src/ui_runner.py`가 기존 `pipeline.run_loop3b`를 **호출만** 한다(엔진 파일 미수정).

## 2. UI 구성
- **Sidebar 입력 영역**: API Key(password), 회사명/종목코드, 사업연도, 고정표시(사업보고서·연결 CFS), 버튼(새 분석 실행 / 최근 결과 불러오기), 안전 안내.
- **Main**:
  - 상단 제목/부제 + 요약 카드(회사·연도·peer 후보·CFS 성공/실패·계산 비율·판정 요약)
  - 핵심 해석 요약(실제 label/percentile/benchmark_quality에서 생성)
  - 탭: `요약` · `수익성` · `안정성/재무구조` · `운전자본/계정리스크` · `회전율` · `Peer List` · `계산불가/제외사유` · `Methodology` · `다운로드`

## 3. API key 정책
- **우선순위**: `.env`의 `OPENDART_API_KEY` → sidebar 입력값.
- sidebar 입력 키는 **현재 세션에서만** 사용(`os.environ` 인메모리 주입, **파일 미기록**).
- 키 값을 **화면/로그/산출물/manifest/파일에 저장·출력 금지**. UI는 "키 설정됨/미설정"만 표시.
- `.env` **자동 수정 금지**.

## 4. 산출물 정책
- 기존 `output/` 파일 **덮어쓰기 금지**. 새 분석은 엔진의 `_atomic_new_path`로 **새 timestamp 파일** 생성.
- "최근 결과 불러오기"는 최신 **최종 리포트 + benchmark_debug**를 **읽기 전용**으로 표시(재생성 없음, `.tmp`·중간 실패 파일 무시).
- **timestamp 쌍 가드(Loop 4-A)**: report/debug를 독립 최신으로 고르지 않고, **최신 report의 timestamp에 대응하는 debug**를 매칭한다. 대응 debug가 없으면 report는 표시하되 **debug 다운로드를 비활성화**하고 "동일 timestamp debug 없음" 경고를 표시한다(엉뚱한 debug 조용히 제공 금지).

## 5. 실행 모드
- **A. 최근 결과 불러오기(필수 동작)**: `output/`에서 `삼성전자_산업대비_이상징후_리포트_{year}_*.xlsx` / `benchmark_debug_{year}_*.xlsx` 최신본 탐지·표시.
- **B. 새 분석 실행**: `pipeline.run_loop3b` 호출(캐시 기반·결정적, 새 timestamp). **MVP는 삼성전자 2025 기준**으로 동작. 그 외 입력은 안내 후 중단(엔진 tripwire가 `StopConditionError`로 halt → UI가 친절 안내). 다른 회사를 삼성 로직에 끼워맞추지 않음.

## 6. 범위 제외 (이번 루프 미포함)
배포 · 로그인 · DB 저장 · 여러 회사 동시 비교 · 자동완성 · 실행 history 관리 · 원문 HTML 자동 대조.

## 7. 파일 구성
- `app.py` — Streamlit 엔트리포인트(sidebar + 탭 + 다운로드)
- `src/ui_helpers.py` — Excel 탐지/읽기/요약추출/해석문구/다운로드 bytes/키 안전 처리(순수 함수, 단위테스트)
- `src/ui_runner.py` — 새 분석 실행 wrapper(기존 pipeline 호출, 엔진 미수정)
- `tests/test_ui_helpers.py` — helper 단위 테스트
- `requirements.txt` — 실행 의존성
- `run_app.bat` (Loop 4-B) — Windows 원클릭 런처(더블클릭 → `python -m streamlit run app.py`). `%~dp0`로 루트 이동, app.py/Python/Streamlit 미존재 시 안내 후 종료, 오류 시 `pause`. `.env` 미접근·key 미출력.
- `run_app.ps1` (Loop 4-B, 선택) — PowerShell 런처(`-ExecutionPolicy Bypass`). 사용법은 README.md.

## 8. 사용자 표현/색상 정책
- 판정 색상: NORMAL=중립(회색), HIGH=주황, LOW=파랑, 계산불가/peer부족=회색. **초록/빨강(좋음·나쁨) 금지**.
- HIGH/LOW/NORMAL은 **확정 판단이 아닌 검토 보조 분류**. **NORMAL은 위험 없음이 아님**. benchmark는 peer universe·mapping 정책 한계 있음. 매출채권·매입채무 비율은 순수계정 기준이라 peer 수 제한 가능. 사용자 표시 텍스트는 **한글 중심**.

## 9. Loop 7-2 — DARTLens Production-like UX Landing
> 데모 전시 페이지가 아니라 **실제 구동되는 분석 도구**처럼 정리하는 UX/문구/레이아웃 루프(기능 확장 아님, 엔진 불변).

- **브랜딩**: 앱 이름 **DARTLens — 동종산업대비 재무 이상징후 분석기**. page_title/hero에 반영. "데모/샘플 결과" 표현 미사용.
- **첫 화면(입력 중심)**: 상단 hero(DARTLens + 부제 + 2줄 설명) → 사이드바 **분석 입력** 패널(API Key·회사/종목코드·사업연도·**분석 실행**·**최근 분석 결과 불러오기**) → 결과 없을 때 **기능 카드 4개**(동종산업 Peer 구성·CFS 수집·15개 재무비율 분석·Excel 리포트 생성)를 작고 단정하게 표시. 5개 회사 결과 카드 나열식 데모 지양.
- **표시 layer 변환(원본 불변)**: `ui_helpers.status_display`로 raw status→한글 표시(PASS→분석 완료, PASS_WITH_WARNINGS→분석 완료·판정 제한, FAIL→분석 실패, INSUFFICIENT_PEERS→표본 제한, NOT_COMPUTABLE→계산 불가). debug/summary 원본 데이터는 변경하지 않음.
- **HIGH/LOW 고지**: "오류·부정의 결론이 아니라 동종산업 peer 대비 추가 검토가 필요한 재무비율 후보"임을 명시.
- **sparse peer 09시트 안내**: 리포트에 `09_제한적_peer_비교` 시트가 있을 때만(`ui_helpers.has_sparse_sheet`) 다운로드 영역에 참고 비교 안내 노출(없으면 과노출 금지). 09시트 테이블 전면 렌더링은 후속 루프.
- **최근 결과**: "데모"가 아닌 **기존 산출물 확인** 기능으로 표기. 최신 timestamp 우선, 읽기 전용(파일 삭제·정리 없음).
- **미변경**: 엔진 계산 로직, 판정 기준, min_peers, sparse 정책, `run_loop3b` 삼성 실행 경로, run_app.bat/ps1.

## 10. Loop 8-1 — GitHub Packaging README (문서 전용)
> 코드 변경 없음. `README.md`를 GitHub/포트폴리오 공개용 구조(이게 뭔가요 → 실행법 → 예시 결과 → 산출물 → 방법론 → 설계 원칙/한계 → 면접 포인트)로 재구성. 정확한 Excel 시트명(00~09)은 실제 산출물 기준으로 기재, 데모 영상/스크린샷은 `docs/screenshots/` placeholder만(이미지 미커밋). 실제 API Key·`.env` 미기재.

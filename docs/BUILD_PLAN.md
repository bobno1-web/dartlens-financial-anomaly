# BUILD_PLAN.md — 삼성전자 MVP

## Context (왜 만드는가)
OpenDART 연결재무제표(CFS) 기반 산업대비 이상징후 탐지 도구의 **첫 MVP**를 구현하기 위한 실행 계획.
대상=삼성전자(종목 005930), 사업연도=2025, 보고서=사업보고서(`reprt_code=11011`), `fs_div=CFS`.
원시 금액을 직접 비교하지 않고 **재무비율 + 계정 기반 구조비율**을 산업 benchmark(같은 `induty_code` 3자리 상장사, robust 통계, leave-one-out)와 비교해 HIGH/LOW(산업 대비 높음/낮음)를 표시하고, 근거·소스참조가 붙은 Excel을 산출한다.
문서/스캐폴딩은 완료 상태이며, 이 계획 승인 후 비즈니스 로직 구현을 시작한다.

## Ralph Loop 1 외부검증 결과 및 다음 루프 필수 조건 (2026-07-05)
**결과: `PASS_WITH_WARNINGS`.** 삼성전자 2025 CFS 수집 + peer universe(induty `264`, effective_prefix `264`, peer 후보 60) 디버그 산출물의 내부 검증 16/16 통과. 아래는 warning에서 도출한 **다음 루프(비율/벤치마크) 필수 조건**이다.
- **peer 후보 전체 CFS 수집 필수.** 벤치마크 계산 전에 effective_prefix 기준 peer 후보 **전체**의 CFS를 수집한다.
- **디버그 상한 subset은 벤치마크 미사용.** Loop 1에서 `peer_cfs_debug_limit`(=20)로 수집한 subset은 디버그 검증용이며 **산업 benchmark 계산에 사용하지 않는다.**
- **Long export에 `stock_code` 포함.** 다음 루프부터 FinancialFact(LONG) export에 `stock_code`를 포함한다(추적성).
- **비율 계산용 계정 추출**: `sj_div` 필터 + **결정적 dedup**(중복 시 max `rcept_no`). **SCE(자본변동표) 구성행은 비율 계산 원천으로 사용하지 않는다.** 손익계정은 **IS/CIS 양쪽**을, 영업이익은 `dart_OperatingIncomeLoss`와 `ifrs-full_ProfitLossFromOperatingActivities`를 **모두** 고려한다.
- **불확실 매핑**은 fuzzy matching을 확장하지 않고 `NOT_COMPUTABLE` + `reason=mapping_not_confident`로 처리한다.
- **산업 benchmark는 median/IQR 중심**, 평균(mean)은 winsorized **참고값**(판정 근거 아님).
- **Excel 사용자 표시 텍스트는 한글**(시트명·컬럼명·안내·판정/상태·감사코멘트·README/Methodology). 코드 식별자는 예외.

## Ralph Loop 2 역할·범위 (2026-07-05)
- **역할**: effective_prefix `264` peer 후보 **전체 CFS 수집** + 계정 매핑 + **회사별 ratio input(개별 비율값) 준비/검증**. 산업 benchmark·HIGH/LOW 판정은 **Loop 3**.
- **완료 기준**: 사업보고서 HTML 전수 대조가 아니라 **OpenDART API raw → ratio input까지의 추적 가능성 검증**. HTML 원문 대조는 삼성전자 + 일부 peer 샘플에 한해 별도 외부검증으로 수행하며, **60개사 전수 HTML 대조는 이번 루프 범위가 아님**.
- **debug subset 사용 금지**: Loop 1의 `peer_cfs_debug_limit=20` subset은 benchmark 계산에 사용하지 않는다. debug 상한이 적용된 데이터는 `debug_only`/`incomplete`로 표시. Loop 2는 상한을 해제하고 peer 후보 전체 CFS를 시도한다.
- **개별 비율값 허용**: Loop 2는 회사별 개별 비율값을 계산·표시할 수 있으나, **산업 benchmark 기반 HIGH/LOW 판정은 하지 않는다**(해당 칸은 "Ralph Loop 3에서 산업 benchmark 판정 예정"으로 한글 표기).
- **source traceability 필드**: `corp_code, stock_code, account_id, account_nm, amount, rcept_no, retrieved_at, request_hash`.

## Ralph Loop 2 외부검증 결과 (2026-07-05)
**결과: `PASS_WITH_WARNINGS` (hard blocker 없음).** Loop 3 진입 가능.
- peer 후보 **60개 전체** CFS 수집 시도 완료(디버그 상한 없음).
- CFS 성공 **51개**, 실패 **9개**. 실패 9개는 전부 `status=013` 등 **정당한 CFS 사용불가**로 검증됨.
- **OFS 자동 대체 흔적 없음**(CFS만 수집).
- ratio input 780건(52개사 × 15비율), 삼성전자 15/15 계산 가능, NOT_COMPUTABLE 84건(missing_account 75 / mapping_not_confident 6 / invalid_statement_section 3).

## Ralph Loop 3 정책·범위 (2026-07-05)
- **역할**: 비율별 산업 benchmark(median/IQR 중심) 계산 + 삼성전자 leave-one-out 비교 + HIGH/LOW/NORMAL/INSUFFICIENT_PEERS/NOT_COMPUTABLE/INSUFFICIENT_VARIANCE 판정 + 최종 사용자용 Excel + 검증용 debug Excel. (Loop 3에서 처음 수행.)
- **mapping 정책(엄격 유지)**: 매출채권·매입채무는 **순수 계정 기준**을 유지한다. `매출채권및기타채권`/`매입채무및기타채무` fallback과 재고자산 nm-fallback은 **Loop 3 기본 benchmark에 포함하지 않는다**(후속 개선 과제로 분리). 불확실 매핑은 `NOT_COMPUTABLE` + `reason=mapping_not_confident`로 둔다.
- **benchmark pool 정책**: pool은 51개 전체 고정이 아니라 **비율별 계산 가능 peer n 기준**이다. 산출물에 peer 후보 60 / CFS 성공 51 / CFS 실패 9 / **비율별 계산 가능 peer 수 n**을 모두 표시한다. 삼성전자는 각 비율의 benchmark 계산에서 제외(**leave-one-out**, 함수는 target `corp_code`를 인자로 받아 다중 target 확장 대비). 평균은 참고값, 판정은 median/IQR 중심, winsorized mean은 참고값 표시. `min_peers`는 config 기준.
- **benchmark_quality**: 비율별 `STRONG/LIMITED/WEAK/NOT_AVAILABLE`을 산출·표시하고 07_Methodology에 기준 설명.
- **색상/표현 정책**: HIGH=산업 대비 높음, LOW=산업 대비 낮음, NORMAL=IQR fence 기준 정상 범위. HIGH/LOW는 부정·오류·왜곡표시·좋음/나쁨이 아니다. **초록/빨강으로 좋고 나쁨을 암시하지 않는다**(HIGH=주황 계열, LOW=파랑 계열, 정상=무색/연회색, 계산불가/peer부족/분포부족=회색 계열). Excel 방법론 시트에 이 한계를 명시하고, 모든 사용자 표시 텍스트는 한글.

## Ralph Loop 3 외부검증 결과 및 Loop 3-B 보정 (2026-07-05)
**결과: `PASS_WITH_WARNINGS` (hard blocker 없음).**
- 통과: 계산 정확성·leave-one-out·NOT_COMPUTABLE/CFS 실패 제외·매핑 정책(순수계정)·traceability·색상/언어/키 미포함.
- warning: 사용자 배포 전 **deviation_rate 표현**과 **IQR 한계 고지** 보정 권고.

**Loop 3-B 보정 원칙(표현/해석만, 계산·label 불변):**
- benchmark pool·leave-one-out·median/IQR·label 판정 결과를 **임의 변경하지 않는다**. 15개 NORMAL 유지.
- 사용자 오독을 줄이기 위해 **표시명·비고·방법론 설명만** 보완한다.
- HIGH/LOW/NORMAL은 계속 IQR fence 기준. **NORMAL = "위험 없음"이 아니라 "현재 peer universe·IQR 기준상 정상 범위(이상치 아님)"**.
- **deviation_rate 표현**: "산업 대비 차이" 같은 모호한 이름 금지. ① 중앙값 대비 비율차이(%)와 ② **중앙값 대비 차이(%p, =값−중앙값)** 를 병행 표시. %단위 비율은 %p를 우선 해석값으로 제시, 회전율/배수 항목은 값 차이로 표시. 중앙값이 작아 배수차이가 크게 보이면 비고를 남긴다.
- **IQR 한계 고지**: induty_code 264 peer는 소형 peer와 대형 복합사(삼성)가 섞여 분포 꼬리가 두껍고 IQR fence가 넓어져 전부 NORMAL이 될 수 있음 → percentile·robust_z·benchmark_quality·peer 수를 함께 해석. README/Methodology에 명시.

## 확정 결정 (Plan 세션)
- **Peer**: OpenDART `corp_cls` 기준 상장회사 범위(초기 의도: 유가증권·코스닥 상장사 전체) 중 `induty_code` 3자리 prefix가 같은 회사. **구체 `corp_cls` 값은 구현 시 OpenDART 응답 정의를 확인해 `config/settings.yaml` 또는 `mappings/`로 관리(코드 하드코딩 금지).** 캐시우선. peer<`min_peers`면 2자리로 1회 rollup 후 부족 시 `INSUFFICIENT_PEERS`. **실제 사용된 effective prefix·rollup 발생 여부·peer `corp_code` 목록을 `06_Peer_List`·`07_Methodology`에 반드시 기록.**
- **ROA/ROE**: MVP는 기말값 사용(ROA=당기순이익/기말총자산, ROE=당기순이익/기말자본). 전기(2024) 미수집. (한계·확장은 `07_Methodology`에 명시 — 아래 참조.)
- **차입금**: 이자부 차입금 = 단기차입금 + 유동성장기부채 + 사채 + 장기차입금(리스부채 제외).
- **매입채무비율 분모**: 매출원가.
- **산업 대비 차이**: 중앙값 대비 부호 있는 % = (삼성값 − 산업중앙값)/|산업중앙값|. 산업평균은 winsorized 참고값으로 별도 표시.
- **판정**: IQR fence(k=1.5), robust z(|z|>3.5)·percentile은 심각도 보조. `min_peers=5`. 값은 `config/settings.yaml`.
- **감사 관점 코멘트**: 비율·방향·심각도 기반 규칙 템플릿(결정적, 설명가능).
- **데이터 가용성**: 2025 사업보고서가 **OpenDART API에서 조회 가능한 경우에만 진행**. 조회 불가·불완전·정정공시 충돌 시 **자동으로 2024로 fallback하지 않고, 사용자 확인 후 진행**.

## 계정 매핑 (mappings/account_concepts.csv, account_id 우선·명시 account_nm 폴백)
| 개념 | 표준 개념(예시) | 비고 |
|---|---|---|
| 매출액 | ifrs-full_Revenue | |
| 매출원가 | ifrs-full_CostOfSales | |
| 영업이익 | dart_OperatingIncomeLoss / ifrs-full_ProfitLossFromOperatingActivities | 필러 변형 → 둘 다 매핑 |
| 당기순이익 | ifrs-full_ProfitLoss | |
| 자산총계 / 유동자산 | ifrs-full_Assets / ifrs-full_CurrentAssets | |
| 부채총계 / 유동부채 | ifrs-full_Liabilities / ifrs-full_CurrentLiabilities | |
| 자본총계 | ifrs-full_Equity | 총자본 기준 |
| 재고자산 | ifrs-full_Inventories | |
| 매출채권 | 매출채권(전용) 우선, 없으면 매출채권및기타채권 | 매핑 리스크 |
| 매입채무 | 매입채무 우선, 없으면 매입채무및기타채무 | 매핑 리스크 |
| 차입금 구성 | 단기차입금·유동성장기부채·사채·장기차입금 | 단일 태그 없음 → 매핑 리스크 |

파생: 운전자본 = 유동자산 − 유동부채.

**매핑 신뢰 규칙**: canonical mapping으로 **확정 가능한 경우에만** 계산한다. 불확실하면 **임의 fuzzy matching으로 확장하지 않는다.** 해당 비율을 `NOT_COMPUTABLE`로 두고 `reason = mapping_not_confident`를 기록한다.

## 구현 순서 · 단계별 파일 · 성공 기준
- **S0 기반** — `src/config.py`. settings.yaml + `.env` 로드, 로깅. ✅ 키 없으면 즉시 중단, 임계값은 config에서.
- **S1 dart_client** — `src/dart_client.py`. HTTP·상태코드(000/013/020/010·011/800)·retry/backoff·`request_hash` 캐시·raw 스냅샷+manifest. ✅ 캐시 히트 시 API 미호출, raw verbatim 저장.
- **S2 corp_codes** — `src/corp_codes.py`. corpCode.xml 캐시, 종목 005930→`corp_code`(상수화 금지, 조회). ✅ 매핑 확인, 모호 시 에러.
- **S3 collect** — `src/collect.py`. company.json(`induty_code`) + 삼성·peer CFS 수집. **2025 조회 가능성 확인, 불가/불완전/정정충돌 시 사용자 확인(자동 2024 fallback 금지).** ✅ 삼성 induty_code 확보, peer 목록 확정·기록, 각 CFS raw 저장.
- **S4 parse+accounts** — `src/parse.py`, `src/accounts.py`, `mappings/account_concepts.csv`. raw→FinancialFact(LONG), account_id→개념. ✅ 결정적 dedup(max `rcept_no`), CFS/OFS 태그 분리, 매핑 커버리지·누락 리포트, **불확실 매핑은 확장 없이 mapping_not_confident**.
- **S5 ratios** — `src/ratios.py`. 15개 비율(NOT_COMPUTABLE 가드). ✅ 분모≤0/누락→NOT_COMPUTABLE, **불확실 매핑→NOT_COMPUTABLE(reason=mapping_not_confident)**, inf/NaN 미유출, `source_rcept_no` 기록.
- **S6 benchmarks** — `src/benchmarks.py`. 3자리 그룹·CFS만·`acc_mt` 공통월 필터·leave-one-out·robust stats. ✅ `peer_corp_codes`·effective prefix·rollup 여부 기록, `n_companies`=계산가능 수.
- **S7 compare** — `src/compare.py`. ComparisonResult+label+reason+감사코멘트. ✅ 라벨 규칙대로, deviation_rate=중앙값 대비 %, reason 결정적(mapping_not_confident 포함).
- **S8 excel_report** — `src/excel_report.py`. 7시트·컬럼·label 기반 조건부서식·소스참조·원자적 no-clobber 쓰기. ✅ 7시트 생성, 각 비율행 소스참조, `--overwrite` 없이 미덮어씀.
- **S9 pipeline+tests+methodology** — `src/pipeline.py`, `tests/test_ratios.py`·`test_benchmarks.py`·`test_compare.py`·`test_excel_report.py`, `07_Methodology` 채움. ✅ 삼성 2025 end-to-end 리포트 생성, 위험경로 테스트 통과.

## Excel 산출물
7시트: `01_삼성전자_연결재무제표`·`02_수익성`·`03_안정성_재무구조`·`04_운전자본_계정리스크`·`05_회전율`·`06_Peer_List`·`07_Methodology`.
비율 시트 컬럼: 비율명·산식·삼성전자 값·산업 평균(winsorized)·산업 중앙값·산업 대비 차이·판정·감사 관점 코멘트·사용 계정·peer 수 (+소스참조: rcept_no/account_ids/retrieved_at). 라이브러리 xlsxwriter.

**언어 규칙**: 두 Excel의 사용자 표시 텍스트(시트명·컬럼명·안내·판정/상태·감사 관점 코멘트·README/Methodology)는 **한글**을 기본으로 한다. 코드 내부 식별자·변수명은 예외.

**06_Peer_List 필수 기록**: effective `induty_code` prefix, rollup 발생 여부, 포함된 peer `corp_code` 전체 목록·수.
**07_Methodology 필수 기재**:
- ROA/ROE는 MVP에서 **기말총자산·기말자본 기준**으로 계산한다는 한계, **추후 다개년 수집 시 평균총자산·평균자본 기준으로 확장** 예정.
- 사용된 effective prefix·rollup 여부·peer 목록(요약), 비율 정의·차입금 구성·판정 규칙·라벨 의미·"검토 후보 ≠ 부정" 고지.

## cr1 리뷰 지점
- **S4 후**: 계정 매핑·dedup 결정성·CFS/OFS 분리·데이터 손실·mapping_not_confident 처리.
- **S6 후**: peer 정의·leave-one-out·robust 수식·`acc_mt` 필터.
- **S7 후**: 라벨·설명가능성·삼성 한 회사 과적합.
- **S8~S9**: 소스 추적성·no-clobber·과장 표기 (경량 최종 1회).
(cr1은 리뷰만, 파일 수정 안 함.)

## 금지사항
- 회사/계정/파일 하드코딩(삼성 `corp_code`도 상수화 금지 — 조회).
- raw 덮어쓰기, 조용한 drop, 원시금액 직접 비교.
- 불확실 계정의 임의 fuzzy matching 확장.
- 데이터 가용성 문제 시 자동 연도 fallback.
- HIGH/LOW를 좋음/나쁨으로 표기.
- config 밖 임계값 하드코딩.
- 승인 전 구현. webapp·DB·ML·MCP·hook·plugin.

## Verification (end-to-end)
1. `.env`에 실제 키 설정 후 파이프라인 실행(예: `python -m src.pipeline --company 005930 --year 2025`) → `output/`에 타임스탬프 `.xlsx` 생성.
2. 7시트 존재, 02~05에 삼성값·중앙값·판정·소스참조, 06_Peer_List에 effective prefix·rollup 여부·peer 목록, 07_Methodology 채워짐 확인.
3. **재현성**: 재실행 시 캐시로 API 미호출·동일 산출.
4. `pytest`로 위험경로 통과(벤치마크 수식·NOT_COMPUTABLE·dedup 결정성·no-clobber).
5. **역추적 1건 수기 확인**: 임의 비율값 → 사용 계정 → FinancialFact → raw 스냅샷/rcept_no.

## 승인 후 첫 작업
S0(config)부터 구현, S4·S6·S7에서 cr1 리뷰. (본 계획 저장 시점에는 구현 미착수.)

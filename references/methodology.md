# 분석 방법론 (methodology)

> **목적:** 이상치를 **어떻게** 판단하는지 — 비율 비교, robust 통계, leave-one-out, 라벨 정의. 임계값 수치는 `config/settings.yaml`에 있다.

## 왜 원시 금액이 아니라 비율인가
같은 산업이라도 회사 규모 차이가 매우 크다. 원시 금액(매출·자산·부채)을 비교하면 규모순 정렬이 되어 크거나 작은 회사가 전부 "이상치"로 잡힌다. 대신 **재무비율**(수익성·수익률·레버리지·유동성·효율성)을 비교한다. 비율은 규모 독립적이다. 단, 분자·분모의 `currency`·`unit`이 일치할 때만 계산한다.

## 비율 계산용 계정 추출 규칙
CFS LONG에서 비율의 분자·분모 계정을 뽑을 때:
- **`sj_div` 필터**를 적용해 해당 재무제표 구분에서만 계정을 취한다.
- **결정적 dedup**: 동일 계정 중복 시 max `rcept_no` 하나만 남긴다(순서 의존 금지).
- **SCE(자본변동표) 구성행은 비율 계산 원천으로 사용하지 않는다**(부분합·중복 성격).
- **손익계정은 IS/CIS 양쪽**을 고려한다(필러에 따라 손익이 IS 또는 CIS에 나타남).
- **영업이익**은 `dart_OperatingIncomeLoss`와 `ifrs-full_ProfitLossFromOperatingActivities`를 **모두** 고려한다.
- **불확실한 매핑은 fuzzy matching을 확장하지 않는다.** 확정 불가 시 `NOT_COMPUTABLE` + `reason=mapping_not_confident`로 남긴다.

## Robust 벤치마크 통계 (median / IQR / MAD)
**산업 benchmark는 평균이 아니라 median/IQR를 중심으로 산출한다.** 산업 내 비율 분포는 표본이 적고 꼬리가 두껍다(분모가 작으면 비율이 폭발). 평균·표준편차는 이상치 하나에 왜곡되므로 **robust 통계를 정본**으로 쓴다.
- **median** — 이상치에 강한 중심값
- **IQR** (p75 − p25) — 산포. 1차 이상탐지 fence 근거
- **MAD** (median absolute deviation) — robust z-score용 산포

평균·표준편차도 보고하되 **winsorized(5%/95%)한 참고값**일 뿐, 플래그 근거로 쓰지 않는다.

## Leave-one-out 벤치마크
대상 회사는 **자기 자신의 벤치마크에서 제외**한다. median·IQR·MAD는 대상 행을 뺀 peer 풀에서 재계산한다. 표본이 적을 때 대상을 포함하면 벤치마크가 대상 쪽으로 끌려가 정작 잡아야 할 이상치가 희석된다.

## 이상탐지 규칙
1차: **IQR(Tukey) fence**, 배수 `k`(config `iqr_fence_k`).
`LOW` = value < Q1 − k·IQR, `HIGH` = value > Q3 + k·IQR.
**robust z**(`|0.6745·(value − median)/MAD| > robust_z_cutoff`)와 **percentile**(< p05 / > p95)은 *심각도(severity)* 정보를 더할 뿐, 단독으로 플래그를 만들지 않는다.

## 라벨 정의
(company, ratio, year)마다 정확히 하나의 라벨:

| label | 의미 |
|---|---|
| NORMAL | peer 범위 안 — 검토 후보 아님 |
| HIGH | 상단 fence 초과 (Q3 + k·IQR) — peer 대비 비정상적으로 높음 |
| LOW | 하단 fence 미만 (Q1 − k·IQR) — peer 대비 비정상적으로 낮음 |
| INSUFFICIENT_PEERS | 계산가능 peer가 `min_peers` 미만(1회 KSIC rollup 후) — 판정 안 함 |
| NOT_COMPUTABLE | 비율 미정의(분모 ≤ 0, 계정 누락, 음(−) 자본) — 분포에서 제외, 대치 없음 |
| INSUFFICIENT_VARIANCE | peer 분산이 0(IQR=0 & MAD=0) — 의미 있는 fence 없음, 플래그 없음 |

`HIGH`/`LOW`가 검토 후보다. 모든 플래그는 사람이 읽을 수 있는 `reason` 문자열과 원본 참조를 동반한다. **플래그는 사람의 검토를 요청하는 신호이지, 부정·오류의 결론이 아니다**(→ `references/project-goal.md`).

## Loop 3 benchmark 운영 정책 (2026-07-05)
- **비율별 benchmark pool**: pool은 CFS 성공 peer 고정 수가 아니라 **해당 비율을 계산 가능한 peer만** 포함한다. `NOT_COMPUTABLE`인 회사와 CFS 실패 회사는 그 비율의 pool에서 제외한다. **`n_companies`는 "CFS 성공 peer 수"가 아니라 그 비율의 계산 가능 peer 수**다.
- **leave-one-out**: target(삼성전자)은 모든 비율의 산업 benchmark 계산에서 제외한다. 단 target 값은 비교 대상값으로 유지한다. benchmark 함수는 향후 다중 target 확장을 위해 target `corp_code`를 인자로 받는다.
- **통계 산출**: `mean, winsorized_mean, median, p25, p75, iqr, mad, std, min, max, n_companies`. 판정은 median/IQR 중심, `mean`·`winsorized_mean`은 참고값. p25/p75/median은 선형보간(정렬 후 위치보간) 기준. n이 부족하면 무리하게 계산하지 않고 라벨로 처리한다. NaN/inf는 최종 산출물에 남기지 않는다.
- **판정 순서(결정적)**: ① target `NOT_COMPUTABLE` → `NOT_COMPUTABLE` ② `n_companies < min_peers` → `INSUFFICIENT_PEERS` ③ `iqr` 계산 불가 또는 `iqr ≤ 0`(변동성 부족) → `INSUFFICIENT_VARIANCE` ④ `target > p75 + k·iqr` → `HIGH` ⑤ `target < p25 − k·iqr` → `LOW` ⑥ 그 외 `NORMAL`.
- **보조 지표**: `robust_z`(=0.6745·(value−median)/MAD, MAD=0이면 None), `percentile`(pool 대비 위치), `deviation_rate`(=(value−median)/|median|, `median`이 0 또는 매우 작으면 계산 부적절로 두고 별도 reason 기록).
- **benchmark_quality**: 비율별 등급 — `STRONG`(n이 min_peers의 2배 이상 + iqr>0 + coverage 충분), `LIMITED`(n은 충분하나 iqr=0이거나 mapping coverage 낮음/분포 불안정), `WEAK`(n이 min_peers는 넘지만 작음), `NOT_AVAILABLE`(계산 불가). 산출물에 표시하고 07_Methodology에 기준을 요약한다.
- **mapping 엄격 유지**: 매출채권·매입채무는 순수 계정 기준. `및기타채권/및기타채무` fallback과 재고자산 nm-fallback은 Loop 3 기본 benchmark에서 확장하지 않는다.

## Loop 3-B 표현/해석 보정 (2026-07-05, 계산 불변)
계산·pool·label은 그대로 두고 사용자 오독 리스크만 낮춘다.
- **deviation 표시 이원화**: ① `중앙값 대비 비율차이(%)` = (값−median)/|median| (상대 배수 성격) ② `중앙값 대비 차이(%p·값)` = 값−median. 비율(%)단위 항목(수익성·안정성·운전자본)은 **%p**(=(값−median)×100)를 우선 해석값으로, **회전율(배수)** 항목은 값 차이로 표시한다. 표시 기준은 07_Methodology에 기재.
- **해석 비고(자동 규칙)**: median 절대값이 작아 배수차이가 크게 보이면 "중앙값이 작아 배수차이가 크게 보일 수 있음(다만 IQR 이상치 미초과)", NORMAL이지만 percentile≥90/≤10이면 "상대적 상·하위권이나 IQR 이상치 미초과", benchmark_quality가 WEAK/LIMITED면 "peer 수/커버리지 제한, 해석 주의"를 남긴다.
- **NORMAL 의미**: "위험 없음"이 아니라 **현재 peer universe·IQR fence 기준상 이상치로 분류되지 않음**. percentile·robust_z·benchmark_quality·peer 수를 함께 해석한다.
- **IQR fence 한계**: peer 분포 꼬리가 두껍거나 비교가능성이 낮은 회사가 섞이면 fence가 넓어져 HIGH/LOW가 줄고 전부 NORMAL이 나올 수 있다. 전부 NORMAL은 "검토 불필요"가 아니다.

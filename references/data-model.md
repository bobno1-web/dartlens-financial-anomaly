# 데이터 모델 (data-model)

> **목적:** 모듈 간 **공유 필드 이름의 정본**. 여기 정의를 바꾸면 전 파이프라인에 영향을 준다. 표 형식 상세는 `docs/DATA_MODEL.md`와 항상 일치시킨다.

## 공통 원칙
- 금액은 **full-value Decimal**로 verbatim 저장한다(수집 시 재스케일 금지). `currency` + `unit`(=1)을 동반한다.
- 사실(fact)의 키는 표준 `account_id`. `account_nm`은 **표시용**이며 키로 쓰지 않는다.
- 결측값은 **대치(imputation)하지 않는다** — 계산 불가로 표시하고 분포에서 제외한다.
- 표준 개념 매핑은 코드가 아니라 `mappings/account_concepts.csv`에서 온다.

## 엔티티 (필드 목록)

**Company**
`corp_code, corp_name, stock_code, corp_cls, induty_code, industry_name, est_dt, acc_mt, source`
- `acc_mt` = 결산월(연말). 동일 회계기간 peer 필터에 사용.

**FinancialFact** — LONG, 계정 한 줄당 한 행
`corp_code, stock_code, bsns_year, reprt_code, fs_div(요청), fs_div_actual(응답), sj_div, account_id, account_nm, amount(Decimal), currency, unit(=1), rcept_no, ord, retrieved_at, request_hash`
- `fs_div_actual`은 CFS 폴백 여부를 구분한다(벤치마크 오염 방지의 핵심).
- **`stock_code`**: Ralph Loop 1 외부검증 결과 반영 — 다음 루프부터 LONG export에 포함(추적성).

**DerivedRatio**
`corp_code, bsns_year, ratio_name, ratio_value(None 가능), numerator_account, denominator_account, source_rcept_no`

**IndustryBenchmark** (Loop 3)
`induty_code(유효 prefix), fs_div_actual, bsns_year, ratio_name, n_companies(비율별 계산가능 peer 수), peer_corp_codes, median, p25, p75, iqr, mad, mean, winsorized_mean, std, min, max, benchmark_quality`
- `median/p25/p75/iqr/mad` = robust 정본. `mean/winsorized_mean/std` = 참고용(판정 근거 아님).
- `n_companies` = **비율별 계산가능 peer 수**(CFS 성공 고정 수가 아님). `peer_corp_codes` = 풀에 포함된 peer 목록(추적성). target(삼성전자)은 leave-one-out으로 제외.
- `benchmark_quality` ∈ `{STRONG, LIMITED, WEAK, NOT_AVAILABLE}` — 기준은 `references/methodology.md`.

**ComparisonResult** (Loop 3, Loop 3-B 표시필드 포함)
`corp_code, bsns_year, ratio_name, company_value, industry_median, industry_mean, deviation_rate, deviation_pp, deviation_reason, robust_z, percentile, n_companies, peer_candidates, cfs_success, cfs_fail, label, reason, audit_comment, interpret_note, benchmark_quality, source_reference`
- `label` 값 정의는 `references/methodology.md` 참조. HIGH/LOW=산업 대비 높음/낮음(좋음/나쁨 아님).
- `deviation_rate` = (company_value − median)/|median| (비율차이%); `median`≈0이면 None + `deviation_reason`.
- **`deviation_pp`** (Loop 3-B) = company_value − median. 비율(%)단위는 %p(×100), 회전율은 값 차이로 표시.
- `audit_comment` = 그룹·방향 결정적 템플릿(과장 금지). **`interpret_note`** (Loop 3-B) = median 작음/percentile 상하위권/quality 제한 자동 비고.

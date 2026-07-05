# docs/PLAN.md — MVP Development Plan

OpenDART consolidated-financial-statement industry-anomaly tool.
MVP, local Python script. **Not a web app.**

## Objective
For a target company: collect consolidated (CFS) financial statements from
OpenDART, classify by industry, compute **ratio-based** industry benchmarks,
compare the target to peers, and export review candidates to Excel — every value
traceable to its source filing.

## Pipeline (module / implementation order)
1. `config` + `dart_client` — load config & API key (hard-stop if key missing);
   HTTP with retry/backoff and OpenDART status-code handling.
2. `corp_codes` — corpCode master → resolve target (prefer `stock_code`;
   ambiguous name → error, never guess).
3. `collect` — `company.json` (industry) + CFS facts; raw snapshot + request-hash cache.
4. `parse` + `accounts` — raw JSON → `FinancialFact`; map `account_id` → canonical concept.
5. `ratios` — `DerivedRatio` with not-computable guards.
6. `benchmarks` — `IndustryBenchmark` (robust statistics).
7. `compare` — `ComparisonResult` + anomaly labels + `reason` strings.
8. `excel_report` — the workbook.
9. `pipeline` — CLI wiring + methodology notes + a few practical tests.

## Five locked corrections (from cr1 review)
Mandatory design constraints, not optional refinements:

1. **Peer universe recorded.** The peer set is an explicit, reproducible query
   (listed companies, `corp_cls in {Y,K}`, same effective KSIC prefix, same
   `bsns_year`). The full peer `corp_code` list is written into the benchmark
   output so a reviewer sees exactly who was in the pool.
2. **CFS/OFS separation.** Benchmarks are computed per `fs_div_actual`. Peers that
   fall back to OFS are excluded from the CFS pool (or pooled separately). The
   target is always compared like-for-like (CFS vs CFS).
3. **Fiscal month filter.** Peers are filtered to a common fiscal month using
   `acc_mt`; off-cycle companies are flagged, not silently blended.
4. **Deterministic amended-filing dedup.** When original and amended filings
   collide, keep a deterministic survivor (max `rcept_no`) and record which
   `rcept_no` won. Same input → same output.
5. **Leave-one-out benchmark.** The target is excluded from its own benchmark
   (median/IQR/MAD recomputed without the target row) to avoid dampening its own
   anomaly at small peer counts.

## Ratios (MVP)
Compare **ratios, never raw amounts**: net profit margin, operating margin, ROA,
ROE, debt-to-equity, debt ratio, current ratio, asset turnover.
(revenue growth optional — needs the prior year's own filing.)

## Guards
- `min_peers = 5`; one KSIC-prefix rollup if short, then `INSUFFICIENT_PEERS`.
- denominator ≤ 0 or missing input → `NOT_COMPUTABLE`, excluded from the
  distribution (no inf/NaN leaks into statistics).
- negative equity → ROE / debt-to-equity `NOT_COMPUTABLE` + flagged.
- `n_companies` counts the **computable** distribution, not the raw pool.

## Practical tests (risky paths only)
Benchmark math + fallbacks (`MAD==0`→IQR, `IQR==0 & MAD==0`→`INSUFFICIENT_VARIANCE`);
not-computable paths leak no inf/NaN; dedup determinism (original + amended → one
deterministic survivor); CFS-missing peer tagged OFS and **not** pooled into CFS;
prefix rollup records the effective prefix; Excel rows carry source refs and
refuse to clobber without `--overwrite`.

## Open decisions
See `docs/DECISIONS.md` — notably peer-universe API cost (OpenDART ~20k calls/day),
single vs multi-year, and annual-only vs quarterly.

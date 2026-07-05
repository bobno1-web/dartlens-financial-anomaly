# docs/DECISIONS.md — MVP decisions log

Current locked decisions for the MVP. Revisit as the tool matures.

| # | Decision | Rationale |
|---|---|---|
| D1 | **Annual reports only** (`reprt_code = 11011`) | Simplest, most complete filings; quarterly deferred. |
| D2 | **Consolidated statements first** (`fs_div = CFS`) | Consolidated is the primary basis for cross-company comparison. |
| D3 | **Single business year per run** | Keeps MVP scope tight; multi-year deferred. |
| D4 | **Cache-first API collection** | Reproducible, API-free re-runs; respects OpenDART's daily quota. |
| D5 | **Benchmark by listed peers in the same effective KSIC prefix** | Industry-comparable, reproducible peer pool (see the five locked corrections in `docs/PLAN.md`). |

## Open questions to confirm
- **Peer-universe API cost.** Enumerating all listed peers × fetching each one's
  CFS may approach OpenDART's ~20,000 calls/day quota. Confirm: all listed peers
  vs a capped sample.
- **Single vs multi-year.** MVP assumes one `bsns_year`.
- **Annual vs quarterly.** MVP assumes annual only.

## Related documents
- Five locked corrections & roadmap: `docs/PLAN.md`
- Core data model: `docs/DATA_MODEL.md`
- Methodology & labels: `docs/METHODOLOGY.md`

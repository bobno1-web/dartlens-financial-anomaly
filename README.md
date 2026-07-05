# 재무제표 이상징후 — OpenDART Financial-Statement Industry-Anomaly Tool

A local Python tool that uses the **OpenDART API** to collect consolidated
financial statements, benchmark a target company against its listed industry
peers, and export **review candidates** to Excel.

## What it does
- Collects **consolidated (CFS)** financial statements for a target company and its
  listed industry peers from OpenDART.
- Classifies companies by industry using the KSIC industry code (`induty_code`).
- Computes **ratio-based** industry benchmarks with robust statistics
  (median / IQR / MAD) on a **leave-one-out** peer pool.
- Compares the target's ratios to its peer benchmarks and labels each ratio.
- Exports results to an Excel workbook with unusually high/low values marked for
  human review, each value traceable back to its source filing.

## MVP scope
- **Annual reports only** (`reprt_code = 11011`).
- **Consolidated statements first** (`fs_div = CFS`).
- **Single business year** per run.
- **Cache-first** API collection — re-runs are reproducible and API-free.
- Peers = **listed companies in the same effective KSIC prefix**.
- Output = a single, timestamped `.xlsx` report. **Not a web app.**

## What this tool does NOT claim
- Flagged items are **review candidates only** — statistical outliers relative to
  industry peers. They are **NOT** conclusions of fraud, error, or misstatement.
- A flag means "a human should look at this," nothing more.
- A `NORMAL` label does **not** certify a company as healthy or correct.
- Benchmarks depend on peer availability and data quality; small or noisy peer
  groups are labelled as such and must be treated with caution.

## Documentation
- `docs/PLAN.md` — MVP roadmap and the five locked design corrections.
- `docs/DATA_MODEL.md` — core data model (shared field names).
- `docs/METHODOLOGY.md` — ratio-based comparison, robust stats, labels.
- `docs/DECISIONS.md` — locked MVP decisions and open questions.

## Status
Scaffolding stage — structure and planning docs only. No business logic
implemented yet (see `CLAUDE.md`: no implementation before plan approval).

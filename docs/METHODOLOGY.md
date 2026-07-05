# docs/METHODOLOGY.md — Analysis methodology

## Why ratios, not raw amounts
Companies in the same industry differ enormously in size. Comparing raw amounts
(revenue, assets, liabilities) would rank companies by scale and flag every large
or small firm as an "anomaly." Instead we compare **financial ratios** (margins,
returns, leverage, liquidity, efficiency), which are scale-independent: a small
and a large company with the same current ratio look the same. A ratio is only
computed when its numerator and denominator share currency and unit.

## Robust benchmark statistics (median / IQR / MAD)
Ratio distributions within an industry are small-n and fat-tailed (ratios explode
near small denominators). Classical mean / standard deviation are distorted by a
single outlier, so **robust** statistics are primary:

- **median** — central tendency, resistant to outliers.
- **IQR** (p75 − p25) — spread; drives the primary anomaly fence.
- **MAD** (median absolute deviation) — spread for the robust z-score.

Mean and standard deviation are still reported but are **winsorized (5% / 95%) and
informational only** — never the basis for a flag.

## Leave-one-out benchmark
The target company is **excluded from its own benchmark**. Median, IQR, and MAD
are recomputed on the peer pool without the target row. At small peer counts,
including the target would pull the benchmark toward itself and dampen the very
anomaly we are trying to surface.

## Anomaly rule
Primary: the **IQR (Tukey) fence** with multiplier `k` (config `iqr_fence_k`):
`LOW` if value < Q1 − k·IQR, `HIGH` if value > Q3 + k·IQR. The **robust z-score**
(`|0.6745·(value − median)/MAD| > robust_z_cutoff`) and the **percentile**
(< p05 / > p95) add *severity* context but do **not** by themselves create a flag.

## Labels
Each (company, ratio, year) receives exactly one label:

| label | meaning |
|---|---|
| NORMAL | within the peer range; not a review candidate |
| HIGH | above the upper fence (Q3 + k·IQR) — unusually high vs peers |
| LOW | below the lower fence (Q1 − k·IQR) — unusually low vs peers |
| INSUFFICIENT_PEERS | fewer than `min_peers` computable peers (after one KSIC rollup); not assessed |
| NOT_COMPUTABLE | ratio undefined (denominator ≤ 0, missing account, negative equity); excluded from the distribution, never imputed |
| INSUFFICIENT_VARIANCE | peer spread is zero (IQR = 0 and MAD = 0); no meaningful fence, no flag |

`HIGH` / `LOW` are the review candidates. Every flag carries a human-readable
`reason` string and full source references. **A flag is a prompt for human
review — not a conclusion of fraud, error, or misstatement.**

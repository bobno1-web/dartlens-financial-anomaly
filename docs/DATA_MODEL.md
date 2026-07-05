# docs/DATA_MODEL.md — Core data model

Field names are **shared across all modules** and must stay consistent.
Amounts are stored verbatim as full-value Decimals (no rescaling at ingest).
Facts are keyed on standardized `account_id`; `account_nm` is display-only.

## Company
| field | meaning |
|---|---|
| corp_code | OpenDART 8-digit company code (primary key) |
| corp_name | company name |
| stock_code | 6-digit stock code (blank if unlisted) |
| corp_cls | market class: Y/K/N/E |
| induty_code | KSIC-style industry code |
| industry_name | industry name (from `ksic_names` mapping; may be null) |
| est_dt | establishment date |
| acc_mt | fiscal month (year-end); used for the fiscal-month peer filter |
| source | endpoint + rcept_no + retrieved_at |

## FinancialFact — LONG (one row per account line)
| field | meaning |
|---|---|
| corp_code | company code |
| bsns_year | business (reporting) year |
| reprt_code | report type (11011 annual, ...) |
| fs_div | requested statement division (CFS/OFS) |
| fs_div_actual | division actually returned (CFS, or OFS on fallback) |
| sj_div | statement type: BS/IS/CIS/CF/SCE |
| account_id | standardized account id (**key**) |
| account_nm | account label (display only) |
| amount | full-value Decimal |
| currency | reported currency |
| unit | 1 (OpenDART returns full values) |
| rcept_no | filing receipt number (source trace) |
| ord | line order within the statement |
| retrieved_at | UTC retrieval timestamp |
| request_hash | content hash of the API request (cache key) |

## DerivedRatio
| field | meaning |
|---|---|
| corp_code | company code |
| bsns_year | business year |
| ratio_name | e.g. `current_ratio`, `roa` |
| ratio_value | computed ratio (None if not computable) |
| numerator_account | canonical concept used as numerator |
| denominator_account | canonical concept used as denominator |
| source_rcept_no | rcept_no(s) of the source facts |

## IndustryBenchmark
| field | meaning |
|---|---|
| induty_code | effective KSIC prefix actually used |
| fs_div_actual | basis of the pool (CFS) |
| bsns_year | business year |
| ratio_name | ratio |
| n_companies | count of computable peers (leave-one-out) |
| peer_corp_codes | list of peers in the pool (traceability) |
| mean, std | winsorized — informational only |
| median, p25, p75, iqr, mad | robust primary statistics |

## ComparisonResult
| field | meaning |
|---|---|
| corp_code | target company |
| bsns_year | business year |
| ratio_name | ratio |
| company_value | target's ratio value |
| industry_median | peer median (leave-one-out) |
| industry_mean | peer winsorized mean (informational) |
| deviation_rate | (value − median) / \|median\|, signed |
| robust_z | 0.6745 × (value − median) / MAD |
| percentile | target's percentile within peers |
| n_companies | computable peer count |
| label | NORMAL / HIGH / LOW / INSUFFICIENT_PEERS / NOT_COMPUTABLE / INSUFFICIENT_VARIANCE |
| reason | human-readable explanation |

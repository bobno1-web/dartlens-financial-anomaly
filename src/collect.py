"""Collection orchestration for Loop 1 (collection + peer universe, NO ratios).

Flow:
  1. resolve target stock_code -> corp_code (corpCode master)
  2. company.json for the target -> induty_code, corp_cls, acc_mt; effective_prefix
  3. scan listed companies' company.json for induty_code (threaded, cached) and
     keep those whose induty_code prefix == target effective_prefix and whose
     corp_cls is in listed_corp_cls -> peer candidates
  4. collect CFS (fnlttSinglAcntAll, fs_div=CFS) for the target + a capped subset
     of peers (debug), recording status for every candidate.

Nothing is silently dropped: every candidate carries cfs_fetch_status and
exclude_reason; caps are explicit and logged.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from . import corp_codes as cc
from .dart_client import DartClient, StopConditionError
from .parse import parse_cfs_rows

REPRT_ANNUAL = "11011"


def _company_info(client: DartClient, corp_code: str) -> dict:
    res = client.get_json("company.json", {"corp_code": corp_code}, "company")
    return res["data"]


def resolve_target(client: DartClient, records: list[dict], stock_code: str,
                   prefix_len: int) -> dict:
    rec = cc.resolve_by_stock(records, stock_code)
    corp_code = rec["corp_code"]
    info = _company_info(client, corp_code)
    if info.get("status") != "000":
        raise StopConditionError(
            f"삼성전자 기업개황 조회 실패(status {info.get('status')}: {info.get('message')}). (STOP)")
    induty = (info.get("induty_code") or "").strip()
    if not induty:
        raise StopConditionError("삼성전자 induty_code가 조회되지 않았습니다. (STOP)")
    return {
        "corp_code": corp_code,
        "corp_name": info.get("corp_name") or rec["corp_name"],
        "stock_code": (info.get("stock_code") or rec["stock_code"]).strip(),
        "corp_cls": (info.get("corp_cls") or "").strip(),
        "induty_code": induty,
        "effective_prefix": induty[:prefix_len],
        "acc_mt": (info.get("acc_mt") or "").strip(),
    }


def scan_peers(client: DartClient, listed: list[dict], target_corp_code: str,
               effective_prefix: str, allowed_cls: list[str], workers: int,
               scan_limit: int) -> tuple[list[dict], dict]:
    """Return (peer_candidates, scan_stats). Threaded, cache-first.

    A peer candidate: corp_cls in allowed_cls AND induty_code startswith prefix.
    """
    pool = [r for r in listed if r["corp_code"] != target_corp_code]
    scanned_note = None
    if scan_limit and scan_limit > 0:
        scanned_note = f"peer_scan_limit={scan_limit} (전체 {len(pool)} 중 상한 적용)"
        pool = pool[:scan_limit]

    peers: list[dict] = []
    stats = {"scanned": 0, "errors": 0, "pool_total": len(pool), "note": scanned_note}

    def probe(rec: dict):
        try:
            info = _company_info(client, rec["corp_code"])
        except Exception as e:  # keep scanning; record error
            return ("err", rec, str(e))
        return ("ok", rec, info)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = [ex.submit(probe, r) for r in pool]
        for fut in as_completed(futs):
            kind, rec, payload = fut.result()
            stats["scanned"] += 1
            if kind == "err":
                stats["errors"] += 1
                continue
            info = payload
            if info.get("status") != "000":
                continue
            induty = (info.get("induty_code") or "").strip()
            corp_cls = (info.get("corp_cls") or "").strip()
            if not induty:
                continue
            if corp_cls in allowed_cls and induty.startswith(effective_prefix):
                peers.append({
                    "corp_code": rec["corp_code"],
                    "corp_name": info.get("corp_name") or rec["corp_name"],
                    "stock_code": (info.get("stock_code") or rec["stock_code"]).strip(),
                    "corp_cls": corp_cls,
                    "induty_code": induty,
                    "effective_prefix": induty[: len(effective_prefix)],
                    "acc_mt": (info.get("acc_mt") or "").strip(),
                })
    peers.sort(key=lambda p: p["corp_code"])
    return peers, stats


def fetch_cfs(client: DartClient, corp_code: str, corp_name: str, bsns_year,
              fs_div="CFS", stock_code: str = ""):
    """Return (rows, status, request_hash, raw_path). rows=[] if no CFS."""
    res = client.get_json(
        "fnlttSinglAcntAll.json",
        {"corp_code": corp_code, "bsns_year": str(bsns_year),
         "reprt_code": REPRT_ANNUAL, "fs_div": fs_div},
        "fnlttSinglAcntAll",
    )
    data = res["data"]
    status = data.get("status")
    rows = []
    if status == "000":
        rows = parse_cfs_rows(
            data, corp_code=corp_code, corp_name=corp_name, stock_code=stock_code,
            bsns_year=bsns_year, reprt_code=REPRT_ANNUAL, fs_div=fs_div,
            retrieved_at=data.get("_retrieved_at", ""),
            req_hash=res["request_hash"], raw_path=res["raw_path"],
        )
    return rows, status, res["request_hash"], res["raw_path"]

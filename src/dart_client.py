"""OpenDART HTTP client.

Responsibilities:
  - cache-first, content-addressed requests (request_hash = hash(endpoint + sorted
    params excluding the API key)); reruns are reproducible and API-free.
  - verbatim raw snapshots under data/raw/<endpoint>/<hash>.(json|xml) + a
    manifest.jsonl append log (source traceability).
  - retry/backoff; hard-stop on auth/maintenance status codes (no silent fallback).

The API key is never written to snapshots, the manifest, or logs. Thread-safe for
concurrent get_json() calls (used by the induty_code scan).
"""
from __future__ import annotations

import hashlib
import io
import json
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://opendart.fss.or.kr/api/"


class DartError(RuntimeError):
    """Transient/technical failure after retries."""


class StopConditionError(RuntimeError):
    """A condition the loop must HALT on (auth error, maintenance, no fallback)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_hash(endpoint: str, params: dict) -> str:
    safe = {k: v for k, v in params.items() if k != "crtfc_key"}
    blob = endpoint + "?" + "&".join(f"{k}={safe[k]}" for k in sorted(safe))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class DartClient:
    def __init__(self, api_key: str, raw_dir: Path, cache_dir: Path, project_root: Path,
                 timeout: int = 20, delay: float = 0.0, max_retries: int = 3):
        self._api_key = api_key
        self.raw_dir = Path(raw_dir)
        self.cache_dir = Path(cache_dir)
        self.project_root = Path(project_root)
        self.timeout = timeout
        self.delay = delay
        self.max_retries = max_retries
        self.log_records: list[dict] = []
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.cache_dir / "manifest.jsonl"
        self._lock = threading.Lock()

    # -- helpers -------------------------------------------------------------
    def _snap_path(self, endpoint_name: str, h: str, ext: str) -> Path:
        d = self.raw_dir / endpoint_name
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{h}.{ext}"

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.project_root)).replace("\\", "/")
        except ValueError:
            return str(path)

    def _record(self, rec: dict) -> None:
        with self._lock:
            self.log_records.append(rec)
            with open(self.manifest_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # -- endpoints -----------------------------------------------------------
    def get_json(self, endpoint: str, params: dict, endpoint_name: str) -> dict:
        """Return {'data','request_hash','raw_path','from_cache','status'}."""
        h = request_hash(endpoint, params)
        snap = self._snap_path(endpoint_name, h, "json")
        safe_params = {k: v for k, v in params.items() if k != "crtfc_key"}

        if snap.exists():
            data = json.loads(snap.read_text(encoding="utf-8"))
            rec = dict(endpoint=endpoint_name, request_hash=h, params=safe_params,
                       status=data.get("status"), message=data.get("message"),
                       retrieved_at=data.get("_retrieved_at"),
                       raw_path=self._rel(snap), from_cache=True)
            self._record(rec)
            return dict(data=data, request_hash=h, raw_path=self._rel(snap),
                        from_cache=True, status=data.get("status"))

        last_exc = None
        for attempt in range(self.max_retries):
            try:
                if self.delay:
                    time.sleep(self.delay)
                r = requests.get(BASE + endpoint,
                                 params={**params, "crtfc_key": self._api_key},
                                 timeout=self.timeout)
                data = r.json()
            except Exception as e:  # network / decode
                last_exc = e
                time.sleep(1.5 * (attempt + 1))
                continue

            status = data.get("status")
            if status == "020":  # rate limited -> back off and retry
                time.sleep(2.0 * (attempt + 1))
                last_exc = DartError("rate limited (020)")
                continue
            if status in ("010", "011"):
                raise StopConditionError(
                    f"OpenDART 인증 오류(status {status}): API 키를 확인하세요. (STOP)")
            if status == "800":
                raise StopConditionError(
                    "OpenDART 서비스 점검 중(status 800). 나중에 다시 시도하세요. (STOP)")

            data["_retrieved_at"] = _now_iso()
            snap.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            rec = dict(endpoint=endpoint_name, request_hash=h, params=safe_params,
                       status=status, message=data.get("message"),
                       retrieved_at=data["_retrieved_at"],
                       raw_path=self._rel(snap), from_cache=False)
            self._record(rec)
            return dict(data=data, request_hash=h, raw_path=self._rel(snap),
                        from_cache=False, status=status)

        raise DartError(f"요청 실패({endpoint_name}, {safe_params}): {last_exc}")

    def get_corpcode_xml(self) -> str:
        """Download+cache the corpCode master (a ZIP of CORPCODE.xml)."""
        h = request_hash("corpCode.xml", {})
        snap = self._snap_path("corpCode", h, "xml")
        if snap.exists():
            self._record(dict(endpoint="corpCode", request_hash=h, params={},
                              status="000", retrieved_at=None,
                              raw_path=self._rel(snap), from_cache=True))
            return snap.read_text(encoding="utf-8")

        r = requests.get(BASE + "corpCode.xml", params={"crtfc_key": self._api_key},
                         timeout=self.timeout)
        try:
            zf = zipfile.ZipFile(io.BytesIO(r.content))
            xml = zf.read(zf.namelist()[0]).decode("utf-8")
        except zipfile.BadZipFile:
            raise StopConditionError(
                f"corpCode 조회 실패(키/네트워크 확인): {r.text[:200]} (STOP)")
        snap.write_text(xml, encoding="utf-8")
        self._record(dict(endpoint="corpCode", request_hash=h, params={},
                          status="000", retrieved_at=_now_iso(),
                          raw_path=self._rel(snap), from_cache=False))
        return xml

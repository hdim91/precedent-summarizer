"""국가법령정보센터(law.go.kr) Open API 클라이언트.

원본: OneDrive `Leagal Tech/CODE/python/src/common/law_api.py`(LawGoKrClient)를 이식·확장.
변경점: HTTPS, 예외 마스킹, 호출 간격 제한, 판례 검색 필터(법원종류·선고일자), raw 저장 시 마스킹·불변.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests

from precedent_summarizer.common.security import MaskedRequestError, mask_bytes
from precedent_summarizer.config import require_secret

SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"

ORG_SUPREME_COURT = "400201"   # 법원종류코드: 대법원 (2026-10-23 실측 totalCnt=75,467)
ORG_LOWER_COURTS = "400202"    # 하위법원
RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass
class LawGoKrClient:
    oc: Optional[str] = field(default=None, repr=False)
    timeout: int = 20
    max_retries: int = 3
    retry_backoff_sec: float = 1.5
    min_interval_sec: float = 0.1
    session: Optional[requests.Session] = field(default=None, repr=False)
    _last_call: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.oc is None:
            self.oc = require_secret("LAW_API_KEY")
        if self.session is None:
            self.session = requests.Session()

    # ---- 저수준 ----------------------------------------------------------
    def _throttle(self) -> None:
        wait = self.min_interval_sec - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _get(self, url: str, params: dict[str, Any]) -> requests.Response:
        q = {"OC": self.oc, **params}
        last_exc: Optional[BaseException] = None
        status: Optional[int] = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, params=q, timeout=self.timeout)
                status = resp.status_code
                if status in RETRY_STATUS and attempt < self.max_retries:
                    time.sleep(self.retry_backoff_sec * attempt)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_sec * attempt)
        assert last_exc is not None
        raise MaskedRequestError(last_exc, status_code=status) from None

    # ---- 검색 -------------------------------------------------------------
    def search(
        self,
        target: str,
        query: str = "",
        *,
        display: int = 100,
        page: int = 1,
        response_type: str = "JSON",
        extra_params: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        params: dict[str, Any] = {"target": target, "display": display, "page": page, "type": response_type}
        if query:
            params["query"] = query
        if extra_params:
            params.update(extra_params)
        return self._get(SEARCH_URL, params)

    def search_precedents(
        self,
        query: str = "",
        *,
        org: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        display: int = 100,
        page: int = 1,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        """판례 목록 검색. org=ORG_SUPREME_COURT로 대법원 한정. date_*는 'YYYYMMDD'(선고일자 prncYd 범위)."""
        p: dict[str, Any] = dict(extra_params or {})
        if org:
            p["org"] = org
        if date_from or date_to:
            if not (date_from and date_to):
                raise ValueError("date_from과 date_to는 함께 지정해야 합니다.")
            p["prncYd"] = f"{date_from}~{date_to}"
        return self.search("prec", query, display=display, page=page, extra_params=p)

    # ---- 본문 -------------------------------------------------------------
    def get_precedent_detail(self, prec_id: str, *, response_type: str = "JSON") -> requests.Response:
        return self._get(SERVICE_URL, {"target": "prec", "ID": prec_id, "type": response_type})

    def get_law_detail(
        self,
        *,
        law_id: Optional[str] = None,
        mst: Optional[str] = None,
        response_type: str = "JSON",
        extra_params: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 반드시 지정해야 합니다.")
        p: dict[str, Any] = {"target": "law", "type": response_type, **(extra_params or {})}
        if law_id:
            p["ID"] = law_id
        if mst:
            p["MST"] = mst
        return self._get(SERVICE_URL, p)


def save_raw_response(resp: requests.Response, out_path: Path, *, overwrite: bool = False) -> Path:
    """응답 본문만 마스킹해 저장. 기본은 불변(이미 있으면 덮어쓰지 않음, RULES 5장)."""
    out_path = Path(out_path)
    if out_path.exists() and not overwrite:
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_bytes(mask_bytes(resp.content))
    tmp.replace(out_path)  # 원자적 교체: 중단 시 반쪽 파일 방지
    return out_path

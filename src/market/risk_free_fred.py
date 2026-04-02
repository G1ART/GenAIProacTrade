"""FRED DTB3 일별 % CSV — httpx + 구간 한정 URL(cosd/coed)로 504 완화 + 재시도."""

from __future__ import annotations

import csv
import io
import logging
import time
from datetime import date, datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 전체 시계열은 FRED 쪽에서 자주 504 → 항상 cosd/coed 로 구간만 요청
_FRED_GRAPH_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
_USER_AGENT = "Mozilla/5.0 (compatible; GenAIProacTrade/1.0)"

SOURCE_NAME = "fred_dtb3_graph_csv"
_DEFAULT_RETRIES = 3


def _fred_dtb3_url(start: date, end: date) -> str:
    """FRED graph CSV: 구간 지정 시 서버 부하·504 가 줄어드는 경우가 많다."""
    return (
        f"{_FRED_GRAPH_BASE}?id=DTB3"
        f"&cosd={start.isoformat()}&coed={end.isoformat()}"
    )


def _download_fred_csv(
    *,
    start: date,
    end: date,
    http_timeout_sec: int,
    retries: int,
) -> tuple[str | None, str | None]:
    """
    (text, error_message). 성공 시 (body, None), 실패 시 (None, 마지막 오류 문자열).
    """
    url = _fred_dtb3_url(start, end)
    read_s = max(30, float(http_timeout_sec))
    timeout = httpx.Timeout(connect=60.0, read=read_s, write=60.0, pool=60.0)
    last_msg: str | None = None
    for attempt in range(max(1, retries)):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                r = client.get(url)
                r.raise_for_status()
                text = r.text
                logger.info(
                    "FRED CSV 수신 완료 (%d bytes, 시도 %d, cosd~coed)",
                    len(r.content),
                    attempt + 1,
                )
                return text, None
        except httpx.HTTPStatusError as e:
            code = e.response.status_code if e.response is not None else 0
            last_msg = f"HTTP {code}: {e}"
            logger.warning(
                "FRED CSV 시도 %d/%d HTTP 오류: %s (URL 구간=%s~%s)",
                attempt + 1,
                retries,
                last_msg,
                start.isoformat(),
                end.isoformat(),
            )
            if attempt + 1 < retries and code in (408, 429, 500, 502, 503, 504):
                time.sleep(5.0 * (attempt + 1))
                continue
            return None, last_msg
        except (httpx.TimeoutException, httpx.TransportError, OSError) as e:
            last_msg = f"{type(e).__name__}: {e}"
            logger.warning(
                "FRED CSV 시도 %d/%d 실패: %s",
                attempt + 1,
                retries,
                last_msg,
            )
            if attempt + 1 < retries:
                time.sleep(5.0 * (attempt + 1))
                continue
            return None, last_msg
    return None, last_msg or "unknown_error"


def fetch_dtb3_series(
    start: date,
    end: date,
    *,
    http_timeout_sec: int = 240,
    retries: int = _DEFAULT_RETRIES,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    (rows, download_error).

    download_error 가 None 이 아니면 다운로드 단계 실패(빈 리스트).
    """
    logger.info(
        "FRED DTB3 CSV 다운로드 (cosd/coed 구간=%s~%s, read 타임아웃 %ss, 재시도 %d)",
        start.isoformat(),
        end.isoformat(),
        http_timeout_sec,
        retries,
    )
    text, err = _download_fred_csv(
        start=start,
        end=end,
        http_timeout_sec=http_timeout_sec,
        retries=retries,
    )
    if text is None:
        logger.warning("FRED CSV 포기: %s", err)
        return [], err

    rdr = csv.reader(io.StringIO(text))
    header = next(rdr, None)
    if not header or "observation_date" not in header[0].lower():
        pass
    out: list[dict[str, Any]] = []
    for row in rdr:
        if len(row) < 2:
            continue
        ds, vs = row[0].strip(), row[1].strip()
        if not ds or vs in (".", ""):
            continue
        try:
            d = date.fromisoformat(ds[:10])
        except ValueError:
            continue
        if d < start or d > end:
            continue
        try:
            rate = float(vs)
        except ValueError:
            continue
        out.append(
            {
                "rate_date": d.isoformat(),
                "annualized_rate": rate,
                "source_name": SOURCE_NAME,
                "source_payload_json": {
                    "series": "DTB3",
                    "fred_csv": True,
                    "cosd": start.isoformat(),
                    "coed": end.isoformat(),
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    logger.info("FRED CSV 파싱 후 적재 대상 행: %d (lookback 필터 적용)", len(out))
    return out, None

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.odds.exceptions import (
    OddsProviderAuthenticationError,
    OddsProviderConfigurationError,
    OddsProviderRateLimitError,
    OddsProviderResponseError,
)
from app.odds.schemas import ProviderBookmaker, ProviderEvent, ProviderMarket, ProviderOutcome, QuotaMetadata
from app.utils.logging import log_event

logger = logging.getLogger(__name__)
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
RECOGNISED_SPORT_KEYS = ("mma_mixed_martial_arts", "mma_ufc")


@dataclass(frozen=True, slots=True)
class ProviderResult:
    events: list[ProviderEvent]
    quota: QuotaMetadata
    invalid_records: int = 0


class OddsApiClient:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.odds_api_key:
            raise OddsProviderConfigurationError("ODDS_API_KEY is required for odds ingestion")
        if self.settings.odds_api_markets != "h2h" or self.settings.odds_api_odds_format != "decimal":
            raise OddsProviderConfigurationError("Phase 4A supports only h2h markets with decimal odds")
        self._client = client or httpx.Client(timeout=float(self.settings.odds_api_timeout_seconds))
        self._sport_key: str | None = self.settings.odds_api_sport_key or None
        self.last_quota = QuotaMetadata()

    def list_sports(self) -> list[dict[str, Any]]:
        payload = self._request("/v4/sports")
        if not isinstance(payload, list):
            raise OddsProviderResponseError("sports response must be a JSON array")
        return [item for item in payload if isinstance(item, dict)]

    def resolve_sport_key(self) -> str:
        if self._sport_key:
            return self._sport_key
        active = [item for item in self.list_sports() if item.get("active") is True]
        by_key = {str(item.get("key")): item for item in active}
        for key in RECOGNISED_SPORT_KEYS:
            if key in by_key:
                self._sport_key = key
                return key
        candidates = [
            item for item in active
            if "mma" in f"{item.get('key', '')} {item.get('group', '')} {item.get('title', '')}".lower()
            or "ufc" in f"{item.get('key', '')} {item.get('group', '')} {item.get('title', '')}".lower()
        ]
        if len(candidates) != 1:
            raise OddsProviderResponseError("no unambiguous active MMA/UFC sport key was returned")
        self._sport_key = str(candidates[0]["key"])
        return self._sport_key

    def get_upcoming_moneyline_odds(self) -> ProviderResult:
        sport_key = self.resolve_sport_key()
        payload = self._request(
            f"/v4/sports/{sport_key}/odds",
            regions=",".join(self.settings.odds_api_regions),
            markets="h2h",
            oddsFormat="decimal",
            dateFormat=self.settings.odds_api_date_format,
        )
        if not isinstance(payload, list):
            raise OddsProviderResponseError("odds response must be a JSON array")
        events: list[ProviderEvent] = []
        invalid = 0
        for item in payload:
            try:
                event, skipped = _parse_event(item)
                events.append(event)
                invalid += skipped
            except ValidationError as exc:
                invalid += 1
                log_event(logger, "odds_provider_event_invalid", error=str(exc))
        return ProviderResult(events, self.last_quota, invalid)

    def _request(self, path: str, **parameters: str) -> Any:
        params = {"apiKey": self.settings.odds_api_key, **parameters}
        attempts = self.settings.odds_api_max_retries + 1
        for attempt in range(attempts):
            try:
                response = self._client.get(f"{self.settings.odds_api_base_url.rstrip('/')}{path}", params=params)
                self._capture_quota(response)
                if response.status_code in {401, 403}:
                    raise OddsProviderAuthenticationError("The Odds API rejected the configured credentials")
                if response.status_code in RETRYABLE_STATUSES:
                    if attempt + 1 < attempts:
                        time.sleep(2**attempt)
                        continue
                    if response.status_code == 429:
                        raise OddsProviderRateLimitError("The Odds API rate limit was exceeded")
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError as exc:
                    raise OddsProviderResponseError("The Odds API returned invalid JSON") from exc
            except OddsProviderAuthenticationError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt + 1 < attempts:
                    time.sleep(2**attempt)
                    continue
                raise OddsProviderResponseError("The Odds API request failed after retries") from exc
            except httpx.HTTPStatusError as exc:
                raise OddsProviderResponseError(
                    f"The Odds API returned HTTP {exc.response.status_code}"
                ) from None
        raise OddsProviderResponseError("The Odds API request failed")

    def _capture_quota(self, response: httpx.Response) -> None:
        self.last_quota = QuotaMetadata(
            requests_remaining=_header_int(response, "x-requests-remaining"),
            requests_used=_header_int(response, "x-requests-used"),
            last_request_cost=_header_int(response, "x-requests-last"),
        )
        log_event(logger, "odds_api_quota", **self.last_quota.model_dump())
        remaining = self.last_quota.requests_remaining
        if remaining is not None and remaining < self.settings.odds_api_low_quota_warning:
            logger.warning("The Odds API quota is low: %s requests remaining", remaining)


def _header_int(response: httpx.Response, name: str) -> int | None:
    value = response.headers.get(name)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _parse_event(payload: object) -> tuple[ProviderEvent, int]:
    if not isinstance(payload, dict):
        return ProviderEvent.model_validate(payload), 0
    skipped = 0
    bookmakers: list[ProviderBookmaker] = []
    raw_bookmakers = payload.get("bookmakers", [])
    if not isinstance(raw_bookmakers, list):
        raw_bookmakers = []
        skipped += 1
    for raw_bookmaker in raw_bookmakers:
        if not isinstance(raw_bookmaker, dict):
            skipped += 1
            continue
        markets: list[ProviderMarket] = []
        for raw_market in raw_bookmaker.get("markets", []) or []:
            if not isinstance(raw_market, dict) or raw_market.get("key") != "h2h":
                continue
            outcomes: list[ProviderOutcome] = []
            for raw_outcome in raw_market.get("outcomes", []) or []:
                try:
                    outcomes.append(ProviderOutcome.model_validate(raw_outcome))
                except ValidationError:
                    skipped += 1
            try:
                markets.append(ProviderMarket.model_validate({**raw_market, "outcomes": outcomes}))
            except ValidationError:
                skipped += 1
        try:
            bookmakers.append(ProviderBookmaker.model_validate({**raw_bookmaker, "markets": markets}))
        except ValidationError:
            skipped += 1
    return ProviderEvent.model_validate({**payload, "bookmakers": bookmakers}), skipped

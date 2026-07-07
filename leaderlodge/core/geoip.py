"""Approximate geolocation from IP for auth-event-log and admin alerts."""

from __future__ import annotations

import ipaddress
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)

_LOOKUP_TIMEOUT_SECONDS = 2
_IP_API_FIELDS = "status,message,country,regionName,city,timezone,isp"


@dataclass(frozen=True)
class GeoLookup:
    city: str = ""
    region: str = ""
    country: str = ""
    timezone: str = ""
    isp: str = ""

    @property
    def label(self) -> str:
        return format_geo_label(self.city, self.region, self.country)

    @property
    def has_data(self) -> bool:
        return bool(self.label)

    def extras(self) -> dict[str, str]:
        payload: dict[str, str] = {}
        if self.timezone:
            payload["timezone"] = self.timezone
        if self.isp:
            payload["isp"] = self.isp
        return payload


def geoip_enabled() -> bool:
    return getattr(settings, "GEOIP_ENABLED", True)


def format_geo_label(city: str, region: str, country: str) -> str:
    """Human label such as 'Istanbul, Turkey'."""
    city = (city or "").strip()
    region = (region or "").strip()
    country = (country or "").strip()
    if city and country:
        return f"{city}, {country}"
    if region and country:
        return f"{region}, {country}"
    return city or region or country


def is_public_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip.strip()).is_global
    except ValueError:
        return False


def _lookup_ip_http(ip: str) -> GeoLookup:
    url = f"http://ip-api.com/json/{ip}?fields={_IP_API_FIELDS}"
    request = urllib.request.Request(url, headers={"User-Agent": "LeaderLodge/1.0"})
    with urllib.request.urlopen(request, timeout=_LOOKUP_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    if payload.get("status") != "success":
        message = payload.get("message", "lookup failed")
        logger.info("GeoIP lookup skipped for %s: %s", ip, message)
        return GeoLookup()
    return GeoLookup(
        city=str(payload.get("city") or "").strip(),
        region=str(payload.get("regionName") or "").strip(),
        country=str(payload.get("country") or "").strip(),
        timezone=str(payload.get("timezone") or "").strip(),
        isp=str(payload.get("isp") or "").strip(),
    )


@lru_cache(maxsize=512)
def lookup_ip(ip: str) -> GeoLookup:
    """Resolve a public IP to city/region/country. Never raises."""
    cleaned = (ip or "").strip()
    if not geoip_enabled() or not cleaned or not is_public_ip(cleaned):
        return GeoLookup()
    try:
        return _lookup_ip_http(cleaned)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning("GeoIP lookup failed for %s: %s", cleaned, exc)
        return GeoLookup()

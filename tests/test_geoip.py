import json
from unittest import mock

import pytest

from leaderlodge.accounts.auth_log import record_auth_event
from leaderlodge.accounts.models import AuthEvent
from leaderlodge.core.geoip import (
    GeoLookup,
    format_geo_label,
    is_public_ip,
    lookup_ip,
)


@pytest.fixture(autouse=True)
def clear_geo_cache():
    lookup_ip.cache_clear()
    yield
    lookup_ip.cache_clear()


def test_format_geo_label_city_country():
    assert format_geo_label("Istanbul", "Istanbul", "Turkey") == "Istanbul, Turkey"


def test_format_geo_label_region_country():
    assert (
        format_geo_label("", "California", "United States")
        == "California, United States"
    )


def test_is_public_ip():
    assert is_public_ip("31.40.204.182") is True
    assert is_public_ip("127.0.0.1") is False
    assert is_public_ip("192.168.1.4") is False


@mock.patch("leaderlodge.core.geoip._lookup_ip_http")
def test_lookup_ip_caches_results(mock_lookup):
    mock_lookup.return_value = GeoLookup(city="Istanbul", country="Turkey")
    assert lookup_ip("31.40.204.182").label == "Istanbul, Turkey"
    assert lookup_ip("31.40.204.182").label == "Istanbul, Turkey"
    mock_lookup.assert_called_once()


@mock.patch("leaderlodge.core.geoip._lookup_ip_http")
def test_lookup_ip_skips_private_addresses(mock_lookup):
    assert lookup_ip("127.0.0.1").label == ""
    mock_lookup.assert_not_called()


@mock.patch("leaderlodge.core.geoip._lookup_ip_http")
def test_lookup_ip_parses_http_payload(mock_lookup):
    mock_lookup.return_value = GeoLookup(
        city="Istanbul",
        region="Istanbul",
        country="Turkey",
        timezone="Europe/Istanbul",
        isp="Example ISP",
    )
    geo = lookup_ip("31.40.204.182")
    assert geo.label == "Istanbul, Turkey"
    assert geo.timezone == "Europe/Istanbul"
    assert geo.isp == "Example ISP"


@pytest.mark.django_db
@mock.patch("leaderlodge.core.geoip._lookup_ip_http")
def test_record_auth_event_stores_geo_fields(mock_lookup, rf):
    mock_lookup.return_value = GeoLookup(
        city="Istanbul",
        region="Istanbul",
        country="Turkey",
        timezone="Europe/Istanbul",
        isp="Example ISP",
    )
    request = rf.post("/accounts/signup/", REMOTE_ADDR="31.40.204.182")
    event = record_auth_event(
        event_type=AuthEvent.EventType.SIGNUP_BLOCKED,
        request=request,
        email="bot@example.com",
        source="signup",
        reason="honeypot_filled",
    )

    assert event is not None
    assert event.geo_city == "Istanbul"
    assert event.geo_country == "Turkey"
    assert event.geo_label == "Istanbul, Turkey"
    assert event.metadata["geo"] == {
        "timezone": "Europe/Istanbul",
        "isp": "Example ISP",
    }

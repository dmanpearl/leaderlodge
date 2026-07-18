from unittest import mock


from leaderlodge.core.geoip import (
    GeoLookup,
    lookup_ip,
)


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

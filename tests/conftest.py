import pytest


def pytest_collection_modifyitems(config, items):
    """Use savepoint rollbacks instead of full DB flushes between tests."""
    for item in items:
        if item.get_closest_marker("django_db") is not None:
            item.add_marker(pytest.mark.django_db(transaction=True))


@pytest.fixture(autouse=True)
def _clear_geoip_cache():
    """Prevent cached IP lookups from leaking geo data between tests."""
    from leaderlodge.core.geoip import lookup_ip

    lookup_ip.cache_clear()
    yield
    lookup_ip.cache_clear()

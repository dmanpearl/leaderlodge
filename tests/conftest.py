import pytest


def pytest_collection_modifyitems(config, items):
    """Use savepoint rollbacks instead of full DB flushes between tests."""
    for item in items:
        if item.get_closest_marker("django_db") is not None:
            item.add_marker(pytest.mark.django_db(transaction=True))

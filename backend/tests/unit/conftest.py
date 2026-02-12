import pytest


@pytest.fixture(autouse=True)
def setup_db():
    """Override parent setup_db — unit tests don't need a database."""
    yield

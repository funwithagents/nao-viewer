# Fast tier shared fixtures.
#
# If the package has process-global or singleton state (a module-level registry,
# a cached client, a configured logger), add an `autouse=True` fixture here that
# resets it before and after each test so state can't leak between tests. Keep
# this tier deterministic and network-free — anything that hits a real service
# belongs in tests-e2e/ instead.

from collections.abc import Iterator

import pytest
from mock_naoqi import MockNaoqi


@pytest.fixture
def mock_naoqi() -> Iterator[tuple[str, MockNaoqi]]:
    """A virtual-robot mock NAOqi on a loopback port: yields (url, mock)."""
    mock = MockNaoqi().start()
    try:
        yield mock.url, mock
    finally:
        mock.close()

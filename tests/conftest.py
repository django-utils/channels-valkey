import asyncio
import pytest


@pytest.fixture()
def asyncio_event_loop():
    e = asyncio.new_event_loop()
    yield e
    e.close()

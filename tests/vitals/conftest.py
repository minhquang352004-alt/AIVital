from datetime import UTC, datetime

import pytest

from aivitals_engine.benchmark.synthetic import synthesize_bvp_window

FIXED_TIME = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def fixed_time():
    return FIXED_TIME


@pytest.fixture
def fixed_clock():
    return lambda: FIXED_TIME


@pytest.fixture(scope="session")
def clean_window():
    return synthesize_bvp_window(heart_rate_bpm=72.0, respiratory_rate_brpm=15.0, noise_std=0.1, seed=11)

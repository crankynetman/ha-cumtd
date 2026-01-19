"""Tests for CUMTD API client."""

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
import vcr

# Import directly from api module to avoid __init__.py dependencies
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components" / "cumtd_bus"))
from api import (
    AuthenticationError,
    CUMTDClient,
)

# VCR configuration: set VCR_RECORD_MODE=all to re-record cassettes when API changes
cumtd_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode=os.environ.get("VCR_RECORD_MODE", "none"),  # Default: replay only
    match_on=["uri", "method"],
    filter_headers=["authorization"],
    filter_query_parameters=["key"],  # Scrub API key from cassettes
)


@pytest_asyncio.fixture
async def client() -> CUMTDClient:
    """Create API client for testing.

    Uses dummy key - VCR replays from cassettes without hitting the API.
    To re-record: set CUMTD_API_KEY env var and VCR_RECORD_MODE=all
    """
    # Dummy key for VCR playback (only use real key when re-recording)
    api_key = os.environ.get("CUMTD_API_KEY", "test_key_not_used_in_playback")
    client = CUMTDClient(api_key)
    yield client
    await client.close()


@pytest.mark.asyncio
@cumtd_vcr.use_cassette("validate_api_key_valid.yaml")
async def test_validate_api_key_valid(client: CUMTDClient) -> None:
    """Valid API key validation."""
    result = await client.validate_api_key()
    assert result is True


@pytest.mark.asyncio
@cumtd_vcr.use_cassette("validate_api_key_invalid.yaml")
async def test_validate_api_key_invalid() -> None:
    """Invalid API key raises AuthenticationError."""
    client = CUMTDClient("invalid_key_12345")
    try:
        with pytest.raises(AuthenticationError):
            await client.validate_api_key()
    finally:
        await client.close()


@pytest.mark.asyncio
@cumtd_vcr.use_cassette("get_stops_by_search.yaml")
async def test_get_stops_by_search(client: CUMTDClient) -> None:
    """Search returns stops matching query."""
    response = await client.get_stops_by_search("Springfield")

    assert len(response.stops) > 0
    # All results should contain search term
    assert all("Springfield" in stop.stop_name for stop in response.stops)
    # Check structure of returned data
    stop = response.stops[0]
    assert stop.stop_id
    assert stop.stop_name


@pytest.mark.asyncio
@cumtd_vcr.use_cassette("get_stops_no_results.yaml")
async def test_get_stops_by_search_no_results(client: CUMTDClient) -> None:
    """Search with no matches returns empty list."""
    response = await client.get_stops_by_search("ThisStopDoesNotExist12345")
    assert len(response.stops) == 0


@pytest.mark.asyncio
@cumtd_vcr.use_cassette("get_departures_by_stop.yaml")
async def test_get_departures_by_stop(client: CUMTDClient) -> None:
    """Departures include expected bus data."""
    response = await client.get_departures_by_stop(stop_id="IU", count=10)

    # VCR cassette has recorded departures, so we can test reliably
    assert len(response.departures) > 0
    dep = response.departures[0]
    assert dep.stop_id.startswith("IU")
    assert dep.headsign
    assert dep.expected_mins >= 0
    assert dep.route.route_id
    assert dep.trip_id

"""Test floor registry API."""
from collections.abc import Awaitable, Callable, Generator
from typing import Any

from aiohttp import ClientWebSocketResponse
import pytest

from homeassistant.components.config import floor_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import floor_registry as fr


@pytest.fixture(name="client")
def client_fixture(
    hass: HomeAssistant,
    hass_ws_client: Callable[
        [HomeAssistant], Awaitable[Generator[ClientWebSocketResponse, Any, Any]]
    ],
) -> Generator[ClientWebSocketResponse, None, None]:
    """Fixture that can interact with the config manager API."""
    hass.loop.run_until_complete(floor_registry.async_setup(hass))
    return hass.loop.run_until_complete(hass_ws_client(hass))


@pytest.mark.usefixtures("hass")
async def test_list_floors(
    client: ClientWebSocketResponse,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test list entries."""
    floor_registry.async_create("First floor")
    floor_registry.async_create(
        name="Second floor",
        icon="mdi:home-floor-2",
        level=2,
    )

    assert len(floor_registry.floors) == 2

    await client.send_json_auto_id({"type": "config/floor_registry/list"})

    msg = await client.receive_json()

    assert len(msg["result"]) == len(floor_registry.floors)
    assert msg["result"][0] == {
        "icon": None,
        "floor_id": "first_floor",
        "name": "First floor",
        "level": 0,
    }
    assert msg["result"][1] == {
        "icon": "mdi:home-floor-2",
        "floor_id": "second_floor",
        "name": "Second floor",
        "level": 2,
    }


@pytest.mark.usefixtures("hass")
async def test_create_floor(
    client: ClientWebSocketResponse,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test create entry."""
    await client.send_json_auto_id(
        {"type": "config/floor_registry/create", "name": "First floor"}
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "icon": None,
        "floor_id": "first_floor",
        "name": "First floor",
        "level": 0,
    }

    await client.send_json_auto_id(
        {
            "name": "Second floor",
            "type": "config/floor_registry/create",
            "icon": "mdi:home-floor-2",
            "level": 2,
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 2
    assert msg["result"] == {
        "icon": "mdi:home-floor-2",
        "floor_id": "second_floor",
        "name": "Second floor",
        "level": 2,
    }


@pytest.mark.usefixtures("hass")
async def test_create_floor_with_name_already_in_use(
    client: ClientWebSocketResponse,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test create entry that should fail."""
    floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {"name": "First floor", "type": "config/floor_registry/create"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert (
        msg["error"]["message"] == "The name First floor (firstfloor) is already in use"
    )
    assert len(floor_registry.floors) == 1


@pytest.mark.usefixtures("hass")
async def test_delete_floor(
    client: ClientWebSocketResponse,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test delete entry."""
    floor = floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {"floor_id": floor.floor_id, "type": "config/floor_registry/delete"}
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert not floor_registry.floors


@pytest.mark.usefixtures("hass")
async def test_delete_non_existing_floor(
    client: ClientWebSocketResponse,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test delete entry that should fail."""
    floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {
            "floor_id": "zaphotbeeblebrox",
            "type": "config/floor_registry/delete",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Floor ID doesn't exist"
    assert len(floor_registry.floors) == 1


@pytest.mark.usefixtures("hass")
async def test_update_floor(
    client: ClientWebSocketResponse,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test update entry."""
    floor = floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "Second floor",
            "icon": "mdi:home-floor-2",
            "type": "config/floor_registry/update",
            "level": 2,
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "icon": "mdi:home-floor-2",
        "floor_id": floor.floor_id,
        "name": "Second floor",
        "level": 2,
    }

    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "First floor",
            "icon": None,
            "level": 1,
            "type": "config/floor_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "icon": None,
        "floor_id": floor.floor_id,
        "name": "First floor",
        "level": 1,
    }


@pytest.mark.usefixtures("hass")
async def test_update_with_name_already_in_use(
    client: ClientWebSocketResponse,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test update entry."""
    floor = floor_registry.async_create("First floor")
    floor_registry.async_create("Second floor")
    assert len(floor_registry.floors) == 2

    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "Second floor",
            "type": "config/floor_registry/update",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert (
        msg["error"]["message"]
        == "The name Second floor (secondfloor) is already in use"
    )
    assert len(floor_registry.floors) == 2

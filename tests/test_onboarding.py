import json
import uuid
from importlib import resources
from pathlib import Path

import pytest

from naib.onboarding import (
    describe_channel_setup,
    install_playbook,
    onboard_client,
    validate_icp_config,
    validate_playbook,
)
from naib.playbook import load_playbook
from naib.schemas.icp_config import ICPConfig

_VALID_PLAYBOOK = [
    {
        "id": "website-basic",
        "service_name": "Basic Website Package",
        "description": "5-page marketing site.",
        "scope_template": "5 pages, one revision round.",
        "capabilities": ["website-design"],
        "price_band_low": 80000,
        "price_band_high": 120000,
        "currency": "PKR",
        "is_placeholder": False,
    }
]

_VALID_ICP = {
    "criteria": [
        {"name": "budget_stated", "description": "Has a stated budget", "weight": 1.0}
    ],
    "qualify_threshold": 0.6,
    "hard_disqualifiers": ["existing_client"],
}


@pytest.fixture
def _restore_bundled_playbook():
    dest = resources.files("naib.data").joinpath("playbook.json")
    original = dest.read_text(encoding="utf-8")
    yield
    dest.write_text(original, encoding="utf-8")  # type: ignore[attr-defined]
    load_playbook.cache_clear()


def test_validate_playbook_accepts_a_real_catalog(tmp_path: Path) -> None:
    path = tmp_path / "playbook.json"
    path.write_text(json.dumps(_VALID_PLAYBOOK), encoding="utf-8")

    entries = validate_playbook(path)

    assert len(entries) == 1
    assert entries[0].id == "website-basic"


def test_validate_playbook_refuses_placeholder_entries(tmp_path: Path) -> None:
    placeholder = [{**_VALID_PLAYBOOK[0], "is_placeholder": True}]
    path = tmp_path / "playbook.json"
    path.write_text(json.dumps(placeholder), encoding="utf-8")

    with pytest.raises(ValueError, match="placeholder"):
        validate_playbook(path)


def test_validate_playbook_refuses_an_empty_catalog(tmp_path: Path) -> None:
    path = tmp_path / "playbook.json"
    path.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(ValueError, match="no playbook entries"):
        validate_playbook(path)


def test_install_playbook_round_trips_through_load_playbook(
    tmp_path: Path, _restore_bundled_playbook: None
) -> None:
    path = tmp_path / "playbook.json"
    path.write_text(json.dumps(_VALID_PLAYBOOK), encoding="utf-8")
    entries = validate_playbook(path)

    install_playbook(entries)

    loaded = load_playbook()
    assert [e.id for e in loaded] == ["website-basic"]
    assert loaded[0].is_placeholder is False


def test_validate_icp_config_accepts_a_real_rubric(tmp_path: Path) -> None:
    path = tmp_path / "icp.json"
    path.write_text(json.dumps(_VALID_ICP), encoding="utf-8")

    icp = validate_icp_config(path)

    assert isinstance(icp, ICPConfig)
    assert icp.qualify_threshold == 0.6


def test_describe_channel_setup_returns_the_expected_urls() -> None:
    client_id = uuid.uuid4()

    channels = describe_channel_setup(client_id, base_url="https://naib.example.com")

    assert channels.email_webhook == "https://naib.example.com/webhooks/email"
    assert channels.voice_incoming_webhook == (
        f"https://naib.example.com/webhooks/voice/{client_id}/incoming"
    )


async def test_onboard_client_creates_a_client_row() -> None:
    icp = ICPConfig.model_validate(_VALID_ICP)

    client = await onboard_client(
        name="New Test Agency",
        plan="pilot",
        icp_config=icp,
        playbook_version="v1",
        price_floor=50000,
    )

    assert client.id is not None
    assert client.name == "New Test Agency"
    assert client.playbook_version == "v1"
    assert client.price_floor == 50000
    assert client.icp_config["qualify_threshold"] == 0.6

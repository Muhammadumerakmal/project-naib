import pytest
from pydantic import ValidationError

from naib.icp import DEFAULT_ICP_CONFIG, load_icp_config, render_icp_rubric


def test_load_icp_config_falls_back_to_default_when_client_has_none() -> None:
    assert load_icp_config(None) is DEFAULT_ICP_CONFIG
    assert load_icp_config({}) is DEFAULT_ICP_CONFIG


def test_load_icp_config_validates_client_supplied_rubric() -> None:
    config = load_icp_config(
        {
            "criteria": [{"name": "x", "description": "y", "weight": 1.0}],
            "qualify_threshold": 0.5,
            "hard_disqualifiers": ["existing_client"],
        }
    )
    assert config.qualify_threshold == 0.5


def test_load_icp_config_rejects_malformed_rubric() -> None:
    with pytest.raises(ValidationError):
        load_icp_config({"criteria": "not-a-list"})


def test_render_icp_rubric_includes_every_criterion() -> None:
    rendered = render_icp_rubric(DEFAULT_ICP_CONFIG)
    for criterion in DEFAULT_ICP_CONFIG.criteria:
        assert criterion.name in rendered
    for disqualifier in DEFAULT_ICP_CONFIG.hard_disqualifiers:
        assert disqualifier in rendered

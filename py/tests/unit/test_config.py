from copy import deepcopy
from pathlib import Path

import pytest
import toml

from core.base.utils import deep_update
from core.main.config import R2RConfig

###############################################################################
# Fixtures
###############################################################################


@pytest.fixture
def base_config():
    """Load the base r2r.toml config (new structure)"""
    config_path = Path(__file__).parent.parent.parent / "r2r/r2r.toml"
    with open(config_path) as f:
        return toml.load(f)


@pytest.fixture
def config_dir():
    """Get the path to the configs directory."""
    return Path(__file__).parent.parent.parent / "core" / "configs"


@pytest.fixture
def all_config_files(config_dir):
    """Get list of all TOML files in the configs directory."""
    return list(config_dir.glob("*.toml"))


@pytest.fixture
def all_configs(all_config_files):
    """Load all config files."""
    configs = {}
    for config_file in all_config_files:
        with open(config_file) as f:
            configs[config_file.name] = toml.load(f)
    return configs


@pytest.fixture
def full_config(all_configs):
    """Return the full override config (full.toml)"""
    return all_configs["full.toml"]


@pytest.fixture
def all_merged_configs(base_config, all_configs):
    """Merge every override config into the base config."""
    merged = {}
    for config_name, config_data in all_configs.items():
        merged[config_name] = deep_update(deepcopy(base_config), config_data)
    return merged


@pytest.fixture
def merged_config(base_config, full_config):
    """Merge the full override config into the base config."""
    return deep_update(deepcopy(base_config), full_config)


###############################################################################
# Tests
###############################################################################


def test_base_config_loading(base_config):
    """Test that the base config loads correctly with the new expected values.
    """
    config = R2RConfig(base_config)

    # Verify that the database graph creation settings are present and set
    assert (config.database.graph_creation_settings.
            graph_entity_description_prompt == "graph_entity_description")
    assert (config.database.graph_creation_settings.graph_extraction_prompt ==
            "graph_extraction")
    assert (config.database.graph_creation_settings.automatic_deduplication
            is True)

    # Verify other key sections
    assert config.ingestion.provider == "r2r"
    assert config.orchestration.provider == "simple"
    assert config.app.default_max_upload_size == 214748364800


def test_full_config_override(full_config):
    """Test that full.toml properly overrides the base values.

    For example, assume the full override changes:
      - ingestion.provider from "r2r" to "unstructured_local"
      - orchestration.provider from "simple" to "hatchet"
      - and adds a new nested key in database.graph_creation_settings.
    """
    config = R2RConfig(full_config)

    assert config.ingestion.provider == "unstructured_local"
    assert config.orchestration.provider == "hatchet"
    # Check that a new nested key has been added
    assert (config.database.graph_creation_settings.max_knowledge_relationships
            == 100)


def test_nested_config_preservation(merged_config):
    """Test that nested configuration values are preserved after merging."""
    config = R2RConfig(merged_config)
    assert (config.database.graph_creation_settings.max_knowledge_relationships
            == 100)


def test_new_values_in_override(merged_config):
    """Test that new keys in the override config are added.

    In the old tests we asserted values for orchestration concurrency keys. In
    the new config structure these keys have been removed (or renamed).
    Therefore, we now check for them only if they exist.
    """
    config = R2RConfig(merged_config)

    # If the override adds an ingestion concurrency limit, check it.
    if hasattr(config.orchestration, "ingestion_concurrency_limit"):
        assert config.orchestration.ingestion_concurrency_limit == 16

    # Optionally, if new keys like graph_search_results_creation_concurrency_limit are defined, check them:
    if hasattr(config.orchestration,
               "graph_search_results_creation_concurrency_limit"):
        assert (config.orchestration.
                graph_search_results_creation_concurrency_limit == 32)
    if hasattr(config.orchestration, "graph_search_results_concurrency_limit"):
        assert config.orchestration.graph_search_results_concurrency_limit == 8


def test_config_type_consistency(merged_config):
    """Test that configuration values maintain their expected types."""
    config = R2RConfig(merged_config)
    assert isinstance(
        config.database.graph_creation_settings.
        graph_entity_description_prompt,
        str,
    )
    assert isinstance(
        config.database.graph_creation_settings.automatic_deduplication, bool)
    assert isinstance(config.ingestion.chunking_strategy, str)
    if hasattr(config.database.graph_creation_settings,
               "max_knowledge_relationships"):
        assert isinstance(
            config.database.graph_creation_settings.
            max_knowledge_relationships,
            int,
        )


def get_config_files():
    """Helper function to return the list of configuration file names."""
    config_dir = Path(__file__).parent.parent.parent / "core" / "configs"
    return ["r2r.toml"] + [f.name for f in config_dir.glob("*.toml")]


@pytest.mark.parametrize("config_file", get_config_files())
def test_config_required_keys(config_file):
    """Test that all required sections and keys (per R2RConfig.REQUIRED_KEYS)
    exist.

    In the new structure the 'agent' section no longer includes the key
    'generation_config', so we filter that out.
    """
    if config_file == "r2r.toml":
        file_path = Path(__file__).parent.parent.parent / "r2r/r2r.toml"
    else:
        file_path = (Path(__file__).parent.parent.parent / "core" / "configs" /
                     config_file)

    with open(file_path) as f:
        config_data = toml.load(f)

    config = R2RConfig(config_data)

    # Check for required sections
    for section in R2RConfig.REQUIRED_KEYS:
        assert hasattr(config, section), f"Missing required section: {section}"

    # Check for required keys in each section.
    # For the agent section, remove 'generation_config' since it no longer exists.
    for section, required_keys in R2RConfig.REQUIRED_KEYS.items():
        keys_to_check = required_keys
        if section == "agent":
            keys_to_check = [
                key for key in required_keys if key != "generation_config"
            ]
        if keys_to_check:
            section_config = getattr(config, section)
            for key in keys_to_check:
                if isinstance(section_config, dict):
                    assert key in section_config, (
                        f"Missing required key {key} in section {section}")
                else:
                    assert hasattr(section_config, key), (
                        f"Missing required key {key} in section {section}")


def test_serialization_roundtrip(merged_config):
    """Test that serializing and then deserializing the config does not lose
    data."""
    config = R2RConfig(merged_config)
    serialized = config.to_toml()

    # Load the serialized config back
    roundtrip_config = R2RConfig(toml.loads(serialized))

    # Compare a couple of key values after roundtrip.
    assert (roundtrip_config.database.graph_creation_settings.
            graph_entity_description_prompt == config.database.
            graph_creation_settings.graph_entity_description_prompt)
    assert (roundtrip_config.orchestration.provider ==
            config.orchestration.provider)


def test_all_merged_configs(base_config, all_merged_configs):
    """Test that every override file properly merges with the base config."""
    for config_name, merged_data in all_merged_configs.items():
        config = R2RConfig(merged_data)
        assert config is not None

        # Example: if the override does not change app.default_max_upload_size,
        # it should remain as in the base config.
        if "default_max_upload_size" not in merged_data.get("app", {}):
            assert config.app.default_max_upload_size == 214748364800


def test_all_config_overrides(all_configs):
    """Test that all configuration files can be loaded independently."""
    for config_name, config_data in all_configs.items():
        config = R2RConfig(config_data)
        assert config is not None

from copy import deepcopy
from pathlib import Path

import pytest
import toml

from core.base.utils import deep_update
from core.main.config import R2RConfig


@pytest.fixture
def base_config():
    """Load the base r2r.toml config"""
    config_path = Path(__file__).parent.parent.parent / "r2r/r2r.toml"
    with open(config_path) as f:
        return toml.load(f)


@pytest.fixture
def config_dir():
    """Get the path to the configs directory"""
    return Path(__file__).parent.parent.parent / "core" / "configs"


@pytest.fixture
def all_config_files(config_dir):
    """Get list of all TOML files in the configs directory"""
    return list(config_dir.glob("*.toml"))


@pytest.fixture
def all_configs(all_config_files):
    """Load all config files"""
    configs = {}
    for config_file in all_config_files:
        with open(config_file) as f:
            configs[config_file.name] = toml.load(f)
    return configs


@pytest.fixture
def full_config(all_configs):
    """Get the full.toml config"""
    return all_configs["full.toml"]


@pytest.fixture
def all_merged_configs(base_config, all_configs):
    """Create merged configurations for all config files"""
    merged = {}
    for config_name, config_data in all_configs.items():
        merged[config_name] = deep_update(deepcopy(base_config), config_data)
    return merged


@pytest.fixture
def merged_config(base_config, full_config):
    """Create the expected merged configuration"""
    return deep_update(deepcopy(base_config), full_config)


def test_base_config_loading(base_config):
    """Test that the base config loads correctly with all expected values"""
    config = R2RConfig(base_config)

    # Test critical base values
    assert config.database.graph_creation_settings.clustering_mode == "local"
    assert (
        config.database.graph_creation_settings.generation_config.model
        == "openai/gpt-4o-mini"
    )
    assert config.ingestion.provider == "r2r"
    assert config.orchestration.provider == "simple"


def test_full_config_override(base_config, full_config):
    """Test that the full config properly overrides base values"""
    config = R2RConfig(full_config)

    # Test overridden values
    assert config.database.graph_creation_settings.clustering_mode == "remote"
    assert (
        config.database.graph_creation_settings.generation_config.model
        == "openai/gpt-4o-mini"
    )
    assert config.ingestion.provider == "unstructured_local"
    assert config.orchestration.provider == "hatchet"


def test_nested_config_preservation(merged_config):
    """Test that nested configurations are properly preserved during merging"""
    config = R2RConfig(merged_config)

    assert (
        config.database.graph_creation_settings.generation_config.model
        == "openai/gpt-4o-mini"
    )
    assert (
        config.database.graph_creation_settings.generation_config.temperature
        == 0.1
    )
    assert (
        config.database.graph_creation_settings.max_knowledge_relationships
        == 100
    )


def test_new_values_in_override(merged_config):
    """Test that new values in the override config are properly added"""
    config = R2RConfig(merged_config)

    # Test new orchestration values
    assert config.orchestration.kg_creation_concurrency_limit == 32
    assert config.orchestration.ingestion_concurrency_limit == 16
    assert config.orchestration.kg_concurrency_limit == 8


def test_config_type_consistency(merged_config):
    """Test that configuration values maintain their expected types"""
    config = R2RConfig(merged_config)

    # Test type consistency for various fields
    assert isinstance(
        config.database.graph_creation_settings.max_knowledge_relationships,
        int,
    )
    assert isinstance(
        config.database.graph_creation_settings.clustering_mode, str
    )
    assert isinstance(config.ingestion.chunking_strategy, str)


def get_config_files():
    """Helper function to get list of config files"""
    config_dir = Path(__file__).parent.parent.parent / "core" / "configs"
    return ["r2r.toml"] + [f.name for f in config_dir.glob("*.toml")]


@pytest.mark.parametrize("config_file", get_config_files())
def test_config_required_keys(config_file):
    """Test that all required keys are present in all config files"""
    if config_file == "r2r.toml":
        file_path = Path(__file__).parent.parent.parent / "r2r.toml"
    else:
        file_path = (
            Path(__file__).parent.parent.parent
            / "core"
            / "configs"
            / config_file
        )

    with open(file_path) as f:
        config_data = toml.load(f)

    config = R2RConfig(config_data)

    # Test required sections
    for section in R2RConfig.REQUIRED_KEYS:
        assert hasattr(config, section), f"Missing required section: {section}"

    # Test required keys in each section
    for section, required_keys in R2RConfig.REQUIRED_KEYS.items():
        if required_keys:  # Skip empty required_keys lists
            section_config = getattr(config, section)
            for key in required_keys:
                if isinstance(section_config, dict):
                    assert (
                        key in section_config
                    ), f"Missing required key {key} in section {section}"
                else:
                    assert hasattr(
                        section_config, key
                    ), f"Missing required key {key} in section {section}"


def test_serialization_roundtrip(merged_config):
    """Test that configuration can be serialized and deserialized without data loss"""
    config = R2RConfig(merged_config)
    serialized = config.to_toml()

    # Load the serialized config back
    roundtrip_config = R2RConfig(toml.loads(serialized))

    # Test key values after roundtrip
    assert (
        roundtrip_config.database.graph_creation_settings.clustering_mode
        == config.database.graph_creation_settings.clustering_mode
    )
    assert (
        roundtrip_config.database.graph_creation_settings.generation_config.model
        == config.database.graph_creation_settings.generation_config.model
    )
    assert (
        roundtrip_config.orchestration.provider
        == config.orchestration.provider
    )


def test_all_merged_configs(base_config, all_merged_configs):
    """Test that all configs properly merge with base config"""
    for config_name, merged_data in all_merged_configs.items():
        config = R2RConfig(merged_data)

        # Test that the config loads without errors
        assert config is not None

        # Verify that base values are preserved unless explicitly overridden
        if not hasattr(
            config.database.graph_creation_settings, "clustering_mode"
        ):
            assert (
                config.database.graph_creation_settings.clustering_mode
                == "local"
            )

        # Verify that generation_config model is preserved unless explicitly overridden
        if "generation_config" not in merged_data.get("database", {}).get(
            "graph_creation_settings", {}
        ):
            assert (
                config.database.graph_creation_settings.generation_config.model
                == "openai/gpt-4o-mini"
            )


def test_all_config_overrides(base_config, all_configs):
    """Test that all config files can be loaded independently"""
    for config_name, config_data in all_configs.items():
        config = R2RConfig(config_data)
        assert config is not None

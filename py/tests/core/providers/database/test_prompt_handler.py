import uuid
from datetime import timedelta
from typing import Any, Optional

import pytest

from core.base import PromptHandler
from core.providers.database.prompt import PostgresPromptHandler


# Additional fixtures for prompt testing
@pytest.fixture(scope="function")
def prompt_handler_config(app_config):
    return {"cache_ttl": timedelta(hours=1), "max_cache_size": 100}


@pytest.fixture(scope="function")
async def prompt_handler(
    postgres_db_provider, prompt_handler_config, app_config
):
    handler = PostgresPromptHandler(
        project_name=app_config.project_name,
        connection_manager=postgres_db_provider.connection_manager,
        **prompt_handler_config,
    )
    await handler.create_tables()
    yield handler
    # Cleanup will happen via postgres_db_provider fixture


@pytest.fixture(scope="function")
def sample_prompt():
    return {
        "name": "test_prompt",
        "template": "This is a test prompt with {input_var}",
        "input_types": {"input_var": "string"},
    }


# Tests
@pytest.mark.asyncio
async def test_prompt_handler_initialization(prompt_handler):
    """Test that prompt handler initializes properly"""
    assert isinstance(prompt_handler, PromptHandler)


@pytest.mark.asyncio
async def test_add_and_get_prompt(prompt_handler, sample_prompt):
    """Test adding a prompt and retrieving it"""
    await prompt_handler.add_prompt(**sample_prompt)

    result = await prompt_handler.get_prompt(sample_prompt["name"])
    assert result == sample_prompt["template"]


@pytest.mark.asyncio
async def test_get_prompt_with_inputs(prompt_handler, sample_prompt):
    """Test getting a prompt with input variables"""
    await prompt_handler.add_prompt(**sample_prompt)

    test_input = "test value"
    result = await prompt_handler.get_prompt(
        sample_prompt["name"], inputs={"input_var": test_input}
    )
    assert result == sample_prompt["template"].format(input_var=test_input)


@pytest.mark.asyncio
async def test_prompt_cache_behavior(prompt_handler, sample_prompt):
    """Test that caching works as expected"""
    await prompt_handler.add_prompt(**sample_prompt)

    # First call should hit database
    test_input = {"input_var": "cache test"}
    first_result = await prompt_handler.get_prompt(
        sample_prompt["name"], inputs=test_input
    )

    # Second call should hit cache
    second_result = await prompt_handler.get_prompt(
        sample_prompt["name"], inputs=test_input
    )

    # Results should be the same
    assert first_result == second_result

    # Modify the template directly in the database
    new_template = "Modified template {input_var}"
    await prompt_handler._update_prompt_impl(
        name=sample_prompt["name"], template=new_template
    )

    # Third call should get the new value since we invalidate cache on update
    third_result = await prompt_handler.get_prompt(
        sample_prompt["name"], inputs=test_input
    )

    # Verify the change is reflected
    assert third_result == new_template.format(**test_input)
    assert third_result != first_result

    # Test bypass_cache explicitly
    bypass_result = await prompt_handler.get_prompt(
        sample_prompt["name"], inputs=test_input, bypass_cache=True
    )
    assert bypass_result == new_template.format(**test_input)


@pytest.mark.asyncio
async def test_message_payload_creation(prompt_handler, sample_prompt):
    """Test creation of message payloads"""
    await prompt_handler.add_prompt(**sample_prompt)

    payload = await prompt_handler.get_message_payload(
        system_prompt_name=sample_prompt["name"],
        system_inputs={"input_var": "system context"},
        task_prompt_name=sample_prompt["name"],
        task_inputs={"input_var": "task context"},
    )

    assert len(payload) == 2
    assert payload[0]["role"] == "system"
    assert payload[1]["role"] == "user"
    assert "system context" in payload[0]["content"]
    assert "task context" in payload[1]["content"]


@pytest.mark.asyncio
async def test_get_all_prompts(prompt_handler, sample_prompt):
    """Test retrieving all stored prompts"""
    await prompt_handler.add_prompt(**sample_prompt)

    all_prompts = await prompt_handler.get_all_prompts()
    assert len(all_prompts) >= 1
    assert sample_prompt["name"] in all_prompts
    assert (
        all_prompts[sample_prompt["name"]]["template"]
        == sample_prompt["template"]
    )


@pytest.mark.asyncio
async def test_delete_prompt(prompt_handler, sample_prompt):
    """Test deleting a prompt"""
    await prompt_handler.add_prompt(**sample_prompt)

    await prompt_handler.delete_prompt(sample_prompt["name"])

    with pytest.raises(ValueError):
        await prompt_handler.get_prompt(sample_prompt["name"])


@pytest.mark.asyncio
async def test_prompt_bypass_cache(prompt_handler, sample_prompt):
    """Test bypassing the cache"""
    await prompt_handler.add_prompt(**sample_prompt)

    # First call to cache the result
    test_input = {"input_var": "bypass test"}
    first_result = await prompt_handler.get_prompt(
        sample_prompt["name"], inputs=test_input
    )

    # Update template
    new_template = "Updated template {input_var}"
    await prompt_handler._update_prompt_impl(
        name=sample_prompt["name"], template=new_template
    )

    # Get with bypass_cache=True should return new template
    bypass_result = await prompt_handler.get_prompt(
        sample_prompt["name"], inputs=test_input, bypass_cache=True
    )

    assert bypass_result != first_result
    assert bypass_result == new_template.format(**test_input)


@pytest.mark.asyncio
async def test_prompt_update(prompt_handler, sample_prompt):
    """Test updating an existing prompt"""
    # Add initial prompt
    await prompt_handler.add_prompt(**sample_prompt)
    initial_result = await prompt_handler.get_prompt(sample_prompt["name"])
    assert initial_result == sample_prompt["template"]

    # Update template
    updated_template = "This is an updated prompt with {input_var}!"
    await prompt_handler.update_prompt(
        name=sample_prompt["name"], template=updated_template
    )

    # Test immediate result
    updated_result = await prompt_handler.get_prompt(sample_prompt["name"])
    assert updated_result == updated_template

    # Test with cache bypass to ensure database update
    db_result = await prompt_handler.get_prompt(
        sample_prompt["name"], bypass_cache=True
    )
    assert db_result == updated_template

    # Test with input formatting
    formatted_result = await prompt_handler.get_prompt(
        sample_prompt["name"], inputs={"input_var": "test"}
    )
    assert formatted_result == "This is an updated prompt with test!"

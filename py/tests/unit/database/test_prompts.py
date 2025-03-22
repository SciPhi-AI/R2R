import uuid

import pytest

# from core.providers.database.postgres_prompts import PostgresPromptsHandler


@pytest.mark.asyncio
async def test_add_prompt_basic(prompt_handler):
    """Test basic addition of a new prompt."""
    prompt_name = f"test_prompt_{uuid.uuid4()}"
    template = "Hello, {name}!"
    input_types = {"name": "str"}

    await prompt_handler.add_prompt(
        name=prompt_name,
        template=template,
        input_types=input_types,
    )

    # Verify in-memory
    assert prompt_name in prompt_handler.prompts
    # Verify DB read is consistent
    prompt_info = prompt_handler.prompts[prompt_name]
    assert prompt_info["template"] == template
    assert prompt_info["input_types"] == input_types

    # Attempt retrieval using the get_prompt method (should exist)
    db_data = await prompt_handler.get_prompt(prompt_name)
    assert db_data["template"] == template
    assert db_data["input_types"] == input_types


@pytest.mark.asyncio
async def test_add_prompt_preserve_existing(prompt_handler):
    """If preserve_existing is True, we skip overwriting even if we supply new
    data."""
    prompt_name = f"test_preserve_{uuid.uuid4()}"
    template_original = "Original template"
    input_types_original = {"param": "str"}

    # Create original
    await prompt_handler.add_prompt(
        name=prompt_name,
        template=template_original,
        input_types=input_types_original,
    )

    # Attempt second add with new data but preserve_existing = True
    template_new = "New template"
    input_types_new = {"param": "int"}
    await prompt_handler.add_prompt(
        name=prompt_name,
        template=template_new,
        input_types=input_types_new,
        preserve_existing=True,
    )

    # Expect no changes to the original prompt
    existing = prompt_handler.prompts[prompt_name]
    assert existing["template"] == template_original
    assert existing["input_types"] == input_types_original


@pytest.mark.asyncio
async def test_add_prompt_overwrite_on_diff_false(prompt_handler, caplog):
    """If overwrite_on_diff=False but there is a diff, skip updating and log an
    info message."""
    prompt_name = f"test_diff_false_{uuid.uuid4()}"
    template_original = "Original template: {key}"
    input_types_original = {"key": "str"}

    # Create original
    await prompt_handler.add_prompt(
        name=prompt_name,
        template=template_original,
        input_types=input_types_original,
    )

    # Attempt second add with new data but overwrite_on_diff=False
    new_template = "New template: {key}"
    new_input_types = {"key": "int"}
    await prompt_handler.add_prompt(
        name=prompt_name,
        template=new_template,
        input_types=new_input_types,
        overwrite_on_diff=False,
    )

    # Should be no changes
    existing = prompt_handler.prompts[prompt_name]
    assert existing["template"] == template_original
    assert existing["input_types"] == input_types_original

    # Check logs for the skipping message
    assert any(
        "Skipping update" in record.message
        for record in caplog.records), "Expected a skip update log message."


@pytest.mark.asyncio
async def test_add_prompt_overwrite_on_diff_true(prompt_handler, caplog):
    """If overwrite_on_diff=True and there's a diff, we overwrite existing
    prompt and log a warning."""
    prompt_name = f"test_diff_true_{uuid.uuid4()}"
    template_original = "Original template: {key}"
    input_types_original = {"key": "str"}

    # Create original
    await prompt_handler.add_prompt(
        name=prompt_name,
        template=template_original,
        input_types=input_types_original,
    )

    # Attempt second add with new data but overwrite_on_diff=True
    new_template = "New template: {new_key}"
    new_input_types = {"new_key": "int"}
    await prompt_handler.add_prompt(
        name=prompt_name,
        template=new_template,
        input_types=new_input_types,
        overwrite_on_diff=True,
    )

    # Expect changes
    existing = prompt_handler.prompts[prompt_name]
    assert existing["template"] == new_template
    assert existing["input_types"] == new_input_types

    # Check logs for the overwriting warning
    assert any(
        "Overwriting existing prompt" in record.message
        for record in caplog.records), "Expected an overwrite warning message."


@pytest.mark.asyncio
async def test_get_cached_prompt(prompt_handler):
    """Test that get_cached_prompt uses caching properly."""
    prompt_name = f"test_cached_{uuid.uuid4()}"
    template = "Cached template: {key}"
    input_types = {"key": "str"}

    await prompt_handler.add_prompt(
        name=prompt_name,
        template=template,
        input_types=input_types,
    )

    # First retrieval should set the cache
    content_1 = await prompt_handler.get_cached_prompt(prompt_name,
                                                       {"key": "Bob"})
    assert "Bob" in content_1

    # Modify in DB behind the scenes (simulate a change not going through add_prompt)
    # We'll do a direct DB update to illustrate caching effect
    new_template = "Updated in DB: {key}"
    query = f"""
        UPDATE {prompt_handler._get_table_name("prompts")}
        SET template=$1
        WHERE name=$2
    """
    await prompt_handler.connection_manager.execute_query(
        query, [new_template, prompt_name])

    # Second retrieval should still reflect the old template if the cache is not bypassed
    content_2 = await prompt_handler.get_cached_prompt(prompt_name,
                                                       {"key": "Alice"})
    assert "Bob" not in content_2  # Just to ensure we see the difference
    assert "Updated in DB" not in content_2, (
        "Should not see updated text if cache is used.")
    assert "Cached template" in content_2

    # Bypass cache
    content_3 = await prompt_handler.get_cached_prompt(prompt_name,
                                                       {"key": "Alice"},
                                                       bypass_cache=True)
    assert "Updated in DB" in content_3, (
        "Now we should see the new DB changes after bypassing cache.")

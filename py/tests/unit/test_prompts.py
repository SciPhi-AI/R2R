import uuid

import pytest

# from core.providers.database.postgres_prompts import PostgresPromptsHandler


@pytest.mark.asyncio
async def test_add_prompt_basic(mock_prompt_handler):
    """Test basic addition of a new prompt."""
    prompt_name = f"test_prompt_{uuid.uuid4()}"
    template = "Hello, {name}!"
    input_types = {"name": "str"}

    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template,
        input_types=input_types,
    )

    # Verify in-memory
    assert prompt_name in mock_prompt_handler.prompts
    # Verify DB read is consistent
    prompt_info = mock_prompt_handler.prompts[prompt_name]
    assert prompt_info["template"] == template
    assert prompt_info["input_types"] == input_types

    # Attempt retrieval using the get_prompt method (should exist)
    db_data = await mock_prompt_handler.get_prompt(prompt_name)
    assert db_data["template"] == template
    assert db_data["input_types"] == input_types


@pytest.mark.asyncio
async def test_add_prompt_preserve_existing(mock_prompt_handler):
    """If preserve_existing is True, we skip overwriting even if we supply new
    data."""
    prompt_name = f"test_preserve_{uuid.uuid4()}"
    template_original = "Original template"
    input_types_original = {"param": "str"}

    # Create original
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template_original,
        input_types=input_types_original,
    )

    # Attempt second add with new data but preserve_existing = True
    template_new = "New template"
    input_types_new = {"param": "int"}
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template_new,
        input_types=input_types_new,
        preserve_existing=True,
    )

    # Expect no changes to the original prompt
    existing = mock_prompt_handler.prompts[prompt_name]
    assert existing["template"] == template_original
    assert existing["input_types"] == input_types_original


@pytest.mark.asyncio
async def test_add_prompt_overwrite_on_diff_false(mock_prompt_handler, caplog):
    """If overwrite_on_diff=False but there is a diff, skip updating and log an
    info message."""
    # This test is now obsolete since we removed overwrite_on_diff
    # We'll test with preserve_existing instead
    prompt_name = f"test_preserve_existing_{uuid.uuid4()}"
    template_original = "Original template: {key}"
    input_types_original = {"key": "str"}

    # Create original
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template_original,
        input_types=input_types_original,
    )

    # Try to update with preserve_existing=True
    new_template = "New template: {key}"
    new_input_types = {"key": "int"}
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=new_template,
        input_types=new_input_types,
        preserve_existing=True,
    )

    # Should be no changes
    existing = mock_prompt_handler.prompts[prompt_name]
    assert existing["template"] == template_original
    assert existing["input_types"] == input_types_original


@pytest.mark.asyncio
async def test_add_prompt_overwrite_on_diff_true(mock_prompt_handler, caplog):
    """If preserve_existing=False (default), we overwrite the existing prompt."""
    prompt_name = f"test_overwrite_{uuid.uuid4()}"
    template_original = "Original template: {key}"
    input_types_original = {"key": "str"}

    # Create original
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template_original,
        input_types=input_types_original,
    )

    # Update with preserve_existing=False (default)
    new_template = "New template: {new_key}"
    new_input_types = {"new_key": "int"}
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=new_template,
        input_types=new_input_types,
    )

    # Expect changes
    existing = mock_prompt_handler.prompts[prompt_name]
    assert existing["template"] == new_template
    assert existing["input_types"] == new_input_types


@pytest.mark.asyncio
async def test_update_prompt_updates_db_and_dict(mock_prompt_handler):
    """Test that update_prompt updates both the database and in-memory dictionary."""
    prompt_name = f"test_update_{uuid.uuid4()}"
    original_template = "Original template: {param}"
    original_input_types = {"param": "str"}

    # First add the prompt
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=original_template,
        input_types=original_input_types,
    )

    # Verify initial state
    initial_db_prompt = await mock_prompt_handler.get_prompt(prompt_name)
    assert initial_db_prompt["template"] == original_template
    assert initial_db_prompt["input_types"] == original_input_types
    assert mock_prompt_handler.prompts[prompt_name]["template"] == original_template

    # Update the prompt
    new_template = "Updated template: {param} and {new_param}"
    new_input_types = {"param": "str", "new_param": "int"}

    await mock_prompt_handler.update_prompt(
        name=prompt_name,
        template=new_template,
        input_types=new_input_types,
    )

    # Verify database update
    updated_db_prompt = await mock_prompt_handler.get_prompt(prompt_name)
    assert updated_db_prompt["template"] == new_template
    assert updated_db_prompt["input_types"] == new_input_types

    # Verify in-memory dictionary update
    assert mock_prompt_handler.prompts[prompt_name]["template"] == new_template
    assert mock_prompt_handler.prompts[prompt_name]["input_types"] == new_input_types


@pytest.mark.asyncio
async def test_update_prompt_partial_updates(mock_prompt_handler):
    """Test that update_prompt works with partial updates (only template or only input_types)."""
    prompt_name = f"test_partial_update_{uuid.uuid4()}"
    original_template = "Original template: {param}"
    original_input_types = {"param": "str"}

    # First add the prompt
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=original_template,
        input_types=original_input_types,
    )

    # Update only the template
    new_template = "Updated template: {param}"
    await mock_prompt_handler.update_prompt(
        name=prompt_name,
        template=new_template,
    )

    # Verify partial update
    updated_prompt = await mock_prompt_handler.get_prompt(prompt_name)
    assert updated_prompt["template"] == new_template
    assert updated_prompt["input_types"] == original_input_types

    # Verify in-memory dictionary update
    assert mock_prompt_handler.prompts[prompt_name]["template"] == new_template
    assert mock_prompt_handler.prompts[prompt_name]["input_types"] == original_input_types

    # Update only the input_types
    new_input_types = {"param": "str", "optional_param": "int"}
    await mock_prompt_handler.update_prompt(
        name=prompt_name,
        input_types=new_input_types,
    )

    # Verify second partial update
    updated_prompt = await mock_prompt_handler.get_prompt(prompt_name)
    assert updated_prompt["template"] == new_template  # From previous update
    assert updated_prompt["input_types"] == new_input_types

    # Verify in-memory dictionary update
    assert mock_prompt_handler.prompts[prompt_name]["template"] == new_template
    assert mock_prompt_handler.prompts[prompt_name]["input_types"] == new_input_types


@pytest.mark.asyncio
async def test_template_cache_consistency(mock_prompt_handler):
    """Test that the template cache correctly updates when prompts are modified."""
    prompt_name = f"test_cache_consistency_{uuid.uuid4()}"
    template = "Test template: {param}"
    input_types = {"param": "str"}

    # Add the prompt
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template,
        input_types=input_types,
    )

    # First access to cache the template
    await mock_prompt_handler.get_cached_prompt(prompt_name, {"param": "value1"})

    # Update the prompt
    updated_template = "Updated template: {param}"
    await mock_prompt_handler.update_prompt(
        name=prompt_name,
        template=updated_template,
    )

    # Verify that a new request gets the updated template
    # This should happen even without bypass_cache because the template cache was cleared on update
    result = await mock_prompt_handler.get_cached_prompt(prompt_name, {"param": "value2"})
    assert "Updated template: value2" in result

    # The stored template in the cache should match the DB
    cached_template = mock_prompt_handler._template_cache.get(prompt_name)
    assert cached_template is not None
    assert cached_template["template"] == updated_template


@pytest.mark.asyncio
async def test_prompt_deletion_cleanup(mock_prompt_handler):
    """Test that deleting a prompt removes it from the database, in-memory dictionary, and caches."""
    prompt_name = f"test_deletion_{uuid.uuid4()}"
    template = "To be deleted: {param}"
    input_types = {"param": "str"}

    # Add the prompt
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template,
        input_types=input_types,
    )

    # Access it once to ensure it's in caches
    await mock_prompt_handler.get_cached_prompt(prompt_name, {"param": "value"})

    # Delete the prompt
    await mock_prompt_handler.delete_prompt(prompt_name)

    # Verify it's gone from the in-memory dictionary
    assert prompt_name not in mock_prompt_handler.prompts

    # Verify it's gone from template cache
    assert mock_prompt_handler._template_cache.get(prompt_name) is None

    # Verify it's gone from prompt cache
    cache_key = mock_prompt_handler._cache_key(prompt_name, {"param": "value"})
    assert mock_prompt_handler._prompt_cache.get(cache_key) is None

    # Verify it's gone from database
    with pytest.raises(ValueError, match=f"Prompt template '{prompt_name}' not found"):
        await mock_prompt_handler.get_prompt(prompt_name)


@pytest.mark.asyncio
async def test_immediate_database_updates(mock_prompt_handler):
    """Test that the database is immediately updated when a prompt is modified."""
    prompt_name = f"test_immediate_db_{uuid.uuid4()}"
    template = "Original: {param}"
    input_types = {"param": "str"}

    # Add the prompt
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template,
        input_types=input_types,
    )

    # Get original directly from database
    query = f"""
    SELECT template FROM {mock_prompt_handler._get_table_name("prompts")}
    WHERE name = $1
    """
    result = await mock_prompt_handler.connection_manager.fetchrow_query(query, [prompt_name])
    assert result["template"] == template

    # Update the prompt
    updated_template = "Updated: {param}"
    await mock_prompt_handler.update_prompt(
        name=prompt_name,
        template=updated_template,
    )

    # Immediately verify in database
    result = await mock_prompt_handler.connection_manager.fetchrow_query(query, [prompt_name])
    assert result["template"] == updated_template

    # Also verify in-memory state
    assert mock_prompt_handler.prompts[prompt_name]["template"] == updated_template


@pytest.mark.asyncio
async def test_get_cached_prompt(mock_prompt_handler):
    """Test that get_cached_prompt uses caching properly."""
    prompt_name = f"test_cached_{uuid.uuid4()}"
    template = "Cached template: {key}"
    input_types = {"key": "str"}

    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template,
        input_types=input_types,
    )

    # First retrieval should set the cache
    content_1 = await mock_prompt_handler.get_cached_prompt(prompt_name,
                                                       {"key": "Bob"})
    assert "Bob" in content_1

    # Simulate a direct DB update by modifying the mock connection manager's data
    new_template = "Updated in DB: {key}"
    mock_prompt_handler.connection_manager.db['prompts'][prompt_name]['template'] = new_template

    # Second retrieval should still reflect the old template if the cache is not bypassed
    content_2 = await mock_prompt_handler.get_cached_prompt(prompt_name,
                                                       {"key": "Alice"})
    assert "Bob" not in content_2  # Just to ensure we see the difference
    assert "Updated in DB" not in content_2, (
        "Should not see updated text if cache is used.")
    assert "Cached template" in content_2

    # Bypass cache
    content_3 = await mock_prompt_handler.get_cached_prompt(prompt_name,
                                                       {"key": "Alice"},
                                                       bypass_cache=True)
    assert "Updated in DB" in content_3, (
        "Now we should see the new DB changes after bypassing cache.")

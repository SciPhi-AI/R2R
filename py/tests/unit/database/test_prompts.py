import uuid

import pytest
import yaml
from io import StringIO

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


@pytest.mark.asyncio
async def test_yaml_loading(mock_prompt_handler):
    """Test loading prompts from YAML content."""
    # Create a simple YAML string with prompt definitions
    yaml_content = """
    prompts:
      - name: yaml_test_prompt
        template: "This is a test prompt from YAML: {param}"
        input_types:
          param: str
      - name: yaml_test_prompt2
        template: "Another test prompt: {value}"
        input_types:
          value: str
    """

    # Load prompts from YAML
    await mock_prompt_handler.load_prompts_from_yaml(yaml_content)

    # Verify prompts were loaded
    prompt1 = await mock_prompt_handler.get_prompt("yaml_test_prompt")
    assert prompt1["template"] == "This is a test prompt from YAML: {param}"
    assert prompt1["input_types"] == {"param": "str"}

    prompt2 = await mock_prompt_handler.get_prompt("yaml_test_prompt2")
    assert prompt2["template"] == "Another test prompt: {value}"
    assert prompt2["input_types"] == {"value": "str"}

    # Test formatting the loaded prompts
    formatted = await mock_prompt_handler.get_cached_prompt("yaml_test_prompt", {"param": "yaml_value"})
    assert formatted == "This is a test prompt from YAML: yaml_value"


@pytest.mark.asyncio
async def test_special_character_handling(mock_prompt_handler):
    """Test handling of special characters in templates."""
    prompt_name = f"special_chars_{uuid.uuid4()}"
    # Template with various special characters
    template = """
    Line 1: {param1}
    Line 2: {{escaped_braces}}
    Line 3: Special chars: !@#$%^&*()
    Line 4: Unicode: 你好, 世界
    Line 5: HTML-like: <tag>{param2}</tag>
    """
    input_types = {"param1": "str", "param2": "str"}

    # Add the prompt
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template,
        input_types=input_types,
    )

    # Get the formatted prompt
    formatted = await mock_prompt_handler.get_cached_prompt(
        prompt_name,
        {"param1": "Value 1", "param2": "Value 2"}
    )

    # Check that special characters are preserved
    assert "Line 1: Value 1" in formatted
    assert "Line 2: {escaped_braces}" in formatted
    assert "Line 3: Special chars: !@#$%^&*()" in formatted
    assert "Line 4: Unicode: 你好, 世界" in formatted
    assert "Line 5: HTML-like: <tag>Value 2</tag>" in formatted


@pytest.mark.asyncio
async def test_cache_invalidation_methods(mock_prompt_handler):
    """Test different ways the cache can be invalidated."""
    prompt_name = f"cache_invalidation_{uuid.uuid4()}"
    original_template = "Original: {param}"
    input_types = {"param": "str"}

    # Add the prompt
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=original_template,
        input_types=input_types,
    )

    # First access caches the result
    first_result = await mock_prompt_handler.get_cached_prompt(
        prompt_name, {"param": "test"}
    )
    assert "Original: test" in first_result

    # Method 1: Update via update_prompt
    await mock_prompt_handler.update_prompt(
        name=prompt_name,
        template="Method1: {param}"
    )

    method1_result = await mock_prompt_handler.get_cached_prompt(
        prompt_name, {"param": "test"}
    )
    assert "Method1: test" in method1_result

    # Method 2: Update via add_prompt with same name
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template="Method2: {param}",
        input_types=input_types,
    )

    method2_result = await mock_prompt_handler.get_cached_prompt(
        prompt_name, {"param": "test"}
    )
    assert "Method2: test" in method2_result

    # Method 3: Direct database update simulation
    mock_prompt_handler.connection_manager.db['prompts'][prompt_name]['template'] = "Method3: {param}"

    # This should still use the cache
    cached_result = await mock_prompt_handler.get_cached_prompt(
        prompt_name, {"param": "test"}
    )
    assert "Method2: test" in cached_result  # Should be the previous version

    # But with bypass_cache it should get the latest
    bypass_result = await mock_prompt_handler.get_cached_prompt(
        prompt_name, {"param": "test"}, bypass_cache=True
    )
    assert "Method3: test" in bypass_result


@pytest.mark.asyncio
async def test_input_validation(mock_prompt_handler):
    """Test validation of input types when formatting prompts."""
    prompt_name = f"validation_{uuid.uuid4()}"
    template = "Test with {num:d} and {text}!"
    input_types = {"num": "int", "text": "str"}

    # Add the prompt
    await mock_prompt_handler.add_prompt(
        name=prompt_name,
        template=template,
        input_types=input_types,
    )

    # Valid inputs
    valid_result = await mock_prompt_handler.get_cached_prompt(
        prompt_name, {"num": 42, "text": "hello"}
    )
    assert valid_result == "Test with 42 and hello!"

    # Test with missing input (should raise KeyError)
    with pytest.raises(KeyError):
        await mock_prompt_handler.get_cached_prompt(
            prompt_name, {"num": 42}  # Missing 'text'
        )

    # Test with incorrect type (handled by Python's format method)
    with pytest.raises(ValueError):
        await mock_prompt_handler.get_cached_prompt(
            prompt_name, {"num": "not-a-number", "text": "hello"}
        )


@pytest.mark.asyncio
async def test_batch_operations(mock_prompt_handler):
    """Test handling multiple prompt operations in sequence."""
    # Generate 5 prompt names
    prompt_names = [f"batch_prompt_{uuid.uuid4()}" for _ in range(5)]

    # Add all prompts in sequence
    for i, name in enumerate(prompt_names):
        await mock_prompt_handler.add_prompt(
            name=name,
            template=f"Batch prompt {i}: {{param}}",
            input_types={"param": "str"},
        )

    # Verify all were added correctly
    all_prompts = await mock_prompt_handler.list_prompts()
    all_prompt_names = [prompt["name"] for prompt in all_prompts]
    for name in prompt_names:
        assert name in all_prompt_names

    # Format all prompts
    formatted_results = []
    for name in prompt_names:
        result = await mock_prompt_handler.get_cached_prompt(
            name, {"param": "batch_value"}
        )
        formatted_results.append(result)

    # Verify formatting worked for all
    for i, result in enumerate(formatted_results):
        assert f"Batch prompt {i}: batch_value" in result

    # Update multiple prompts
    for i, name in enumerate(prompt_names[:3]):  # Update first 3
        await mock_prompt_handler.update_prompt(
            name=name,
            template=f"Updated batch {i}: {{param}}",
        )

    # Delete the last 2 prompts
    for name in prompt_names[3:]:
        await mock_prompt_handler.delete_prompt(name)

    # Verify updates and deletions
    remaining_prompts = await mock_prompt_handler.list_prompts()
    remaining_names = [prompt["name"] for prompt in remaining_prompts]

    # First 3 should still exist
    for name in prompt_names[:3]:
        assert name in remaining_names

    # Last 2 should be gone
    for name in prompt_names[3:]:
        assert name not in remaining_names

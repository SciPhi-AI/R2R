from uuid import uuid4

import pytest

from shared.abstractions.vector import (
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
    VectorTableName,
)


@pytest.mark.asyncio
async def test_index_lifecycle(postgres_db_provider):
    """Test the full lifecycle of index operations"""

    # Create an index
    index_name = f"test_index_{uuid4().hex[:8]}"
    await postgres_db_provider.create_index(
        table_name=VectorTableName.VECTORS,
        index_measure=IndexMeasure.cosine_distance,
        index_method=IndexMethod.hnsw,
        index_name=index_name,
        concurrently=False,  # Changed to avoid isolation level issues
    )

    # List indices and verify our index exists
    indices = await postgres_db_provider.list_indices(VectorTableName.VECTORS)
    print("indices = ", indices)
    assert indices, "No indices returned"
    assert any(index["name"] == index_name for index in indices)

    # # Select the index for use
    # await postgres_db_provider.select_index(
    #     index_name, VectorTableName.VECTORS
    # )

    # Delete the index
    await postgres_db_provider.delete_index(
        index_name,
        table_name=VectorTableName.VECTORS,
        concurrently=False,  # Consistent with creation
    )

    # Verify index was deleted
    indices_after = await postgres_db_provider.list_indices(
        VectorTableName.VECTORS
    )
    assert not any(index["name"] == index_name for index in indices_after)


@pytest.mark.asyncio
async def test_multiple_index_types(postgres_db_provider):
    """Test creating and managing multiple types of indices"""

    # Create HNSW index
    hnsw_name = f"hnsw_index_{uuid4().hex[:8]}"
    await postgres_db_provider.create_index(
        table_name=VectorTableName.VECTORS,
        index_measure=IndexMeasure.cosine_distance,
        index_method=IndexMethod.hnsw,
        index_name=hnsw_name,
        index_arguments=IndexArgsHNSW(m=16, ef_construction=64),
        concurrently=False,  # Changed to avoid isolation level issues
    )

    # Create IVF-Flat index
    ivf_name = f"ivf_index_{uuid4().hex[:8]}"
    await postgres_db_provider.create_index(
        table_name=VectorTableName.VECTORS,
        index_measure=IndexMeasure.cosine_distance,
        index_method=IndexMethod.ivfflat,
        index_name=ivf_name,
        index_arguments=IndexArgsIVFFlat(n_lists=100),
        concurrently=False,  # Changed to avoid isolation level issues
    )

    # List indices and verify both exist
    indices = await postgres_db_provider.list_indices(VectorTableName.VECTORS)
    assert any(index["name"] == hnsw_name for index in indices)
    assert any(index["name"] == ivf_name for index in indices)

    # Clean up
    await postgres_db_provider.delete_index(
        hnsw_name, table_name=VectorTableName.VECTORS, concurrently=False
    )
    await postgres_db_provider.delete_index(
        ivf_name, table_name=VectorTableName.VECTORS, concurrently=False
    )


@pytest.mark.asyncio
async def test_index_operations_invalid_inputs(postgres_db_provider):
    """Test error handling for invalid index operations"""

    # Try to list indices for invalid table
    with pytest.raises(Exception):
        await postgres_db_provider.list_indices("invalid_table")

    # Try to delete non-existent index
    with pytest.raises(Exception):
        await postgres_db_provider.delete_index(
            "nonexistent_index", VectorTableName.VECTORS
        )

    # Try to select non-existent index
    # with pytest.raises(Exception):
    #     await postgres_db_provider.select_index(
    #         "nonexistent_index", VectorTableName.VECTORS
    #     )


@pytest.mark.asyncio
async def test_index_persistence(
    postgres_db_provider, temporary_postgres_db_provider
):
    """Test that indices persist and are usable between connections"""

    # Create index using first connection
    index_name = f"persist_test_{uuid4().hex[:8]}"
    await postgres_db_provider.create_index(
        table_name=VectorTableName.VECTORS,
        index_measure=IndexMeasure.cosine_distance,
        index_method=IndexMethod.hnsw,
        index_name=index_name,
        concurrently=False,  # Changed to avoid isolation level issues
    )

    # Verify index exists using second connection
    indices = await temporary_postgres_db_provider.list_indices(
        VectorTableName.VECTORS
    )
    assert any(index["name"] == index_name for index in indices)

    # Clean up
    await postgres_db_provider.delete_index(
        index_name, table_name=VectorTableName.VECTORS, concurrently=False
    )

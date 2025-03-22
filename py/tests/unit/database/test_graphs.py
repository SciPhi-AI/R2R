import uuid
from enum import Enum

import pytest

from core.base.api.models import GraphResponse


class StoreType(str, Enum):
    GRAPHS = "graphs"
    DOCUMENTS = "documents"


@pytest.mark.asyncio
async def test_create_graph(graphs_handler):
    coll_id = uuid.uuid4()
    resp = await graphs_handler.create(collection_id=coll_id,
                                       name="My Graph",
                                       description="Test Graph")
    assert isinstance(resp, GraphResponse)
    assert resp.name == "My Graph"
    assert resp.collection_id == coll_id


@pytest.mark.asyncio
async def test_add_entities_and_relationships(graphs_handler):
    # Create a graph
    coll_id = uuid.uuid4()
    graph_resp = await graphs_handler.create(collection_id=coll_id,
                                             name="TestGraph")
    graph_id = graph_resp.id

    # Add an entity
    entity = await graphs_handler.entities.create(
        parent_id=graph_id,
        store_type=StoreType.GRAPHS,
        name="TestEntity",
        category="Person",
        description="A test entity",
    )
    assert entity.name == "TestEntity"

    # Add another entity
    entity2 = await graphs_handler.entities.create(
        parent_id=graph_id,
        store_type=StoreType.GRAPHS,
        name="AnotherEntity",
        category="Place",
        description="A test place",
    )

    # Add a relationship between them
    rel = await graphs_handler.relationships.create(
        subject="TestEntity",
        subject_id=entity.id,
        predicate="lives_in",
        object="AnotherEntity",
        object_id=entity2.id,
        parent_id=graph_id,
        store_type=StoreType.GRAPHS,
        description="Entity lives in AnotherEntity",
    )
    assert rel.predicate == "lives_in"

    # Verify entities retrieval
    ents, total_ents = await graphs_handler.get_entities(parent_id=graph_id,
                                                         offset=0,
                                                         limit=10)
    assert total_ents == 2
    names = [e.name for e in ents]
    assert "TestEntity" in names and "AnotherEntity" in names

    # Verify relationships retrieval
    rels, total_rels = await graphs_handler.get_relationships(
        parent_id=graph_id, offset=0, limit=10)
    assert total_rels == 1
    assert rels[0].predicate == "lives_in"


@pytest.mark.asyncio
async def test_delete_entities_and_relationships(graphs_handler):
    # Create another graph
    coll_id = uuid.uuid4()
    graph_resp = await graphs_handler.create(collection_id=coll_id,
                                             name="DeletableGraph")
    graph_id = graph_resp.id

    # Add entities
    e1 = await graphs_handler.entities.create(
        parent_id=graph_id,
        store_type=StoreType.GRAPHS,
        name="DeleteMe",
    )
    e2 = await graphs_handler.entities.create(
        parent_id=graph_id,
        store_type=StoreType.GRAPHS,
        name="DeleteMeToo",
    )

    # Add relationship
    rel = await graphs_handler.relationships.create(
        subject="DeleteMe",
        subject_id=e1.id,
        predicate="related_to",
        object="DeleteMeToo",
        object_id=e2.id,
        parent_id=graph_id,
        store_type=StoreType.GRAPHS,
    )

    # Delete one entity
    await graphs_handler.entities.delete(
        parent_id=graph_id,
        entity_ids=[e1.id],
        store_type=StoreType.GRAPHS,
    )
    ents, count = await graphs_handler.get_entities(parent_id=graph_id,
                                                    offset=0,
                                                    limit=10)
    assert count == 1
    assert ents[0].id == e2.id

    # Delete the relationship
    await graphs_handler.relationships.delete(
        parent_id=graph_id,
        relationship_ids=[rel.id],
        store_type=StoreType.GRAPHS,
    )
    rels, rel_count = await graphs_handler.get_relationships(
        parent_id=graph_id, offset=0, limit=10)
    assert rel_count == 0


@pytest.mark.asyncio
async def test_communities(graphs_handler):
    # Insert a community for a collection_id (not strictly related to a graph_id)
    coll_id = uuid.uuid4()
    await graphs_handler.communities.create(
        parent_id=coll_id,
        store_type=StoreType.GRAPHS,
        name="CommunityOne",
        summary="Test community",
        findings=["finding1", "finding2"],
        rating=4.5,
        rating_explanation="Excellent",
        description_embedding=[0.1, 0.2, 0.3, 0.4],
    )

    comms, count = await graphs_handler.communities.get(
        parent_id=coll_id,
        store_type=StoreType.GRAPHS,
        offset=0,
        limit=10,
    )
    assert count == 1
    assert comms[0].name == "CommunityOne"


# TODO - Fix code such that these tests pass
# # @pytest.mark.asyncio
# # async def test_delete_graph(graphs_handler):
# #     # Create a graph and then delete it
# #     coll_id = uuid.uuid4()
# #     graph_resp = await graphs_handler.create(collection_id=coll_id, name="TempGraph")
# #     graph_id = graph_resp.id

# #     # reset or delete calls are complicated in the code. We'll just call `reset` and `delete`
# #     await graphs_handler.reset(graph_id)
# #     # This should remove all entities & relationships from the graph_id

# #     # Now delete the graph itself
# #     # The `delete` method seems to be tied to collection_id rather than graph_id
# #     await graphs_handler.delete(collection_id=graph_id, cascade=False)
# #     # If the code is structured so that delete requires a collection_id,
# #     # ensure `graph_id == collection_id` or adapt the code accordingly.

# #     # Try fetching the graph
# #     overview = await graphs_handler.list_graphs(offset=0, limit=10, filter_graph_ids=[graph_id])
# #     assert overview["total_entries"] == 0, "Graph should be deleted"

# @pytest.mark.asyncio
# async def test_delete_graph(graphs_handler):
#     # Create a graph and then delete it
#     coll_id = uuid.uuid4()
#     graph_resp = await graphs_handler.create(collection_id=coll_id, name="TempGraph")
#     graph_id = graph_resp.id

#     # Reset the graph (remove entities, relationships, communities)
#     await graphs_handler.reset(graph_id)

#     # Now delete the graph using collection_id (which equals graph_id in this code)
#     await graphs_handler.delete(collection_id=coll_id)

#     # Verify the graph is deleted
#     overview = await graphs_handler.list_graphs(offset=0, limit=10, filter_graph_ids=[coll_id])
#     assert overview["total_entries"] == 0, "Graph should be deleted"


@pytest.mark.asyncio
async def test_create_graph_defaults(graphs_handler):
    # Create a graph without specifying name or description
    coll_id = uuid.uuid4()
    resp = await graphs_handler.create(collection_id=coll_id)
    assert resp.collection_id == coll_id
    # The code sets a default name, which should be "Graph {coll_id}"
    assert resp.name == f"Graph {coll_id}"
    # Default description should be empty string as per code
    assert resp.description == ""


# @pytest.mark.asyncio
# async def test_list_multiple_graphs(graphs_handler):
#     # Create multiple graphs
#     coll_id1 = uuid.uuid4()
#     coll_id2 = uuid.uuid4()
#     graph_resp1 = await graphs_handler.create(collection_id=coll_id1, name="Graph1")
#     graph_resp2 = await graphs_handler.create(collection_id=coll_id2, name="Graph2")
#     graph_resp3 = await graphs_handler.create(collection_id=coll_id2, name="Graph3")

#     # List all graphs without filters
#     overview = await graphs_handler.list_graphs(offset=0, limit=10)
#     # Ensure at least these three are in there
#     found_ids = [g.id for g in overview["results"]]
#     assert graph_resp1.id in found_ids
#     assert graph_resp2.id in found_ids
#     assert graph_resp3.id in found_ids

#     # Filter by collection_id = coll_id2 should return Graph2 and Graph3 (the most recent one first if same collection)
#     overview_coll2 = await graphs_handler.list_graphs(offset=0, limit=10, filter_collection_id=coll_id2)
#     returned_ids = [g.id for g in overview_coll2["results"]]
#     # According to the code, we only see the "most recent" graph per collection. Verify this logic.
#     # If your code is returning only the most recent graph per collection, we should see only one graph per collection_id here.
#     # Adjust test according to actual logic you desire.
#     # For this example, let's assume we should only get the latest graph per collection. Graph3 should be newer than Graph2.
#     assert len(returned_ids) == 1
#     assert graph_resp3.id in returned_ids


@pytest.mark.asyncio
async def test_update_graph(graphs_handler):
    coll_id = uuid.uuid4()
    graph_resp = await graphs_handler.create(collection_id=coll_id,
                                             name="OldName",
                                             description="OldDescription")
    graph_id = graph_resp.id

    # Update name and description
    updated_resp = await graphs_handler.update(collection_id=graph_id,
                                               name="NewName",
                                               description="NewDescription")
    assert updated_resp.name == "NewName"
    assert updated_resp.description == "NewDescription"

    # Retrieve and verify
    overview = await graphs_handler.list_graphs(offset=0,
                                                limit=10,
                                                filter_graph_ids=[graph_id])
    assert overview["total_entries"] == 1
    fetched_graph = overview["results"][0]
    assert fetched_graph.name == "NewName"
    assert fetched_graph.description == "NewDescription"


@pytest.mark.asyncio
async def test_bulk_entities(graphs_handler):
    coll_id = uuid.uuid4()
    graph_resp = await graphs_handler.create(collection_id=coll_id,
                                             name="BulkEntities")
    graph_id = graph_resp.id

    # Add multiple entities
    entities_to_add = [
        {
            "name": "EntityA",
            "category": "CategoryA",
            "description": "DescA"
        },
        {
            "name": "EntityB",
            "category": "CategoryB",
            "description": "DescB"
        },
        {
            "name": "EntityC",
            "category": "CategoryC",
            "description": "DescC"
        },
    ]
    for ent in entities_to_add:
        await graphs_handler.entities.create(
            parent_id=graph_id,
            store_type=StoreType.GRAPHS,
            name=ent["name"],
            category=ent["category"],
            description=ent["description"],
        )

    ents, total = await graphs_handler.get_entities(parent_id=graph_id,
                                                    offset=0,
                                                    limit=10)
    assert total == 3
    fetched_names = [e.name for e in ents]
    for ent in entities_to_add:
        assert ent["name"] in fetched_names


@pytest.mark.asyncio
async def test_relationship_filtering(graphs_handler):
    coll_id = uuid.uuid4()
    graph_resp = await graphs_handler.create(collection_id=coll_id,
                                             name="RelFilteringGraph")
    graph_id = graph_resp.id

    # Add entities
    e1 = await graphs_handler.entities.create(parent_id=graph_id,
                                              store_type=StoreType.GRAPHS,
                                              name="Node1")
    e2 = await graphs_handler.entities.create(parent_id=graph_id,
                                              store_type=StoreType.GRAPHS,
                                              name="Node2")
    e3 = await graphs_handler.entities.create(parent_id=graph_id,
                                              store_type=StoreType.GRAPHS,
                                              name="Node3")

    # Add different relationships
    await graphs_handler.relationships.create(
        subject="Node1",
        subject_id=e1.id,
        predicate="connected_to",
        object="Node2",
        object_id=e2.id,
        parent_id=graph_id,
        store_type=StoreType.GRAPHS,
    )

    await graphs_handler.relationships.create(
        subject="Node2",
        subject_id=e2.id,
        predicate="linked_with",
        object="Node3",
        object_id=e3.id,
        parent_id=graph_id,
        store_type=StoreType.GRAPHS,
    )

    # Get all relationships
    all_rels, all_count = await graphs_handler.get_relationships(
        parent_id=graph_id, offset=0, limit=10)
    assert all_count == 2

    # Filter by relationship_type = ["connected_to"]
    filtered_rels, filt_count = await graphs_handler.get_relationships(
        parent_id=graph_id,
        offset=0,
        limit=10,
        relationship_types=["connected_to"],
    )
    assert filt_count == 1
    assert filtered_rels[0].predicate == "connected_to"


@pytest.mark.asyncio
async def test_delete_all_entities(graphs_handler):
    coll_id = uuid.uuid4()
    graph_resp = await graphs_handler.create(collection_id=coll_id,
                                             name="DeleteAllEntities")
    graph_id = graph_resp.id

    # Add some entities
    await graphs_handler.entities.create(parent_id=graph_id,
                                         store_type=StoreType.GRAPHS,
                                         name="E1")
    await graphs_handler.entities.create(parent_id=graph_id,
                                         store_type=StoreType.GRAPHS,
                                         name="E2")

    # Delete all entities without specifying IDs
    await graphs_handler.entities.delete(parent_id=graph_id,
                                         store_type=StoreType.GRAPHS)
    ents, count = await graphs_handler.get_entities(parent_id=graph_id,
                                                    offset=0,
                                                    limit=10)
    assert count == 0


@pytest.mark.asyncio
async def test_delete_all_relationships(graphs_handler):
    coll_id = uuid.uuid4()
    graph_resp = await graphs_handler.create(collection_id=coll_id,
                                             name="DeleteAllRels")
    graph_id = graph_resp.id

    # Add two entities and a relationship
    e1 = await graphs_handler.entities.create(parent_id=graph_id,
                                              store_type=StoreType.GRAPHS,
                                              name="E1")
    e2 = await graphs_handler.entities.create(parent_id=graph_id,
                                              store_type=StoreType.GRAPHS,
                                              name="E2")
    await graphs_handler.relationships.create(
        subject="E1",
        subject_id=e1.id,
        predicate="connected",
        object="E2",
        object_id=e2.id,
        parent_id=graph_id,
        store_type=StoreType.GRAPHS,
    )

    # Delete all relationships
    await graphs_handler.relationships.delete(parent_id=graph_id,
                                              store_type=StoreType.GRAPHS)
    rels, rel_count = await graphs_handler.get_relationships(
        parent_id=graph_id, offset=0, limit=10)
    assert rel_count == 0


@pytest.mark.asyncio
async def test_error_handling_invalid_graph_id(graphs_handler):
    # Attempt to get a non-existent graph
    non_existent_id = uuid.uuid4()
    overview = await graphs_handler.list_graphs(
        offset=0, limit=10, filter_graph_ids=[non_existent_id])
    assert overview["total_entries"] == 0

    # Attempt to delete a non-existent graph
    with pytest.raises(Exception) as exc_info:
        await graphs_handler.delete(collection_id=non_existent_id)
    # Expect an R2RException or HTTPException (depending on your code)
    # Check the message or type if needed


@pytest.mark.asyncio
async def test_filter_by_collection_ids_in_entities(graphs_handler):
    # 1) Create a row in "graphs" so it can be referenced by entities
    some_parent_id = uuid.uuid4()
    some_collection_id = uuid.uuid4()

    insert_graph_sql = f"""
        INSERT INTO "{graphs_handler.project_name}"."graphs"
        (id, collection_id, name, description, status)
        VALUES ($1, $2, $3, $4, $5)
    """
    await graphs_handler.connection_manager.execute_query(
        insert_graph_sql,
        [
            some_parent_id,
            some_collection_id,
            "MyTestGraph",
            "Graph for unit test",
            "pending",
        ],
    )

    # 2) Insert a row in "graphs_entities" that references parent_id = some_parent_id
    row_id = uuid.uuid4()
    insert_entity_sql = f"""
        INSERT INTO "{graphs_handler.project_name}"."graphs_entities"
        (id, name, parent_id, metadata)
        VALUES ($1, $2, $3, $4)
    """
    await graphs_handler.connection_manager.execute_query(
        insert_entity_sql, [row_id, "TestEntity", some_parent_id, None])

    # 3) Now run your actual test search
    filter_dict = {"collection_ids": {"$in": [str(some_parent_id)]}}
    results = []
    async for row in graphs_handler.graph_search(
            query="anything",
            search_type="entities",
            filters=filter_dict,
            limit=10,
            use_fulltext_search=False,
            use_hybrid_search=False,
            query_embedding=[0, 0, 0, 0],
    ):
        results.append(row)

    assert len(results) == 1, f"Expected 1 matching entity, got {len(results)}"
    assert results[0]["name"] == "TestEntity"

    # 4) Cleanup if needed
    delete_entity_sql = f"""
        DELETE FROM "{graphs_handler.project_name}"."graphs_entities" WHERE id = $1
    """
    await graphs_handler.connection_manager.execute_query(
        delete_entity_sql, [row_id])

    delete_graph_sql = f"""
        DELETE FROM "{graphs_handler.project_name}"."graphs" WHERE id = $1
    """
    await graphs_handler.connection_manager.execute_query(
        delete_graph_sql, [some_parent_id])


# # TODO - Fix code to pass this test.
# # @pytest.mark.asyncio
# # async def test_delete_graph_cascade(graphs_handler):
# #     coll_id = uuid.uuid4()
# #     graph_resp = await graphs_handler.create(collection_id=coll_id, name="CascadeGraph")
# #     graph_id = graph_resp.id

# #     # Add entities/relationships here if you have documents attached
# #     # This test would verify that cascade=True behavior is correct
# #     # For now, just call delete with cascade=True
# #     # Depending on your implementation, you might need documents associated with the collection to test fully.
# #     await graphs_handler.delete(collection_id=coll_id)
# #     overview = await graphs_handler.list_graphs(offset=0, limit=10, filter_graph_ids=[graph_id])
# #     assert overview["total_entries"] == 0

# # tests/test_graph_filters.py
# import pytest
# import uuid
# from core.providers.database.postgres import PostgresGraphsHandler

# @pytest.mark.asyncio
# async def test_filter_by_collection_ids_in_entities(graphs_handler: PostgresGraphsHandler):
#     # Suppose we want to test an entity row whose parent_id=some_uuid
#     some_parent_id = uuid.uuid4()
#     row_id = uuid.uuid4()

#     # Insert an entity row manually for the test
#     insert_sql = f"""
#         INSERT INTO "{graphs_handler.project_name}"."graphs_entities"
#         (id, name, parent_id, metadata)
#         VALUES ($1, $2, $3, $4)
#     """
#     await graphs_handler.connection_manager.execute_query(
#         insert_sql,
#         [row_id, "TestEntity", some_parent_id, None]
#     )

#     # Now do a search with "collection_ids": { "$in": [some_parent_id] }
#     filter_dict = {
#         "collection_ids": { "$in": [str(some_parent_id)] }
#     }

#     # graph_search with search_type='entities' triggers the logic
#     results = []
#     async for row in graphs_handler.graph_search(
#         query="anything",
#         search_type="entities",
#         filters=filter_dict,
#         limit=10,
#         use_fulltext_search=False,
#         use_hybrid_search=False,
#         query_embedding=[0.0,0.0,0.0,0.0],  # placeholder
#     ):
#         results.append(row)

#     assert len(results) == 1, f"Expected 1 matching entity, got {len(results)}"
#     assert results[0]["name"] == "TestEntity"

#     # cleanup
#     delete_sql = f"""
#         DELETE FROM "{graphs_handler.project_name}"."graphs_entities" WHERE id = $1
#     """
#     await graphs_handler.connection_manager.execute_query(delete_sql, [row_id])

import logging

import networkx as nx
from fastapi import FastAPI, HTTPException

# Make sure graspologic and networkx are installed
# Requires that "graspologic[leiden]" extras are installed if needed.
from graspologic.partition import hierarchical_leiden
from pydantic import BaseModel

app = FastAPI()
logger = logging.getLogger("graspologic_service")
logger.setLevel(logging.INFO)

class Relationship(BaseModel):
    id: str
    subject: str
    object: str
    weight: float = 1.0

class LeidenParams(BaseModel):
    # Add any parameters you use in your code. Here are some examples:
    resolution: float = 1.0
    randomness: float = 0.001
    max_cluster_size: int = 1000
    extra_forced_iterations: int = 0
    use_modularity: bool = True
    random_seed: int = 7272
    weight_attribute: str = "weight"
    # Add any other parameters as needed.

class ClusterRequest(BaseModel):
    relationships: list[Relationship]
    leiden_params: LeidenParams

class CommunityAssignment(BaseModel):
    node: str
    cluster: int
    level: int

class ClusterResponse(BaseModel):
    communities: list[CommunityAssignment]


@app.post("/cluster", response_model=ClusterResponse)
def cluster_graph(request: ClusterRequest):
    try:
        # Build graph from relationships
        G = nx.Graph()
        for rel in request.relationships:
            G.add_edge(rel.subject, rel.object, weight=rel.weight, id=rel.id)

        # Compute hierarchical leiden
        # hierarchical_leiden returns a list of objects with node, cluster, level
        # Adjust this code to match exactly how you handle the returned structure in your code.
        logger.info("Starting Leiden clustering")
        communities = hierarchical_leiden(
            G,
            resolution=request.leiden_params.resolution,
            randomness=request.leiden_params.randomness,
            max_cluster_size=request.leiden_params.max_cluster_size,
            extra_forced_iterations=request.leiden_params.extra_forced_iterations,
            use_modularity=request.leiden_params.use_modularity,
            random_seed=request.leiden_params.random_seed,
            weight_attribute=request.leiden_params.weight_attribute,
        )
        logger.info("Leiden clustering complete")

        # Convert communities to response model
        # communities is typically a list of objects with node, cluster, and level attributes.
        # If hierarchical_leiden returns a named tuple or a custom object, adapt accordingly.
        assignments = [
            CommunityAssignment(
                node=c.node, cluster=c.cluster, level=c.level
            )
            for c in communities
        ]

        return ClusterResponse(communities=assignments)
    except Exception as e:
        logger.error(f"Error clustering graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}

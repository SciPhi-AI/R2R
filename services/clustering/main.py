import logging

import networkx as nx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Ensure that graspologic and networkx are installed.
# Requires that "graspologic[leiden]" extras are installed if needed.
from graspologic.partition import hierarchical_leiden

app = FastAPI()
logger = logging.getLogger("graspologic_service")
logger.setLevel(logging.INFO)

# Define data models for relationships and clustering parameters
class Relationship(BaseModel):
    id: str = Field(..., description="Unique identifier for the relationship")
    subject: str = Field(..., description="Subject node of the relationship")
    object: str = Field(..., description="Object node of the relationship")
    weight: float = Field(1.0, description="Weight of the relationship, default is 1.0")

class LeidenParams(BaseModel):
    resolution: float = Field(1.0, description="Resolution parameter for clustering")
    randomness: float = Field(0.001, description="Randomness parameter for clustering")
    max_cluster_size: int = Field(1000, description="Maximum size of clusters")
    extra_forced_iterations: int = Field(0, description="Extra iterations for convergence")
    use_modularity: bool = Field(True, description="Use modularity in clustering")
    random_seed: int = Field(7272, description="Random seed for reproducibility")
    weight_attribute: str = Field("weight", description="Attribute to use as weight")

class ClusterRequest(BaseModel):
    relationships: list[Relationship] = Field(..., description="List of relationships to create the graph")
    leiden_params: LeidenParams = Field(..., description="Parameters for the Leiden algorithm")

class CommunityAssignment(BaseModel):
    node: str = Field(..., description="Node identifier")
    cluster: int = Field(..., description="Cluster identifier")
    level: int = Field(..., description="Hierarchical level of the cluster")

class ClusterResponse(BaseModel):
    communities: list[CommunityAssignment] = Field(..., description="List of community assignments")

# Endpoint for clustering the graph
@app.post("/cluster", response_model=ClusterResponse)
def cluster_graph(request: ClusterRequest):
    logger.info("Received clustering request")
    try:
        # Build graph from relationships
        G = nx.Graph()
        for rel in request.relationships:
            G.add_edge(rel.subject, rel.object, weight=rel.weight, id=rel.id)

        # Compute hierarchical leiden
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
        assignments = [
            CommunityAssignment(
                node=c.node, cluster=c.cluster, level=c.level
            )
            for c in communities
        ]

        return ClusterResponse(communities=assignments)
    except Exception as e:
        logger.error(f"Error clustering graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}

import logging
from typing import List, Optional
import networkx as nx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, confloat, conint
from graspologic.partition import hierarchical_leiden
from contextlib import asynccontextmanager
import uvicorn

# Configure structured logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("graspologic_service")

# --- Data Models (Improved Validation) ---
class Relationship(BaseModel):
    id: str = Field(..., min_length=1, description="Unique relationship identifier")
    subject: str = Field(..., min_length=1, description="Subject node")
    object: str = Field(..., min_length=1, description="Object node")
    weight: confloat(ge=0.0, le=1.0) = Field(1.0, description="Normalized weight [0,1]")

class LeidenParams(BaseModel):
    resolution: confloat(ge=0.0) = Field(1.0, description="Resolution parameter")
    randomness: confloat(ge=0.0) = Field(0.001, description="Randomness parameter")
    max_cluster_size: conint(ge=10) = Field(1000, description="Max cluster size")
    extra_forced_iterations: conint(ge=0) = Field(0, description="Extra iterations")
    use_modularity: bool = Field(True, description="Use modularity optimization")
    random_seed: int = Field(7272, description="Reproducibility seed")
    weight_attribute: str = Field("weight", min_length=1, description="Weight attribute")

class ClusterRequest(BaseModel):
    relationships: List[Relationship] = Field(..., min_items=1, description="Edges list")
    leiden_params: LeidenParams = Field(..., description="Clustering parameters")

class CommunityAssignment(BaseModel):
    node: str = Field(..., description="Node identifier")
    cluster: int = Field(..., description="Cluster ID")
    level: int = Field(..., description="Hierarchy level")

class ClusterResponse(BaseModel):
    communities: List[CommunityAssignment] = Field(..., description="Cluster assignments")

# --- Application Setup with Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events"""
    logger.info("Starting service")
    yield
    logger.info("Shutting down service")

app = FastAPI(
    title="Graph Clustering Service",
    description="API for hierarchical Leiden clustering of graphs",
    lifespan=lifespan
)

# --- Helper Functions (Separation of Concerns) ---
def build_graph(relationships: List[Relationship]) -> nx.Graph:
    """Construct networkx graph from relationships with validation"""
    if not relationships:
        raise ValueError("Empty relationships list")
    
    G = nx.Graph()
    edge_data = [
        (rel.subject, rel.object, {"weight": rel.weight, "id": rel.id})
        for rel in relationships
    ]
    
    try:
        G.add_edges_from(edge_data)
    except nx.NetworkXError as e:
        logger.error(f"Invalid edge data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid graph structure: {str(e)}"
        )
    
    if nx.number_of_selfloops(G) > 0:
        logger.warning("Graph contains self-loops which may affect clustering")
    
    return G

def validate_clustering_parameters(params: LeidenParams) -> None:
    """Validate clustering parameters before execution"""
    if params.resolution == 0 and params.use_modularity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Resolution cannot be zero when using modularity"
        )

# --- Core API Endpoints ---
@app.post(
    "/cluster",
    response_model=ClusterResponse,
    status_code=status.HTTP_200_OK,
    summary="Perform hierarchical Leiden clustering",
    response_description="Cluster assignments for all nodes"
)
async def cluster_graph(request: ClusterRequest) -> ClusterResponse:
    """
    Process graph clustering request with validation and error handling
    
    - **relationships**: List of edges with weights
    - **leiden_params**: Configuration for Leiden algorithm
    """
    logger.info(f"Clustering request received for {len(request.relationships)} edges")
    
    try:
        # Input validation
        validate_clustering_parameters(request.leiden_params)
        G = build_graph(request.relationships)
        
        logger.info(f"Graph built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        
        # Execute clustering
        communities = hierarchical_leiden(
            G,
            **request.leiden_params.dict(exclude={"random_seed"}),  # Safe parameter unpacking
            random_seed=request.leiden_params.random_seed
        )
        
        # Format response
        return ClusterResponse(
            communities=[
                CommunityAssignment(node=c.node, cluster=c.cluster, level=c.level)
                for c in communities
            ]
        )
        
    except nx.NetworkXError as e:
        logger.error(f"NetworkX error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Graph processing error: {str(e)}"
        )
    except Exception as e:
        logger.exception("Unexpected error during clustering")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal processing error"
        )

@app.get("/health", include_in_schema=False)
async def health() -> dict:
    """Service health check endpoint"""
    return {"status": "ok", "service": "graph-clustering"}

# --- Main Execution (Dev Mode) ---
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000, # Do you can change the port to another
        log_config=None  # Use default logging configuration 
    )

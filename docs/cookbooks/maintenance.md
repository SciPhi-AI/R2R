<Warning>
User management features are currently restricted to:
- Self-hosted instances
- Enterprise tier cloud accounts

Contact our sales team for Enterprise pricing and features.
</Warning>

This guide covers essential maintenance tasks for R2R deployments, with a focus on vector index management and system updates.
Understanding when and how to build vector indices, as well as keeping your R2R installation current, is crucial for maintaining
optimal performance at scale.

## PostgreSQL VACUUM
PostgreSQL's VACUUM operation is a critical maintenance process that reclaims storage space occupied by deleted or obsolete data,
updates statistics for the query planner to optimize performance prevents transaction ID wraparound issues, and improves overall
database performance. In normal PostgreSQL operation, when you delete or update rows, the original data is not immediately removed
from disk but marked as obsolete. These obsolete rows (called "dead tuples") accumulate over time, consuming disk space and potentially
slowing down queries.

R2R includes automatic scheduled maintenance to optimize your PostgreSQL database:
```toml
[database.maintenance]
vacuum_schedule = "0 3 * * *"  # Run at 3:00 AM daily
```

Regular vacuum operations keep your database healthy, however it's recommended to schedule these operations during periods of low system usage.

## Vector Indices
### Do You Need Vector Indices?

Vector indices are **not necessary for all deployments**, especially in multi-user applications where each user typically queries their own subset of documents. Consider that:

- In multi-user applications, queries are usually filtered by user_id, drastically reducing the actual number of vectors being searched
- A system with 1 million total vectors but 1000 users might only search through 1000 vectors per query
- Performance impact of not having indices is minimal when searching small per-user document sets

Only consider implementing vector indices when:
- Individual users are searching across hundreds of thousands of documents
- Query latency becomes a bottleneck even with user-specific filtering
- You need to support cross-user search functionality at scale

For development environments or smaller deployments, the overhead of maintaining vector indices often outweighs their benefits.

### Vector Index Management

R2R supports multiple indexing methods, with HNSW (Hierarchical Navigable Small World) being recommended for most use cases:

```python
# Create vector index

create_response = client.indices.create(
    {
        "table_name": "vectors",
        "index_method": "hnsw",
        "index_measure": "cosine_distance",
        "index_arguments": {
            "m": 16,              # Number of connections per element
            "ef_construction": 64 # Size of dynamic candidate list
        },
    }
)
# List existing indices
indices = client.indices.list()

# Delete an index
delete_response = client.indices.delete(
    index_name="ix_vector_cosine_ops_hnsw__20241021211541",
    table_name="vectors",
)
print('delete_response = ', delete_response)
```

#### Important Considerations

1. **Pre-warming Requirement**
   - New indices start "cold" and require warming for optimal performance
   - Initial queries will be slower until the index is loaded into memory
   - Consider implementing explicit pre-warming in production
   - Warming must be repeated after system restarts

2. **Resource Usage**
   - Index creation is CPU and memory intensive
   - Memory usage scales with both dataset size and `m` parameter
   - Consider creating indices during off-peak hours

3. **Performance Tuning**
   - HNSW Parameters:
     - `m`: 16-64 (higher = better quality, more memory)
     - `ef_construction`: 64-100 (higher = better quality, longer build time)
   - Distance Measures:
     - `cosine_distance`: Best for normalized vectors (most common)
     - `l2_distance`: Better for absolute distances
     - `max_inner_product`: Optimized for dot product similarity


## Scaling Strategies

### Horizontal Scaling

For applications serving many users, it is advantageous to scale the number of R2R replicas horizontally. This improves concurrent handling of requests and reliability.

1. **Load Balancing**
   - Deploy multiple R2R replicas behind a load balancer
   - Requests are distributed amongst the replicas
   - Particularly effective since most queries are user-specific

2. **Sharding**
   - Consider sharding by user_id for large multi-user deployments
   - Each shard handles a subset of users
   - Maintains performance even with millions of total documents

#### Horizontal Scaling with Docker Swarm

R2R ships with an example compose file to deploy to [Swarm](https://docs.docker.com/engine/swarm/), an advanced Docker feature that manages a cluster of Docker daemons.

After cloning the R2R repository, we can initialize Swarm and start our stack:
```zsh
# Set the number of R2R replicas to create, defaults to 3 if not set
export R2R_REPLICAS=3

# Initialize swarm (if not already running)
docker swarm init

# Create overlay networks
docker network create --driver overlay r2r_r2r-network

# Source environment file
set -a
source /path/to/.env
set +a

# Deploy stacks
docker stack deploy -c R2R/py/r2r/compose.swarm.yaml r2r

# Commands to bring down stacks (when needed)
docker stack rm r2r
```

### Vertical Scaling

For applications requiring large single-user searches:

1. **Cloud Provider Solutions**
   - AWS RDS supports up to 1 billion vectors per instance
   - Scale up compute and memory resources as needed
   - Example instance types:
     - `db.r6g.16xlarge`: Suitable for up to 100M vectors
     - `db.r6g.metal`: Can handle 1B+ vectors

2. **Memory Optimization**
   ```python
   # Optimize for large vector collections
   client.indices.create(
       table_name="vectors",
       index_method="hnsw",
       index_arguments={
           "m": 32,              # Increased for better performance
           "ef_construction": 80  # Balanced for large collections
       }
   )
   ```

### Multi-User Considerations

1. **Filtering Optimization**
   ```python
   # Efficient per-user search
   response = client.retrieval.search(
       "query",
       search_settings={
           "filters": {
               "user_id": {"$eq": "current_user_id"}
           }
       }
   )
   ```

2. **Collection Management**
   - Group related documents into collections
   - Enable efficient access control
   - Optimize search scope

3. **Resource Allocation**
   - Monitor per-user resource usage
   - Implement usage quotas if needed
   - Consider dedicated instances for power users


### Performance Monitoring

Monitor these metrics to inform scaling decisions:

1. **Query Performance**
   - Average query latency per user
   - Number of vectors searched per query
   - Cache hit rates

2. **System Resources**
   - Memory usage per instance
   - CPU utilization
   - Storage growth rate

3. **User Patterns**
   - Number of active users
   - Query patterns and peak usage times
   - Document count per user

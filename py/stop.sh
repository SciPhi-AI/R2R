#!/bin/bash

# Stop Memgraph
docker stop memgraph
sleep 1
docker rm memgraph

# Stop Neo4j
docker stop neo4j
sleep 1
docker rm neo4j

# Stop PostgreSQL
docker stop postgres
sleep 1
docker rm postgres


# Remove volumes
docker volume rm neo4j_data
docker volume rm neo4j_logs
docker volume rm neo4j_plugins
docker volume rm postgres_data
docker volume rm memgraph_data
docker volume rm memgraph_logs
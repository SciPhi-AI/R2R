# Understanding Internals of R2R Library

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
   - [Prerequisites](#prerequisites)
   - [Docker Installation](#docker-installation)
     - [Install the R2R CLI & Python SDK](#install-the-r2r-cli--python-sdk)
     - [Start R2R with Docker](#start-r2r-with-docker)
   - [Google Cloud Platform Deployment](#google-cloud-platform-deployment)
     - [Overview](#overview)
     - [Creating a Google Compute Engine Instance](#creating-a-google-compute-engine-instance)
     - [Installing Dependencies](#installing-dependencies)
     - [Setting up R2R](#setting-up-r2r)
     - [Configuring Port Forwarding for Local Access](#configuring-port-forwarding-for-local-access)
     - [Exposing Ports for Public Access (Optional)](#exposing-ports-for-public-access-optional)
     - [Conclusion](#conclusion-1)
3. [R2R Application Lifecycle](#r2r-application-lifecycle)
   - [Developer Workflow](#developer-workflow)
   - [User Interaction](#user-interaction)
   - [Hello R2R (Code Example)](#hello-r2r-code-example)
4. [Configuration](#configuration)
   - [Configuration Overview](#configuration-overview)
   - [Server-Side Configuration (`r2r.toml`)](#server-side-configuration-r2rtoml)
     - [Example: `r2r.toml`](#example-r2rtoml)
   - [Runtime Overrides](#runtime-overrides)
   - [Postgres Configuration](#postgres-configuration)
     - [Example Configuration](#example-configuration-1)
     - [Key Features](#key-features)
   - [Embedding Configuration](#embedding-configuration)
     - [Example Configuration](#example-configuration-2)
   - [Auth & Users Configuration](#auth--users-configuration)
     - [Example Configuration](#example-configuration-3)
     - [Key Features](#key-features-1)
   - [Data Ingestion Configuration](#data-ingestion-configuration)
     - [Example Configuration](#example-configuration-4)
   - [Retrieval Configuration](#retrieval-configuration)
     - [Example Configuration](#example-configuration-5)
   - [RAG Configuration](#rag-configuration)
     - [Example Configuration](#example-configuration-6)
   - [Graphs Configuration](#graphs-configuration)
     - [Example Configuration](#example-configuration-7)
   - [Prompts Configuration](#prompts-configuration)
     - [Example Configuration](#example-configuration-8)
5. [Data Ingestion](#data-ingestion)
   - [Introduction](#introduction-1)
   - [Ingestion Modes](#ingestion-modes)
   - [Ingesting Documents](#ingesting-documents)
     - [Example Response](#example-response)
   - [Ingesting Pre-Processed Chunks](#ingesting-pre-processed-chunks)
     - [Example](#example-1)
   - [Deleting Documents and Chunks](#deleting-documents-and-chunks)
     - [Delete a Document](#delete-a-document)
     - [Sample Output](#sample-output)
     - [Key Features of Deletion](#key-features-of-deletion)
   - [Additional Configuration & Concepts](#additional-configuration--concepts)
     - [Light vs. Full Deployments](#light-vs-full-deployments)
     - [Provider Configuration](#provider-configuration)
   - [Conclusion](#conclusion-2)
6. [Contextual Enrichment](#contextual-enrichment)
   - [The Challenge of Context Loss](#the-challenge-of-context-loss)
   - [Introducing Contextual Enrichment](#introducing-contextual-enrichment)
   - [Enabling Enrichment](#enabling-enrichment)
   - [Enrichment Strategies Explained](#enrichment-strategies-explained)
     - [Neighborhood Strategy](#neighborhood-strategy)
     - [Semantic Strategy](#semantic-strategy)
   - [The Enrichment Process](#the-enrichment-process)
   - [Implementation and Results](#implementation-and-results)
     - [Viewing Enriched Results](#viewing-enriched-results)
   - [Metadata and Storage](#metadata-and-storage)
   - [Best Practices](#best-practices-1)
   - [Conclusion](#conclusion-3)
7. [AI Powered Search](#ai-powered-search)
   - [Introduction](#introduction-2)
   - [Understanding Search Modes](#understanding-search-modes)
   - [How R2R Hybrid Search Works](#how-r2r-hybrid-search-works)
   - [Vector Search](#vector-search)
     - [Example](#example-2)
   - [Hybrid Search](#hybrid-search)
     - [Example](#example-3)
   - [Knowledge Graph Search](#knowledge-graph-search)
     - [Example](#example-4)
   - [Reciprocal Rank Fusion (RRF)](#reciprocal-rank-fusion-rrf)
   - [Result Ranking](#result-ranking)
   - [Configuration](#configuration-1)
     - [Choosing a Search Mode](#choosing-a-search-mode)
   - [Best Practices](#best-practices-2)
   - [Conclusion](#conclusion-4)
8. [Retrieval-Augmented Generation (RAG)](#retrieval-augmented-generation-rag)
   - [Basic RAG](#basic-rag)
     - [Example](#example-5)
     - [Sample Output](#sample-output-1)
   - [RAG with Hybrid Search](#rag-w-hybrid-search)
     - [Example](#example-6)
   - [Streaming RAG](#streaming-rag)
     - [Example](#example-7)
   - [Customizing RAG](#customizing-rag)
     - [Example](#example-8)
   - [Advanced RAG Techniques](#advanced-rag-techniques)
     - [HyDE (Hypothetical Document Embeddings)](#hyde-hypothetical-document-embeddings)
       - [Workflow](#workflow)
       - [Python Example](#python-example-1)
       - [Sample Output](#sample-output-2)
     - [RAG-Fusion](#rag-fusion)
       - [Workflow](#workflow-1)
       - [Python Example](#python-example-2)
       - [Sample Output](#sample-output-3)
   - [Combining with Other Settings](#combining-with-other-settings)
     - [Example](#example-9)
   - [Customization and Server-Side Defaults](#customization-and-server-side-defaults)
     - [Example](#example-10)
   - [Conclusion](#conclusion-5)
9. [Knowledge Graphs in R2R](#knowledge-graphs-in-r2r)
   - [Overview](#overview-2)
   - [System Architecture](#system-architecture)
   - [Getting Started](#getting-started)
     - [Document-Level Extraction](#document-level-extraction)
       - [Python Example](#python-example-3)
     - [Creating Collection Graphs](#creating-collection-graphs)
       - [Python Example](#python-example-4)
     - [Managing Collection Graphs](#managing-collection-graphs)
       - [Python Example](#python-example-5)
       - [Example Output](#example-output-4)
   - [Graph-Collection Relationship](#graph-collection-relationship)
   - [Knowledge Graph Workflow](#knowledge-graph-workflow)
     - [Step 1: Extract Document Knowledge](#step-1-extract-document-knowledge)
     - [Step 2: Initialize and Populate Graph](#step-2-initialize-and-populate-graph)
     - [Step 3: View Entities and Relationships](#step-3-view-entities-and-relationships)
     - [Step 4: Build Graph Communities](#step-4-build-graph-communities)
     - [Step 5: KG-Enhanced Search](#step-5-kg-enhanced-search)
     - [Step 6: Reset Graph](#step-6-reset-graph)
   - [Graph Synchronization](#graph-synchronization)
     - [Document Updates](#document-updates)
     - [Cross-Collection Updates](#cross-collection-updates)
   - [Access Control](#access-control)
     - [Python Example](#python-example-6)
   - [Using Knowledge Graphs](#using-knowledge-graphs)
     - [Search Integration](#search-integration)
       - [Curl Example](#curl-example-1)
     - [RAG Integration](#rag-integration)
       - [Python Example](#python-example-7)
   - [Best Practices](#best-practices-3)
     - [Document Management](#document-management)
     - [Collection Management](#collection-management)
     - [Performance Optimization](#performance-optimization)
     - [Access Control](#access-control-1)
   - [Troubleshooting](#troubleshooting-1)
   - [Conclusion](#conclusion-6)
   - [Next Steps](#next-steps-1)
10. [GraphRAG in R2R](#graphrag-in-r2r)
    - [Overview](#overview-1)
    - [Architecture](#architecture)
    - [Understanding Communities](#understanding-communities)
       - [Example Communities](#example-communities)
    - [Implementation Guide](#implementation-guide)
       - [Prerequisites](#prerequisites-1)
         - [Python Example](#python-example-8)
       - [Building Communities](#building-communities)
         - [Python Example](#python-example-9)
         - [Build Process Includes](#build-process-includes)
       - [Using GraphRAG](#using-graphrag)
         - [Python Example](#python-example-10)
    - [Understanding Results](#understanding-results)
       - [Document Chunks](#document-chunks)
       - [Graph Elements](#graph-elements)
       - [Communities](#communities-1)
    - [Scaling GraphRAG](#scaling-graphrag)
       - [Using Orchestration](#using-orchestration)
         - [Access Hatchet UI](#access-hatchet-ui)
         - [Features](#features-1)
         - [Example Diagram](#example-diagram)
    - [Best Practices](#best-practices-4)
       - [Development](#development)
       - [Performance](#performance-1)
       - [Quality](#quality)
    - [Troubleshooting](#troubleshooting-2)
    - [Next Steps](#next-steps-2)
    - [Conclusion](#conclusion-7)
    - [Security Considerations](#security-considerations-1)
11. [Agent](#agent)
    - [Understanding R2R’s RAG Agent](#understanding-r2rs-rag-agent)
       - [Planned Extensions](#planned-extensions)
    - [Configuration](#configuration-2)
       - [Default Configuration](#default-configuration)
       - [Enable Web Search](#enable-web-search)
    - [Using the RAG Agent](#using-the-rag-agent)
       - [Python Example](#python-example-11)
       - [Streaming Responses](#streaming-responses)
    - [Context-Aware Responses](#context-aware-responses)
    - [Working with Files](#working-with-files)
       - [Python Example](#python-example-12)
    - [Advanced Features](#advanced-features)
       - [Combined Search Capabilities](#combined-search-capabilities)
          - [Example](#example-11)
       - [Custom Search Settings](#custom-search-settings)
          - [Example](#example-12)
    - [Best Practices](#best-practices-5)
       - [Conversation Management](#conversation-management)
       - [Search Optimization](#search-optimization)
       - [Response Handling](#response-handling)
    - [Error Handling](#error-handling-1)
       - [Python Example](#python-example-13)
    - [Limitations](#limitations)
    - [Future Developments](#future-developments)
    - [Conclusion](#conclusion-8)
    - [Security Considerations](#security-considerations-2)
12. [Orchestration](#orchestration)
    - [Key Concepts](#key-concepts)
    - [Orchestration in R2R](#orchestration-in-r2r)
       - [Benefits of Orchestration](#benefits-of-orchestration)
       - [Workflows in R2R](#workflows-in-r2r)
          - [List of Workflows](#list-of-workflows)
    - [Orchestration GUI](#orchestration-gui)
       - [Access GUI](#access-gui)
       - [Login](#login-1)
          - [Credentials](#credentials-1)
          - [Logging into Hatchet](#logging-into-hatchet)
       - [Running Tasks](#running-tasks)
          - [Running Tasks Screenshot](#running-tasks-screenshot)
       - [Inspecting a Workflow](#inspecting-a-workflow)
          - [Inspecting a Workflow Screenshot](#inspecting-a-workflow-screenshot)
       - [Long Running Tasks](#long-running-tasks)
          - [Long Running Tasks Screenshot](#long-running-tasks-screenshot)
    - [Coming Soon](#coming-soon)
    - [Best Practices](#best-practices-6)
       - [Development](#development-1)
       - [Performance](#performance-2)
       - [Quality](#quality-1)
    - [Troubleshooting](#troubleshooting-3)
    - [Conclusion](#conclusion-9)
13. [Maintenance & Scaling](#maintenance--scaling)
    - [Vector Indices](#vector-indices)
       - [Do You Need Vector Indices?](#do-you-need-vector-indices)
       - [Vector Index Management](#vector-index-management)
          - [Python Example: Creating and Deleting a Vector Index](#python-example-14)
       - [Important Considerations](#important-considerations-1)
    - [System Updates and Maintenance](#system-updates-and-maintenance)
       - [Version Management](#version-management)
          - [Check Current R2R Version](#check-current-r2r-version)
       - [Update Process](#update-process)
          - [Steps with Commands](#steps-with-commands)
       - [Database Migration Management](#database-migration-management)
          - [Check Current Migration](#check-current-migration)
          - [Apply Migrations](#apply-migrations)
    - [Managing Multiple Environments](#managing-multiple-environments)
       - [Example with Environment Variables](#example-with-environment-variables)
    - [Troubleshooting](#troubleshooting-4)
       - [Steps](#steps-1)
    - [Scaling Strategies](#scaling-strategies)
       - [Horizontal Scaling](#horizontal-scaling)
          - [Load Balancing](#load-balancing)
          - [Sharding](#sharding)
       - [Vertical Scaling](#vertical-scaling)
          - [Cloud Provider Solutions](#cloud-provider-solutions)
          - [Memory Optimization](#memory-optimization)
       - [Multi-User Considerations](#multi-user-considerations)
          - [Filtering Optimization](#filtering-optimization)
          - [Collection Management](#collection-management-1)
          - [Resource Allocation](#resource-allocation)
       - [Performance Monitoring](#performance-monitoring)
          - [Metrics](#metrics)
    - [Performance Considerations](#performance-considerations-1)
       - [Strategies](#strategies)
    - [Additional Resources](#additional-resources-1)
    - [Best Practices](#best-practices-7)
       - [Optimize Indexing](#optimize-indexing)
       - [Monitor Resources](#monitor-resources)
       - [Regular Maintenance](#regular-maintenance)
       - [Plan Scaling Ahead](#plan-scaling-ahead)
    - [Conclusion](#conclusion-10)
14. [Web Development](#web-development)
    - [Hello R2R—JavaScript](#hello-r2rjavascript)
       - [Example: `r2r-js/examples/hello_r2r.js`](#example-r2r-jsexampleshello_r2rjs)
    - [r2r-js Client](#r2r-js-client)
       - [Installing](#installing-1)
       - [Creating the Client](#creating-the-client)
       - [Log into the Server](#log-into-the-server)
       - [Ingesting Files](#ingesting-files-1)
          - [Example and Sample Output](#example-and-sample-output-1)
       - [Performing RAG](#performing-rag-1)
          - [Example and Sample Output](#example-and-sample-output-2)
    - [Connecting to a Web App](#connecting-to-a-web-app)
       - [Setting up an API Route](#setting-up-an-api-route)
       - [Frontend: React Component](#frontend-react-component)
       - [Template Repository](#template-repository)
          - [Usage Steps](#usage-steps-1)
    - [Best Practices](#best-practices-8)
       - [Secure API Routes](#secure-api-routes)
       - [Optimize Frontend Performance](#optimize-frontend-performance)
       - [Handle Errors Gracefully](#handle-errors-gracefully)
       - [Implement Caching](#implement-caching)
       - [Maintain Consistent State](#maintain-consistent-state)
    - [Conclusion](#conclusion-11)
15. [User Management](#user-management)
    - [Introduction](#introduction-3)
    - [Basic Usage](#basic-usage-2)
       - [User Registration and Login](#user-registration-and-login-1)
          - [Python Example](#python-example-15)
       - [Email Verification (Optional)](#email-verification-optional-1)
       - [Token Refresh](#token-refresh-1)
       - [User-Specific Search](#user-specific-search-1)
          - [Curl Example](#curl-example-2)
       - [User Logout](#user-logout-1)
          - [Curl Example](#curl-example-3)
    - [Advanced Authentication Features](#advanced-authentication-features-1)
       - [Password Management](#password-management-1)
          - [Python Example](#python-example-16)
       - [User Profile Management](#user-profile-management-1)
          - [Python Example](#python-example-17)
       - [Account Deletion](#account-deletion-1)
          - [Python Example](#python-example-18)
       - [Logout](#logout-2)
          - [Python Example](#python-example-19)
    - [Superuser Capabilities and Default Admin Creation](#superuser-capabilities-and-default-admin-creation)
       - [Superuser Capabilities](#superuser-capabilities-1)
       - [Default Admin Creation](#default-admin-creation-1)
          - [Configuration](#configuration-3)
       - [Accessing Superuser Features](#accessing-superuser-features-1)
          - [Python Example](#python-example-20)
    - [Security Considerations for Superusers](#security-considerations-for-superusers)
    - [Security Considerations](#security-considerations-3)
    - [Customizing Authentication](#customizing-authentication)
    - [Troubleshooting](#troubleshooting-5)
    - [Conclusion](#conclusion-12)
16. [Collections](#collections)
    - [Introduction](#introduction-4)
    - [Basic Usage](#basic-usage-3)
       - [Collection CRUD Operations](#collection-crud-operations-1)
          - [Creating a Collection](#creating-a-collection)
             - [Python Example](#python-example-21)
          - [Retrieving Collection Details](#retrieving-collection-details)
             - [Python Example](#python-example-22)
          - [Updating a Collection](#updating-a-collection-1)
             - [Python Example](#python-example-23)
          - [Deleting a Collection](#deleting-a-collection-1)
             - [Example](#example-13)
    - [User Management in Collections](#user-management-in-collections)
       - [Adding a User to a Collection](#adding-a-user-to-a-collection)
          - [Example](#example-14)
       - [Removing a User from a Collection](#removing-a-user-from-a-collection)
          - [Example](#example-15)
       - [Listing Users in a Collection](#listing-users-in-a-collection)
          - [Example](#example-16)
       - [Getting Collections for a User](#getting-collections-for-a-user)
          - [Example](#example-17)
    - [Document Management in Collections](#document-management-in-collections)
       - [Assigning a Document to a Collection](#assigning-a-document-to-a-collection)
          - [Example](#example-18)
       - [Removing a Document from a Collection](#removing-a-document-from-a-collection)
          - [Example](#example-19)
       - [Listing Documents in a Collection](#listing-documents-in-a-collection)
          - [Example](#example-20)
       - [Getting Collections for a Document](#getting-collections-for-a-document)
          - [Example](#example-21)
    - [Advanced Collection Management](#advanced-collection-management)
       - [Generating Synthetic Descriptions](#generating-synthetic-descriptions)
          - [Example](#example-22)
       - [Collection Overview](#collection-overview-1)
          - [Example](#example-23)
    - [Pagination and Filtering](#pagination-and-filtering-1)
       - [Examples](#examples-1)
    - [Security Considerations](#security-considerations-4)
    - [Customizing Collection Permissions](#customizing-collection-permissions)
    - [Troubleshooting](#troubleshooting-6)
    - [Conclusion](#conclusion-13)
    - [Next Steps](#next-steps-3)
17. [Telemetry](#telemetry)
    - [Introduction](#introduction-5)
    - [Disabling Telemetry](#disabling-telemetry)
       - [Example](#example-24)
    - [Collected Information](#collected-information)
    - [Telemetry Data Storage](#telemetry-data-storage)
       - [Note](#note)
    - [Why We Collect Telemetry](#why-we-collect-telemetry)
    - [Conclusion](#conclusion-14)
18. [Embedding](#embedding)
    - [Embedding System](#embedding-system)
    - [Embedding Configuration](#embedding-configuration-1)
       - [Example: `r2r.toml`](#example-r2rtoml-1)
    - [Advanced Embedding Features in R2R](#advanced-embedding-features-in-r2r)
       - [Batched Processing](#batched-processing)
          - [Python Example](#python-example-24)
       - [Concurrent Request Management](#concurrent-request-management-1)
    - [Performance Considerations](#performance-considerations-2)
       - [Strategies](#strategies-1)
    - [Supported LiteLLM Providers](#supported-litellm-providers)
       - [Example Configuration](#example-configuration-9)
       - [Supported Models](#supported-models)
    - [Performance Considerations](#performance-considerations-3)
    - [Conclusion](#conclusion-15)
19. [Prompts](#prompts)
    - [Prompt Management in R2R](#prompt-management-in-r2r)
    - [Default Prompts](#default-prompts)
       - [Example: `rag.yaml`](#example-default_ragyaml)
       - [Prompt Files](#prompt-files)
    - [Prompt Provider](#prompt-provider)
    - [Prompt Structure](#prompt-structure)
    - [Managing Prompts](#managing-prompts)
       - [Adding a Prompt](#adding-a-prompt)
          - [Example](#example-25)
       - [Updating a Prompt](#updating-a-prompt)
          - [Example](#example-26)
       - [Retrieving a Prompt](#retrieving-a-prompt)
          - [Example](#example-27)
    - [Security Considerations](#security-considerations-5)
    - [Conclusion](#conclusion-16)
20. [RAG](#rag)
    - [RAG Customization](#rag-customization)
       - [Components](#components)
    - [LLM Provider Configuration](#llm-provider-configuration)
    - [Retrieval Configuration](#retrieval-configuration-1)
    - [Combining LLM and Retrieval Configuration for RAG](#combining-llm-and-retrieval-configuration-for-rag)
       - [Example](#example-28)
    - [RAG Prompt Override](#rag-prompt-override)
       - [Example](#example-29)
    - [Agent-based Interaction](#agent-based-interaction)
       - [Example](#example-30)
    - [Conclusion](#conclusion-17)
21. [Graphs](#graphs)
    - [Graphs](#graphs-1)
    - [Knowledge Graph Operations](#knowledge-graph-operations)
       - [Entity Management](#entity-management-1)
       - [Relationship Management](#relationship-management-1)
       - [Batch Import](#batch-import)
       - [Vector Search](#vector-search-1)
       - [Community Detection](#community-detection)
    - [Customization](#customization-1)
    - [Conclusion](#conclusion-18)
22. [Conclusion](#conclusion-19)

---

## Introduction

**R2R** (Retrieval to Riches) is an engine for building user-facing **Retrieval-Augmented Generation (RAG)** applications. It provides core services through an architecture of providers, services, and an integrated RESTful API. This documentation offers a detailed walkthrough of interacting with R2R, including installation, configuration, and leveraging its advanced features such as data ingestion, search, RAG, and knowledge graphs.

For a deeper dive into the R2R system architecture, refer to the [R2R System Architecture](https://r2r-docs.sciphi.ai/introduction/system).

---

## Installation

Before diving into R2R's features, ensure that you have completed the [installation instructions](https://r2r-docs.sciphi.ai/documentation/installation/overview).

### Prerequisites

- **Python 3.8+**: Ensure Python is installed on your system.
- **Docker**: Required for Docker-based installations. Install Docker from the [official Docker installation guide](https://docs.docker.com/engine/install/).
- **pip**: Python package installer.

### Docker Installation

This installation guide is for the **Full R2R**. For solo developers or teams prototyping, start with [R2R Light](https://r2r-docs.sciphi.ai/documentation/installation/light/local-system).

#### Install the R2R CLI & Python SDK

```bash
pip install r2r
```

> **Note**: A distinct CLI binary for R2R is under active development. For specific needs or feature requests, reach out to the R2R team.

#### Start R2R with Docker

The Full R2R installation uses a custom configuration (`full.toml`). Launch R2R with Docker:

```bash
r2r serve --docker --config-path=full.toml
```

> This command pulls necessary Docker images and starts required containers, including R2R, Hatchet, and Postgres+pgvector. Access the live server at [http://localhost:7272](http://localhost:7272/).

### Google Cloud Platform Deployment

Deploying R2R on Google Cloud Platform (GCP) involves setting up a Compute Engine instance, installing dependencies, and configuring port forwarding.

#### Overview

1. **Creating a Google Compute Engine Instance**
2. **Installing Dependencies**
3. **Setting up R2R**
4. **Configuring Port Forwarding for Local Access**
5. **Exposing Ports for Public Access (Optional)**
6. **Security Considerations**

#### Creating a Google Compute Engine Instance

1. **Log in** to the Google Cloud Console.
2. Navigate to **Compute Engine** > **VM instances**.
3. Click **Create Instance**.
4. Configure the instance:
   - **Name**: Choose a name.
   - **Region and Zone**: Select based on preference.
   - **Machine Configuration**:
     - **Series**: N1
     - **Machine type**: `n1-standard-4` (4 vCPU, 15 GB memory) or higher.
   - **Boot Disk**:
     - **OS**: Ubuntu 22.04 LTS
     - **Size**: 500 GB
   - **Firewall**: Allow HTTP and HTTPS traffic.
5. Click **Create** to launch the instance.

#### Installing Dependencies

SSH into your instance and run the following commands:

```bash
# Update package list and install Python and pip
sudo apt update
sudo apt install python3-pip -y

# Install R2R
pip install r2r

# Add R2R to PATH
echo 'export PATH=$PATH:$HOME/.local/bin' >> ~/.bashrc
source ~/.bashrc

# Install Docker
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg -y
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y

# Add your user to the Docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify Docker installation
docker run hello-world
```

#### Setting up R2R

```bash
# Set required remote providers
export OPENAI_API_KEY=sk-...

# Optional - pass in a custom configuration
r2r serve --docker --full
```

#### Configuring Port Forwarding for Local Access

Use SSH port forwarding to access R2R locally:

```bash
gcloud compute ssh --zone "your-zone" "your-instance-name" -- -L 7273:localhost:7273 -L 7274:localhost:7274
```

#### Exposing Ports for Public Access (Optional)

To make R2R publicly accessible:

1. **Create a Firewall Rule**:
   - Navigate to **VPC network** > **Firewall**.
   - Click **Create Firewall Rule**.
   - **Name**: Allow-R2R
   - **Target tags**: `r2r-server`
   - **Source IP ranges**: `0.0.0.0/0`
   - **Protocols and ports**: `tcp:7272`
2. **Add Network Tag to Instance**:
   - Go to **Compute Engine** > **VM instances**.
   - Click on your instance.
   - Click **Edit**.
   - Under **Network tags**, add `r2r-server`.
   - Click **Save**.
3. **Ensure R2R Listens on All Interfaces**.

After starting R2R, access it at:

```
http://<your-instance-external-ip>:7272
```

> **Security Considerations**:
> - Use HTTPS with a valid SSL certificate.
> - Restrict source IP addresses in firewall rules.
> - Regularly update and patch your system.

#### Conclusion

You have successfully deployed R2R on Google Cloud Platform. The application is accessible locally via SSH tunneling and optionally publicly. Ensure proper security measures are in place before exposing R2R to the internet.

For more details, refer to the [R2R Configuration Documentation](https://r2r-docs.sciphi.ai/documentation/configuration/overview).

---

## R2R Application Lifecycle

R2R's application lifecycle encompasses customization, configuration, deployment, implementation, and interaction. The lifecycle is designed to provide flexibility and scalability for various use cases.

### Developer Workflow

- **Customize**: Developers tailor R2R applications using R2RConfig and the R2R SDK.
- **Configure**: Adjust settings via configuration files (`r2r.toml`) or runtime overrides.
- **Deploy**: Launch R2R using Docker, cloud platforms, or local installations.
- **Implement**: Integrate R2R into applications using provided APIs and SDKs.
- **Interact**: Users engage with the R2R application through interfaces like dashboards or APIs to perform RAG queries or search documents.

### User Interaction

- **Users** interact with the R2R application, typically over an HTTP interface, to run RAG queries or search documents.
- Access the **R2R Dashboard** for managing documents, collections, and performing searches.

### Hello R2R (Code Example)

**Python Example** at `core/examples/hello_r2r.py`:

```python
from r2r import R2RClient

client = R2RClient("http://localhost:7272")

# Create a test document
with open("test.txt", "w") as file:
    file.write("John is a person that works at Google.")

client.documents.create(file_path="test.txt")

# Call RAG directly
rag_response = client.retrieval.rag(
    query="Who is John",
    rag_generation_config={"model": "openai/gpt-4o-mini", "temperature": 0.0},
)

results = rag_response["results"]

print(f"Search Results:\n{results['search_results']}")
print(f"Completion:\n{results['completion']}")
```

**Sample Output:**

```json
{
  "results": {
    "search_results": {
      "chunk_search_results": [
        {
          "chunk_id": "b9f40dbd-2c8e-5c0a-8454-027ac45cb0ed",
          "document_id": "7c319fbe-ca61-5770-bae2-c3d0eaa8f45c",
          "score": 0.6847735847465275,
          "text": "John is a person that works at Google.",
          "metadata": {
            "version": "v0",
            "chunk_order": 0,
            "document_type": "txt",
            "associated_query": "Who is John"
          }
        }
      ],
      "kg_search_results": []
    },
    "completion": {
      "id": "chatcmpl-AV1Sc9DORfHvq7yrmukxfJPDV5dCB",
      "choices": [
        {
          "finish_reason": "stop",
          "index": 0,
          "message": {
            "content": "John is a person that works at Google [1].",
            "role": "assistant"
          }
        }
      ],
      "created": 1731957146,
      "model": "gpt-4o-mini",
      "object": "chat.completion",
      "usage": {
        "completion_tokens": 11,
        "prompt_tokens": 145,
        "total_tokens": 156
      }
    }
  }
}
```

This snippet:
1. Creates a file with simple text.
2. Ingests it to R2R.
3. Runs a **Retrieval-Augmented Generation** query.
4. Prints the context matched (“search_results”) and the generated answer (“completion”).

---

## Configuration

R2R is highly configurable, allowing you to tailor its behavior to your specific needs. Configuration can be done at the server-side using configuration files (`r2r.toml`) or at runtime via API calls.

### Configuration Overview

R2R configurations are divided into two primary levels:
1. **Server-Side Configuration**: Managed through the `r2r.toml` file and environment variables.
2. **Runtime Overrides**: Passed directly in API calls to adjust settings dynamically.

### Server-Side Configuration (`r2r.toml`)

The `r2r.toml` file allows you to define server-side settings that govern the behavior of R2R. Below are the main configuration sections:

#### Example: `r2r.toml`

```toml
[completion]
provider = "litellm"
concurrent_request_limit = 16

[completion.generation_config]
model = "openai/gpt-4o"
temperature = 0.5

[ingestion]
provider = "r2r"
chunking_strategy = "recursive"
chunk_size = 1024
chunk_overlap = 512
excluded_parsers = ["mp4"]

[database]
provider = "postgres"
user = "your_postgres_user"
password = "your_postgres_password"
host = "your_postgres_host"
port = "your_postgres_port"
db_name = "your_database_name"
project_name = "your_project_name"

[embedding]
provider = "litellm"
base_model = "openai/text-embedding-3-small"
base_dimension = 512
batch_size = 512
rerank_model = "BAAI/bge-reranker-v2-m3"
concurrent_request_limit = 256

[auth]
provider = "r2r"
require_authentication = true
require_email_verification = false
default_admin_email = "admin@example.com"
default_admin_password = "change_me_immediately"
access_token_lifetime_in_minutes = 60
refresh_token_lifetime_in_days = 7
secret_key = "your-secret-key"

[ingestion.chunk_enrichment_settings]
enable_chunk_enrichment = true
strategies = ["semantic", "neighborhood"]
forward_chunks = 3
backward_chunks = 3
semantic_neighbors = 10
semantic_similarity_threshold = 0.7
generation_config = { model = "openai/gpt-4o-mini" }

[agent]
rag_agent_static_prompt = "rag_agent"
tools = ["search_file_knowledge", "web_search"]

[database.graph_creation_settings]
entity_types = []
relation_types = []
max_knowledge_triples = 100
fragment_merge_count = 4
generation_config = { model = "openai/gpt-4o-mini" }

[database.graph_enrichment_settings]
max_description_input_length = 65536
max_summary_input_length = 65536
generation_config = { model = "openai/gpt-4o-mini" }
leiden_params = {}

[database.graph_settings]
generation_config = { model = "openai/gpt-4o-mini" }
```

### Runtime Overrides

Runtime overrides allow you to adjust configurations dynamically without modifying the `r2r.toml` file. This is useful for temporary changes or testing different settings on the fly.

**Example: Customizing RAG Query at Runtime**

```python
rag_response = client.retrieval.rag(
    query="Who is Jon Snow?",
    rag_generation_config={
        "model": "anthropic/claude-3-haiku-20240307",
        "temperature": 0.7
    },
    search_settings={
        "use_semantic_search": True,
        "limit": 20,
        "use_hybrid_search": True
    }
)
```

### Postgres Configuration

R2R uses Postgres for relational and vector data storage, leveraging the `pgvector` extension for vector indexing.

#### Example Configuration

```toml
[database]
provider = "postgres"
user = "your_postgres_user"
password = "your_postgres_password"
host = "your_postgres_host"
port = "your_postgres_port"
db_name = "your_database_name"
project_name = "your_project_name"
```

**Key Features:**
- **pgvector**: Enables efficient vector operations.
- **Full-Text Indexing**: Utilizes Postgres’s `ts_rank` for full-text search.
- **JSONB**: Stores flexible metadata.

### Embedding Configuration

R2R uses **LiteLLM** to manage embedding providers, allowing flexibility in selecting different LLM providers.

#### Example Configuration

```toml
[embedding]
provider = "litellm"
base_model = "openai/text-embedding-3-small"
base_dimension = 512
batch_size = 512
rerank_model = "BAAI/bge-reranker-v2-m3"
concurrent_request_limit = 256
```

**Environment Variables:**
- `OPENAI_API_KEY`
- `HUGGINGFACE_API_KEY`
- `ANTHROPIC_API_KEY`
- `COHERE_API_KEY`
- `OLLAMA_API_KEY`
- etc.

**Supported Providers:**
- OpenAI
- Azure
- Anthropic
- Cohere
- Ollama
- HuggingFace
- Bedrock
- Vertex AI
- Voyage AI

### Auth & Users Configuration

R2R’s authentication system supports secure user registration, login, session management, and access control.

#### Example Configuration

```toml
[auth]
provider = "r2r"
require_authentication = true
require_email_verification = false
default_admin_email = "admin@example.com"
default_admin_password = "change_me_immediately"
access_token_lifetime_in_minutes = 60
refresh_token_lifetime_in_days = 7
secret_key = "your-secret-key"
```

**Key Features:**
- **JWT-Based Authentication**: Utilizes access and refresh tokens.
- **Email Verification**: Optional, recommended for production.
- **Superuser Management**: Default admin creation and superuser capabilities.

### Data Ingestion Configuration

Configure how R2R ingests documents, including parsing, chunking, and embedding strategies.

#### Example Configuration

```toml
[ingestion]
provider = "r2r"
chunking_strategy = "recursive"
chunk_size = 1024
chunk_overlap = 512
excluded_parsers = ["mp4"]

[ingestion.chunk_enrichment_settings]
enable_chunk_enrichment = true
strategies = ["semantic", "neighborhood"]
forward_chunks = 3
backward_chunks = 3
semantic_neighbors = 10
semantic_similarity_threshold = 0.7
generation_config = { model = "openai/gpt-4o-mini" }
```

**Modes:**
- `fast`: Speed-oriented ingestion.
- `hi-res`: Comprehensive, high-quality ingestion.
- `custom`: Fine-grained control with a full `ingestion_config` dictionary.

### Retrieval Configuration

Focuses on search settings, combining vector and knowledge-graph search capabilities.

#### Example Configuration

```json
{
  "search_settings": {
    "use_semantic_search": true,
    "limit": 20,
    "use_hybrid_search": true,
    "graph_search_settings": {
      "use_graph_search": true,
      "kg_search_type": "local"
    }
  }
}
```

### RAG Configuration

Customize RAG (Retrieval-Augmented Generation) settings, including the language model's behavior.

#### Example Configuration

```python
rag_generation_config = {
    "model": "anthropic/claude-3-haiku-20240307",
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens_to_sample": 1500,
    "stream": True
}
```

### Graphs Configuration

Defines settings related to knowledge graph creation and enrichment.

#### Example Configuration

```toml
[database.graph_creation_settings]
entity_types = []
relation_types = []
max_knowledge_triples = 100
fragment_merge_count = 4
generation_config = { model = "openai/gpt-4o-mini" }

[database.graph_enrichment_settings]
max_description_input_length = 65536
max_summary_input_length = 65536
generation_config = { model = "openai/gpt-4o-mini" }
leiden_params = {}

[database.graph_settings]
generation_config = { model = "openai/gpt-4o-mini" }
```

### Prompts Configuration

Manages prompt templates used for various tasks within R2R.

#### Example Configuration

Prompts are stored in Postgres and can be managed via the SDK.

**Example: Adding a Prompt**

```python
response = client.prompts.add_prompt(
    name="my_new_prompt",
    template="Hello, {name}! Welcome to {service}.",
    input_types={"name": "str", "service": "str"}
)
```

---

## Data Ingestion

### Introduction

R2R provides a powerful and flexible ingestion pipeline to process and manage various types of documents. It supports a wide range of file formats—text, documents, PDFs, images, audio, and video—and transforms them into searchable, analyzable content. The ingestion process includes parsing, chunking, embedding, and optionally extracting entities and relationships for knowledge graph construction.

This section will guide you through:

- Ingesting files, raw text, or pre-processed chunks
- Choosing an ingestion mode (`fast`, `hi-res`, or `custom`)
- Updating and deleting documents and chunks

For more on configuring ingestion, see the [Ingestion Configuration Overview](https://r2r-docs.sciphi.ai/documentation/configuration/ingestion) and [Parsing & Chunking](https://r2r-docs.sciphi.ai/documentation/configuration/ingestion/parsing_and_chunking).

### Ingestion Modes

R2R offers three primary ingestion modes to tailor the process to your requirements:

| Mode    | Description                                                                                                          |
|---------|----------------------------------------------------------------------------------------------------------------------|
| `fast`  | Speed-oriented ingestion that prioritizes rapid processing with minimal enrichment. Ideal for quickly processing large volumes of documents. |
| `hi-res`| Comprehensive, high-quality ingestion that may leverage multimodal foundation models for parsing complex documents and PDFs. Suitable for documents requiring detailed analysis. |
| `custom`| Advanced mode offering fine-grained control. Users provide a full `ingestion_config` dict or object to specify parser options, chunking strategy, character limits, and more. |

**Example Usage:**

```python
file_path = 'path/to/file.txt'
metadata = {'key1': 'value1'}

# hi-res mode for thorough extraction
ingest_response = client.documents.create(
    file_path=file_path,
    metadata=metadata,
    ingestion_mode="hi-res"
)

# fast mode for quick processing
ingest_response = client.documents.create(
    file_path=file_path,
    ingestion_mode="fast"
)

# custom mode for full control
ingest_response = client.documents.create(
    file_path=file_path,
    ingestion_mode="custom",
    ingestion_config={
        "provider": "unstructured_local",
        "strategy": "auto",
        "chunking_strategy": "by_title",
        "new_after_n_chars": 256,
        "max_characters": 512,
        "combine_under_n_chars": 64,
        "overlap": 100,
    }
)
```

### Ingesting Documents

A `Document` represents ingested content in R2R. When you ingest a file, text, or chunks:

1. **Parsing**: Converts source files into text.
2. **Chunking**: Breaks text into manageable units.
3. **Embedding**: Generates embeddings for semantic search.
4. **Storing**: Persists chunks and embeddings for retrieval.
5. **Knowledge Graph Integration**: Optionally extracts entities and relationships.

In a **full** R2R installation, ingestion is asynchronous. Monitor ingestion status and confirm when documents are ready:

```bash
r2r documents list
```

**Example Response:**

```json
{
  "id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
  "title": "file.txt",
  "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
  "type": "txt",
  "created_at": "2024-09-05T18:20:47.921933Z",
  "updated_at": "2024-09-05T18:20:47.921938Z",
  "ingestion_status": "success",
  "restructuring_status": "pending",
  "version": "v0",
  "summary": "The document contains a ....",
  "collection_ids": [],
  "metadata": {"version": "v0"}
}
```

An `ingestion_status` of `"success"` confirms the document is fully ingested. Also, check the R2R dashboard at [http://localhost:7273](http://localhost:7273/) for ingestion progress and status.

For more details on creating documents, refer to the [Create Document API](https://r2r-docs.sciphi.ai/api-and-sdks/documents/create-document).

### Ingesting Pre-Processed Chunks

If you have pre-processed chunks from your own pipeline, ingest them directly. Useful if content is already divided into logical segments.

**Example:**

```python
chunks = ["This is my first parsed chunk", "This is my second parsed chunk"]

ingest_response = client.documents.create(
    chunks=chunks,
    ingestion_mode="fast"  # use fast for quick chunk ingestion
)

print(ingest_response)
# {'results': [{'message': 'Document created and ingested successfully.', 'document_id': '7a0dad00-b041-544e-8028-bc9631a0a527'}]}
```

For more on ingesting chunks, see the [Create Chunks API](https://r2r-docs.sciphi.ai/api-and-sdks/chunks/create-chunks).

### Deleting Documents and Chunks

To remove documents or chunks, use their respective `delete` methods.

**Delete a Document:**

```bash
curl -X DELETE http://localhost:7272/v3/documents/9fbe403b-c11c-5aae-8ade-ef22980c3ad1 \
  -H "Content-Type: application/json"
```

**Sample Output:**

```json
{"results": {"success": true}}
```

**Key Features of Deletion:**

1. **Deletion by Document ID**: Remove specific documents.
2. **Cascading Deletion**: Deletes associated chunks and metadata.
3. **Deletion by Filter**: Delete documents based on criteria like text match or user ID using `documents/by-filter`.

This mechanism ensures precise control over document management within R2R.

For advanced document management and user authentication details, refer to the [User Auth Cookbook](https://r2r-docs.sciphi.ai/cookbooks/user-auth).

### Additional Configuration & Concepts

- **Light vs. Full Deployments**:
  - **Light**: Uses R2R’s built-in parser and supports synchronous ingestion.
  - **Full**: Orchestrates ingestion tasks asynchronously and integrates with complex providers like `unstructured_local`.

- **Provider Configuration**:
  - Settings in `r2r.toml` or at runtime (`ingestion_config`) adjust parsing and chunking strategies.
    - `fast` and `hi-res` modes influenced by strategies like `"auto"` or `"hi_res"`.
    - `custom` mode allows overriding chunk size, overlap, excluded parsers, and more at runtime.

For detailed configuration options, see:

- [Data Ingestion Configuration](https://r2r-docs.sciphi.ai/documentation/configuration/ingestion)
- [Parsing & Chunking Configuration](https://r2r-docs.sciphi.ai/documentation/configuration/ingestion/parsing_and_chunking)

### Conclusion

R2R’s ingestion pipeline is flexible and efficient, allowing you to tailor ingestion to your needs:

- Use `fast` for quick processing.
- Use `hi-res` for high-quality, multimodal analysis.
- Use `custom` for advanced, granular control.

Easily ingest documents or pre-processed chunks, update their content, and delete them when no longer needed. Combined with powerful retrieval and knowledge graph capabilities, R2R enables seamless integration of advanced document management into your applications.

---

## Contextual Enrichment

Enhance your RAG system chunks with rich contextual information to address the challenge of context loss in individual chunks.

### The Challenge of Context Loss

During ingestion, large documents are broken down into smaller chunks for efficient processing. However, isolated chunks may lack broader context, leading to incomplete or unclear responses.

**Example:**

Using Lyft’s 2021 annual report:

- **Original Chunk:**
  ```
  storing unrented and returned vehicles. These impacts to the demand for and operations of the different rental programs have and may continue to adversely affect our business, financial condition and results of operation.
  ```

- **Questions Raised:**
  - What specific impacts are being discussed?
  - Which rental programs are affected?
  - What’s the broader context of these business challenges?

### Introducing Contextual Enrichment

Contextual enrichment enhances chunks with relevant information from surrounding or semantically related content, giving each chunk a “memory” of related information.

### Enabling Enrichment

Configure your `r2r.toml` file with the following settings:

```toml
[ingestion.chunk_enrichment_settings]
enable_chunk_enrichment = true  # disabled by default
strategies = ["semantic", "neighborhood"]
forward_chunks = 3  # Look ahead 3 chunks
backward_chunks = 3  # Look behind 3 chunks
semantic_neighbors = 10  # Find 10 semantically similar chunks
semantic_similarity_threshold = 0.7  # Minimum similarity score
generation_config = { model = "openai/gpt-4o-mini" }
```

### Enrichment Strategies Explained

R2R implements two strategies for chunk enrichment:

#### 1. Neighborhood Strategy

- **Forward Looking**: Captures upcoming context (default: 3 chunks).
- **Backward Looking**: Incorporates previous context (default: 3 chunks).
- **Use Case**: Effective for narrative documents with linear context flow.

#### 2. Semantic Strategy

- **Vector Similarity**: Identifies chunks with similar meanings regardless of location.
- **Configurable Neighbors**: Customizable number of similar chunks.
- **Similarity Threshold**: Ensures relevance by setting minimum similarity scores.
- **Use Case**: Ideal for documents with recurring themes across sections.

### The Enrichment Process

R2R uses a prompt to guide the Language Model (LLM) during enrichment:

**Task:**

Enrich and refine the given chunk of text using information from the provided context chunks. The goal is to make the chunk more precise and self-contained.

**Context Chunks:**

```
{context_chunks}
```

**Chunk to Enrich:**

```
{chunk}
```

**Instructions:**

1. Rewrite the chunk in third person.
2. Replace all common nouns with appropriate proper nouns.
3. Use information from the context chunks to enhance clarity.
4. Ensure the enriched chunk remains independent and self-contained.
5. Maintain original scope without bleeding information.
6. Focus on precision and informativeness.
7. Preserve original meaning while improving clarity.
8. Output only the enriched chunk.

**Enriched Chunk:**

```
[Enriched Chunk Output]
```

### Implementation and Results

To process documents with enrichment:

```bash
r2r documents create --file_path path/to/lyft_2021.pdf
```

#### Viewing Enriched Results

Access enriched chunks through the API:

```bash
curl -X GET http://localhost:7272/v3/document/{document_id}/chunks
```

**Before Enrichment:**

```
storing unrented and returned vehicles. These impacts to the demand for and operations of the different rental programs have and may continue to adversely affect our business, financial condition and results of operation.
```

**After Enrichment:**

```
The impacts of the COVID-19 pandemic on the demand for and operations of the various vehicle rental programs, including Lyft Rentals and the Express Drive program, have resulted in challenges regarding the storage of unrented and returned vehicles. These adverse conditions are anticipated to continue affecting Lyft's overall business performance, financial condition, and operational results.
```

**Enhancements in Enriched Chunk:**

- Specifies the cause (COVID-19 pandemic).
- Names specific programs (Lyft Rentals, Express Drive).
- Provides clearer context about the business impact.
- Maintains professional, third-person tone.

### Metadata and Storage

R2R maintains both enriched and original versions:

```json
{
  "results": [
    {
      "text": "enriched_version",
      "metadata": {
        "original_text": "original_version",
        "chunk_enrichment_status": "success"
        // ... additional metadata ...
      }
    }
  ]
}
```

This dual storage ensures transparency and allows for version comparison when needed.

### Best Practices

1. **Tune Your Parameters**: Adjust `forward_chunks`, `backward_chunks`, and `semantic_neighbors` based on document structure.
2. **Monitor Enrichment Quality**: Regularly review enriched chunks to ensure accuracy.
3. **Consider Document Type**: Different documents may benefit from different enrichment strategies.
4. **Balance Context Size**: More context isn’t always better; find the optimal size for your use case.

---

## AI Powered Search

R2R supports advanced search capabilities, including vector search, hybrid search (keyword + vector), and knowledge graph-enhanced search. This section covers the understanding of search modes, configuration, and best practices.

### Introduction

R2R’s hybrid search blends keyword-based full-text search with semantic vector search, delivering results that are both contextually relevant and precise. This unified approach excels at handling complex queries where both exact terms and overall meaning matter.

### Understanding Search Modes

R2R supports multiple search modes to simplify or customize your search configuration:

| Mode      | Description                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| `basic`   | Primarily semantic search. Suitable for straightforward scenarios where semantic understanding is key.              |
| `advanced`| Combines semantic and full-text search by default, enabling hybrid search with well-tuned default parameters.         |
| `custom`  | Allows full control over search settings, including toggling semantic and full-text search independently.            |

- **`advanced` Mode**: Automatically configures hybrid search with balanced parameters.
- **`custom` Mode**: Manually set `use_hybrid_search=True` or enable both `use_semantic_search` and `use_fulltext_search` for a hybrid setup.

### How R2R Hybrid Search Works

1. **Full-Text Search**:
   - Utilizes Postgres’s `ts_rank_cd` and `websearch_to_tsquery` for exact term matches.

2. **Semantic Search**:
   - Employs vector embeddings to locate contextually related documents, even without exact keyword matches.

3. **Reciprocal Rank Fusion (RRF)**:
   - Merges results from both full-text and semantic searches using a formula to ensure balanced ranking.

4. **Result Ranking**:
   - Orders results based on the combined RRF score, providing balanced and meaningful search outcomes.

### Vector Search

Vector search leverages semantic embeddings to find documents that are contextually similar to the query, even if they don't contain the exact keywords.

**Example:**

```bash
curl -X POST http://localhost:7272/v3/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What was Uber'\''s profit in 2020?",
    "search_settings": {
      "use_semantic_search": true,
      "search_settings": {
        "chunk_settings": {
          "index_measure": "l2_distance",
          "limit": 10
        }
      }
    }
  }'
```

**Sample Output:**

Includes chunk-based results with text, metadata, etc.

### Hybrid Search

Hybrid search combines keyword-based full-text search with semantic vector search to deliver more relevant results.

**Example:**

```bash
curl -X POST http://localhost:7272/v3/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What was Uber'\''s profit in 2020?",
    "search_settings": {
      "use_hybrid_search": true,
      "hybrid_settings": {
        "full_text_weight": 1.0,
        "semantic_weight": 5.0,
        "full_text_limit": 200,
        "rrf_k": 50
      },
      "filters": {
        "title": {
          "$in": ["lyft_2021.pdf", "uber_2021.pdf"]
        }
      },
      "limit": 10,
      "chunk_settings": {
        "index_measure": "l2_distance",
        "probes": 25,
        "ef_search": 100
      }
    }
  }'
```

### Knowledge Graph Search

Knowledge graph search enhances retrieval by leveraging relationships and entities extracted from documents.

**Example:**

```bash
curl -X POST http://localhost:7272/v3/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Who was Aristotle?",
    "graph_search_settings": {
      "use_graph_search": true,
      "kg_search_type": "local"
    }
  }'
```

### Reciprocal Rank Fusion (RRF)

RRF is a technique used to merge results from different search strategies, ensuring balanced and relevant ranking.

### Result Ranking

Results are ranked based on the combined RRF score, providing a balanced mix of exact term matches and semantic relevance.

### Configuration

**Choosing a Search Mode:**

| Mode      | Description                                               | Example Configuration                                                 |
|-----------|-----------------------------------------------------------|-----------------------------------------------------------------------|
| `basic`   | Semantic-only search                                      | `search_mode = "basic"`                                                |
| `advanced`| Hybrid search with well-tuned defaults                    | `search_mode = "advanced"`                                             |
| `custom`  | Manually configure hybrid search settings                 | ```python<br>search_mode = "custom"<br>search_settings = {<br> "use_semantic_search": True,<br> "use_fulltext_search": True,<br> "hybrid_settings": {<br> "full_text_weight": 1.0,<br> "semantic_weight": 5.0,<br> "full_text_limit": 200,<br> "rrf_k": 50<br> }<br> }``` |

For detailed runtime configuration and combining `search_mode` with custom `search_settings`, refer to the [Search API Documentation](https://r2r-docs.sciphi.ai/api-and-sdks/retrieval/search-app).

### Best Practices

1. **Optimize Database and Embeddings**:
   - Ensure Postgres indexing and vector store configurations are optimized for performance.

2. **Adjust Weights and Limits**:
   - Tweak `full_text_weight`, `semantic_weight`, and `rrf_k` values in `custom` mode.

3. **Regular Updates**:
   - Keep embeddings and indexes up-to-date to maintain search quality.

4. **Choose Appropriate Embeddings**:
   - Select an embedding model that fits your content domain for the best semantic results.

### Conclusion

R2R’s hybrid search delivers robust, context-aware retrieval by merging semantic and keyword-driven approaches. Whether you choose `basic` mode for simplicity, `advanced` mode for out-of-the-box hybrid search, or `custom` mode for granular control, R2R ensures you can tailor the search experience to your unique needs.

---

## Retrieval-Augmented Generation (RAG)

R2R couples its powerful retrieval capabilities with large language models (LLMs) to provide comprehensive Q&A and content generation based on ingested documents.

### Basic RAG

**Example:**

```bash
curl -X POST http://localhost:7272/v3/retrieval/rag \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What was Uber'\''s profit in 2020?"
  }'
```

**Sample Output:**

```json
{
  "results": [
    "ChatCompletion(...)"
  ]
}
```

### RAG with Hybrid Search

Combine hybrid search logic with RAG for enhanced results.

**Example:**

```bash
curl -X POST http://localhost:7272/v3/retrieval/rag \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Who is Jon Snow?",
    "search_settings": {
      "use_hybrid_search": true,
      "limit": 10
    }
  }'
```

### Streaming RAG

Stream RAG responses in real-time, providing partial results as they are generated.

**Example:**

```bash
r2r retrieval rag --query="who was aristotle" --use-hybrid-search=True --stream
```

It streams real-time tokens.

### Customizing RAG

You can control various aspects of RAG, including search settings, generation config, and LLM providers.

**Example:**

```bash
curl -X POST http://localhost:7272/v3/retrieval/rag \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Who is Jon Snow?",
    "rag_generation_config": {
      "model": "claude-3-haiku-20240307",
      "temperature": 0.7
    }
  }'
```

### Advanced RAG Techniques

R2R supports advanced RAG techniques, currently in beta, including HyDE and RAG-Fusion.

#### HyDE (Hypothetical Document Embeddings)

HyDE enhances retrieval by generating and embedding hypothetical documents based on the query.

**Workflow:**

1. **Query Expansion**: Generates hypothetical answers or documents using an LLM.
2. **Enhanced Embedding**: Embeds these hypothetical documents to create a richer semantic search space.
3. **Similarity Search**: Uses the embeddings to find the most relevant actual documents in the database.
4. **Informed Generation**: Combines retrieved documents and the original query to generate the final response.

**Python Example:**

```python
from r2r import R2RClient

client = R2RClient()

hyde_response = client.retrieval.rag(
    "What are the main themes in Shakespeare's plays?",
    search_settings={
        "search_strategy": "hyde",
        "limit": 10
    }
)

print('hyde_response = ', hyde_response)
```

**Sample Output:**

```json
{
  "results": {
    "completion": "...",
    "search_results": {
      "chunk_search_results": [
        {
          "score": 0.7715058326721191,
          "text": "## Paragraph from the Chapter...",
          "metadata": {
            "associated_query": "The fundamental theorem of calculus..."
          }
        }
      ]
    }
  }
}
```

#### RAG-Fusion

RAG-Fusion improves retrieval quality by combining results from multiple search iterations.

**Workflow:**

1. **Query Expansion**: Generates multiple related queries.
2. **Multiple Retrievals**: Each query retrieves relevant documents.
3. **Reciprocal Rank Fusion (RRF)**: Re-ranks documents using RRF.
4. **Enhanced RAG**: Uses re-ranked documents to generate the final response.

**Python Example:**

```python
from r2r import R2RClient

client = R2RClient()

rag_fusion_response = client.retrieval.rag(
    "Explain the theory of relativity",
    search_settings={
        "search_strategy": "rag_fusion",
        "limit": 20
    }
)

print('rag_fusion_response = ', rag_fusion_response)
```

**Sample Output:**

```json
{
  "results": {
    "completion": "...",
    "search_results": {
      "chunk_search_results": [
        {
          "score": 0.04767399003253049,
          "text": "18. The theory of relativity, proposed by Albert Einstein in 1905...",
          "metadata": {
            "associated_queries": ["What is the theory of relativity?", ...]
          }
        }
      ]
    }
  }
}
```

### Combining with Other Settings

You can combine advanced RAG techniques with other search and RAG settings for enhanced performance.

**Example:**

```python
custom_rag_response = client.retrieval.rag(
    "Describe the impact of climate change on biodiversity",
    search_settings={
        "search_strategy": "hyde",
        "limit": 15,
        "use_hybrid_search": True
    },
    rag_generation_config={
        "model": "anthropic/claude-3-opus-20240229",
        "temperature": 0.7
    }
)
```

### Customization and Server-Side Defaults

While R2R allows runtime configuration of advanced techniques, server-side defaults can also be modified for consistent behavior. This includes updating prompts used for techniques like HyDE and RAG-Fusion.

- **General Configuration**: Refer to the [R2R Configuration Documentation](https://r2r-docs.sciphi.ai/documentation/configuration/overview).
- **Customizing Prompts**: Learn about customizing prompts [here](https://r2r-docs.sciphi.ai/documentation/configuration/retrieval/prompts).

**Example:**

```toml
[rag_generation_config]
model = "anthropic/claude-3-opus-20240229"
temperature = 0.7
```

### Conclusion

By leveraging advanced RAG techniques and customizing their underlying prompts, you can significantly enhance the quality and relevance of your retrieval and generation processes. Experiment with different strategies, settings, and prompt variations to find the optimal configuration for your specific use case. R2R's flexibility allows iterative improvement and adaptation to changing requirements.

---

## Knowledge Graphs in R2R

Knowledge graphs enhance search accuracy and context understanding by extracting and connecting information from your documents. R2R uses a two-level architecture:

1. **Document Level**: Entities and relationships are first extracted and stored with their source documents.
2. **Collection Level**: Collections act as soft containers that include documents and maintain corresponding graphs.

### Overview

R2R supports robust knowledge graph functionality to enhance document understanding and retrieval. By extracting entities and relationships from documents and organizing them into collections, R2R enables advanced graph-based analysis and search capabilities.

**Note**: Refer to the [Knowledge Graph Cookbook](https://r2r-docs.sciphi.ai/cookbooks/knowledge-graphs) and [GraphRAG Cookbook](https://r2r-docs.sciphi.ai/cookbooks/graphrag) for detailed guides.

### System Architecture

```
Collection (Soft Container)
    |
Documents
    |--> Extracted Entities & Relationships
Knowledge Graph
    |
Permissions
    |
User
```

**Collections Provide:**

- Flexible document organization (documents can belong to multiple collections)
- Access control and sharing
- Graph synchronization and updates

### Getting Started

#### Document-Level Extraction

Extract entities and relationships from documents.

**Python Example:**

```python
from r2r import R2RClient

client = R2RClient("http://localhost:7272")

# Extract entities and relationships
document_id = "your-document-id"
extract_response = client.documents.extract(document_id)

# View extracted knowledge
entities = client.documents.list_entities(document_id)
relationships = client.documents.list_relationships(document_id)
```

#### Creating Collection Graphs

Each collection maintains its own graph.

**Python Example:**

```python
# Create collection
collection = client.collections.create(
    "Research Papers",
    "ML research papers with knowledge graph analysis"
)
collection_id = collection["results"]["id"]

# Add documents to collection
client.collections.add_document(collection_id, document_id)

# Generate description for the collection
client.collections.update(
    collection_id,
    generate_description=True
)

# Pull document knowledge into collection graph
client.graphs.pull(collection_id)
```

#### Managing Collection Graphs

**Python Example:**

```python
# List entities in collection graph
entities = client.graphs.list_entities(collection_id)

# List relationships in collection graph
relationships = client.graphs.list_relationships(collection_id)
```

**Example Output:**

- **Entity:**
  ```json
  {
    "name": "DEEP_LEARNING",
    "description": "A subset of machine learning using neural networks",
    "category": "CONCEPT",
    "id": "ce46e955-ed77-4c17-8169-e878baf3fbb9"
  }
  ```
- **Relationship:**
  ```json
  {
    "subject": "DEEP_LEARNING",
    "predicate": "IS_SUBSET_OF",
    "object": "MACHINE_LEARNING",
    "description": "Deep learning is a specialized branch of machine learning"
  }
  ```

### Graph-Collection Relationship

- Each collection has an associated graph.
- The `pull` operation syncs the graph with the collection.
- Allows experimental modifications without affecting the base data.

### Knowledge Graph Workflow

1. **Extract Document Knowledge**:
   ```bash
   curl -X POST http://localhost:7272/v3/documents/${document_id}/extract
   ```
2. **Initialize and Populate Graph**:
   ```bash
   curl -X POST http://localhost:7272/v3/graphs/${collection_id}/pull
   ```
3. **View Entities and Relationships**:
   ```bash
   curl -X GET http://localhost:7272/v3/graphs/${collection_id}/entities
   curl -X GET http://localhost:7272/v3/graphs/${collection_id}/relationships
   ```
4. **Build Graph Communities**:
   ```bash
   curl -X POST http://localhost:7272/v3/graphs/${collection_id}/communities/build
   curl -X GET http://localhost:7272/v3/graphs/${collection_id}/communities
   ```
5. **KG-Enhanced Search**:
   ```bash
   curl -X POST http://localhost:7272/v3/retrieval/search \
    -H "Content-Type: application/json" \
    -d '{
      "query": "who was aristotle?",
      "graph_search_settings": {
        "use_graph_search": true,
        "kg_search_type": "local"
      }
    }'
   ```
6. **Reset Graph**:
   ```bash
   curl -X POST http://localhost:7272/v3/graphs/${collection_id}/reset
   ```

### Graph Synchronization

#### Document Updates

When documents change:

```python
# Update document
client.documents.update(document_id, new_content)

# Re-extract knowledge
client.documents.extract(document_id)

# Update collection graphs
client.graphs.pull(collection_id)
```

#### Cross-Collection Updates

Documents can belong to multiple collections:

```python
# Add document to multiple collections
client.collections.add_document(document_id, collection_id_1)
client.collections.add_document(document_id, collection_id_2)

# Update all relevant graphs
client.graphs.pull(collection_id_1)
client.graphs.pull(collection_id_2)
```

### Access Control

Manage access to graphs through collection permissions.

**Python Example:**

```python
# Give user access to collection and its graph
client.collections.add_user(user_id, collection_id)

# Remove access
client.collections.remove_user(user_id, collection_id)

# List users with access
users = client.collections.list_users(collection_id)
```

### Using Knowledge Graphs

#### Search Integration

Graphs automatically enhance search for collection members.

**Curl Example:**

```bash
curl -X POST http://localhost:7272/v3/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is deep learning?",
    "graph_search_settings": {
      "use_graph_search": true,
      "kg_search_type": "local"
    }
  }'
```

#### RAG Integration

Knowledge graphs enhance RAG responses.

**Python Example:**

```python
response = client.retrieval.rag(
    "Explain deep learning's relationship to ML",
    graph_search_settings={
        "enabled": True
    }
)
```

### Best Practices

#### Document Management

- Extract knowledge after document updates.
- Monitor extraction quality at the document level.
- Extractions stay with source documents.
- Consider document size and complexity when extracting.

#### Collection Management

- Keep collections focused on related documents.
- Use meaningful collection names and descriptions.
- Documents can belong to multiple collections.
- Pull changes when document extractions update.

#### Performance Optimization

- Start with small document sets to test extraction.
- Use collection-level operations for bulk processing.
- Monitor graph size and complexity.
- Consider using [orchestration](https://r2r-docs.sciphi.ai/cookbooks/orchestration) for large collections.

#### Access Control

- Plan collection structure around sharing needs.
- Review access permissions regularly.
- Document collection purposes and access patterns.
- Use collection metadata to track graph usage.

### Troubleshooting

**Common Issues and Solutions:**

1. **Missing Extractions**:
   - Verify document extraction completed successfully.
   - Check document format and content.
   - Ensure collection graph was pulled after extraction.

2. **Graph Sync Issues**:
   - Confirm all documents are properly extracted.
   - Check collection membership.
   - Try resetting and re-pulling collection graph.

3. **Performance Problems**:
   - Monitor collection size.
   - Check extraction batch sizes.
   - Consider splitting large collections.
   - Use pagination for large result sets.

### Conclusion

R2R’s knowledge graph capabilities enhance document understanding and improve search and RAG operations by providing structured and interconnected information from your documents.

### Next Steps

- Explore [GraphRAG](https://r2r-docs.sciphi.ai/cookbooks/graphrag) for advanced features.
- Learn about [hybrid search](https://r2r-docs.sciphi.ai/cookbooks/hybrid-search) integration.
- Discover more about [collections](https://r2r-docs.sciphi.ai/cookbooks/collections).
- Set up [orchestration](https://r2r-docs.sciphi.ai/cookbooks/orchestration) for large-scale processing.

---

## GraphRAG in R2R

GraphRAG extends traditional RAG by leveraging community detection and summarization within knowledge graphs. This approach provides richer context and more comprehensive answers by understanding how information is clustered and connected across your documents.

### Overview

GraphRAG enhances RAG by integrating community detection and summarization within knowledge graphs, enabling more contextual and clustered information retrieval.

#### Architecture

```
User Query
    |
QueryTransformPipe
    |
MultiSearchPipe
    |
VectorSearchPipe
    |
RAG-Fusion Process
    |
Reciprocal Rank Fusion
    |
RAG Generation
    |
Knowledge Graph DB
```

### Understanding Communities

**Communities** are automatically detected clusters of related information in your knowledge graph, providing:

1. **Higher-Level Understanding**: Grasp document themes.
2. **Summarized Context**: Concise summaries for related concepts.
3. **Improved Retrieval**: Topic-based organization enhances search relevance.

**Example Communities:**

| Domain           | Community Examples                                     |
|------------------|--------------------------------------------------------|
| Scientific Papers| Research methods, theories, research teams             |
| News Articles    | World events, industry sectors, key figures           |
| Technical Docs   | System components, APIs, user workflows                |
| Legal Documents  | Case types, jurisdictions, legal principles            |

### Implementation Guide

#### Prerequisites

Ensure you have:

- Documents ingested into a collection.
- Entities and relationships extracted.
- Graph synchronized.

**Python Example:**

```python
from r2r import R2RClient

client = R2RClient("http://localhost:7272")

# Setup collection and extract knowledge
collection_id = "your-collection-id"
client.collections.extract(collection_id)
client.graphs.pull(collection_id)
```

#### Building Communities

**Python Example:**

```python
# Generate a description for the collection
client.collections.update(
    collection_id,
    generate_description=True
)

# Build communities for your collection's graph
build_response = client.graphs.build(collection_id)
```

**Build Process Includes:**

1. Analyzes graph connectivity.
2. Identifies dense subgraphs.
3. Generates community summaries.
4. Creates findings and insights.

#### Using GraphRAG

Once communities are built, they integrate into search and RAG.

**Python Example:**

```python
# Search across all levels
search_response = client.retrieval.search(
    "What are the key theories?",
    search_settings={
        "graph_settings": {
            "enabled": True,
        }
    }
)

# RAG with community context
rag_response = client.retrieval.rag(
    "Explain the relationships between theories",
    graph_search_settings={
        "enabled": True
    }
)
```

### Understanding Results

GraphRAG returns three types of results:

#### 1. Document Chunks

```json
{
  "chunk_id": "70c96e8f-e5d3-5912-b79b-13c5793f17b5",
  "text": "Example document text...",
  "score": 0.78,
  "metadata": {
    "document_type": "txt",
    "associated_query": "query text"
  }
}
```

#### 2. Graph Elements

```json
{
  "content": {
    "name": "CONCEPT_NAME",
    "description": "Entity description..."
  },
  "result_type": "entity",
  "score": 0.74
}
```

#### 3. Communities

```json
{
  "content": {
    "name": "Community Name",
    "summary": "High-level community description...",
    "findings": [
      "Key insight 1 with supporting evidence...",
      "Key insight 2 with supporting evidence..."
    ],
    "rating": 9.0,
    "rating_explanation": "Explanation of importance..."
  },
  "result_type": "community",
  "score": 0.57
}
```

### Scaling GraphRAG

#### Using Orchestration

For large collections, utilize R2R’s orchestration capabilities via Hatchet UI.

**Access Hatchet UI:**

- **URL**: [http://localhost:7274](http://localhost:7274)
- **Login Credentials**:
  - **Email**: admin@example.com
  - **Password**: Admin123!!

**Features:**

- Monitor document extraction progress.
- Track community detection status.
- Handle errors and workflow retries.

**Example Diagram:**

![Monitoring GraphRAG workflows in Hatchet](https://files.buildwithfern.com/https://sciphi.docs.buildwithfern.com/2024-12-13T18:29:49.890Z/images/hatchet_workflow.png)

### Best Practices

1. **Development**:
   - Start with small document sets.
   - Test with single documents first.
   - Scale gradually to larger collections.

2. **Performance**:
   - Monitor community size and complexity.
   - Use pagination for large result sets.
   - Consider breaking very large collections.

3. **Quality**:
   - Review community summaries.
   - Validate findings accuracy.
   - Monitor retrieval relevance.

### Troubleshooting

**Common Issues and Solutions:**

1. **Poor Community Quality**:
   - Check entity extraction quality.
   - Review relationship connections.
   - Adjust collection scope.

2. **Performance Issues**:
   - Monitor graph size.
   - Check community complexity.
   - Use orchestration for large graphs.

3. **Integration Problems**:
   - Verify extraction completion.
   - Check collection synchronization.
   - Review API configurations.

### Next Steps

- Explore [hybrid search](https://r2r-docs.sciphi.ai/cookbooks/hybrid-search) integration.
- Learn about [collection management](https://r2r-docs.sciphi.ai/cookbooks/collections).
- Discover more about [observability](https://r2r-docs.sciphi.ai/cookbooks/observability).

### Conclusion

GraphRAG enhances R2R’s RAG capabilities by integrating community detection and summarization within knowledge graphs. This results in richer, more contextualized responses, improving the overall quality of information retrieval and generation.

---

## Agent

R2R’s agentic capabilities allow for intelligent systems that formulate their own questions, search for information, and provide informed responses based on retrieved context. Agents can be customized on the fly to suit various tasks.

**Note**: Agents in R2R are in beta. Feedback is encouraged at [founders@sciphi.ai](mailto:founders@sciphi.ai).

### Understanding R2R’s RAG Agent

R2R’s RAG agent combines large language models with search capabilities over ingested documents to provide powerful, context-aware responses. When initializing an R2R application, it automatically creates a RAG assistant ready for use.

**Planned Extensions:**

- Multiple tool support (e.g., code interpreter, file search)
- Persistent conversation threads
- Complete end-to-end observability of agent interactions
- Local RAG capabilities for offline AI agents

### Configuration

The RAG agent is configured through the `r2r.toml` file. By default, it uses local search.

**Default Configuration:**

```toml
[agent]
rag_agent_static_prompt = "rag_agent"
tools = ["search_file_knowledge"]
```

**Enable Web Search:**

```toml
[agent]
rag_agent_static_prompt = "rag_agent"
tools = ["search_file_knowledge", "web_search"]
```

### Using the RAG Agent

Access the agent through the R2R API via the `agent` endpoint.

**Python Example:**

```python
from r2r import R2RClient

# Initialize the client
client = R2RClient("http://localhost:7272")

# Make a simple query
first_reply = client.retrieval.agent(
    message={"role": "user", "content": "Who was Aristotle?"},
    search_settings={"limit": 5, "filters": {}},
)

# Save the conversation ID for continued interaction
conversation_id = first_reply["results"]["conversation_id"]

# Make a follow-up query using the conversation context
second_reply = client.retrieval.agent(
    message={"role": "user", "content": "What were his contributions to philosophy?"},
    search_settings={"limit": 5, "filters": {}},
    conversation_id=conversation_id,
)
```

**Streaming Responses:**

```python
streaming_response = client.agent(
    message={"role": "user", "content": "Who was Aristotle?"},
    search_settings={"limit": 5, "filters": {}},
    rag_generation_config={"max_tokens": 300, "stream": True},
    conversation_id=conversation_id,
)

print("Streaming RAG Assistant Response:")
for chunk in streaming_response:
    print(chunk, end="", flush=True)
```

### Context-Aware Responses

The agent maintains conversation context, enabling it to handle follow-up questions intelligently based on conversation history.

### Working with Files

The Conversation API allows the agent to be aware of specific files within a conversation.

**Python Example:**

```python
# Create a new conversation
conversation = client.conversations.create("results")

# Inform the agent about available files
client.conversations.add_message(
    conversation_id=conversation["id"],
    role="system",
    content="You have access to the following file: {document_info['title']}"
)

# Query with file context
response = client.retrieval.agent(
    message={
        "role": "user",
        "content": "Summarize the main points of the document"
    },
    search_settings={"limit": 5, "filters": {}},
    conversation_id=conversation["id"]
)
```

### Advanced Features

#### Combined Search Capabilities

When both local and web search are enabled, the agent can:

- Search through your local document store.
- Perform web searches for additional context.
- Maintain conversation context.
- Synthesize information from multiple sources.

**Example:**

```python
response = client.retrieval.agent(
    message={
        "role": "user",
        "content": "Compare historical and modern interpretations"
    },
    search_settings={
        "limit": 5,
        "filters": {},
        "use_web_search": True  # requires `Serper` API key
    },
    conversation_id=conversation_id
)
```

#### Custom Search Settings

Customize search behavior using the `search_settings` parameter.

**Example:**

```python
response = client.retrieval.agent(
    message={"role": "user", "content": "Query"},
    search_settings={
        "limit": 5,  # Number of results to return
        "filters": {
            "date": "2023",  # Example filter
            "category": "technology"
        }
    }
)
```

### Best Practices

1. **Conversation Management**:
   - Maintain conversation IDs for related queries.
   - Use the system role to provide context about available files.
   - Clear conversation context when starting new topics.

2. **Search Optimization**:
   - Adjust the `limit` parameter based on needed context.
   - Use filters to narrow search scope.
   - Consider enabling web search for broader context.

3. **Response Handling**:
   - Use streaming for long responses.
   - Process response chunks appropriately in streaming mode.
   - Check for error messages in responses.

### Error Handling

The agent may return error messages in the response. Always check for errors.

**Python Example:**

```python
from r2r import R2RException

try:
    await client.retrieval.agent(...)
except R2RException as e:
    if e.status_code == 401:
        print("Invalid credentials")
    elif e.status_code == 400:
        print("Email not verified")
```

### Limitations

- **Beta Feature**: The agent is currently in beta.
- **Web Search Requirements**: Requires additional configuration.
- **Streaming Response Structure**: May differ from non-streaming responses.
- **Offline Mode Limitations**: Some features may not be available offline.

### Future Developments

R2R plans to enhance the agent system with:

- Enhanced tool integration.
- Improved conversation management.
- Better search capabilities.
- More customization options.

Stay updated with the latest developments by checking the R2R documentation regularly.

### Conclusion

R2R’s agent system provides powerful, context-aware interactions by combining LLMs with advanced search capabilities. By leveraging these features, you can create intelligent assistants that offer comprehensive and accurate responses based on your document corpus.

---

## Orchestration

Orchestration in R2R is managed using [Hatchet](https://docs.hatchet.run/home), a distributed, fault-tolerant task queue that handles complex workflows such as ingestion and knowledge graph construction.

### Key Concepts

| Concept          | Description                                                                 |
|------------------|-----------------------------------------------------------------------------|
| **Workflows**    | Sets of functions executed in response to external triggers.               |
| **Workers**      | Long-running processes that execute workflow functions.                    |
| **Managed Queue**| Low-latency queue for handling real-time tasks.                            |

### Orchestration in R2R

#### Benefits of Orchestration

1. **Scalability**: Efficiently handles large-scale tasks.
2. **Fault Tolerance**: Built-in retry mechanisms and error handling.
3. **Flexibility**: Easy to add or modify workflows as R2R’s capabilities expand.

#### Workflows in R2R

1. **IngestFilesWorkflow**: Handles file ingestion, parsing, chunking, and embedding.
2. **UpdateFilesWorkflow**: Manages updating existing files.
3. **KgExtractAndStoreWorkflow**: Extracts and stores knowledge graph information.
4. **CreateGraphWorkflow**: Orchestrates knowledge graph creation.
5. **EnrichGraphWorkflow**: Handles graph enrichment processes like node creation and clustering.

### Orchestration GUI

Access the Hatchet front-end application at [http://localhost:7274](http://localhost:7274).

#### Login

Use the following credentials to log in:

- **Email**: admin@example.com
- **Password**: Admin123!!

![Logging into Hatchet](https://files.buildwithfern.com/https://sciphi.docs.buildwithfern.com/2024-12-13T18:29:49.890Z/images/hatchet_login.png)

#### Running Tasks

After initiating tasks like `r2r documents create-samples`, view running workflows:

![Running Workflows](https://files.buildwithfern.com/https://sciphi.docs.buildwithfern.com/2024-12-13T18:29:49.890Z/images/hatchet_running.png)

#### Inspecting a Workflow

Inspect and manage individual workflows, including retrying failed jobs:

![Inspecting a Workflow](https://files.buildwithfern.com/https://sciphi.docs.buildwithfern.com/2024-12-13T18:29:49.890Z/images/hatchet_workflow.png)

#### Long Running Tasks

Hatchet supports long-running tasks, essential for processes like graph construction.

![Long Running Tasks](https://files.buildwithfern.com/https://sciphi.docs.buildwithfern.com/2024-12-13T18:29:49.890Z/images/hatchet_long_running.png)

### Coming Soon

Details about upcoming orchestration features will be available soon.

### Best Practices

1. **Development**:
   - Start with small document sets.
   - Test with single documents first.
   - Scale gradually to larger collections.

2. **Performance**:
   - Monitor community size and complexity.
   - Use pagination for large result sets.
   - Consider breaking very large collections.

3. **Quality**:
   - Review community summaries.
   - Validate findings accuracy.
   - Monitor retrieval relevance.

### Troubleshooting

**Common Issues and Solutions:**

1. **Unable to Create/Modify Collections**:
   - Ensure the user has superuser privileges.

2. **User Not Seeing Collection Content**:
   - Verify that the user is correctly added to the collection.
   - Ensure documents are properly assigned.

3. **Performance Issues with Large Collections**:
   - Use pagination when retrieving users or documents.
   - Consider splitting large collections.

### Conclusion

Orchestration via Hatchet enables R2R to handle complex and large-scale workflows efficiently. By leveraging workflows and monitoring tools, you can ensure smooth and scalable operations within your R2R deployment.

---

## Maintenance & Scaling

Effective maintenance and scaling are crucial for ensuring R2R operates optimally, especially as data volumes grow.

### Vector Indices

#### Do You Need Vector Indices?

Vector indices are **not necessary for all deployments**, particularly in multi-user applications where queries are typically filtered by `user_id`, reducing the number of vectors searched.

**Consider implementing vector indices when:**

- Users search across hundreds of thousands of documents.
- Query latency becomes a bottleneck even with user-specific filtering.
- Supporting cross-user search functionality at scale.

For development or smaller deployments, the overhead of maintaining vector indices often outweighs their benefits.

#### Vector Index Management

R2R supports multiple indexing methods, with HNSW (Hierarchical Navigable Small World) being recommended for most use cases.

**Python Example: Creating and Deleting a Vector Index**

```python
from r2r import R2RClient

client = R2RClient()

# Create vector index
create_response = client.indices.create(
    {
        "table_name": "vectors",
        "index_method": "hnsw",
        "index_measure": "cosine_distance",
        "index_arguments": {
            "m": 16,  # Number of connections per element
            "ef_construction": 64  # Size of dynamic candidate list
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

1. **Pre-warming Requirement**:
   - New indices start “cold” and require warming for optimal performance.
   - Initial queries will be slower until the index is loaded into memory.
   - Implement explicit pre-warming in production.
   - Warming must be repeated after system restarts.

2. **Resource Usage**:
   - Index creation is CPU and memory intensive.
   - Memory usage scales with dataset size and the `m` parameter.
   - Create indices during off-peak hours.

3. **Performance Tuning**:
   - **HNSW Parameters**:
     - `m`: 16-64 (higher = better quality, more memory)
     - `ef_construction`: 64-100 (higher = better quality, longer build time)
   - **Distance Measures**:
     - `cosine_distance`: Best for normalized vectors (most common)
     - `l2_distance`: Better for absolute distances
     - `max_inner_product`: Optimized for dot product similarity

### System Updates and Maintenance

#### Version Management

**Check Current R2R Version:**

```bash
r2r version
```

#### Update Process

1. **Prepare for Update**

```bash
# Check current versions
r2r version
r2r db current

# Generate system report (optional)
r2r generate-report
```

2. **Stop Running Services**

```bash
r2r docker-down
```

3. **Update R2R**

```bash
r2r update
```

4. **Update Database**

```bash
r2r db upgrade
```

5. **Restart Services**

```bash
r2r serve --docker [additional options]
```

#### Database Migration Management

R2R uses database migrations to manage schema changes.

**Check Current Migration:**

```bash
r2r db current
```

**Apply Migrations:**

```bash
r2r db upgrade
```

### Managing Multiple Environments

Use different project names and schemas for different environments.

**Example:**

```bash
# Development
export R2R_PROJECT_NAME=r2r_dev
r2r serve --docker --project-name r2r-dev

# Staging
export R2R_PROJECT_NAME=r2r_staging
r2r serve --docker --project-name r2r-staging

# Production
export R2R_PROJECT_NAME=r2r_prod
r2r serve --docker --project-name r2r-prod
```

### Troubleshooting

If issues occur:

1. **Generate a System Report**

```bash
r2r generate-report
```

2. **Check Container Health**

```bash
r2r docker-down
r2r serve --docker
```

3. **Review Database State**

```bash
r2r db current
r2r db history
```

4. **Roll Back if Needed**

```bash
r2r db downgrade --revision <previous-working-version>
```

### Scaling Strategies

#### Horizontal Scaling

For applications serving many users:

1. **Load Balancing**
   - Deploy multiple R2R instances behind a load balancer.
   - Each instance handles a subset of users.

2. **Sharding**
   - Shard by `user_id` for large multi-user deployments.
   - Each shard handles a subset of users, maintaining performance with millions of documents.

#### Vertical Scaling

For applications requiring large single-user searches:

1. **Cloud Provider Solutions**
   - **AWS RDS**: Supports up to 1 billion vectors per instance.
   - **Example Instance Types**:
     - `db.r6g.16xlarge`: Suitable for up to 100M vectors.
     - `db.r6g.metal`: Can handle 1B+ vectors.

2. **Memory Optimization**

```python
# Optimize for large vector collections
client.indices.create(
    table_name="vectors",
    index_method="hnsw",
    index_arguments={
        "m": 32,  # Increased for better performance
        "ef_construction": 80  # Balanced for large collections
    }
)
```

#### Multi-User Considerations

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
   - Group related documents into collections.
   - Enable efficient access control.
   - Optimize search scope.

3. **Resource Allocation**
   - Monitor per-user resource usage.
   - Implement usage quotas if needed.
   - Consider dedicated instances for power users.

#### Performance Monitoring

Monitor the following metrics to inform scaling decisions:

1. **Query Performance**
   - Average query latency per user.
   - Number of vectors searched per query.
   - Cache hit rates.

2. **System Resources**
   - Memory usage per instance.
   - CPU utilization.
   - Storage growth rate.

3. **User Patterns**
   - Number of active users.
   - Query patterns and peak usage times.
   - Document count per user.

### Performance Considerations

When configuring embeddings in R2R, consider these optimization strategies:

1. **Batch Size Optimization**:
   - Larger batch sizes improve throughput but increase latency.
   - Consider provider-specific rate limits when setting batch size.
   - Balance memory usage with processing speed.

2. **Concurrent Requests**:
   - Adjust `concurrent_request_limit` based on provider capabilities.
   - Monitor API usage and adjust limits accordingly.
   - Implement local caching for frequently embedded texts.

3. **Model Selection**:
   - Balance embedding dimension size with accuracy requirements.
   - Consider cost per token for different providers.
   - Evaluate multilingual requirements when choosing models.

4. **Resource Management**:
   - Monitor memory usage with large batch sizes.
   - Implement appropriate error handling and retry strategies.
   - Consider implementing local model fallbacks for critical systems.

### Additional Resources

- [Python SDK Ingestion Documentation](https://r2r-docs.sciphi.ai/documentation/python-sdk/ingestion)
- [CLI Maintenance Documentation](https://r2r-docs.sciphi.ai/documentation/cli/maintenance)
- [Ingestion Configuration Documentation](https://r2r-docs.sciphi.ai/documentation/configuration/ingestion)

### Best Practices

1. **Optimize Indexing**: Ensure proper indexing for both full-text and vector searches.
2. **Monitor Resources**: Keep track of CPU, memory, and storage usage.
3. **Regular Maintenance**: Perform regular vacuuming and updates to maintain database performance.
4. **Plan Scaling Ahead**: Anticipate growth and implement scaling strategies proactively.

### Conclusion

Effective maintenance and scaling strategies ensure that R2R remains performant and reliable as your data and user base grow. By optimizing vector indices, managing system updates, and employing robust scaling strategies, you can maintain an efficient and scalable R2R deployment.

---

## Web Development

Web developers can easily integrate R2R into their projects using the [R2R JavaScript client](https://github.com/SciPhi-AI/r2r-js). For extensive references and examples, explore the [R2R Application](https://r2r-docs.sciphi.ai/cookbooks/application) and its source code.

### Hello R2R—JavaScript

R2R offers configurable vector search and RAG capabilities with direct method calls.

#### Example: `r2r-js/examples/hello_r2r.js`

```javascript
const { r2rClient } = require("r2r-js");

const client = new r2rClient("http://localhost:7272");

async function main() {
    const files = [
        { path: "examples/data/raskolnikov.txt", name: "raskolnikov.txt" },
    ];

    const EMAIL = "admin@example.com";
    const PASSWORD = "change_me_immediately";

    console.log("Logging in...");
    await client.users.login(EMAIL, PASSWORD);

    console.log("Ingesting file...");
    const documentResult = await client.documents.create({
        file: { path: "examples/data/raskolnikov.txt", name: "raskolnikov.txt" },
        metadata: { title: "raskolnikov.txt" },
    });

    console.log("Document result:", JSON.stringify(documentResult, null, 2));

    console.log("Performing RAG...");
    const ragResponse = await client.rag({
        query: "What does the file talk about?",
        rag_generation_config: {
            model: "openai/gpt-4o",
            temperature: 0.0,
            stream: false,
        },
    });

    console.log("Search Results:");
    ragResponse.results.search_results.chunk_search_results.forEach(
        (result, index) => {
            console.log(`\nResult ${index + 1}:`);
            console.log(`Text: ${result.metadata.text.substring(0, 100)}...`);
            console.log(`Score: ${result.score}`);
        },
    );

    console.log("\nCompletion:");
    console.log(ragResponse.results.completion.choices[0].message.content);
}

main();
```

### r2r-js Client

#### Installing

Install the R2R JavaScript client using [npm](https://www.npmjs.com/package/r2r-js):

```bash
npm install r2r-js
```

#### Creating the Client

First, create the R2R client and specify the base URL where the R2R server is running.

```javascript
const { r2rClient } = require("r2r-js");

// http://localhost:7272 or your R2R server address
const client = new r2rClient("http://localhost:7272");
```

#### Log into the Server

Authenticate the session using default superuser credentials.

```javascript
const EMAIL = "admin@example.com";
const PASSWORD = "change_me_immediately";

console.log("Logging in...");
await client.users.login(EMAIL, PASSWORD);
```

#### Ingesting Files

Specify and ingest files.

```javascript
const file = { path: "examples/data/raskolnikov.txt", name: "raskolnikov.txt" };

console.log("Ingesting file...");
const ingestResult = await client.documents.create({
    file: { path: "examples/data/raskolnikov.txt", name: "raskolnikov.txt" },
    metadata: { title: "raskolnikov.txt" },
});

console.log("Ingest result:", JSON.stringify(ingestResult, null, 2));
```

**Sample Output:**

```json
{
  "results": {
    "processed_documents": [
      "Document 'raskolnikov.txt' processed successfully."
    ],
    "failed_documents": [],
    "skipped_documents": []
  }
}
```

#### Performing RAG

Make a RAG request.

```javascript
console.log("Performing RAG...");
const ragResponse = await client.rag({
    query: "What does the file talk about?",
    rag_generation_config: {
        model: "openai/gpt-4o",
        temperature: 0.0,
        stream: false,
    },
});

console.log("Search Results:");
ragResponse.results.search_results.chunk_search_results.forEach(
    (result, index) => {
        console.log(`\nResult ${index + 1}:`);
        console.log(`Text: ${result.metadata.text.substring(0, 100)}...`);
        console.log(`Score: ${result.score}`);
    },
);

console.log("\nCompletion:");
console.log(ragResponse.results.completion.choices[0].message.content);
```

**Sample Output:**

```
Performing RAG...

Search Results:

Result 1:
Text: praeterire culinam eius, cuius ianua semper aperta erat, cogebatur. Et quoties praeteribat,...

Score: 0.08281802143835804

Result 2:
Text: In vespera praecipue calida ineunte Iulio iuvenis e cenaculo in quo hospitabatur in S. loco exiit et...

Score: 0.052743945852283036

...

Completion:
The file discusses the experiences and emotions of a young man who is staying in a small room in a tall house.
He is burdened by debt and feels anxious and ashamed whenever he passes by the kitchen of his landlady, whose
door is always open [1]. On a particularly warm evening in early July, he leaves his room and walks slowly towards
a bridge, trying to avoid encountering his landlady on the stairs. His room, which is more like a closet than a
proper room, is located under the roof of the five-story house, while the landlady lives on the floor below and
provides him with meals and services [2].
```

### Connecting to a Web App

Integrate R2R into web applications by creating API routes and React components.

#### Setting up an API Route

Create `r2r-query.ts` in the `pages/api` directory to handle R2R queries.

#### Frontend: React Component

Create a React component, e.g., `index.tsx`, to interact with the API route, providing an interface for user queries and displaying results.

#### Template Repository

For a complete working example, check out the [R2R Web Dev Template Repository](https://github.com/SciPhi-AI/r2r-webdev-template).

**Usage:**

1. **Clone the Repository:**

```bash
git clone https://github.com/SciPhi-AI/r2r-webdev-template.git
cd r2r-webdev-template
```

2. **Install Dependencies:**

```bash
pnpm install
```

3. **Run the Development Server:**

Ensure your R2R server is running, then start the frontend:

```bash
pnpm dev
```

Access the dashboard at [http://localhost:3000](http://localhost:3000).

### Best Practices

1. **Secure API Routes**: Ensure API routes are protected and validate user input.
2. **Optimize Frontend Performance**: Lazy load components and manage state efficiently.
3. **Handle Errors Gracefully**: Provide user-friendly error messages and fallback options.
4. **Implement Caching**: Cache frequent queries to reduce load and improve response times.
5. **Maintain Consistent State**: Synchronize frontend state with backend data to prevent discrepancies.

### Conclusion

The R2R JavaScript client simplifies integration into web applications, enabling developers to build powerful RAG features with minimal setup. Utilize the template repository for a quick start and explore more advanced examples in the [R2R Dashboard](https://github.com/SciPhi-AI/R2R-Application).

---

## User Management

R2R provides robust user authentication and management capabilities, ensuring secure and efficient access control over documents and features.

### Introduction

R2R's authentication system supports secure user registration, login, session management, and access control. This guide covers basic usage, advanced features, security considerations, and troubleshooting.

For detailed configuration, refer to the [Authentication Configuration Documentation](https://r2r-docs.sciphi.ai/documentation/configuration/auth) and the [User API Reference](https://r2r-docs.sciphi.ai/api-and-sdks/users/users).

**Default Behavior**: When `require_authentication` is set to `false` (default in `r2r.toml`), unauthenticated requests use default admin credentials. Use caution in production environments.

### Basic Usage

#### User Registration and Login

**Python Example:**

```python
from r2r import R2RClient

client = R2RClient("http://localhost:7272")  # Replace with your R2R deployment URL

# Register a new user
user_result = client.users.create("user1@test.com", "password123")
print(user_result)
# {'results': {'email': 'user1@test.com', 'id': 'bf417057-f104-4e75-8579-c74d26fcbed3', ...}}

# Login immediately (assuming email verification is disabled)
login_result = client.users.login("user1@test.com", "password123")
print(login_result)
# {'results': {'access_token': {...}, 'refresh_token': {...}}}
```

#### Email Verification (Optional)

If email verification is enabled:

```python
# Verify email
verify_result = client.users.verify_email("verification_code_here")
print(verify_result)
# {"results": {"message": "Email verified successfully"}}
```

#### Token Refresh

Refresh an expired access token:

```python
refresh_result = client.users.refresh_access_token("YOUR_REFRESH_TOKEN")
print(refresh_result)
# {'access_token': {...}, 'refresh_token': {...}}
```

#### User-Specific Search

Authenticated searches are filtered based on the user's permissions.

**Curl Example:**

```bash
curl -X POST http://localhost:7272/v3/retrieval/search \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Who was Aristotle"
  }'
```

**Sample Output:**

```json
{
  "results": {
    "chunk_search_results": [],
    "kg_search_results": []
  }
}
```

> *Search results are empty for a new user.*

#### User Logout

Invalidate the current access token.

**Curl Example:**

```bash
curl -X POST http://localhost:7272/v3/users/logout \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Sample Output:**

```json
{
  "results": {"message": "Logged out successfully"}
}
```

### Advanced Authentication Features

#### Password Management

Users can change their passwords and request password resets.

**Python Example:**

```python
# Change password
change_password_result = client.users.change_password("password123", "new_password")
print(change_password_result)
# {"results": {"message": "Password changed successfully"}}

# Request password reset
reset_request_result = client.users.request_password_reset("user@example.com")
print(reset_request_result)
# {"results": {"message": "If the email exists, a reset link has been sent"}}

# Confirm password reset
reset_confirm_result = client.users.confirm_password_reset("reset_token_here", "new_password")
print(reset_confirm_result)
# {"results": {"message": "Password reset successfully"}}
```

#### User Profile Management

Users can view and update their profiles.

**Python Example:**

```python
# Update user profile (requires login)
update_result = client.users.update_user(name="John Doe", bio="R2R enthusiast")
print(update_result)
# {'results': {'email': 'user1@test.com', 'id': '76eea168-9f98-4672-af3b-2c26ec92d7f8', ...}}
```

#### Account Deletion

Users can delete their accounts.

**Python Example:**

```python
# Delete account (requires password confirmation)
user_id = register_response["results"]["id"]  # Use the actual user ID
delete_result = client.delete_user(user_id, "password123")
print(delete_result)
# {'results': {'message': 'User account deleted successfully'}}
```

#### Logout

To end a user session:

```python
# Logout
logout_result = client.users.logout()
print(f"Logout Result:\n{logout_result}")
# {'results': {'message': 'Logged out successfully'}}
```

### Superuser Capabilities and Default Admin Creation

#### Superuser Capabilities

Superusers have elevated privileges, enabling them to:

1. **User Management**: View, modify, and delete user accounts.
2. **System-wide Document Access**: Access and manage all documents.
3. **Analytics and Observability**: Access system-wide analytics and logs.
4. **Configuration Management**: Modify system configurations and settings.

#### Default Admin Creation

R2R automatically creates a default admin user during initialization via the `R2RAuthProvider` class.

**Configuration:**

```toml
[auth]
provider = "r2r"
access_token_lifetime_in_minutes = 60
refresh_token_lifetime_in_days = 7
require_authentication = true
require_email_verification = false
default_admin_email = "admin@example.com"
default_admin_password = "change_me_immediately"
```

- **`require_authentication`**: Set to `false` for development/testing; `true` for production.
- **`require_email_verification`**: Set to `false` by default; consider enabling for production.

#### Accessing Superuser Features

Authenticate as the default admin or another superuser to access superuser features.

**Python Example:**

```python
from r2r import R2RClient

client = R2RClient("http://localhost:7272")

# Login as admin
login_result = client.users.login("admin@example.com", "change_me_immediately")

# Access superuser features
users_overview = client.users.list()
print(users_overview)

# Access system-wide logs
logs = client.logs()
print(logs)

# Perform analytics
analytics_result = client.analytics(
    {"all_latencies": "search_latency"},
    {"search_latencies": ["basic_statistics", "search_latency"]}
)
print(analytics_result)
```

### Security Considerations for Superusers

When using superuser capabilities:

1. **Limit Superuser Access**: Only grant to trusted individuals.
2. **Use Strong Passwords**: Ensure superuser accounts use strong, unique passwords.
3. **Enable Authentication and Verification**: Set `require_authentication` and `require_email_verification` to `true` in production.
4. **Audit Superuser Actions**: Regularly review logs of superuser activities.
5. **Rotate Credentials**: Periodically update superuser credentials, including the default admin password.

### Security Considerations

When implementing user authentication, consider the following security best practices:

1. **Use HTTPS**: Always use HTTPS in production to encrypt data in transit.
2. **Implement Rate Limiting**: Protect against brute-force attacks by limiting login attempts.
3. **Use Secure Password Hashing**: R2R uses bcrypt for password hashing by default.
4. **Implement Multi-Factor Authentication (MFA)**: Add MFA for an extra layer of security.
5. **Regular Security Audits**: Conduct regular security audits of your authentication system.

### Customizing Authentication

R2R’s authentication system is flexible and can be customized to fit your specific needs:

1. **Custom User Fields**: Extend the User model to include additional fields.
2. **OAuth Integration**: Integrate with third-party OAuth providers for social login.
3. **Custom Password Policies**: Implement custom password strength requirements.
4. **User Roles and Permissions**: Implement a role-based access control system.

### Troubleshooting

**Common Issues and Solutions:**

1. **Login Fails After Registration**:
   - Ensure email verification is completed if enabled.

2. **Token Refresh Fails**:
   - Check if the refresh token has expired; the user may need to log in again.

3. **Unable to Change Password**:
   - Verify that the current password is correct.

### Conclusion

R2R provides a comprehensive set of user authentication and management features, allowing developers to implement secure and user-friendly applications. By leveraging these capabilities, you can implement robust user authentication, document management, and access control in your R2R-based projects.

For more advanced use cases or custom implementations, refer to the R2R documentation or reach out to the community for support.

---

## Collections

### Introduction

A **collection** in R2R is a logical grouping of users and documents that allows for efficient access control and organization. Collections enable you to manage permissions and access to documents at a group level, rather than individually.

R2R provides robust document collection management, allowing developers to implement efficient access control and organization of users and documents.

**Note**: Collection permissioning in R2R is under development and may continue evolving in future releases.

### Basic Usage

#### Collection CRUD Operations

**Creating a Collection:**

```python
from r2r import R2RClient

client = R2RClient("http://localhost:7272")  # Replace with your R2R deployment URL

# Create a new collection
collection_result = client.collections.create("Marketing Team", "Collection for marketing department")
print(f"Collection creation result: {collection_result}")
# {'results': {'collection_id': '123e4567-e89b-12d3-a456-426614174000', 'name': 'Marketing Team', 'description': 'Collection for marketing department', ...}}
```

**Retrieving Collection Details:**

```python
collection_id = '123e4567-e89b-12d3-a456-426614174000'  # Use the actual collection_id

collection_details = client.collections.retrieve(collection_id)
print(f"Collection details: {collection_details}")
# {'results': {'collection_id': '123e4567-e89b-12d3-a456-426614174000', 'name': 'Marketing Team', 'description': 'Collection for marketing department', ...}}
```

**Updating a Collection:**

```python
update_result = client.collections.update(
    collection_id,
    name="Updated Marketing Team",
    description="New description for marketing team"
)
print(f"Collection update result: {update_result}")
# {'results': {'collection_id': '123e4567-e89b-12d3-a456-426614174000', 'name': 'Updated Marketing Team', 'description': 'New description for marketing team', ...}}
```

**Deleting a Collection:**

```python
client.collections.delete(collection_id)
```

### User Management in Collections

#### Adding a User to a Collection

```python
user_id = '456e789f-g01h-34i5-j678-901234567890'  # Valid user ID
collection_id = '123e4567-e89b-12d3-a456-426614174000'  # Valid collection ID

add_user_result = client.collections.add_user(user_id, collection_id)
print(f"Add user to collection result: {add_user_result}")
# {'results': {'message': 'User successfully added to the collection'}}
```

#### Removing a User from a Collection

```python
remove_user_result = client.collections.remove_user(user_id, collection_id)
print(f"Remove user from collection result: {remove_user_result}")
# {'results': None}
```

#### Listing Users in a Collection

```python
users_in_collection = client.collections.list_users(collection_id)
print(f"Users in collection: {users_in_collection}")
# {'results': [{'user_id': '456e789f-g01h-34i5-j678-901234567890', 'email': 'user@example.com', 'name': 'John Doe', ...}, ...]}
```

#### Getting Collections for a User

```python
user_collections = client.user.list_collections(user_id)
print(f"User's collections: {user_collections}")
# {'results': [{'collection_id': '123e4567-e89b-12d3-a456-426614174000', 'name': 'Updated Marketing Team', ...}, ...]}
```

### Document Management in Collections

#### Assigning a Document to a Collection

```python
document_id = '789g012j-k34l-56m7-n890-123456789012'  # Valid document ID

assign_doc_result = client.collections.add_document(collection_id, document_id)
print(f"Assign document to collection result: {assign_doc_result}")
# {'results': {'message': 'Document successfully assigned to the collection'}}
```

#### Removing a Document from a Collection

```python
remove_doc_result = client.collections.remove_document(collection_id, document_id)
print(f"Remove document from collection result: {remove_doc_result}")
# {'results': {'message': 'Document successfully removed from the collection'}}
```

#### Listing Documents in a Collection

```python
docs_in_collection = client.collections.list_documents(collection_id)
print(f"Documents in collection: {docs_in_collection}")
# {'results': [{'document_id': '789g012j-k34l-56m7-n890-123456789012', 'title': 'Marketing Strategy 2024', ...}, ...]}
```

#### Getting Collections for a Document

```python
document_collections = client.documents.list_collections(document_id)
print(f"Document's collections: {document_collections}")
# {'results': [{'collection_id': '123e4567-e89b-12d3-a456-426614174000', 'name': 'Updated Marketing Team', ...}, ...]}
```

### Advanced Collection Management

#### Generating Synthetic Descriptions

Generate a description for a collection using an LLM.

```python
update_result = client.collections.update(
    collection_id,
    generate_description=True
)
print(f"Collection update result: {update_result}")
# {'results': {'collection_id': '123e4567-e89b-12d3-a456-426614174000', 'name': 'Updated Marketing Team', 'description': 'A rich description...', ...}}
```

#### Collection Overview

Get an overview of collections, including user and document counts.

```python
collections_list = client.collections.list()
print(f"Collections overview: {collections_list}")
# {'results': [{'collection_id': '123e4567-e89b-12d3-a456-426614174000', 'name': 'Updated Marketing Team', 'description': 'New description...', 'user_count': 5, 'document_count': 10, ...}, ...]}
```

### Pagination and Filtering

Many collection-related methods support pagination and filtering.

**Examples:**

```python
# List collections with pagination
paginated_collections = client.collections.list(offset=10, limit=20)

# Get users in a collection with pagination
paginated_users = client.collections.list_users(collection_id, offset=5, limit=10)

# Get documents in a collection with pagination
paginated_docs = client.collections.list_documents(collection_id, offset=0, limit=50)

# Get specific collections by IDs
specific_collections = client.collections.list(collection_ids=['id1', 'id2', 'id3'])
```

### Security Considerations

When implementing collection permissions, consider the following security best practices:

1. **Least Privilege Principle**: Assign minimum necessary permissions to users and collections.
2. **Regular Audits**: Periodically review collection memberships and document assignments.
3. **Access Control**: Ensure only authorized users (e.g., admins) can perform collection management operations.
4. **Logging and Monitoring**: Implement comprehensive logging for all collection-related actions.

### Customizing Collection Permissions

While R2R’s current collection system follows a flat hierarchy, you can build more complex permission structures:

1. **Custom Roles**: Implement application-level roles within collections (e.g., collection admin, editor, viewer).
2. **Hierarchical Collections**: Create a hierarchy by establishing parent-child relationships between collections in your application logic.
3. **Permission Inheritance**: Implement rules for permission inheritance based on collection memberships.

### Troubleshooting

**Common Issues and Solutions:**

1. **Unable to Create/Modify Collections**:
   - Ensure the user has superuser privileges.

2. **User Not Seeing Collection Content**:
   - Verify that the user is correctly added to the collection.
   - Ensure documents are properly assigned.

3. **Performance Issues with Large Collections**:
   - Use pagination when retrieving users or documents.
   - Consider splitting large collections.

### Conclusion

R2R’s collection permissioning system provides a foundation for implementing sophisticated access control in your applications. As the feature set evolves, more advanced capabilities will become available. Regularly update your practices based on the latest R2R documentation.

### Next Steps

- Explore [GraphRAG](https://r2r-docs.sciphi.ai/cookbooks/graphrag) for advanced features.
- Learn about [hybrid search](https://r2r-docs.sciphi.ai/cookbooks/hybrid-search) integration.
- Discover more about [observability](https://r2r-docs.sciphi.ai/cookbooks/observability).
- Set up [orchestration](https://r2r-docs.sciphi.ai/cookbooks/orchestration) for large-scale processing.

---

## Telemetry

R2R uses telemetry to collect **anonymous** usage information. This data helps understand how R2R is used, prioritize new features and bug fixes, and improve overall performance and stability.

### Introduction

R2R uses telemetry to collect **anonymous** usage information. This data helps understand how R2R is used, prioritize new features and bug fixes, and improve overall performance and stability.

### Disabling Telemetry

To opt out of telemetry, set an environment variable:

```bash
export TELEMETRY_ENABLED=false
```

**Valid Values**: `false`, `0`, `f`

When telemetry is disabled, no events are captured.

### Collected Information

Our telemetry system collects basic, anonymous information such as:

- **Feature Usage**: Which features are being used and their frequency.
- **Performance Metrics**: Query latencies, system resource usage.
- **Error Logs**: Information about errors and exceptions.

### Telemetry Data Storage

*Details about telemetry data storage are not provided in the original document.*

### Why We Collect Telemetry

Telemetry data helps us:

1. Understand which features are most valuable to users.
2. Identify areas for improvement.
3. Prioritize development efforts.
4. Enhance R2R’s overall performance and stability.

We appreciate your participation in our telemetry program, as it directly contributes to making R2R better for everyone.

### Conclusion

Telemetry in R2R provides valuable insights into system usage and performance, enabling continuous improvement. Users concerned about privacy can easily disable telemetry by setting the appropriate environment variable.

---

## Embedding

### Embedding System

R2R uses embeddings as the foundation for semantic search and similarity matching capabilities. The embedding system converts text into high-dimensional vectors that capture semantic meaning, enabling powerful search and retrieval operations.

R2R leverages **LiteLLM** to route embedding requests due to their provider flexibility. Read more about [LiteLLM here](https://docs.litellm.ai/).

### Embedding Configuration

Customize the embedding system through the `embedding` section in your `r2r.toml` file, along with corresponding environment variables for sensitive information.

**Example: `r2r.toml`**

```toml
[embedding]
provider = "litellm"  # defaults to "litellm"
base_model = "openai/text-embedding-3-small"  # defaults to "openai/text-embedding-3-large"
base_dimension = 512  # defaults to 3072
batch_size = 512  # defaults to 128
rerank_model = "BAAI/bge-reranker-v2-m3"  # defaults to None
concurrent_request_limit = 256  # defaults to 256
```

**Environment Variables:**

- `OPENAI_API_KEY`
- `OPENAI_API_BASE`
- `HUGGINGFACE_API_KEY`
- `HUGGINGFACE_API_BASE`
- `ANTHROPIC_API_KEY`
- `COHERE_API_KEY`
- `OLLAMA_API_KEY`
- `BEDROCK_API_KEY`
- `VERTEX_AI_API_KEY`
- `VOYAGE_AI_API_KEY`

### Advanced Embedding Features in R2R

#### Batched Processing

R2R implements intelligent batching for embedding operations to optimize throughput and, in some cases, cost.

**Python Example:**

```python
class EmbeddingProvider:
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        batches = [texts[i:i + self.batch_size] for i in range(0, len(texts), self.batch_size)]
        embeddings = []
        for batch in batches:
            batch_embeddings = await self._process_batch(batch)
            embeddings.extend(batch_embeddings)
        return embeddings
```

#### Concurrent Request Management

The system manages requests with rate limiting and concurrency control.

1. **Rate Limiting**: Prevents API throttling through intelligent request scheduling.
2. **Concurrent Processing**: Manages multiple embedding requests efficiently.
3. **Error Handling**: Implements retry logic with exponential backoff.

### Performance Considerations

When configuring embeddings in R2R, consider these optimization strategies:

1. **Batch Size Optimization**:
   - Larger batch sizes improve throughput but increase latency.
   - Consider provider-specific rate limits when setting batch size.
   - Balance memory usage with processing speed.

2. **Concurrent Requests**:
   - Adjust `concurrent_request_limit` based on provider capabilities.
   - Monitor API usage and adjust limits accordingly.
   - Implement local caching for frequently embedded texts.

3. **Model Selection**:
   - Balance embedding dimension size with accuracy requirements.
   - Consider cost per token for different providers.
   - Evaluate multilingual requirements when choosing models.

4. **Resource Management**:
   - Monitor memory usage with large batch sizes.
   - Implement appropriate error handling and retry strategies.
   - Consider implementing local model fallbacks for critical systems.

### Supported LiteLLM Providers

R2R supports multiple LiteLLM providers:

- **OpenAI**
- **Azure**
- **Anthropic**
- **Cohere**
- **Ollama**
- **HuggingFace**
- **Bedrock**
- **Vertex AI**
- **Voyage AI**

**Example Configuration:**

```toml
[embedding]
provider = "litellm"
base_model = "openai/text-embedding-3-small"
base_dimension = 512

# Environment Variables
export OPENAI_API_KEY=your_openai_key
# Set other environment variables as needed
```

**Supported Models:**

- `openai/text-embedding-3-small`
- `openai/text-embedding-3-large`
- `openai/text-embedding-ada-002`

### Performance Considerations

1. **Batch Size Optimization**:
   - Larger batches improve throughput but may increase latency.
   - Balance batch size with memory and processing speed.

2. **Concurrent Requests**:
   - Adjust based on provider capabilities.
   - Monitor and optimize based on API usage.

3. **Model Selection**:
   - Choose models that fit your domain and accuracy needs.
   - Consider cost implications of different models.

### Conclusion

R2R’s embedding system, powered by LiteLLM, offers flexible and powerful semantic search capabilities. By optimizing batch sizes, managing concurrent requests, and selecting appropriate models, you can ensure efficient and accurate embeddings tailored to your application's needs.

---

## Prompts

### Prompt Management in R2R

R2R provides a flexible system for managing prompts, allowing you to create, update, retrieve, and delete prompts dynamically. This system is crucial for customizing the behavior of language models and ensuring consistent interactions across your application.

### Default Prompts

R2R comes with a set of default prompts loaded from YAML files located in the [`py/core/providers/database/prompts`](https://github.com/SciPhi-AI/R2R/tree/main/py/core/providers/database/prompts) directory. These prompts serve as starting points for various tasks.

**Example: `rag.yaml`**

```yaml
rag:
  template: >
    ## Task:

    Answer the query given immediately below given the context which follows later. Use line item references like [1], [2], ... to refer to specifically numbered items in the provided context. Pay close attention to the title of each given source to ensure consistency with the query.

    ### Query:

    {query}

    ### Context:

    {context}

    ### Response:
```

#### Prompt Files

| Prompt File                                  | Purpose                                                                                       |
|----------------------------------------------|-----------------------------------------------------------------------------------------------|
| `rag.yaml`                           | Default prompt for Retrieval-Augmented Generation (RAG) tasks.                              |
| `graphrag_community_reports.yaml`             | Used in GraphRAG to generate reports about communities or clusters in the knowledge graph.   |
| `graph_entity_description.yaml`            | System prompt for the “map” phase in GraphRAG, used to process individual nodes or edges.     |
| `graphrag_map_system.yaml`                    | System prompt for the “map” phase in GraphRAG.                                              |
| `graphrag_reduce_system.yaml`                 | System prompt for the “reduce” phase in GraphRAG.                                           |
| `graphrag_triples_extraction_few_shot.yaml`   | Few-shot prompt for extracting subject-predicate-object triplets in GraphRAG.               |
| `hyde.yaml`                                  | Related to Hypothetical Document Embeddings (HyDE) for improving retrieval performance.      |
| `rag_agent.yaml`                             | Defines behavior and instructions for the RAG agent, coordinating retrieval and generation.  |
| `rag_context.yaml`                           | Used to process or format the context retrieved for RAG tasks.                               |
| `rag_fusion.yaml`                            | Used in RAG fusion techniques for combining information from multiple retrieved passages.    |
| `system.yaml`                                | Contains general system-level prompts or instructions for the R2R system.                    |

### Prompt Provider

R2R uses a Postgres class to manage prompts, enabling storage, retrieval, and manipulation of prompts. This leverages both a Postgres database and YAML files for flexibility and persistence.

**Key Features:**

1. **Database Storage**: Prompts are stored in a Postgres table for efficient querying and updates.
2. **YAML File Support**: Prompts can be loaded from YAML files, facilitating version control and distribution.
3. **In-Memory Cache**: Prompts are kept in memory for fast access during runtime.

### Prompt Structure

Each prompt in R2R consists of:

- **Name**: A unique identifier for the prompt.
- **Template**: The actual text of the prompt, which may include placeholders for dynamic content.
- **Input Types**: A dictionary specifying the expected types for any dynamic inputs to the prompt.

### Managing Prompts

R2R provides several endpoints and SDK methods for managing prompts:

#### Adding a Prompt

```python
from r2r import R2RClient

client = R2RClient()

response = client.prompts.add_prompt(
    name="my_new_prompt",
    template="Hello, {name}! Welcome to {service}.",
    input_types={"name": "str", "service": "str"}
)
```

#### Updating a Prompt

```python
response = client.prompts.update_prompt(
    name="my_existing_prompt",
    template="Updated template: {variable}",
    input_types={"variable": "str"}
)
```

#### Retrieving a Prompt

```python
response = client.prompts.get_prompt(
    prompt_name="my_prompt",
    inputs={"variable": "example"},
    prompt_override="Optional override text"
)
```

Refer to the [Prompt API Reference](https://r2r-docs.sciphi.ai/api-and-sdks/prompts) for more details.

### Security Considerations

Access to prompt management functions is restricted to superusers to prevent unauthorized modifications to system prompts. Ensure only trusted administrators have superuser access to your R2R deployment.

### Conclusion

R2R’s prompt management system offers powerful and flexible control over language model behavior. By effectively managing prompts, you can create dynamic, context-aware, and maintainable AI-powered features tailored to your application's needs.

---

## RAG

### RAG Customization

RAG (Retrieval-Augmented Generation) in R2R can be extensively customized to suit various use cases. The main components for customization are:

1. **Generation Configuration**: Control the language model’s behavior.
2. **Search Settings**: Fine-tune the retrieval process.
3. **Task Prompt Override**: Customize the system prompt for specific tasks.

#### LLM Provider Configuration

Refer to the [LLM Configuration](https://r2r-docs.sciphi.ai/documentation/configuration/llm) page for detailed information.

#### Retrieval Configuration

Refer to the [Retrieval Configuration](https://r2r-docs.sciphi.ai/documentation/configuration/retrieval/overview) page for detailed information.

### Combining LLM and Retrieval Configuration for RAG

The `rag_generation_config` parameter allows you to customize the language model’s behavior. Default settings are set on the server-side using `r2r.toml`. These settings can be overridden at runtime.

**Python Example:**

```python
from r2r import R2RClient

client = R2RClient()

response = client.retrieval.rag(
    "Who was Aristotle?",
    rag_generation_config={
        "model": "anthropic/claude-3-haiku-20240307",
        "temperature": 0.7,
    },
    search_settings={
        "use_semantic_search": True,
        "limit": 20,
        "use_hybrid_search": True
    }
)
```

### RAG Prompt Override

For specialized tasks, override the default RAG task prompt at runtime.

**Python Example:**

```python
task_prompt_override = """You are an AI assistant specializing in quantum computing.

Your task is to provide a concise summary of the latest advancements in the field,
focusing on practical applications and breakthroughs from the past year."""

response = client.retrieval.rag(
    "What are the latest advancements in quantum computing?",
    rag_generation_config=rag_generation_config,
    task_prompt_override=task_prompt_override
)
```

### Agent-based Interaction

R2R supports multi-turn conversations and complex query processing through its agent endpoint.

**Python Example:**

```python
from r2r import R2RClient

client = R2RClient("http://localhost:7272")

messages = [
    {"role": "system", "content": "You are a helpful AI assistant."},
    {"role": "user", "content": "What are the key differences between quantum and classical computing?"}
]

response = client.retrieval.agent(
    messages=messages,
    vector_search_settings=vector_search_settings,
    graph_settings=graph_settings,
    rag_generation_config=rag_generation_config,
)
```

### Conclusion

By leveraging R2R’s RAG customization options, you can fine-tune retrieval and generation processes to best suit your specific use case and requirements, enhancing the overall performance and relevance of your AI-powered features.

---

## Graphs

### Graphs

R2R supports robust knowledge graph functionality to enhance document understanding and retrieval. By extracting entities and relationships from documents and organizing them into collections, R2R enables advanced graph-based analysis and search capabilities.

**Note**: Refer to the [Knowledge Graph Cookbook](https://r2r-docs.sciphi.ai/cookbooks/knowledge-graphs) and [GraphRAG Cookbook](https://r2r-docs.sciphi.ai/cookbooks/graphrag) for detailed guides.

### Knowledge Graph Operations

#### Entity Management

- **Add Entities**: Add new entities to the knowledge graph.
- **Update Entities**: Modify existing entities.
- **Retrieve Entities**: Fetch entities based on criteria.

#### Relationship Management

- **Create Relationships**: Define relationships between entities.
- **Query Relationships**: Fetch relationships based on criteria.

#### Batch Import

Efficiently import large amounts of data using batched operations.

#### Vector Search

Perform similarity searches on entity embeddings to find related entities.

#### Community Detection

Identify and manage communities within the graph to understand clusters of related information.

### Customization

Customize knowledge graph extraction and search processes by modifying `kg_triples_extraction_prompt` and adjusting model configurations in `kg_extraction_settings` and `graph_settings`.

### Conclusion

R2R’s knowledge graph capabilities enhance document understanding and improve search and RAG operations by providing structured and interconnected information from your documents.

# HTTP API of R2R Library

Welcome to the **R2R (Retrieve to Retrieve) API** documentation. This guide provides an exhaustive overview of all available API endpoints, organized into logical sections with detailed descriptions, request and response schemas, error codes, and usage examples. Whether you're integrating R2R into your application or developing workflows around it, this documentation will serve as your essential reference.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Authentication](#authentication)
3. [Documents](#documents)
    - [Overview](#overview)
    - [Available Endpoints](#available-endpoints)
    - [Endpoint Details](#endpoint-details)
4. [Chunks](#chunks)
    - [Overview](#overview-1)
    - [Available Endpoints](#available-endpoints-1)
    - [Endpoint Details](#endpoint-details-1)
5. [Graphs](#graphs)
    - [Overview](#overview-2)
    - [Available Endpoints](#available-endpoints-2)
    - [Endpoint Details](#endpoint-details-2)
6. [Entities](#entities)
    - [Overview](#overview-3)
    - [Available Endpoints](#available-endpoints-3)
    - [Endpoint Details](#endpoint-details-3)
7. [Relationships](#relationships)
    - [Overview](#overview-4)
    - [Available Endpoints](#available-endpoints-4)
    - [Endpoint Details](#endpoint-details-4)
8. [Communities](#communities)
    - [Overview](#overview-5)
    - [Available Endpoints](#available-endpoints-5)
    - [Endpoint Details](#endpoint-details-5)
9. [Retrieval](#retrieval)
    - [Overview](#overview-6)
    - [Available Endpoints](#available-endpoints-6)
    - [Endpoint Details](#endpoint-details-6)
10. [Indices](#indices)
    - [Overview](#overview-7)
    - [Available Endpoints](#available-endpoints-7)
    - [Endpoint Details](#endpoint-details-7)
11. [Users](#users)
    - [Overview](#overview-8)
    - [Available Endpoints](#available-endpoints-8)
    - [Endpoint Details](#endpoint-details-8)
12. [Collections](#collections)
    - [Overview](#overview-9)
    - [Available Endpoints](#available-endpoints-9)
    - [Endpoint Details](#endpoint-details-9)
13. [Conversations](#conversations)
    - [Overview](#overview-10)
    - [Available Endpoints](#available-endpoints-10)
    - [Endpoint Details](#endpoint-details-10)
14. [Prompts](#prompts)
    - [Overview](#overview-11)
    - [Available Endpoints](#available-endpoints-11)
    - [Endpoint Details](#endpoint-details-11)
15. [System](#system)
    - [Overview](#overview-12)
    - [Available Endpoints](#available-endpoints-12)
    - [Endpoint Details](#endpoint-details-12)
16. [Common Use Cases](#common-use-cases)
17. [Conclusion](#conclusion)

---

## Introduction

**R2R (Retrieve to Retrieve)** is a robust content management and retrieval system designed to ingest, manage, and retrieve various types of documents efficiently. It leverages advanced features such as semantic search, knowledge graph creation, and conversational agents powered by large language models (LLMs). This API allows seamless integration with R2R’s functionalities, enabling developers to build sophisticated applications and workflows.

---

## Authentication

Before accessing any R2R API endpoints, ensure you have authenticated and obtained the necessary access tokens. Authentication is handled via Bearer tokens included in the `Authorization` header of each request.

### Example Header

```http
Authorization: Bearer YOUR_API_KEY
```

---

## Documents

### Overview

A **Document** in R2R represents an ingested piece of content such as text files, PDFs, images, or audio files. Documents undergo processing to generate **Chunks**, extract **Entities** & **Relationships**, and facilitate the construction of knowledge graphs. They are central to R2R’s content management system and are associated with metadata and collections for organized access control.

### Core Features of Documents

1. **Ingestion & Processing**
    - Upload new content or update existing documents.
    - Automatic chunking and optional summarization.
    - Metadata storage and advanced filtering capabilities.

2. **Knowledge Graph Extraction**
    - Extract Entities and Relationships for building knowledge graphs.
    - Maintain ingestion and extraction status.

3. **Collections & Access Control**
    - Organize documents into Collections.
    - Manage user access to documents at a collection level.

### Available Endpoints

| Method | Endpoint                           | Description                                                                                         |
| :---- | :---------------------------------- | :-------------------------------------------------------------------------------------------------- |
| POST   | `/documents`                         | Ingest a new document from a file or text content. Supports `multipart/form-data`.                  |
| POST   | `/documents/{id}`                    | Update an existing document with new content or metadata.                                           |
| GET    | `/documents`                         | List documents with pagination. Can filter by IDs.                                                  |
| GET    | `/documents/{id}`                    | Get details of a specific document.                                                                 |
| GET    | `/documents/{id}/chunks`             | Retrieve the chunks generated from a document.                                                      |
| GET    | `/documents/{id}/download`           | Download the original document file.                                                                |
| DELETE | `/documents/{id}`                    | Delete a specific document.                                                                         |
| DELETE | `/documents/by-filter`               | Delete multiple documents using filters.                                                            |
| GET    | `/documents/{id}/collections`        | List collections containing a document (**superuser only**).                                        |
| POST   | `/documents/{id}/extract`            | Extract entities and relationships from a document for knowledge graph creation.                     |
| GET    | `/documents/{id}/entities`           | Retrieve entities extracted from the document.                                                      |
| GET    | `/documents/{id}/relationships`      | List relationships between entities found in the document.                                          |

### Endpoint Details

#### 1. List Documents

```http
GET /v3/documents
```

**Description:**
Returns a paginated list of documents accessible to the authenticated user. Regular users see only their own documents or those shared through collections, while superusers see all documents.

**Query Parameters:**

| Parameter                   | Type     | Required | Description                                                                 |
| :-------------------------- | :------- | :------ | :-------------------------------------------------------------------------- |
| `ids`                       | `string` | No      | A comma-separated list of document IDs to retrieve.                         |
| `offset`                    | `integer`| No      | Number of objects to skip. Defaults to `0`.                                 |
| `limit`                     | `integer`| No      | Max number of objects to return, `1–100`. Defaults to `100`.               |
| `include_summary_embeddings`| `integer`| No      | Whether to include embeddings of each document summary (`1` for true, `0` for false). |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "id",
      "collection_ids": ["collection_ids"],
      "owner_id": "owner_id",
      "document_type": "mp3",
      "metadata": { "key": "value" },
      "version": "version",
      "title": "title",
      "size_in_bytes": 1,
      "ingestion_status": "pending",
      "extraction_status": "pending",
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-01-15T09:30:00Z",
      "ingestion_attempt_number": 1,
      "summary": "summary",
      "summary_embedding": [1.1]
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

---

#### 2. Create a New Document

```http
POST /v3/documents
```

**Description:**
Creates a new Document object from an input file, text content, or pre-processed chunks. The ingestion process can be configured using an `ingestion_mode` or a custom `ingestion_config`.

**Ingestion Modes:**

- `hi-res`: Comprehensive parsing and enrichment, including summaries and thorough processing.
- `fast`: Speed-focused ingestion that skips certain enrichment steps like summaries.
- `custom`: Provide a full `ingestion_config` to customize the entire ingestion process.

**Note:**
Either a file or text content must be provided, but not both. Documents are shared through `Collections`, allowing for specified cross-user interactions. The ingestion process runs asynchronously, and its progress can be tracked using the returned `task_id`.

**Request (Multipart Form):**

| Parameter                 | Type     | Required | Description                                                          |
| :------------------------ | :------- | :------ | :------------------------------------------------------------------- |
| `file`                    | `string` | No      | The file to ingest. Exactly one of `file`, `raw_text`, or `chunks` must be provided. |
| `raw_text`                | `string` | No      | Raw text content to ingest. Exactly one of `file`, `raw_text`, or `chunks` must be provided. |
| `chunks`                  | `string` | No      | Pre-processed text chunks to ingest. Exactly one of `file`, `raw_text`, or `chunks` must be provided. |
| `id`                      | `string` | No      | Document ID. If omitted, a new ID will be generated.                 |
| `collection_ids`          | `string` | No      | Collection IDs to associate with the document. Defaults to the user’s default collection if not provided. |
| `metadata`                | `string` | No      | Metadata such as title, description, or custom fields in JSON format. |
| `ingestion_mode`          | `enum`   | No      | `hi-res`, `fast`, or `custom`.                                       |
| `ingestion_config`        | `string` | No      | Custom ingestion settings if `ingestion_mode` is `custom`.           |
| `run_with_orchestration`  | `boolean`| No      | Whether ingestion runs with orchestration. Default is `true`.         |

**Successful Response:**

```json
{
  "results": {
    "message": "Document ingestion started.",
    "document_id": "generated_document_id",
    "task_id": "ingestion_task_id"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/documents" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -F "file=@/path/to/document.pdf" \
     -F "metadata={\"title\": \"Sample Document\", \"description\": \"A sample document for ingestion.\"}"
```

---

#### 3. Retrieve a Document

```http
GET /v3/documents/:id
```

**Description:**
Retrieves detailed information about a specific document by its ID. This includes metadata and processing status. The document’s content is **not** returned here; use `/documents/{id}/download` to retrieve the file itself.

**Path Parameters:**

| Parameter | Type   | Required | Description                     |
| :-------- | :----- | :------ | :------------------------------ |
| `id`      | `string` | Yes      | The Document ID to retrieve.    |

**Successful Response:**

```json
{
  "results": {
    "id": "id",
    "collection_ids": ["collection_ids"],
    "owner_id": "owner_id",
    "document_type": "pdf",
    "metadata": { "key": "value" },
    "version": "version",
    "title": "title",
    "size_in_bytes": 1024,
    "ingestion_status": "success",
    "extraction_status": "enriched",
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-01-15T09:30:00Z",
    "ingestion_attempt_number": 1,
    "summary": "document summary",
    "summary_embedding": [1.1, 2.2, 3.3]
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/documents/document_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 4. Delete a Document

```http
DELETE /v3/documents/:id
```

**Description:**
Deletes a specific document, including its associated chunks and references. **Note:** This action does not currently affect the knowledge graph or other derived data.

**Path Parameters:**

| Parameter | Type   | Required | Description        |
| :-------- | :----- | :------ | :----------------- |
| `id`      | `string` | Yes      | The Document ID to delete. |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/documents/document_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 5. Delete Documents by Filter

```http
DELETE /v3/documents/by-filter
```

**Description:**
Deletes multiple documents based on provided filters. Only the user’s own documents can be deleted using this method.

**Request Body:**

A JSON object containing filter criteria using operators like `$eq`, `$neq`, `$gt`, `$gte`, `$lt`, `$lte`, `$like`, `$ilike`, `$in`, and `$nin`.

**Example Request Body:**

```json
{
  "filters": {
    "document_type": { "$eq": "pdf" },
    "size_in_bytes": { "$gte": 100000 }
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/documents/by-filter" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"filters": {"document_type": {"$eq": "pdf"}}}'
```

---

#### 6. List Document Chunks

```http
GET /v3/documents/:id/chunks
```

**Description:**
Retrieves the text chunks generated from a document during ingestion. Chunks represent semantic sections of the document and are used for retrieval and analysis.

**Path Parameters:**

| Parameter | Type   | Required | Description                          |
| :-------- | :----- | :------ | :----------------------------------- |
| `id`      | `string` | Yes      | The Document ID to retrieve chunks for. |

**Query Parameters:**

| Parameter         | Type      | Required | Description                                       |
| :---------------- | :-------- | :------ | :------------------------------------------------ |
| `offset`          | `integer` | No      | Number of chunks to skip. Defaults to `0`.        |
| `limit`           | `integer` | No      | Number of chunks to return (`1–100`). Defaults to `100`. |
| `include_vectors` | `boolean` | No      | Whether to include vector embeddings in the response (`true` or `false`). |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "chunk-id",
      "document_id": "document-id",
      "owner_id": "owner-id",
      "collection_ids": ["collection-id"],
      "text": "Chunk content",
      "metadata": { "key": "value" },
      "vector": [1.1, 2.2, 3.3]
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/documents/document_id/chunks?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 7. Download Document Content

```http
GET /v3/documents/:id/download
```

**Description:**
Downloads the original file content of a document. For uploaded files, it returns the file with its proper MIME type. For text-only documents, it returns the content as plain text.

**Path Parameters:**

| Parameter | Type   | Required | Description        |
| :-------- | :----- | :------ | :----------------- |
| `id`      | `string` | Yes      | The Document ID to download. |

**Successful Response:**

- Returns the file content with appropriate headers.

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/documents/document_id/download" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -o downloaded_document.pdf
```

---

#### 8. List Document Collections (Superuser Only)

```http
GET /v3/documents/:id/collections
```

**Description:**
Lists all collections containing the specified document. **Superuser only**.

**Path Parameters:**

| Parameter | Type   | Required | Description        |
| :-------- | :----- | :------ | :----------------- |
| `id`      | `string` | Yes      | The Document ID.    |

**Query Parameters:**

| Parameter | Type      | Required | Description                           |
| :-------- | :-------- | :------ | :------------------------------------ |
| `offset`  | `integer` | No      | Number of collections to skip. Defaults to `0`. |
| `limit`   | `integer` | No      | Number of collections to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "collection-id",
      "name": "Collection Name",
      "graph_cluster_status": "string",
      "graph_sync_status": "string",
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-01-15T09:30:00Z",
      "user_count": 10,
      "document_count": 50,
      "owner_id": "owner_id",
      "description": "A sample collection."
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/documents/document_id/collections" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 9. Extract Entities and Relationships

```http
POST /v3/documents/:id/extract
```

**Description:**
Extracts entities and relationships from a document for knowledge graph creation. This process involves parsing the document into chunks, extracting entities and relationships using LLMs, and storing them in the knowledge graph.

**Path Parameters:**

| Parameter | Type   | Required | Description                                                   |
| :-------- | :----- | :------ | :------------------------------------------------------------ |
| `id`      | `string` | Yes      | The Document ID to extract entities and relationships from.   |

**Query Parameters:**

| Parameter                  | Type     | Required | Description                                                                  |
| :------------------------- | :------- | :------ | :--------------------------------------------------------------------------- |
| `run_type`                 | `string` | No      | `"estimate"` or `"run"`. Determines whether to return an estimate or execute extraction. |
| `run_with_orchestration`   | `boolean`| No      | Whether to run the extraction process with orchestration. Defaults to `true`. |

**Request Body:**

An optional JSON object containing various extraction settings.

| Parameter                          | Type     | Required | Description                                                   |
| :---------------------------------- | :------- | :------ | :------------------------------------------------------------ |
| `graph_extraction` | `string` | No | The prompt to use for knowledge graph extraction. Defaults to `graph_extraction`. |
| `graph_entity_description_prompt` | `string` | No | The prompt to use for entity description generation. Defaults to `graph_entity_description`. |
| `entity_types`                     | `array`  | No       | The types of entities to extract.                            |
| `relation_types`                   | `array`  | No       | The types of relations to extract.                           |
| `chunk_merge_count`                | `integer`| No       | Number of extractions to merge into a single KG extraction. Defaults to `4`. |
| `max_knowledge_relationships`      | `integer`| No       | Maximum number of knowledge relationships to extract from each chunk. Defaults to `100`. |
| `max_description_input_length`     | `integer`| No       | Maximum length of the description for a node in the graph. Defaults to `65536`. |
| `generation_config`                | `object` | No       | Configuration for text generation during graph enrichment.    |
| `model`                            | `string` | No       | Model to use for text generation.                            |
| `temperature`                      | `double` | No       | Temperature setting for generation.                         |
| `top_p`                            | `double` | No       | Top-p setting for generation.                               |
| `max_tokens_to_sample`             | `integer`| No       | Maximum tokens to sample during generation.                 |
| `stream`                           | `boolean`| No       | Whether to stream the generation output.                    |
| `functions`                        | `array`  | No       | List of functions for generation.                           |
| `tools`                            | `array`  | No       | List of tools for generation.                               |
| `add_generation_kwargs`            | `object` | No       | Additional generation keyword arguments.                    |
| `api_base`                         | `string` | No       | API base URL for generation.                                |
| `response_format`                  | `object` | No       | Response format configuration.                              |
| `graphrag_map_system`              | `string` | No       | System prompt for graphrag map prompt. Defaults to `graphrag_map_system`. |
| `graphrag_reduce_system`            | `string` | No       | System prompt for graphrag reduce prompt. Defaults to `graphrag_reduce_system`. |
| `max_community_description_length` | `integer`| No       | Maximum community description length. Defaults to `65536`.   |
| `max_llm_queries_for_global_search`| `integer`| No       | Maximum LLM queries for global search. Defaults to `250`.    |
| `limits`                           | `object` | No       | Limits for graph search.                                    |
| `enabled`                          | `boolean`| No       | Whether to enable graph search.                             |
| `rag_generation_config`            | `object` | No       | Configuration for RAG generation.                           |
| `task_prompt_override`             | `string` | No       | Optional custom prompt to override default.                 |
| `include_title_if_available`       | `boolean`| No       | Include document titles in responses when available.        |

**Example Request Body:**

```json
{
  "run_type": "run",
  "settings": {
    "entity_types": ["Person", "Location"],
    "relation_types": ["BornIn", "WorksAt"],
    "chunk_merge_count": 5,
    "max_knowledge_relationships": 150,
    "generation_config": {
      "model": "gpt-4",
      "temperature": 0.7,
      "top_p": 0.9,
      "max_tokens_to_sample": 100,
      "stream": false
    }
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Entity and relationship extraction started."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/documents/document_id/extract" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "run_type": "run",
           "settings": {
             "entity_types": ["Person", "Location"],
             "relation_types": ["BornIn", "WorksAt"],
             "chunk_merge_count": 5,
             "max_knowledge_relationships": 150
           }
         }'
```

---

#### 10. Get Document Entities

```http
GET /v3/documents/:id/entities
```

**Description:**
Retrieves entities extracted from the specified document.

**Path Parameters:**

| Parameter | Type   | Required | Description                |
| :-------- | :----- | :------ | :------------------------- |
| `id`      | `string` | Yes      | The Document ID.           |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "entity_id",
      "name": "Entity Name",
      "description": "Entity Description",
      "category": "Category",
      "metadata": { "key": "value" },
      "description_embedding": [1.2, 3.4, 5.6],
      "chunk_ids": ["chunk_id1", "chunk_id2"],
      "parent_id": "parent_entity_id"
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/documents/document_id/entities" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 11. Get Document Relationships

```http
GET /v3/documents/:id/relationships
```

**Description:**
Retrieves relationships extracted from the specified document.

**Path Parameters:**

| Parameter | Type   | Required | Description                |
| :-------- | :----- | :------ | :------------------------- |
| `id`      | `string` | Yes      | The Document ID.           |

**Successful Response:**

```json
{
  "results": [
    {
      "subject": "John Doe",
      "predicate": "WorksAt",
      "object": "OpenAI",
      "id": "relationship_id",
      "description": "John Doe works at OpenAI.",
      "subject_id": "entity_id1",
      "object_id": "entity_id2",
      "weight": 1.1,
      "chunk_ids": ["chunk_id1", "chunk_id2"],
      "parent_id": "parent_relationship_id",
      "description_embedding": [1.1, 2.2, 3.3],
      "metadata": { "department": "Research" }
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/documents/document_id/relationships" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Chunks

### Overview

A **Chunk** in R2R represents a processed segment of text derived from a parent Document. Chunks are optimized for semantic retrieval, knowledge graph construction, and vector-based operations. Each chunk contains text content, metadata, and optional vector embeddings, facilitating efficient search and analysis.

### Core Features of Chunks

1. **Semantic Retrieval & Search**
    - Enables semantic similarity searches across document contents.
    - Supports vector-based retrieval methods.

2. **Knowledge Graph Integration**
    - Serves as the basis for extracting and linking Entities and Relationships.
    - Facilitates retrieval-augmented generation (RAG) operations.

3. **Metadata Management**
    - Stores additional information and custom fields for enhanced filtering and organization.

### Available Endpoints

| Method | Endpoint                     | Description                                                           |
| :---- | :--------------------------- | :-------------------------------------------------------------------- |
| GET    | `/chunks`                   | List chunks with pagination and filtering options                     |
| POST   | `/chunks/search`            | Perform semantic search across chunks with complex filtering          |
| GET    | `/chunks/{id}`              | Retrieve a specific chunk by ID                                       |
| POST   | `/chunks/{id}`              | Update an existing chunk’s content or metadata                        |
| DELETE | `/chunks/{id}`              | Delete a specific chunk                                               |

### Endpoint Details

#### 1. List Chunks

```http
GET /v3/chunks
```

**Description:**
Lists chunks with pagination, optionally filtering by metadata or including vectors.

**Query Parameters:**

| Parameter         | Type      | Required | Description                                      |
| :---------------- | :-------- | :------ | :----------------------------------------------- |
| `metadata_filter`  | `string` | No      | Filter chunks based on metadata fields.          |
| `include_vectors`  | `boolean`| No      | Include vector embeddings in the response (`true` or `false`). |
| `offset`           | `integer`| No      | Number of chunks to skip. Defaults to `0`.        |
| `limit`            | `integer`| No      | Number of chunks to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "id",
      "document_id": "document_id",
      "owner_id": "owner_id",
      "collection_ids": ["collection_ids"],
      "text": "text",
      "metadata": { "key": "value" },
      "vector": [1.1, 2.2, 3.3]
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/chunks?limit=10&include_vectors=true" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Search Chunks

```http
POST /v3/chunks/search
```

**Description:**
Performs a semantic search query over all stored chunks. This endpoint allows for complex filtering of search results using PostgreSQL-based queries, supporting various operators and advanced search configurations.

**Allowed Operators:**

- `eq`: Equals
- `neq`: Not equals
- `gt`: Greater than
- `gte`: Greater than or equal
- `lt`: Less than
- `lte`: Less than or equal
- `like`: Pattern matching
- `ilike`: Case-insensitive pattern matching
- `in`: In list
- `nin`: Not in list

**Request Body:**

A JSON object containing the search query and optional search settings.

**Example Request Body:**

```json
{
  "query": "Find documents related to machine learning",
  "search_settings": {
    "use_semantic_search": true,
    "filters": {
      "document_type": { "$eq": "pdf" }
    },
    "limit": 20
  }
}
```

**Successful Response:**

```json
{
  "results": [
    {
      "id": "chunk-id",
      "document_id": "document_id",
      "collection_ids": ["collection_id1", "collection_id2"],
      "score": 0.95,
      "text": "Relevant chunk text.",
      "metadata": { "title": "example.pdf" },
      "owner_id": "owner_id"
    }
  ]
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/chunks/search" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "query": "machine learning",
           "search_settings": {
             "use_semantic_search": true,
             "filters": { "document_type": { "$eq": "pdf" } },
             "limit": 10
           }
         }'
```

---

#### 3. Retrieve a Chunk

```http
GET /v3/chunks/:id
```

**Description:**
Retrieves a specific chunk by its ID, including its content, metadata, and associated document/collection information.

**Path Parameters:**

| Parameter | Type   | Required | Description           |
| :-------- | :----- | :------ | :-------------------- |
| `id`      | `string` | Yes      | The Chunk ID to retrieve. |

**Successful Response:**

```json
{
  "results": {
    "id": "chunk-id",
    "document_id": "document-id",
    "owner_id": "owner-id",
    "collection_ids": ["collection-id"],
    "text": "Chunk content",
    "metadata": { "key": "value" },
    "vector": [1.1, 2.2, 3.3]
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/chunks/chunk_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 4. Update Chunk

```http
POST /v3/chunks/:id
```

**Description:**
Updates an existing chunk’s content and/or metadata. Upon updating, the chunk’s vectors are automatically recomputed based on the new content.

**Path Parameters:**

| Parameter | Type   | Required | Description           |
| :-------- | :----- | :------ | :-------------------- |
| `id`      | `string` | Yes      | The Chunk ID to update. |

**Request Body:**

A JSON object containing the updated chunk details.

**Example Request Body:**

```json
{
  "id": "chunk-id",
  "text": "Updated chunk content.",
  "metadata": { "newKey": "newValue" }
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "chunk-id",
    "document_id": "document-id",
    "owner_id": "owner-id",
    "collection_ids": ["collection-id"],
    "text": "Updated chunk content.",
    "metadata": { "newKey": "newValue" },
    "vector": [4.4, 5.5, 6.6]
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/chunks/chunk_id" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "id": "chunk_id",
           "text": "Updated chunk content.",
           "metadata": { "newKey": "newValue" }
         }'
```

---

#### 5. Delete Chunk

```http
DELETE /v3/chunks/:id
```

**Description:**
Deletes a specific chunk by its ID. The parent document remains intact.

**Path Parameters:**

| Parameter | Type   | Required | Description           |
| :-------- | :----- | :------ | :-------------------- |
| `id`      | `string` | Yes      | The Chunk ID to delete. |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/chunks/chunk_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Graphs

### Overview

A **Graph** in R2R is a knowledge graph associated with a specific **Collection**. It comprises **Entities**, **Relationships**, and **Communities** (groupings of related entities). Graphs facilitate the organization and retrieval of interconnected information, enabling advanced data analysis and exploration.

### Core Features of Graphs

1. **Git-like Model**
    - Each Collection has an associated Graph that can diverge independently.
    - The `pull` operation syncs document knowledge into the graph.
    - Changes can be experimental without affecting the base Collection and underlying documents.

2. **Knowledge Organization**
    - Automatic entity and relationship extraction from documents.
    - Community detection for hierarchical knowledge organization.
    - Support for manual creation and editing of entities, relationships, and communities.
    - Rich metadata and property management.

3. **Access Control**
    - Graph operations are tied to Collection permissions.
    - Superuser privileges required for certain operations like community building.
    - Document-level access checks when pulling content.

### Available Endpoints

| Method | Endpoint                                 | Description                                  |
| :---- | :--------------------------------------- | :------------------------------------------- |
| GET    | `/graphs/{collection_id}`                | Get graph details                           |
| POST   | `/graphs/{collection_id}/pull`           | Sync documents with graph                   |
| POST   | `/graphs/{collection_id}/communities/build` | Build graph communities                 |
| POST   | `/graphs/{collection_id}/reset`          | Reset graph to initial state                |
| GET    | `/graphs/{collection_id}/entities`                 | List entities                                |
| POST   | `/graphs/{collection_id}/entities`                 | Create entity                                |
| GET    | `/graphs/{collection_id}/entities/{entity_id}`     | Get entity                                   |
| POST   | `/graphs/{collection_id}/entities/{entity_id}`     | Update entity                                |
| DELETE | `/graphs/{collection_id}/entities/{entity_id}`     | Delete entity                                |
| GET    | `/graphs/{collection_id}/relationships`            | List relationships                           |
| POST   | `/graphs/{collection_id}/relationships`            | Create relationship                          |
| GET    | `/graphs/{collection_id}/relationships/{relationship_id}` | Get relationship                     |
| POST   | `/graphs/{collection_id}/relationships/{relationship_id}` | Update relationship                  |
| DELETE | `/graphs/{collection_id}/relationships/{relationship_id}` | Delete relationship                  |
| GET    | `/graphs/{collection_id}/communities`               | List communities                             |
| POST   | `/graphs/{collection_id}/communities`               | Create community                             |
| GET    | `/graphs/{collection_id}/communities/{community_id}` | Get community                            |
| POST   | `/graphs/{collection_id}/communities/{community_id}` | Update community                       |
| DELETE | `/graphs/{collection_id}/communities/{community_id}` | Delete community                       |

### Endpoint Details

#### 1. List Graphs

```http
GET /v3/graphs
```

**Description:**
Returns a paginated list of graphs accessible to the authenticated user. Filter by `collection_ids` if needed. Regular users see only their own collections' graphs, while superusers see all graphs.

**Query Parameters:**

| Parameter        | Type     | Required | Description                    |
| :--------------- | :------- | :------ | :----------------------------- |
| `collection_ids` | `string` | No      | Comma-separated list of collection IDs to filter graphs. |
| `offset`         | `integer`| No      | Number of graphs to skip. Defaults to `0`. |
| `limit`          | `integer`| No      | Number of graphs to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "id",
      "collection_id": "collection_id",
      "name": "graph_name",
      "status": "status",
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-01-15T09:30:00Z",
      "document_ids": ["document_ids"],
      "description": "description"
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/graphs?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Retrieve Graph Details

```http
GET /v3/graphs/:collection_id
```

**Description:**
Retrieves detailed information about a specific graph associated with a collection.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Successful Response:**

```json
{
  "results": {
    "id": "id",
    "collection_id": "collection_id",
    "name": "name",
    "status": "status",
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-01-15T09:30:00Z",
    "document_ids": ["document_ids"],
    "description": "description"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/graphs/collection_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 3. Update Graph

```http
POST /v3/graphs/:collection_id
```

**Description:**
Updates the configuration of a specific graph, including its name and description.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Request Body:**

A JSON object containing the updated graph details.

**Example Request Body:**

```json
{
  "name": "new-name",
  "description": "updated description"
}
```

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/graphs/collection_id" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "new-name",
           "description": "updated description"
         }'
```

---

#### 4. Reset Graph

```http
POST /v3/graphs/:collection_id/reset
```

**Description:**
Resets the graph to its initial state by deleting all associated data. This action does **not** delete the underlying source documents.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/graphs/collection_id/reset" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 5. Pull Latest Entities to Graph

```http
POST /v3/graphs/:collection_id/pull
```

**Description:**
Synchronizes document entities and relationships into the graph, ensuring the graph reflects the latest document data.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Request Body:**

Optional boolean parameters to control the pull operation.

**Example Request Body:**

```json
{
  "force": true
}
```

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/graphs/collection_id/pull" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -d '{"force": true}'
```

---

## Entities

### Overview

**Entities** are the fundamental building blocks of a knowledge graph in R2R. They represent distinct concepts, objects, or individuals extracted from documents. Entities are linked through **Relationships**, forming a comprehensive network of interconnected information.

### Core Features of Entities

1. **Extraction & Creation**
    - Automatically extracted from document chunks.
    - Manual creation and editing through API endpoints.

2. **Metadata Management**
    - Stores detailed metadata for each entity.
    - Supports categorization and classification.

3. **Relationship Linking**
    - Connected to other entities via Relationships.
    - Facilitates multi-hop traversal and semantic queries.

### Available Endpoints

| Method | Endpoint                                   | Description                           |
| :---- | :----------------------------------------- | :------------------------------------ |
| GET    | `/graphs/{collection_id}/entities`         | List entities                         |
| POST   | `/graphs/{collection_id}/entities`         | Create entity                         |
| GET    | `/graphs/{collection_id}/entities/{entity_id}` | Get entity                      |
| POST   | `/graphs/{collection_id}/entities/{entity_id}` | Update entity                  |
| DELETE | `/graphs/{collection_id}/entities/{entity_id}` | Delete entity                  |

### Endpoint Details

#### 1. List Entities in a Graph

```http
GET /v3/graphs/:collection_id/entities
```

**Description:**
Lists all entities within a specific graph, supporting pagination.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Query Parameters:**

| Parameter | Type      | Required | Description                    |
| :-------- | :-------- | :------ | :----------------------------- |
| `offset`  | `integer` | No      | Number of entities to skip. Defaults to `0`. |
| `limit`   | `integer` | No      | Number of entities to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "entity_id",
      "name": "Entity Name",
      "description": "Entity Description",
      "category": "Category",
      "metadata": { "key": "value" },
      "description_embedding": [1.2, 3.4, 5.6],
      "chunk_ids": ["chunk_id1", "chunk_id2"],
      "parent_id": "parent_entity_id"
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/graphs/collection_id/entities?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Create Entity in Graph

```http
POST /v3/graphs/:collection_id/entities
```

**Description:**
Creates a new entity within a specified graph.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Request Body:**

A JSON object containing the details of the entity to be created.

**Example Request Body:**

```json
{
  "name": "John Doe",
  "description": "A software engineer.",
  "category": "Person",
  "metadata": {
    "role": "Developer"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "entity_id",
    "name": "John Doe",
    "description": "A software engineer.",
    "category": "Person",
    "metadata": {
      "role": "Developer"
    },
    "description_embedding": [1.2, 3.4, 5.6],
    "chunk_ids": ["chunk_id1", "chunk_id2"],
    "parent_id": "parent_entity_id"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/graphs/collection_id/entities" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "John Doe",
           "description": "A software engineer.",
           "category": "Person",
           "metadata": { "role": "Developer" }
         }'
```

---

#### 3. Get Entity

```http
GET /v3/graphs/:collection_id/entities/:entity_id
```

**Description:**
Retrieves detailed information about a specific entity within a graph.

**Path Parameters:**

| Parameter      | Type   | Required | Description                                |
| :------------- | :----- | :------ | :----------------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |
| `entity_id`     | `string` | Yes      | The Entity ID to retrieve.                  |

**Successful Response:**

```json
{
  "results": {
    "id": "entity_id",
    "name": "John Doe",
    "description": "A software engineer.",
    "category": "Person",
    "metadata": {
      "role": "Developer"
    },
    "description_embedding": [1.2, 3.4, 5.6],
    "chunk_ids": ["chunk_id1", "chunk_id2"],
    "parent_id": "parent_entity_id"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/graphs/collection_id/entities/entity_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 4. Update Entity

```http
POST /v3/graphs/:collection_id/entities/:entity_id
```

**Description:**
Updates the details of an existing entity within a graph.

**Path Parameters:**

| Parameter      | Type   | Required | Description                                |
| :------------- | :----- | :------ | :----------------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |
| `entity_id`     | `string` | Yes      | The Entity ID to update.                   |

**Request Body:**

A JSON object containing the updated details of the entity.

**Example Request Body:**

```json
{
  "name": "Jane Doe",
  "description": "A senior software engineer.",
  "category": "Person",
  "metadata": {
    "role": "Lead Developer"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "entity_id",
    "name": "Jane Doe",
    "description": "A senior software engineer.",
    "category": "Person",
    "metadata": {
      "role": "Lead Developer"
    },
    "description_embedding": [2.3, 4.5, 6.7],
    "chunk_ids": ["chunk_id3", "chunk_id4"],
    "parent_id": "parent_entity_id"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/graphs/collection_id/entities/entity_id" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "Jane Doe",
           "description": "A senior software engineer.",
           "category": "Person",
           "metadata": { "role": "Lead Developer" }
         }'
```

---

#### 5. Delete Entity

```http
DELETE /v3/graphs/:collection_id/entities/:entity_id
```

**Description:**
Deletes a specific entity from the graph.

**Path Parameters:**

| Parameter      | Type   | Required | Description                                |
| :------------- | :----- | :------ | :----------------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |
| `entity_id`     | `string` | Yes      | The Entity ID to delete.                   |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/graphs/collection_id/entities/entity_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Relationships

### Overview

**Relationships** define the connections between **Entities** within a graph, establishing how different entities relate to one another. They are pivotal for understanding the structure and interconnections within your knowledge graph, enabling complex queries and insights.

### Core Features of Relationships

1. **Connection Building**
    - Links between entities to represent interactions, hierarchies, or associations.

2. **Metadata and Weighting**
    - Stores additional information and weightings to signify the strength or importance of the relationship.

3. **Semantic Navigation**
    - Facilitates multi-hop traversal and semantic queries within the graph.

### Available Endpoints

| Method | Endpoint                                      | Description                                    |
| :---- | :-------------------------------------------- | :--------------------------------------------- |
| GET    | `/graphs/{collection_id}/relationships`       | List relationships                            |
| POST   | `/graphs/{collection_id}/relationships`       | Create relationship                           |
| GET    | `/graphs/{collection_id}/relationships/{relationship_id}` | Get relationship                  |
| POST   | `/graphs/{collection_id}/relationships/{relationship_id}` | Update relationship           |
| DELETE | `/graphs/{collection_id}/relationships/{relationship_id}` | Delete relationship           |

### Endpoint Details

#### 1. List Relationships

```http
GET /v3/graphs/:collection_id/relationships
```

**Description:**
Lists all relationships within a specific graph, supporting pagination.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Query Parameters:**

| Parameter | Type      | Required | Description                    |
| :-------- | :-------- | :------ | :----------------------------- |
| `offset`  | `integer` | No      | Number of relationships to skip. Defaults to `0`. |
| `limit`   | `integer` | No      | Number of relationships to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "subject": "John Doe",
      "predicate": "WorksAt",
      "object": "OpenAI",
      "id": "relationship_id",
      "description": "John Doe works at OpenAI.",
      "subject_id": "entity_id1",
      "object_id": "entity_id2",
      "weight": 1.1,
      "chunk_ids": ["chunk_id1", "chunk_id2"],
      "parent_id": "parent_relationship_id",
      "description_embedding": [1.1, 2.2, 3.3],
      "metadata": { "department": "Research" }
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/graphs/collection_id/relationships?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Create Relationship

```http
POST /v3/graphs/:collection_id/relationships
```

**Description:**
Creates a new relationship within a specified graph, linking two entities.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Request Body:**

A JSON object containing the details of the relationship to be created.

**Example Request Body:**

```json
{
  "subject": "John Doe",
  "subject_id": "entity_id1",
  "predicate": "WorksAt",
  "object": "OpenAI",
  "object_id": "entity_id2",
  "description": "John Doe works at OpenAI.",
  "weight": 1.1,
  "metadata": {
    "department": "Research"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "subject": "John Doe",
    "predicate": "WorksAt",
    "object": "OpenAI",
    "id": "relationship_id",
    "description": "John Doe works at OpenAI.",
    "subject_id": "entity_id1",
    "object_id": "entity_id2",
    "weight": 1.1,
    "chunk_ids": ["chunk_id1", "chunk_id2"],
    "parent_id": "parent_relationship_id",
    "description_embedding": [1.1, 2.2, 3.3],
    "metadata": {
      "department": "Research"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/graphs/collection_id/relationships" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "subject": "John Doe",
           "subject_id": "entity_id1",
           "predicate": "WorksAt",
           "object": "OpenAI",
           "object_id": "entity_id2",
           "description": "John Doe works at OpenAI.",
           "weight": 1.1,
           "metadata": { "department": "Research" }
         }'
```

---

#### 3. Get Relationship

```http
GET /v3/graphs/:collection_id/relationships/:relationship_id
```

**Description:**
Retrieves detailed information about a specific relationship within a graph.

**Path Parameters:**

| Parameter          | Type   | Required | Description                                |
| :----------------- | :----- | :------ | :----------------------------------------- |
| `collection_id`    | `string` | Yes      | The Collection ID associated with the graph. |
| `relationship_id`  | `string` | Yes      | The Relationship ID to retrieve.           |

**Successful Response:**

```json
{
  "results": {
    "subject": "John Doe",
    "predicate": "WorksAt",
    "object": "OpenAI",
    "id": "relationship_id",
    "description": "John Doe works at OpenAI.",
    "subject_id": "entity_id1",
    "object_id": "entity_id2",
    "weight": 1.1,
    "chunk_ids": ["chunk_id1", "chunk_id2"],
    "parent_id": "parent_relationship_id",
    "description_embedding": [1.1, 2.2, 3.3],
    "metadata": {
      "department": "Research"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/graphs/collection_id/relationships/relationship_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 4. Update Relationship

```http
POST /v3/graphs/:collection_id/relationships/:relationship_id
```

**Description:**
Updates the details of an existing relationship within a graph.

**Path Parameters:**

| Parameter          | Type   | Required | Description                                |
| :----------------- | :----- | :------ | :----------------------------------------- |
| `collection_id`    | `string` | Yes      | The Collection ID associated with the graph. |
| `relationship_id`  | `string` | Yes      | The Relationship ID to update.             |

**Request Body:**

A JSON object containing the updated details of the relationship.

**Example Request Body:**

```json
{
  "subject": "Jane Doe",
  "subject_id": "entity_id3",
  "predicate": "CollaboratesWith",
  "object": "OpenAI Research",
  "object_id": "entity_id4",
  "description": "Jane Doe collaborates with OpenAI Research.",
  "weight": 2.0,
  "metadata": {
    "project": "AI Development"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "subject": "Jane Doe",
    "predicate": "CollaboratesWith",
    "object": "OpenAI Research",
    "id": "relationship_id",
    "description": "Jane Doe collaborates with OpenAI Research.",
    "subject_id": "entity_id3",
    "object_id": "entity_id4",
    "weight": 2.0,
    "chunk_ids": ["chunk_id3", "chunk_id4"],
    "parent_id": "parent_relationship_id",
    "description_embedding": [2.2, 4.4, 6.6],
    "metadata": {
      "project": "AI Development"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/graphs/collection_id/relationships/relationship_id" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "subject": "Jane Doe",
           "subject_id": "entity_id3",
           "predicate": "CollaboratesWith",
           "object": "OpenAI Research",
           "object_id": "entity_id4",
           "description": "Jane Doe collaborates with OpenAI Research.",
           "weight": 2.0,
           "metadata": { "project": "AI Development" }
         }'
```

---

#### 5. Delete Relationship

```http
DELETE /v3/graphs/:collection_id/relationships/:relationship_id
```

**Description:**
Deletes a specific relationship from the graph.

**Path Parameters:**

| Parameter          | Type   | Required | Description                                |
| :----------------- | :----- | :------ | :----------------------------------------- |
| `collection_id`    | `string` | Yes      | The Collection ID associated with the graph. |
| `relationship_id`  | `string` | Yes      | The Relationship ID to delete.             |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/graphs/collection_id/relationships/relationship_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Communities

### Overview

**Communities** are clusters of related **Entities** within a graph, representing groupings of interconnected information. They are generated through clustering algorithms and can be manually managed to reflect domain-specific knowledge structures.

### Core Features of Communities

1. **Automatic Generation**
    - Built using clustering algorithms based on entity relationships and similarities.

2. **Manual Management**
    - Allows manual creation, editing, and deletion of communities to reflect specific organizational needs.

3. **Hierarchical Organization**
    - Supports hierarchical structures, enabling nested communities for detailed knowledge organization.

4. **Metadata Integration**
    - Stores metadata and descriptions for each community, facilitating better understanding and navigation.

### Available Endpoints

| Method | Endpoint                                      | Description                                         |
| :---- | :-------------------------------------------- | :-------------------------------------------------- |
| POST   | `/graphs/{collection_id}/communities/build`   | Build communities from existing graph data          |
| GET    | `/graphs/{collection_id}/communities`         | List communities                                    |
| POST   | `/graphs/{collection_id}/communities`         | Create community                                    |
| GET    | `/graphs/{collection_id}/communities/{community_id}` | Get community                             |
| POST   | `/graphs/{collection_id}/communities/{community_id}` | Update community                        |
| DELETE | `/graphs/{collection_id}/communities/{community_id}` | Delete community                        |

### Endpoint Details

#### 1. Build Communities

```http
POST /v3/graphs/:collection_id/communities/build
```

**Description:**
Builds communities within the graph by analyzing entity relationships and similarities. This process utilizes clustering algorithms to identify and group related entities.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Request Body:**

A JSON object containing settings for the community building process.

**Example Request Body:**

```json
{
  "run_type": "run",
  "graph_enrichment_settings": {
    "algorithm": "Leiden",
    "parameters": {
      "resolution": 1.0
    }
  },
  "run_with_orchestration": true
}
```

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/graphs/collection_id/communities/build" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "run_type": "run",
           "graph_enrichment_settings": { "algorithm": "Leiden", "parameters": { "resolution": 1.0 } },
           "run_with_orchestration": true
         }'
```

---

#### 2. List Communities

```http
GET /v3/graphs/:collection_id/communities
```

**Description:**
Lists all communities within a specific graph, supporting pagination.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Query Parameters:**

| Parameter | Type      | Required | Description                    |
| :-------- | :-------- | :------ | :----------------------------- |
| `offset`  | `integer` | No      | Number of communities to skip. Defaults to `0`. |
| `limit`   | `integer` | No      | Number of communities to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "name": "AI Researchers",
      "summary": "Community of AI researchers focused on machine learning.",
      "level": 1,
      "findings": ["Research papers", "Collaborative projects"],
      "id": 1,
      "community_id": "community_id",
      "collection_id": "collection_id",
      "rating": 9.5,
      "rating_explanation": "High engagement and output.",
      "description_embedding": [2.2, 4.4, 6.6],
      "attributes": { "key": "value" },
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-01-15T09:30:00Z"
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/graphs/collection_id/communities?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 3. Create Community

```http
POST /v3/graphs/:collection_id/communities
```

**Description:**
Creates a new community within a graph. While communities are typically built automatically via the `/communities/build` endpoint, this endpoint allows for manual creation to reflect specific organizational needs.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |

**Request Body:**

A JSON object containing the details of the community to be created.

**Example Request Body:**

```json
{
  "name": "AI Researchers",
  "summary": "Community of AI researchers focused on machine learning.",
  "findings": ["Research papers", "Collaborative projects"],
  "rating": 9.5,
  "rating_explanation": "High engagement and output."
}
```

**Successful Response:**

```json
{
  "results": {
    "name": "AI Researchers",
    "summary": "Community of AI researchers focused on machine learning.",
    "level": 1,
    "findings": ["Research papers", "Collaborative projects"],
    "id": 1,
    "community_id": "community_id",
    "collection_id": "collection_id",
    "rating": 9.5,
    "rating_explanation": "High engagement and output.",
    "description_embedding": [2.2, 4.4, 6.6],
    "attributes": { "key": "value" },
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-01-15T09:30:00Z"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/graphs/collection_id/communities" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "AI Researchers",
           "summary": "Community of AI researchers focused on machine learning.",
           "findings": ["Research papers", "Collaborative projects"],
           "rating": 9.5,
           "rating_explanation": "High engagement and output."
         }'
```

---

#### 4. Get Community

```http
GET /v3/graphs/:collection_id/communities/:community_id
```

**Description:**
Retrieves detailed information about a specific community within a graph.

**Path Parameters:**

| Parameter      | Type   | Required | Description                                |
| :------------- | :----- | :------ | :----------------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |
| `community_id` | `string` | Yes      | The Community ID to retrieve.              |

**Successful Response:**

```json
{
  "results": {
    "name": "AI Researchers",
    "summary": "Community of AI researchers focused on machine learning.",
    "level": 1,
    "findings": ["Research papers", "Collaborative projects"],
    "id": 1,
    "community_id": "community_id",
    "collection_id": "collection_id",
    "rating": 9.5,
    "rating_explanation": "High engagement and output.",
    "description_embedding": [2.2, 4.4, 6.6],
    "attributes": { "key": "value" },
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-02-20T10:45:00Z"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/graphs/collection_id/communities/community_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 5. Update Community

```http
POST /v3/graphs/:collection_id/communities/:community_id
```

**Description:**
Updates the details of an existing community within a graph.

**Path Parameters:**

| Parameter      | Type   | Required | Description                                |
| :------------- | :----- | :------ | :----------------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |
| `community_id` | `string` | Yes      | The Community ID to update.                |

**Request Body:**

A JSON object containing the updated details of the community.

**Example Request Body:**

```json
{
  "name": "Senior AI Researchers",
  "summary": "Community of senior AI researchers with a focus on deep learning.",
  "findings": ["Advanced research papers", "International collaborations"],
  "rating": 9.8,
  "rating_explanation": "Exceptional contribution and leadership."
}
```

**Successful Response:**

```json
{
  "results": {
    "name": "Senior AI Researchers",
    "summary": "Community of senior AI researchers with a focus on deep learning.",
    "level": 2,
    "findings": ["Advanced research papers", "International collaborations"],
    "id": 1,
    "community_id": "community_id",
    "collection_id": "collection_id",
    "rating": 9.8,
    "rating_explanation": "Exceptional contribution and leadership.",
    "description_embedding": [3.3, 6.6, 9.9],
    "attributes": { "key": "new_value" },
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-02-20T10:45:00Z"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/graphs/collection_id/communities/community_id" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "Senior AI Researchers",
           "summary": "Community of senior AI researchers with a focus on deep learning.",
           "findings": ["Advanced research papers", "International collaborations"],
           "rating": 9.8,
           "rating_explanation": "Exceptional contribution and leadership."
         }'
```

---

#### 6. Delete Community

```http
DELETE /v3/graphs/:collection_id/communities/:community_id
```

**Description:**
Deletes a specific community from the graph.

**Path Parameters:**

| Parameter      | Type   | Required | Description                                |
| :------------- | :----- | :------ | :----------------------------------------- |
| `collection_id`| `string` | Yes      | The Collection ID associated with the graph. |
| `community_id` | `string` | Yes      | The Community ID to delete.                |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/graphs/collection_id/communities/community_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Retrieval

### Overview

R2R’s **Retrieval** system offers advanced search and generation capabilities powered by vector search, knowledge graphs, and large language models (LLMs). The system provides multiple ways to interact with your data, including:

- **Semantic Search**: Direct semantic similarity searches across documents and chunks.
- **Retrieval-Augmented Generation (RAG)**: Combines retrieval with language model generation to produce informative responses grounded in your content.
- **Conversational Agents**: Multi-turn conversational interfaces powered by RAG for complex queries.
- **Completions**: Direct access to language model generation without retrieval.
- **Embeddings**: Generate vector embeddings for provided text.

### Core Features of Retrieval

1. **Vector Search**
    - Semantic similarity matching using document/chunk embeddings.
    - Hybrid search combining vector and keyword approaches.
    - Complex filtering with Postgres-style operators.
    - Configurable search limits and thresholds.

2. **Knowledge Graph Search**
    - Entity and relationship-based retrieval.
    - Multi-hop traversal for connected information.
    - Local and global search strategies.
    - Community-aware knowledge structures.

3. **RAG Generation**
    - Context-aware responses using retrieved content.
    - Customizable generation parameters.
    - Source attribution and citations.
    - Streaming support for real-time responses.

4. **RAG Agent**
    - Multi-turn conversational capabilities.
    - Complex query decomposition.
    - Context maintenance across interactions.
    - Branch management for conversation trees.

5. **Completion**
    - Direct access to language model generation capabilities.
    - Supports both single-turn and multi-turn conversations.

6. **Embeddings**
    - Generate numerical embedding vectors for provided text using specified models.

### Available Endpoints

| Method | Endpoint                  | Description                                                                               |
| :---- | :------------------------ | :---------------------------------------------------------------------------------------- |
| POST   | `/retrieval/search`     | Perform semantic/hybrid/graph search.                                                     |
| POST   | `/retrieval/rag`        | Generate RAG-based responses.                                                             |
| POST   | `/retrieval/agent`      | Engage a RAG-powered conversational agent.                                                |
| POST   | `/retrieval/completion` | Generate text completions using a language model.                                         |
| POST   | `/retrieval/embedding`  | Generate embeddings for the provided text using a specified model.                        |

### Endpoint Details

#### 1. Search R2R

```http
POST /v3/retrieval/search
```

**Description:**
Performs a search query against vector and/or graph-based databases, supporting various search modes and complex filtering.

**Search Modes:**

- `basic`: Defaults to semantic search. Simple and easy to use.
- `advanced`: Combines semantic search with full-text search for more comprehensive results.
- `custom`: Complete control over how search is performed. Provide a full `SearchSettings` object.

**Note:**
If `filters` or `limit` are provided alongside `basic` or `advanced`, they will override the default settings for that mode.

**Allowed Operators:**

- `eq`: Equals
- `neq`: Not equals
- `gt`: Greater than
- `gte`: Greater than or equal
- `lt`: Less than
- `lte`: Less than or equal
- `like`: Pattern matching
- `ilike`: Case-insensitive pattern matching
- `in`: In list
- `nin`: Not in list

**Request Body:**

A JSON object containing the search query and optional search settings.

**Example Request Body:**

```json
{
  "query": "machine learning advancements",
  "search_mode": "advanced",
  "search_settings": {
    "use_semantic_search": true,
    "use_fulltext_search": true,
    "filters": { "document_type": { "$eq": "pdf" } },
    "limit": 20
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "chunk_search_results": [
      {
        "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
        "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
        "collection_ids": ["collection_id1"],
        "score": 0.23943702876567796,
        "text": "Example text from the document",
        "metadata": {
          "associated_query": "What is the capital of France?",
          "title": "example_document.pdf"
        },
        "owner_id": "2acb499e-8428-543b-bd85-0d9098718220"
      }
    ],
    "graph_search_results": [
      {
        "content": {
          "name": "Entity Name",
          "description": "Entity Description",
          "metadata": { "key": "value" }
        },
        "result_type": "entity",
        "chunk_ids": ["c68dc72e-fc23-5452-8f49-d7bd46088a96"],
        "metadata": {
          "associated_query": "What is the capital of France?"
        }
      }
    ]
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/retrieval/search" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "query": "machine learning advancements",
           "search_mode": "advanced",
           "search_settings": {
             "use_semantic_search": true,
             "use_fulltext_search": true,
             "filters": { "document_type": { "$eq": "pdf" } },
             "limit": 20
           }
         }'
```

---

#### 2. RAG Query

```http
POST /v3/retrieval/rag
```

**Description:**
Executes a Retrieval-Augmented Generation (RAG) query. This endpoint combines search results with language model generation, allowing for context-based answers. It supports the same filtering capabilities as the search endpoint and can be customized using the `rag_generation_config` parameter.

**Request Body:**

A JSON object containing the query, search settings, and optional generation configurations.

**Example Request Body:**

```json
{
  "query": "Latest trends in AI",
  "search_mode": "custom",
  "search_settings": {
    "use_semantic_search": true,
    "filters": { "publication_year": { "$gte": 2020 } },
    "limit": 5
  },
  "rag_generation_config": {
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 150
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "chunk_search_results": [
      {
        "id": "chunk_id",
        "document_id": "document_id",
        "collection_ids": ["collection_id1"],
        "score": 0.95,
        "text": "Latest trends in AI include deep learning advancements...",
        "metadata": {
          "associated_query": "Latest trends in AI",
          "title": "ai_trends_2024.pdf"
        },
        "owner_id": "owner_id"
      }
    ],
    "graph_search_results": [
      {
        "content": {
          "name": "Deep Learning",
          "description": "A subset of machine learning involving neural networks.",
          "metadata": { "field": "Artificial Intelligence" }
        },
        "result_type": "entity",
        "chunk_ids": ["chunk_id1"],
        "metadata": {
          "associated_query": "Latest trends in AI"
        }
      }
    ],
    "generated_answer": "Recent advancements in AI include the development of more efficient neural network architectures, improvements in reinforcement learning algorithms, and enhanced capabilities in natural language understanding and generation. These innovations are driving progress in various fields such as healthcare, autonomous vehicles, and personalized education."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/retrieval/rag" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "query": "Latest trends in AI",
           "search_mode": "custom",
           "search_settings": {
             "use_semantic_search": true,
             "filters": { "publication_year": { "$gte": 2020 } },
             "limit": 5
           },
           "rag_generation_config": {
             "model": "gpt-4",
             "temperature": 0.7,
             "max_tokens": 150
           }
         }'
```

---

#### 3. RAG-powered Conversational Agent

```http
POST /v3/retrieval/agent
```

**Description:**
Engages with an intelligent RAG-powered conversational agent for complex information retrieval and analysis. This advanced endpoint combines retrieval-augmented generation (RAG) with a conversational AI agent to provide detailed, context-aware responses based on your document collection.

**Key Features:**

- Hybrid search combining vector and knowledge graph approaches.
- Contextual conversation management with `conversation_id` tracking.
- Customizable generation parameters for response style and length.
- Source document citation with optional title inclusion.
- Streaming support for real-time responses.
- Branch management for exploring different conversation paths.

**Use Cases:**

- Research assistance and literature review.
- Document analysis and summarization.
- Technical support and troubleshooting.
- Educational Q&A and tutoring.
- Knowledge base exploration.

**Request Body:**

A JSON object containing the message, search settings, and optional conversation parameters.

**Example Request Body:**

```json
{
  "message": {
    "role": "user",
    "content": "Can you summarize the latest AI research?",
    "name": "User"
  },
  "search_mode": "advanced",
  "search_settings": {
    "use_semantic_search": true,
    "use_fulltext_search": true,
    "filters": { "publication_year": { "$gte": 2023 } },
    "limit": 3
  },
  "conversation_id": "conversation_id",
  "branch_id": "branch_id"
}
```

**Successful Response:**

```json
{
  "results": {
    "messages": [
      {
        "role": "assistant",
        "content": "Certainly! The latest AI research focuses on advancements in deep learning, reinforcement learning, and natural language processing. Notable projects include the development of more efficient neural network architectures and improved model interpretability techniques.",
        "name": "Assistant",
        "function_call": {},
        "tool_calls": [],
        "conversation_id": "conversation_id",
        "branch_id": "branch_id"
      }
    ]
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/retrieval/agent" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "message": {
             "role": "user",
             "content": "Can you summarize the latest AI research?",
             "name": "User"
           },
           "search_mode": "advanced",
           "search_settings": {
             "use_semantic_search": true,
             "use_fulltext_search": true,
             "filters": { "publication_year": { "$gte": 2023 } },
             "limit": 3
           },
           "conversation_id": "conversation_id",
           "branch_id": "branch_id"
         }'
```

---

#### 4. Generate Message Completions

```http
POST /v3/retrieval/completion
```

**Description:**
Generates completions for a list of messages using the language model. The generation process can be customized using the `generation_config` parameter.

**Request Body:**

A JSON object containing the messages and optional generation configurations.

**Example Request Body:**

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Tell me about the advancements in AI."
    }
  ],
  "generation_config": {
    "model": "gpt-4",
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens_to_sample": 150,
    "stream": false
  },
  "response_model": "gpt-4"
}
```

**Successful Response:**

```json
{
  "results": {
    "messages": [
      {
        "role": "assistant",
        "content": "Recent advancements in AI include the development of more efficient neural network architectures, improvements in reinforcement learning algorithms, and enhanced capabilities in natural language understanding and generation. These innovations are driving progress in various fields such as healthcare, autonomous vehicles, and personalized education.",
        "conversation_id": "conversation_id",
        "branch_id": "branch_id"
      }
    ]
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/retrieval/completion" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "messages": [
             {
               "role": "user",
               "content": "Tell me about the advancements in AI."
             }
           ],
           "generation_config": {
             "model": "gpt-4",
             "temperature": 0.7,
             "top_p": 0.9,
             "max_tokens_to_sample": 150,
             "stream": false
           },
           "response_model": "gpt-4"
         }'
```

---

#### 5. Generate Embeddings

```http
POST /v3/retrieval/embedding
```

**Description:**
Generates numerical embedding vectors for the provided text using a specified model.

**Request Body:**

A JSON object containing the text to generate embeddings for.

**Example Request Body:**

```json
{
  "text": "Artificial Intelligence is transforming the world."
}
```

**Successful Response:**

```json
{
  "results": {
    "embeddings": [0.123, 0.456, 0.789]
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/retrieval/embedding" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "text": "Artificial Intelligence is transforming the world."
         }'
```

---

## Indices

### Overview

An **Index** in R2R represents a vector index structure optimized for similarity search operations across chunks or entities. Indices are crucial for efficient retrieval in Retrieval-Augmented Generation (RAG) applications, supporting various similarity measures and index types tailored to different use cases.

### Core Features of Indices

1. **Fast Similarity Search**
    - Enables rapid retrieval of similar vectors based on specified measures.

2. **Multiple Index Methods**
    - Supports various indexing methods like Hierarchical Navigable Small World (HNSW) and Inverted File (IVF-Flat) for different performance and recall needs.

3. **Configurable Similarity Measures**
    - Allows selection of similarity measures such as cosine distance, L2 distance, and inner product distance.

4. **Concurrent Index Building**
    - Supports concurrent operations to prevent downtime during index construction.

5. **Performance Optimization**
    - Tailors indices for optimized vector operations and query performance.

### Available Endpoints

| Method | Endpoint            | Description                               |
| :---- | :------------------ | :---------------------------------------- |
| POST   | `/indices`          | Create a new vector index                 |
| GET    | `/indices`          | List available indices with pagination    |
| GET    | `/indices/{id}`     | Get details of a specific index           |
| PUT    | `/indices/{id}`     | Update an existing index’s configuration  |
| DELETE | `/indices/{id}`     | Delete an existing index                  |
| GET    | `/indices/{table_name}/{index_name}` | Get vector index details  |
| DELETE | `/indices/{table_name}/{index_name}` | Delete a vector index      |

### Endpoint Details

#### 1. List Vector Indices

```http
GET /v3/indices
```

**Description:**
Lists existing vector similarity search indices with pagination support. Returns details about each index including name, table name, indexing method, parameters, size, and performance statistics.

**Query Parameters:**

| Parameter | Type      | Required | Description                                       |
| :-------- | :-------- | :------ | :------------------------------------------------ |
| `filters` | `string` | No      | Filter based on table name, index method, etc.    |
| `offset`  | `integer`| No      | Number of indices to skip. Defaults to `0`.        |
| `limit`   | `integer`| No      | Number of indices to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": {
    "indices": [
      {
        "id": "index_id",
        "name": "ai_research_vectors",
        "table_name": "vectors",
        "index_method": "HNSW",
        "index_measure": "cosine_distance",
        "index_arguments": {
          "m": 16,
          "ef_construction": 200,
          "ef": 50
        },
        "status": "active",
        "size_in_bytes": 500000000,
        "row_count": 100000,
        "created_at": "2024-01-15T09:30:00Z",
        "updated_at": "2024-01-15T09:30:00Z",
        "performance_statistics": {
          "average_query_time_ms": 5,
          "memory_usage_mb": 250,
          "cache_hit_rate_percent": 90
        }
      }
    ]
  },
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/indices?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Create Vector Index

```http
POST /v3/indices
```

**Description:**
Creates a new vector similarity search index over the target table. Supported tables include `vectors`, `entity`, `document_collections`, etc. This process is resource-intensive and supports concurrent building to prevent downtime.

**Supported Index Methods:**

1. **HNSW (Hierarchical Navigable Small World)**
    - **Best for:** High-dimensional vectors requiring fast approximate nearest neighbor search.
    - **Pros:** Very fast search, good recall, memory-resident for speed.
    - **Cons:** Slower index construction, higher memory usage.
    - **Key Parameters:**
        - `m`: Number of connections per layer (higher = better recall but more memory).
        - `ef_construction`: Build-time search width (higher = better recall but slower build).
        - `ef`: Query-time search width (higher = better recall but slower search).

2. **IVF-Flat (Inverted File with Flat Storage)**
    - **Best for:** Balance between build speed, search speed, and recall.
    - **Pros:** Faster index construction, less memory usage.
    - **Cons:** Slightly slower search than HNSW.
    - **Key Parameters:**
        - `lists`: Number of clusters (usually sqrt(n) where n is number of vectors).
        - `probe`: Number of nearest clusters to search.

**Supported Similarity Measures:**

- `cosine_distance`: Best for comparing semantic similarity.
- `l2_distance`: Best for comparing absolute distances.
- `ip_distance`: Best for comparing raw dot products.

**Notes:**

- Index creation can be resource-intensive for large datasets.
- Use `run_with_orchestration=true` for large indices to prevent timeouts.
- The `concurrently` option allows other operations while building.
- Index names must be unique per table.

**Request Body:**

A JSON object containing the configuration for the index.

**Example Request Body:**

```json
{
  "config": {
    "name": "ai_research_vectors",
    "table_name": "vectors",
    "index_method": "HNSW",
    "index_measure": "cosine_distance",
    "index_arguments": {
      "m": 16,
      "ef_construction": 200,
      "ef": 50
    },
    "concurrently": true,
    "run_with_orchestration": true
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Index creation started."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/indices" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "config": {
             "name": "ai_research_vectors",
             "table_name": "vectors",
             "index_method": "HNSW",
             "index_measure": "cosine_distance",
             "index_arguments": {
               "m": 16,
               "ef_construction": 200,
               "ef": 50
             },
             "concurrently": true,
             "run_with_orchestration": true
           }
         }'
```

---

#### 3. Get Vector Index Details

```http
GET /v3/indices/:table_name/:index_name
```

**Description:**
Retrieves detailed information about a specific vector index, including its configuration, size, performance statistics, and maintenance information.

**Path Parameters:**

| Parameter    | Type   | Required | Description                                     |
| :----------: | :---- | :------ | :---------------------------------------------- |
| `table_name` | `string` | Yes      | The table of vector embeddings (`vectors`, `entity`, `document_collections`). |
| `index_name` | `string` | Yes      | The name of the index to retrieve details for.   |

**Successful Response:**

```json
{
  "results": {
    "configuration": {
      "method": "HNSW",
      "measure": "cosine_distance",
      "parameters": {
        "m": 16,
        "ef_construction": 200,
        "ef": 50
      }
    },
    "size_in_bytes": 500000000,
    "row_count": 100000,
    "build_progress": "Completed",
    "performance_statistics": {
      "average_query_time_ms": 5,
      "memory_usage_mb": 250,
      "cache_hit_rate_percent": 90,
      "recent_query_patterns": ["nearest neighbor", "range search"]
    },
    "maintenance_information": {
      "last_vacuum": "2024-02-01T10:00:00Z",
      "fragmentation_level": "Low",
      "recommended_optimizations": ["Increase ef parameter for better recall."]
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/indices/vectors/ai_research_vectors" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 4. Delete Vector Index

```http
DELETE /v3/indices/:table_name/:index_name
```

**Description:**
Deletes an existing vector similarity search index. Deletion is permanent and cannot be undone. Underlying vector data remains intact, but queries will fall back to sequential scan, potentially slowing down search operations.

**Notes:**

- Deletion may affect dependent operations; ensure index dependencies are managed before deletion.
- Use `run_with_orchestration=true` for large indices to prevent timeouts.

**Path Parameters:**

| Parameter    | Type   | Required | Description                                     |
| :----------: | :---- | :------ | :---------------------------------------------- |
| `table_name` | `string` | Yes      | The table of vector embeddings (`vectors`, `entity`, `document_collections`). |
| `index_name` | `string` | Yes      | The name of the index to delete.                |

**Successful Response:**

```json
{
  "results": {
    "message": "Index deletion initiated."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/indices/vectors/ai_research_vectors" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Users

### Overview

A **User** in R2R represents an authenticated entity that can interact with the system. Users are the foundation of R2R’s access control system, enabling granular permissions management, activity tracking, and content organization through collections.

### Core Features of Users

1. **Authentication & Authorization**
    - Secure login and token-based authentication.
    - Role-based access control (regular users vs. superusers).

2. **Collection Membership Management**
    - Manage access to documents and graphs through collections.
    - Add or remove users from collections to control access.

3. **Activity Tracking & Analytics**
    - Monitor user activities and interactions within the system.

4. **Metadata Customization**
    - Store additional user information such as name, bio, and profile picture.

5. **Superuser Capabilities**
    - Manage system-wide settings, users, and prompts.

### Available Endpoints

| Method | Endpoint                                      | Description                                         |
| :---- | :-------------------------------------------- | :-------------------------------------------------- |
| GET    | `/users`                                      | List users with pagination (superusers only)       |
| GET    | `/users/{user_id}`                            | Get detailed user information                      |
| GET    | `/users/{user_id}/collections`                | List user’s collections                             |
| POST   | `/users/{user_id}/collections/{collection_id}`| Add user to collection                              |
| DELETE | `/users/{user_id}/collections/{collection_id}`| Remove user from collection                         |
| POST   | `/users/{user_id}`                            | Update user information                             |
| POST   | `/users/register`                             | Register a new user                                 |
| POST   | `/users/verify-email`                         | Verify user's email address                         |
| POST   | `/users/login`                                | Authenticate user and get tokens                    |
| POST   | `/users/logout`                               | Log out current user                                |
| POST   | `/users/refresh-token`                        | Refresh access token using a refresh token          |
| POST   | `/users/change-password`                      | Change the authenticated user’s password            |
| POST   | `/users/request-password-reset`               | Request a password reset for a user                  |
| POST   | `/users/reset-password`                       | Reset a user’s password using a reset token          |
| GET    | `/users/me`                                   | Get detailed information about the currently authenticated user |
| GET    | `/users/{id}`                                 | Get detailed information about a specific user       |
| POST   | `/users/{id}`                                 | Update user information                              |
| DELETE | `/users/{id}`                                 | Delete a specific user                               |
| GET    | `/users/{id}/collections`                     | List all collections associated with a specific user |
| POST   | `/users/{id}/collections/{collection_id}`     | Add a user to a collection                          |
| DELETE | `/users/{id}/collections/{collection_id}`     | Remove a user from a collection                     |

### Endpoint Details

#### 1. Register a New User

```http
POST /v3/users/register
```

**Description:**
Registers a new user with the provided email and password. Upon registration, the user is inactive until their email is verified.

**Request Body:**

A JSON object containing the user's email and password.

**Example Request Body:**

```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "user-id",
    "email": "user@example.com",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-01-15T09:30:00Z",
    "is_verified": false,
    "collection_ids": ["collection_id1"],
    "graph_ids": ["graph_id1"],
    "document_ids": ["document_id1"],
    "hashed_password": "hashed_password",
    "verification_code_expiry": "2024-01-16T09:30:00Z",
    "name": "John Doe",
    "bio": "A software developer.",
    "profile_picture": "https://example.com/profile.jpg",
    "total_size_in_bytes": 204800,
    "num_files": 10
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid input or email already exists.

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/users/register" \
     -H "Content-Type: application/json" \
     -d '{
           "email": "user@example.com",
           "password": "SecurePassword123!"
         }'
```

---

#### 2. Verify User's Email Address

```http
POST /v3/users/verify-email
```

**Description:**
Verifies a user’s email address using a verification code sent during registration.

**Request Body:**

A JSON object containing the user's email and verification code.

**Example Request Body:**

```json
{
  "email": "user@example.com",
  "verification_code": "123456"
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Email verified successfully."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid verification code or email.

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/users/verify-email" \
     -H "Content-Type: application/json" \
     -d '{
           "email": "user@example.com",
           "verification_code": "123456"
         }'
```

---

#### 3. Authenticate User and Get Tokens

```http
POST /v3/users/login
```

**Description:**
Authenticates a user and provides access and refresh tokens upon successful login.

**Request Body:**

A JSON object containing the user's email and password.

**Example Request Body:**

```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Successful Response:**

```json
{
  "results": {
    "access_token": {
      "token": "access_token_string",
      "token_type": "Bearer"
    },
    "refresh_token": {
      "token": "refresh_token_string",
      "token_type": "Bearer"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid credentials or account inactive.

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/users/login" \
     -H "Content-Type: application/json" \
     -d '{
           "email": "user@example.com",
           "password": "SecurePassword123!"
         }'
```

---

#### 4. Log Out Current User

```http
POST /v3/users/logout
```

**Description:**
Logs out the current user, invalidating their access token.

**Request Body:**

No parameters required.

**Successful Response:**

```json
{
  "results": {
    "message": "Logged out successfully."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid token or already logged out.

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/users/logout" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 5. Refresh Access Token

```http
POST /v3/users/refresh-token
```

**Description:**
Refreshes the access token using a valid refresh token, providing new access and refresh tokens.

**Request Body:**

A JSON object containing the refresh token.

**Example Request Body:**

```json
{
  "refresh_token": "refresh_token_string"
}
```

**Successful Response:**

```json
{
  "results": {
    "access_token": {
      "token": "new_access_token_string",
      "token_type": "Bearer"
    },
    "refresh_token": {
      "token": "new_refresh_token_string",
      "token_type": "Bearer"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid or expired refresh token.

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/users/refresh-token" \
     -H "Content-Type: application/json" \
     -d '{
           "refresh_token": "refresh_token_string"
         }'
```

---

#### 6. Change User Password

```http
POST /v3/users/change-password
```

**Description:**
Changes the authenticated user’s password.

**Request Body:**

A JSON object containing the current and new passwords.

**Example Request Body:**

```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewSecurePassword456!"
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Password changed successfully."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid current password or new password does not meet criteria.

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/users/change-password" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "current_password": "OldPassword123!",
           "new_password": "NewSecurePassword456!"
         }'
```

---

#### 7. Request Password Reset

```http
POST /v3/users/request-password-reset
```

**Description:**
Requests a password reset for a user by sending a reset link to their email.

**Request Body:**

A JSON object containing the user's email.

**Example Request Body:**

```json
{
  "email": "user@example.com"
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Password reset link sent to email."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Email does not exist or already requested.

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/users/request-password-reset" \
     -H "Content-Type: application/json" \
     -d '{
           "email": "user@example.com"
         }'
```

---

#### 8. Reset Password with Token

```http
POST /v3/users/reset-password
```

**Description:**
Resets a user’s password using a valid reset token.

**Request Body:**

A JSON object containing the reset token and the new password.

**Example Request Body:**

```json
{
  "reset_token": "reset_token_string",
  "new_password": "NewSecurePassword456!"
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Password reset successfully."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid or expired reset token.

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/users/reset-password" \
     -H "Content-Type: application/json" \
     -d '{
           "reset_token": "reset_token_string",
           "new_password": "NewSecurePassword456!"
         }'
```

---

#### 9. List All Users (Superusers Only)

```http
GET /v3/users
```

**Description:**
Lists all users in the system with pagination and filtering options. Accessible only by superusers.

**Query Parameters:**

| Parameter | Type      | Required | Description                           |
| :-------- | :-------- | :------ | :------------------------------------ |
| `ids`     | `string` | No      | A comma-separated list of user IDs to retrieve. |
| `offset`  | `integer`| No      | Number of users to skip. Defaults to `0`. |
| `limit`   | `integer`| No      | Number of users to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "user_id",
      "email": "user@example.com",
      "is_active": true,
      "is_superuser": false,
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-01-15T09:30:00Z",
      "is_verified": true,
      "collection_ids": ["collection_id1"],
      "graph_ids": ["graph_id1"],
      "document_ids": ["document_id1"],
      "hashed_password": "hashed_password",
      "verification_code_expiry": "2024-01-16T09:30:00Z",
      "name": "John Doe",
      "bio": "A software developer.",
      "profile_picture": "https://example.com/profile.jpg",
      "total_size_in_bytes": 204800,
      "num_files": 10
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/users?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 10. Get Authenticated User Details

```http
GET /v3/users/me
```

**Description:**
Retrieves detailed information about the currently authenticated user.

**Successful Response:**

```json
{
  "results": {
    "id": "id",
    "email": "email@example.com",
    "is_active": true,
    "is_superuser": true,
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-01-15T09:30:00Z",
    "is_verified": true,
    "collection_ids": ["collection_id1"],
    "graph_ids": ["graph_id1"],
    "document_ids": ["document_id1"],
    "hashed_password": "hashed_password",
    "verification_code_expiry": "2024-01-16T09:30:00Z",
    "name": "John Doe",
    "bio": "A software developer.",
    "profile_picture": "https://example.com/profile.jpg",
    "total_size_in_bytes": 204800,
    "num_files": 10
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/users/me" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 11. Get User Details

```http
GET /v3/users/:id
```

**Description:**
Retrieves detailed information about a specific user. Users can only access their own information unless they are superusers.

**Path Parameters:**

| Parameter | Type   | Required | Description                |
| :-------- | :----- | :------ | :------------------------- |
| `id`      | `string` | Yes      | The User ID to retrieve.   |

**Successful Response:**

```json
{
  "results": {
    "id": "user_id",
    "email": "user@example.com",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-01-15T09:30:00Z",
    "is_verified": true,
    "collection_ids": ["collection_id1"],
    "graph_ids": ["graph_id1"],
    "document_ids": ["document_id1"],
    "hashed_password": "hashed_password",
    "verification_code_expiry": "2024-01-16T09:30:00Z",
    "name": "John Doe",
    "bio": "A software developer.",
    "profile_picture": "https://example.com/profile.jpg",
    "total_size_in_bytes": 204800,
    "num_files": 10
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/users/user_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 12. Update User Information

```http
POST /v3/users/:id
```

**Description:**
Updates user information. Users can only update their own information unless they are superusers. Superuser status can only be modified by existing superusers.

**Path Parameters:**

| Parameter | Type   | Required | Description                         |
| :-------- | :----- | :------ | :---------------------------------- |
| `id`      | `string` | Yes      | The User ID to update.              |

**Request Body:**

A JSON object containing the updated user details.

**Example Request Body:**

```json
{
  "email": "new_email@example.com",
  "name": "Jane Doe",
  "bio": "An experienced software engineer.",
  "profile_picture": "https://example.com/new_profile.jpg"
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "user_id",
    "email": "new_email@example.com",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-02-20T10:45:00Z",
    "is_verified": true,
    "collection_ids": ["collection_id1"],
    "graph_ids": ["graph_id1"],
    "document_ids": ["document_id1"],
    "hashed_password": "hashed_password",
    "verification_code_expiry": "2024-01-16T09:30:00Z",
    "name": "Jane Doe",
    "bio": "An experienced software engineer.",
    "profile_picture": "https://example.com/new_profile.jpg",
    "total_size_in_bytes": 204800,
    "num_files": 10
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/users/user_id" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "email": "new_email@example.com",
           "name": "Jane Doe",
           "bio": "An experienced software engineer.",
           "profile_picture": "https://example.com/new_profile.jpg"
         }'
```

---

#### 13. Delete User

```http
DELETE /v3/users/:id
```

**Description:**
Deletes a specific user account. Users can only delete their own account unless they are superusers.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The User ID to delete.             |

**Request Body:**

A JSON object containing optional parameters to confirm deletion.

**Example Request Body:**

```json
{
  "password": "SecurePassword123!",
  "delete_vector_data": true
}
```

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/users/user_id" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "password": "SecurePassword123!",
           "delete_vector_data": true
         }'
```

---

#### 14. List User's Collections

```http
GET /v3/users/:id/collections
```

**Description:**
Retrieves all collections associated with a specific user. Users can only access their own collections unless they are superusers.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The User ID to retrieve collections for. |

**Query Parameters:**

| Parameter | Type      | Required | Description                           |
| :-------- | :-------- | :------ | :------------------------------------ |
| `offset`  | `integer` | No      | Number of collections to skip. Defaults to `0`. |
| `limit`   | `integer` | No      | Number of collections to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "collection_id",
      "name": "Collection Name",
      "graph_cluster_status": "status",
      "graph_sync_status": "status",
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-01-15T09:30:00Z",
      "user_count": 10,
      "document_count": 50,
      "owner_id": "owner_id",
      "description": "A sample collection."
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/users/user_id/collections?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 15. Add User to Collection

```http
POST /v3/users/:id/collections/:collection_id
```

**Description:**
Adds a user to a specific collection, granting them access to its documents and graphs. The authenticated user must have admin permissions for the collection to add new users.

**Path Parameters:**

| Parameter      | Type   | Required | Description                                |
| :------------- | :----- | :------ | :----------------------------------------- |
| `id`           | `string` | Yes      | The User ID to add to the collection.      |
| `collection_id`| `string` | Yes      | The Collection ID to add the user to.       |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/users/user_id/collections/collection_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 16. Remove User from Collection

```http
DELETE /v3/users/:id/collections/:collection_id
```

**Description:**
Removes a user from a specific collection, revoking their access to its documents and graphs. The authenticated user must have admin permissions for the collection to remove users.

**Path Parameters:**

| Parameter      | Type   | Required | Description                                |
| :------------- | :----- | :------ | :----------------------------------------- |
| `id`           | `string` | Yes      | The User ID to remove from the collection. |
| `collection_id`| `string` | Yes      | The Collection ID to remove the user from.  |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/users/user_id/collections/collection_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Collections

### Overview

A **Collection** in R2R is a logical grouping mechanism that organizes documents, enabling efficient access control and collaboration among users. Collections serve as the primary unit for managing permissions, sharing content, and organizing related documents across users and teams.

### Core Features of Collections

1. **Organizational Structure**
    - Groups related documents for better management and retrieval.

2. **Access Control & Permissions**
    - Manages user access at the collection level, allowing for granular permissions management.

3. **Content Sharing**
    - Facilitates sharing of documents and associated data among users within the collection.

4. **Collaboration Capabilities**
    - Enables multiple users to collaborate on document ingestion, management, and retrieval within a collection.

5. **Metadata Management**
    - Stores metadata and descriptions for each collection to provide context and organization.

### Available Endpoints

| Method | Endpoint                                         | Description                                                   |
| :---- | :----------------------------------------------- | :------------------------------------------------------------ |
| POST   | `/collections`                                   | Create a new collection                                       |
| GET    | `/collections`                                   | List collections with pagination and filtering               |
| GET    | `/collections/{id}`                              | Get details of a specific collection                          |
| POST   | `/collections/{id}`                              | Update an existing collection                                 |
| DELETE | `/collections/{id}`                              | Delete an existing collection                                 |
| GET    | `/collections/{id}/documents`                    | List documents in a collection                                |
| POST   | `/collections/{id}/documents/{document_id}`      | Add a document to a collection                                |
| POST   | `/collections/{id}/extract`                      | Extract entities and relationships for all unextracted documents in the collection |
| DELETE | `/collections/{id}/documents/{document_id}`      | Remove a document from a collection                           |
| GET    | `/collections/{id}/users`                        | List users with access to a collection                        |
| POST   | `/collections/{id}/users/{user_id}`              | Add a user to a collection                                    |
| DELETE | `/collections/{id}/users/{user_id}`              | Remove a user from a collection                               |

### Endpoint Details

#### 1. List Collections

```http
GET /v3/collections
```

**Description:**
Returns a paginated list of collections the authenticated user has access to. Results can be filtered by specific collection IDs. Regular users will see collections they own or have access to, while superusers can view all collections. Collections are ordered by last modification date, with the most recent first.

**Query Parameters:**

| Parameter | Type      | Required | Description                           |
| :-------- | :-------- | :------ | :------------------------------------ |
| `ids`     | `string` | No      | A comma-separated list of collection IDs to retrieve. If not provided, all accessible collections will be returned. |
| `offset`  | `integer`| No      | Number of collections to skip. Defaults to `0`. |
| `limit`   | `integer`| No      | Number of collections to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "collection_id",
      "name": "AI Research Collection",
      "graph_cluster_status": "active",
      "graph_sync_status": "synchronized",
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-01-15T09:30:00Z",
      "user_count": 5,
      "document_count": 10,
      "owner_id": "owner_id",
      "description": "A collection of documents related to AI research."
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/collections?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Create a New Collection

```http
POST /v3/collections
```

**Description:**
Creates a new collection and automatically adds the creating user to it.

**Request Body:**

A JSON object containing the name and optional description of the collection.

**Example Request Body:**

```json
{
  "name": "AI Research Collection",
  "description": "A collection of documents related to AI research."
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "collection_id",
    "name": "AI Research Collection",
    "graph_cluster_status": "active",
    "graph_sync_status": "synchronized",
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-01-15T09:30:00Z",
    "user_count": 1,
    "document_count": 0,
    "owner_id": "user_id",
    "description": "A collection of documents related to AI research."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/collections" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "AI Research Collection",
           "description": "A collection of documents related to AI research."
         }'
```

---

#### 3. Get Collection Details

```http
GET /v3/collections/:id
```

**Description:**
Retrieves detailed information about a specific collection.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Collection ID to retrieve details for. |

**Successful Response:**

```json
{
  "results": {
    "id": "collection_id",
    "name": "AI Research Collection",
    "graph_cluster_status": "active",
    "graph_sync_status": "synchronized",
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-01-15T09:30:00Z",
    "user_count": 10,
    "document_count": 50,
    "owner_id": "owner_id",
    "description": "A collection of documents related to AI research."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/collections/collection_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 4. Update Collection

```http
POST /v3/collections/:id
```

**Description:**
Updates the configuration of an existing collection, including its name and description.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Collection ID to update.        |

**Request Body:**

A JSON object containing the updated details of the collection.

**Example Request Body:**

```json
{
  "name": "Advanced AI Research Collection",
  "description": "An updated description for the AI research collection."
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "collection_id",
    "name": "Advanced AI Research Collection",
    "graph_cluster_status": "active",
    "graph_sync_status": "synchronized",
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-02-20T10:45:00Z",
    "user_count": 10,
    "document_count": 50,
    "owner_id": "owner_id",
    "description": "An updated description for the AI research collection."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/collections/collection_id" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "Advanced AI Research Collection",
           "description": "An updated description for the AI research collection."
         }'
```

---

#### 5. Delete Collection

```http
DELETE /v3/collections/:id
```

**Description:**
Deletes an existing collection. This action removes all associations but does not delete the documents within it.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Collection ID to delete.        |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/collections/collection_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 6. Add Document to Collection

```http
POST /v3/collections/:id/documents/:document_id
```

**Description:**
Adds a document to a specific collection, enabling access to the document within that collection's context.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `id`           | `string` | Yes      | The Collection ID to add the document to. |
| `document_id`  | `string` | Yes      | The Document ID to add.            |

**Successful Response:**

```json
{
  "results": {
    "message": "Document added to collection successfully."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/collections/collection_id/documents/document_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 7. Remove Document from Collection

```http
DELETE /v3/collections/:id/documents/:document_id
```

**Description:**
Removes a document from a specific collection, revoking access to it within that collection's context. This action does not delete the document itself.

**Path Parameters:**

| Parameter      | Type   | Required | Description                        |
| :------------- | :----- | :------ | :--------------------------------- |
| `id`           | `string` | Yes      | The Collection ID to remove the document from. |
| `document_id`  | `string` | Yes      | The Document ID to remove.         |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/collections/collection_id/documents/document_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 8. List Documents in Collection

```http
GET /v3/collections/:id/documents
```

**Description:**
Retrieves all documents within a specific collection, supporting pagination and sorting options.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Collection ID to retrieve documents from. |

**Query Parameters:**

| Parameter | Type      | Required | Description                           |
| :-------- | :-------- | :------ | :------------------------------------ |
| `offset`  | `integer` | No      | Number of documents to skip. Defaults to `0`. |
| `limit`   | `integer` | No      | Number of documents to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "document_id",
      "collection_ids": ["collection_id1", "collection_id2"],
      "owner_id": "owner_id",
      "document_type": "pdf",
      "metadata": {
        "title": "AI Research Paper",
        "description": "A comprehensive study on AI advancements."
      },
      "version": "1.0",
      "title": "AI Research Paper",
      "size_in_bytes": 102400,
      "ingestion_status": "success",
      "extraction_status": "success",
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-01-15T09:30:00Z",
      "ingestion_attempt_number": 1,
      "summary": "This paper explores recent advancements in artificial intelligence.",
      "summary_embedding": [1.1, 2.2, 3.3],
      "total_entries": 1
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/collections/collection_id/documents?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 9. List Users in Collection

```http
GET /v3/collections/:id/users
```

**Description:**
Retrieves all users with access to a specific collection, supporting pagination and sorting options.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Collection ID to retrieve users from. |

**Query Parameters:**

| Parameter | Type      | Required | Description                           |
| :-------- | :-------- | :------ | :------------------------------------ |
| `offset`  | `integer` | No      | Number of users to skip. Defaults to `0`. |
| `limit`   | `integer` | No      | Number of users to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "user_id",
      "email": "user@example.com",
      "is_active": true,
      "is_superuser": false,
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-01-15T09:30:00Z",
      "is_verified": true,
      "collection_ids": ["collection_id1"],
      "graph_ids": ["graph_id1"],
      "document_ids": ["document_id1"],
      "hashed_password": "hashed_password",
      "verification_code_expiry": "2024-01-16T09:30:00Z",
      "name": "John Doe",
      "bio": "A software developer.",
      "profile_picture": "https://example.com/profile.jpg",
      "total_size_in_bytes": 204800,
      "num_files": 10
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/collections/collection_id/users?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 10. Add User to Collection

```http
POST /v3/collections/:id/users/:user_id
```

**Description:**
Adds a user to a specific collection, granting them access to its documents and graphs. The authenticated user must have admin permissions for the collection to add new users.

**Path Parameters:**

| Parameter      | Type   | Required | Description                                |
| :------------- | :----- | :------ | :----------------------------------------- |
| `id`           | `string` | Yes      | The Collection ID to add the user to.       |
| `user_id`      | `string` | Yes      | The User ID to add to the collection.       |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/collections/collection_id/users/user_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 11. Remove User from Collection

```http
DELETE /v3/collections/:id/users/:user_id
```

**Description:**
Removes a user from a specific collection, revoking their access to its documents and graphs. The authenticated user must have admin permissions for the collection to remove users.

**Path Parameters:**

| Parameter      | Type   | Required | Description                                |
| :------------- | :----- | :------ | :----------------------------------------- |
| `id`           | `string` | Yes      | The Collection ID to remove the user from.  |
| `user_id`      | `string` | Yes      | The User ID to remove from the collection.  |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/collections/collection_id/users/user_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 12. Extract Entities and Relationships (Collection-level)

```http
POST /v3/collections/:id/extract
```

**Description:**
Extracts entities and relationships from all unextracted documents within a collection, facilitating comprehensive knowledge graph construction.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Collection ID to extract from.  |

**Query Parameters:**

| Parameter                | Type      | Required | Description                                     |
| :----------------------- | :-------- | :------ | :---------------------------------------------- |
| `run_type`               | `string` | No      | `"estimate"` or `"run"`. Determines operation type. |
| `run_with_orchestration` | `boolean`| No      | Whether to run the extraction process with orchestration. |

**Request Body:**

An optional JSON object containing various extraction prompts and configurations.

**Example Request Body:**

```json
{
  "run_type": "run",
  "settings": {
    "entity_types": ["Person", "Organization"],
    "relation_types": ["EmployedBy", "CollaboratesWith"],
    "chunk_merge_count": 5,
    "max_knowledge_relationships": 150,
    "generation_config": {
      "model": "gpt-4",
      "temperature": 0.7,
      "top_p": 0.9,
      "max_tokens_to_sample": 100,
      "stream": false
    }
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Entity and relationship extraction initiated for collection."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/collections/collection_id/extract" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "run_type": "run",
           "settings": {
             "entity_types": ["Person", "Organization"],
             "relation_types": ["EmployedBy", "CollaboratesWith"],
             "chunk_merge_count": 5,
             "max_knowledge_relationships": 150
           }
         }'
```

---

## Conversations

### Overview

A **Conversation** in R2R represents a threaded exchange of messages that can branch into multiple paths. Conversations provide a structured way to maintain dialogue history, support branching discussions, and manage message flows, enabling interactive and dynamic interactions with the system.

### Core Features of Conversations

1. **Threaded Message Management**
    - Maintains a history of messages exchanged within the conversation.

2. **Branching Paths**
    - Supports branching, allowing the conversation to explore different topics or directions.

3. **Message Editing**
    - Allows updating existing messages with history preservation.

4. **Metadata Attachment**
    - Stores additional information with messages for enhanced context.

5. **Context Maintenance**
    - Maintains conversational context across multiple interactions for coherent dialogue.

### Available Endpoints

| Method | Endpoint                                      | Description                                  |
| :---- | :-------------------------------------------- | :------------------------------------------- |
| POST   | `/conversations`                              | Create a new conversation                    |
| GET    | `/conversations`                              | List conversations with pagination           |
| GET    | `/conversations/{id}`                         | Get conversation details                     |
| DELETE | `/conversations/{id}`                         | Delete a conversation                        |
| POST   | `/conversations/{id}/messages`                 | Add a message to conversation                |
| PUT    | `/conversations/{id}/messages/{message_id}`    | Update an existing message                   |
| GET    | `/conversations/{id}/branches`                 | List conversation branches                   |

### Endpoint Details

#### 1. List Conversations

```http
GET /v3/conversations
```

**Description:**
Lists all conversations accessible to the authenticated user, supporting pagination and filtering.

**Query Parameters:**

| Parameter | Type      | Required | Description                           |
| :-------- | :-------- | :------ | :------------------------------------ |
| `ids`     | `string` | No      | A comma-separated list of conversation IDs to retrieve. If not provided, all accessible conversations will be returned. |
| `offset`  | `integer`| No      | Number of conversations to skip. Defaults to `0`. |
| `limit`   | `integer`| No      | Number of conversations to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "conversation_id",
      "created_at": "2024-01-15T09:30:00Z",
      "user_id": "user_id",
      "name": "AI Chatbot Conversation"
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/conversations?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Create a New Conversation

```http
POST /v3/conversations
```

**Description:**
Creates a new conversation for the authenticated user.

**Request Body:**

No parameters required.

**Successful Response:**

```json
{
  "results": {
    "id": "conversation_id",
    "created_at": "2024-01-15T09:30:00Z",
    "user_id": "user_id",
    "name": "AI Chatbot Conversation"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/conversations" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 3. Get Conversation Details

```http
GET /v3/conversations/:id
```

**Description:**
Retrieves detailed information about a specific conversation. Can optionally retrieve details of a specific branch.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Conversation ID to retrieve.    |

**Query Parameters:**

| Parameter   | Type      | Required | Description                                |
| :---------- | :-------- | :------ | :----------------------------------------- |
| `branch_id` | `string` | No      | The ID of the specific branch to retrieve. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "conversation_id",
      "message": {
        "role": "assistant",
        "content": "Hello! How can I assist you today?",
        "name": "Assistant",
        "function_call": {},
        "tool_calls": []
      },
      "metadata": {}
    }
  ]
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/conversations/conversation_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 4. Delete Conversation

```http
DELETE /v3/conversations/:id
```

**Description:**
Deletes an existing conversation, removing all associated messages and branches.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Conversation ID to delete.      |

**Successful Response:**

```json
{
  "results": {}
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/conversations/conversation_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 5. Add Message to Conversation

```http
POST /v3/conversations/:id/messages
```

**Description:**
Adds a new message to an existing conversation.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Conversation ID to add the message to. |

**Request Body:**

A JSON object containing the message details.

**Example Request Body:**

```json
{
  "content": "Hello, can you help me with AI research?",
  "role": "user",
  "parent_id": "parent_message_id",
  "metadata": {
    "topic": "AI Research"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "message_id",
    "message": {
      "role": "user",
      "content": "Hello, can you help me with AI research?",
      "name": "User",
      "function_call": {},
      "tool_calls": []
    },
    "metadata": {
      "topic": "AI Research"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/conversations/conversation_id/messages" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "content": "Hello, can you help me with AI research?",
           "role": "user",
           "parent_id": "parent_message_id",
           "metadata": { "topic": "AI Research" }
         }'
```

---

#### 6. Update Message in Conversation

```http
PUT /v3/conversations/:id/messages/:message_id
```

**Description:**
Updates an existing message within a conversation.

**Path Parameters:**

| Parameter     | Type   | Required | Description                                |
| :------------ | :----- | :------ | :----------------------------------------- |
| `id`          | `string` | Yes      | The Conversation ID containing the message. |
| `message_id`  | `string` | Yes      | The Message ID to update.                  |

**Request Body:**

A JSON object containing the updated message details.

**Example Request Body:**

```json
{
  "content": "Hello, can you assist me with advanced AI research?",
  "metadata": {
    "topic": "Advanced AI Research"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "message": {
      "role": "user",
      "content": "Hello, can you assist me with advanced AI research?",
      "name": "User",
      "function_call": {},
      "tool_calls": []
    },
    "metadata": {
      "topic": "Advanced AI Research"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X PUT "https://api.example.com/v3/conversations/conversation_id/messages/message_id" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "content": "Hello, can you assist me with advanced AI research?",
           "metadata": { "topic": "Advanced AI Research" }
         }'
```

---

#### 7. List Conversation Branches

```http
GET /v3/conversations/:id/branches
```

**Description:**
Lists all branches within a specific conversation, supporting pagination.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Conversation ID to retrieve branches for. |

**Query Parameters:**

| Parameter | Type      | Required | Description                           |
| :-------- | :-------- | :------ | :------------------------------------ |
| `offset`  | `integer` | No      | Number of branches to skip. Defaults to `0`. |
| `limit`   | `integer` | No      | Number of branches to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "branch_id": "branch_id",
      "created_at": "2024-01-16T10:00:00Z",
      "branch_point_id": "message_id",
      "content": "Branch content here.",
      "user_id": "user_id",
      "name": "Branch Name"
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/conversations/conversation_id/branches?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Prompts

### Overview

A **Prompt** in R2R represents a templated instruction or query pattern managed by superusers. Prompts provide a consistent and reusable way to structure interactions with language models and other AI components, ensuring standardized outputs and interactions across the system.

### Core Features of Prompts

1. **Templated Instruction Management**
    - Centralizes prompt templates for consistent usage.

2. **Type-safe Input Handling**
    - Defines input types for dynamic prompt generation.

3. **Centralized Governance**
    - Managed by superusers to maintain standardization.

4. **Dynamic Prompt Generation**
    - Supports dynamic insertion of input values into templates.

5. **Version Control**
    - Maintains versions of prompts for historical reference and rollback.

### Available Endpoints

| Method | Endpoint         | Description                                 |
| :---- | :--------------- | :------------------------------------------ |
| POST   | `/prompts`       | Create a new prompt template                |
| GET    | `/prompts`       | List all available prompts                  |
| GET    | `/prompts/{name}`| Get a specific prompt with optional inputs  |
| PUT    | `/prompts/{name}`| Update an existing prompt                   |
| DELETE | `/prompts/{name}`| Delete a prompt template                    |

### Endpoint Details

#### 1. List All Prompts

```http
GET /v3/prompts
```

**Description:**
Lists all available prompts. Accessible only by superusers.

**Successful Response:**

```json
{
  "results": [
    {
      "id": "prompt_id",
      "name": "greeting_prompt",
      "template": "Hello, {name}!",
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-02-20T10:45:00Z",
      "input_types": {
        "name": "string",
        "age": "integer"
      }
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**: Access denied or invalid request.

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/prompts" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Create a New Prompt

```http
POST /v3/prompts
```

**Description:**
Creates a new prompt with the provided configuration. Only superusers can create prompts.

**Request Body:**

A JSON object containing the prompt's name, template, and input types.

**Example Request Body:**

```json
{
  "name": "greeting_prompt",
  "template": "Hello, {name}! You are {age} years old.",
  "input_types": {
    "name": "string",
    "age": "integer"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Prompt created successfully."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid input or access denied.

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/prompts" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "greeting_prompt",
           "template": "Hello, {name}! You are {age} years old.",
           "input_types": { "name": "string", "age": "integer" }
         }'
```

---

#### 3. Get an Existing Prompt

```http
GET /v3/prompts/:name
```

**Description:**
Retrieves a specific prompt by name, optionally with input values and overrides.

**Path Parameters:**

| Parameter | Type   | Required | Description                |
| :-------- | :----- | :------ | :------------------------- |
| `name`    | `string` | Yes      | The name of the prompt.    |

**Query Parameters:**

| Parameter         | Type      | Required | Description                             |
| :---------------- | :-------- | :------ | :-------------------------------------- |
| `prompt_override` | `string` | No      | Optional custom prompt override.        |

**Request Body:**

A JSON object containing input values for the prompt.

**Example Request Body:**

```json
{
  "inputs": {
    "name": "Alice",
    "age": 30
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "prompt_id",
    "name": "greeting_prompt",
    "template": "Hello, Alice! You are 30 years old.",
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-02-20T10:45:00Z",
    "input_types": {
      "name": "string",
      "age": "integer"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid prompt name or access denied.

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/prompts/greeting_prompt" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "inputs": { "name": "Alice", "age": 30 }
         }'
```

---

#### 4. Update an Existing Prompt

```http
PUT /v3/prompts/:name
```

**Description:**
Updates an existing prompt’s template and/or input types. Only superusers can update prompts.

**Path Parameters:**

| Parameter | Type   | Required | Description                |
| :-------- | :----- | :------ | :------------------------- |
| `name`    | `string` | Yes      | The name of the prompt.    |

**Request Body:**

A JSON object containing the updated template and input types.

**Example Request Body:**

```json
{
  "template": "Greetings, {name}! You are {age} years old.",
  "input_types": {
    "name": "string",
    "age": "integer",
    "location": "string"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Prompt updated successfully."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid prompt name or update parameters.

**Example cURL:**

```bash
curl -X PUT "https://api.example.com/v3/prompts/greeting_prompt" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "template": "Greetings, {name}! You are {age} years old.",
           "input_types": { "name": "string", "age": "integer", "location": "string" }
         }'
```

---

#### 5. Delete a Prompt

```http
DELETE /v3/prompts/:name
```

**Description:**
Deletes a prompt by name. Only superusers can delete prompts.

**Path Parameters:**

| Parameter | Type   | Required | Description                |
| :-------- | :----- | :------ | :------------------------- |
| `name`    | `string` | Yes      | The name of the prompt.    |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid prompt name or access denied.

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/prompts/greeting_prompt" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Conversations

### Overview

A **Conversation** in R2R maintains a threaded and potentially branching series of messages between users and the system. Conversations support context persistence, enabling multi-turn dialogues that can adapt and diverge based on user interactions.

### Core Features of Conversations

1. **Threaded Message Management**
    - Maintains a sequence of messages exchanged within the conversation.

2. **Branching Paths**
    - Supports branching to explore different topics or directions within the same conversation.

3. **Message Editing with History Preservation**
    - Allows updating existing messages while preserving the conversation history.

4. **Metadata Attachment**
    - Stores additional information with messages for enhanced context and organization.

5. **Context Maintenance**
    - Maintains conversational context across multiple interactions for coherent and relevant responses.

### Available Endpoints

| Method | Endpoint                                    | Description                                  |
| :---- | :------------------------------------------ | :------------------------------------------- |
| POST   | `/conversations`                            | Create a new conversation                    |
| GET    | `/conversations`                            | List conversations with pagination           |
| GET    | `/conversations/{id}`                       | Get conversation details                     |
| DELETE | `/conversations/{id}`                       | Delete a conversation                        |
| POST   | `/conversations/{id}/messages`               | Add a message to conversation                |
| PUT    | `/conversations/{id}/messages/{message_id}`  | Update an existing message                   |
| GET    | `/conversations/{id}/branches`               | List conversation branches                   |

### Endpoint Details

#### 1. List Conversations

```http
GET /v3/conversations
```

**Description:**
Lists all conversations accessible to the authenticated user, supporting pagination and filtering.

**Query Parameters:**

| Parameter | Type      | Required | Description                           |
| :-------- | :-------- | :------ | :------------------------------------ |
| `ids`     | `string` | No      | A comma-separated list of conversation IDs to retrieve. If not provided, all accessible conversations will be returned. |
| `offset`  | `integer`| No      | Number of conversations to skip. Defaults to `0`. |
| `limit`   | `integer`| No      | Number of conversations to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "conversation_id",
      "created_at": "2024-01-15T09:30:00Z",
      "user_id": "user_id",
      "name": "AI Chatbot Conversation"
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/conversations?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Create a New Conversation

```http
POST /v3/conversations
```

**Description:**
Creates a new conversation for the authenticated user.

**Request Body:**

No parameters required.

**Successful Response:**

```json
{
  "results": {
    "id": "conversation_id",
    "created_at": "2024-01-15T09:30:00Z",
    "user_id": "user_id",
    "name": "AI Chatbot Conversation"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/conversations" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 3. Get Conversation Details

```http
GET /v3/conversations/:id
```

**Description:**
Retrieves detailed information about a specific conversation. Optionally, you can retrieve details of a specific branch within the conversation.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Conversation ID to retrieve.    |

**Query Parameters:**

| Parameter   | Type      | Required | Description                                |
| :---------- | :-------- | :------ | :----------------------------------------- |
| `branch_id` | `string` | No      | The ID of the specific branch to retrieve. |

**Successful Response:**

```json
{
  "results": [
    {
      "id": "conversation_id",
      "message": {
        "role": "assistant",
        "content": "Hello! How can I assist you today?",
        "name": "Assistant",
        "function_call": {},
        "tool_calls": []
      },
      "metadata": {}
    }
  ]
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/conversations/conversation_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 4. Delete Conversation

```http
DELETE /v3/conversations/:id
```

**Description:**
Deletes an existing conversation, removing all associated messages and branches.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Conversation ID to delete.      |

**Successful Response:**

```json
{
  "results": {}
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/conversations/conversation_id" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 5. Add Message to Conversation

```http
POST /v3/conversations/:id/messages
```

**Description:**
Adds a new message to an existing conversation.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Conversation ID to add the message to. |

**Request Body:**

A JSON object containing the message details.

**Example Request Body:**

```json
{
  "content": "Hello, can you help me with AI research?",
  "role": "user",
  "parent_id": "parent_message_id",
  "metadata": {
    "topic": "AI Research"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "message_id",
    "message": {
      "role": "user",
      "content": "Hello, can you help me with AI research?",
      "name": "User",
      "function_call": {},
      "tool_calls": []
    },
    "metadata": {
      "topic": "AI Research"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/conversations/conversation_id/messages" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "content": "Hello, can you help me with AI research?",
           "role": "user",
           "parent_id": "parent_message_id",
           "metadata": { "topic": "AI Research" }
         }'
```

---

#### 6. Update Message in Conversation

```http
PUT /v3/conversations/:id/messages/:message_id
```

**Description:**
Updates an existing message within a conversation.

**Path Parameters:**

| Parameter     | Type   | Required | Description                                |
| :------------ | :----- | :------ | :----------------------------------------- |
| `id`          | `string` | Yes      | The Conversation ID containing the message. |
| `message_id`  | `string` | Yes      | The Message ID to update.                   |

**Request Body:**

A JSON object containing the updated message details.

**Example Request Body:**

```json
{
  "content": "Hello, can you assist me with advanced AI research?",
  "metadata": {
    "topic": "Advanced AI Research"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "message": {
      "role": "user",
      "content": "Hello, can you assist me with advanced AI research?",
      "name": "User",
      "function_call": {},
      "tool_calls": []
    },
    "metadata": {
      "topic": "Advanced AI Research"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X PUT "https://api.example.com/v3/conversations/conversation_id/messages/message_id" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "content": "Hello, can you assist me with advanced AI research?",
           "metadata": { "topic": "Advanced AI Research" }
         }'
```

---

#### 7. List Conversation Branches

```http
GET /v3/conversations/:id/branches
```

**Description:**
Lists all branches within a specific conversation, supporting pagination.

**Path Parameters:**

| Parameter | Type   | Required | Description                        |
| :-------- | :----- | :------ | :--------------------------------- |
| `id`      | `string` | Yes      | The Conversation ID to retrieve branches for. |

**Query Parameters:**

| Parameter | Type      | Required | Description                           |
| :-------- | :-------- | :------ | :------------------------------------ |
| `offset`  | `integer` | No      | Number of branches to skip. Defaults to `0`. |
| `limit`   | `integer` | No      | Number of branches to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "branch_id": "branch_id",
      "created_at": "2024-01-16T10:00:00Z",
      "branch_point_id": "message_id",
      "content": "Branch content here.",
      "user_id": "user_id",
      "name": "Branch Name"
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/conversations/conversation_id/branches?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Prompts

### Overview

A **Prompt** in R2R represents a templated instruction or query pattern that can be reused across the system. Managed by superusers, prompts provide a standardized way to interact with language models and other AI components, ensuring consistent outputs and interactions.

### Core Features of Prompts

1. **Templated Instruction Management**
    - Centralizes prompt templates for consistent usage.

2. **Type-safe Input Handling**
    - Defines input types for dynamic prompt generation.

3. **Centralized Governance**
    - Managed by superusers to maintain standardization.

4. **Dynamic Prompt Generation**
    - Supports dynamic insertion of input values into templates.

5. **Version Control**
    - Maintains versions of prompts for historical reference and rollback.

### Available Endpoints

| Method | Endpoint         | Description                                 |
| :---- | :--------------- | :------------------------------------------ |
| POST   | `/prompts`        | Create a new prompt template                |
| GET    | `/prompts`        | List all available prompts                  |
| GET    | `/prompts/{name}` | Get a specific prompt with optional inputs  |
| PUT    | `/prompts/{name}` | Update an existing prompt                   |
| DELETE | `/prompts/{name}` | Delete a prompt template                    |

### Endpoint Details

#### 1. List All Prompts

```http
GET /v3/prompts
```

**Description:**
Lists all available prompts. Accessible only by superusers.

**Successful Response:**

```json
{
  "results": [
    {
      "id": "prompt_id",
      "name": "greeting_prompt",
      "template": "Hello, {name}!",
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-02-20T10:45:00Z",
      "input_types": {
        "name": "string",
        "age": "integer"
      }
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**: Access denied or invalid request.

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/prompts" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Create a New Prompt

```http
POST /v3/prompts
```

**Description:**
Creates a new prompt with the provided configuration. Only superusers can create prompts.

**Request Body:**

A JSON object containing the prompt's name, template, and input types.

**Example Request Body:**

```json
{
  "name": "greeting_prompt",
  "template": "Hello, {name}! You are {age} years old.",
  "input_types": {
    "name": "string",
    "age": "integer"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Prompt created successfully."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid input or access denied.

**Example cURL:**

```bash
curl -X POST "https://api.example.com/v3/prompts" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "greeting_prompt",
           "template": "Hello, {name}! You are {age} years old.",
           "input_types": { "name": "string", "age": "integer" }
         }'
```

---

#### 3. Get an Existing Prompt

```http
GET /v3/prompts/:name
```

**Description:**
Retrieves a specific prompt by name, optionally with input values and overrides.

**Path Parameters:**

| Parameter | Type   | Required | Description                |
| :-------- | :----- | :------ | :------------------------- |
| `name`    | `string` | Yes      | The name of the prompt.    |

**Query Parameters:**

| Parameter         | Type      | Required | Description                             |
| :---------------- | :-------- | :------ | :-------------------------------------- |
| `prompt_override` | `string` | No      | Optional custom prompt override.        |

**Request Body:**

A JSON object containing input values for the prompt.

**Example Request Body:**

```json
{
  "inputs": {
    "name": "Alice",
    "age": 30
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "id": "prompt_id",
    "name": "greeting_prompt",
    "template": "Hello, Alice! You are 30 years old.",
    "created_at": "2024-01-15T09:30:00Z",
    "updated_at": "2024-02-20T10:45:00Z",
    "input_types": {
      "name": "string",
      "age": "integer"
    }
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid prompt name or access denied.

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/prompts/greeting_prompt" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "inputs": { "name": "Alice", "age": 30 }
         }'
```

---

#### 4. Update an Existing Prompt

```http
PUT /v3/prompts/:name
```

**Description:**
Updates an existing prompt’s template and/or input types. Only superusers can update prompts.

**Path Parameters:**

| Parameter | Type   | Required | Description                |
| :-------- | :----- | :------ | :------------------------- |
| `name`    | `string` | Yes      | The name of the prompt.    |

**Request Body:**

A JSON object containing the updated template and input types.

**Example Request Body:**

```json
{
  "template": "Greetings, {name}! You are {age} years old.",
  "input_types": {
    "name": "string",
    "age": "integer",
    "location": "string"
  }
}
```

**Successful Response:**

```json
{
  "results": {
    "message": "Prompt updated successfully."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid prompt name or update parameters.

**Example cURL:**

```bash
curl -X PUT "https://api.example.com/v3/prompts/greeting_prompt" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
           "template": "Greetings, {name}! You are {age} years old.",
           "input_types": { "name": "string", "age": "integer", "location": "string" }
         }'
```

---

#### 5. Delete a Prompt

```http
DELETE /v3/prompts/:name
```

**Description:**
Deletes a prompt by name. Only superusers can delete prompts.

**Path Parameters:**

| Parameter | Type   | Required | Description                |
| :-------- | :----- | :------ | :------------------------- |
| `name`    | `string` | Yes      | The name of the prompt.    |

**Successful Response:**

```json
{
  "results": {
    "success": true
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Invalid prompt name or access denied.

**Example cURL:**

```bash
curl -X DELETE "https://api.example.com/v3/prompts/greeting_prompt" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## System

### Overview

The **System** section of the R2R API provides endpoints for monitoring and managing the overall health, logs, settings, and status of the R2R system. These tools are essential for administrators and superusers to ensure the system operates smoothly and efficiently.

### Core Features of System Endpoints

1. **Health Monitoring**
    - Check the overall health status of the R2R system.

2. **Log Retrieval**
    - Access system logs for monitoring and debugging purposes.

3. **Settings Management**
    - Retrieve and manage current configuration settings of the R2R system.

4. **Server Status**
    - Get real-time information about server uptime and resource usage.

### Available Endpoints

| Method | Endpoint               | Description                                                   |
| :---- | :--------------------- | :------------------------------------------------------------ |
| GET    | `/system/logs`         | Retrieve system logs for monitoring and debugging purposes.  |
| GET    | `/system/health`       | Check the overall health status of the R2R system.           |
| GET    | `/system/settings`     | Retrieve the current configuration settings of the R2R system. |
| GET    | `/system/status`       | Retrieve the current server status, including uptime and resource usage. |

### Endpoint Details

#### 1. R2R Logs

```http
GET /v3/system/logs
```

**Description:**
Retrieves system logs for monitoring and debugging purposes.

**Query Parameters:**

| Parameter        | Type      | Required | Description                                  |
| :--------------- | :-------- | :------ | :------------------------------------------- |
| `run_type_filter`| `string` | No      | Filter logs based on run type (e.g., "ingestion", "extraction"). |
| `offset`         | `integer`| No      | Number of log entries to skip. Defaults to `0`. |
| `limit`          | `integer`| No      | Number of log entries to return (`1–100`). Defaults to `100`. |

**Successful Response:**

```json
{
  "results": [
    {
      "run_id": "run_id",
      "run_type": "ingestion",
      "entries": [
        {
          "key": "event",
          "value": "Document ingested successfully.",
          "timestamp": "2024-01-15T09:30:00Z",
          "user_id": "user_id"
        }
      ],
      "timestamp": "2024-01-15T09:30:00Z",
      "user_id": "user_id"
    }
  ],
  "total_entries": 1
}
```

**Error Response:**

- **422 Unprocessable Entity**

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/system/logs?limit=10" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 2. Check System Health

```http
GET /v3/system/health
```

**Description:**
Checks the overall health status of the R2R system, ensuring that all components are functioning correctly.

**Successful Response:**

```json
{
  "results": {
    "message": "System is healthy."
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: System is experiencing issues.

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/system/health" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 3. R2R Settings

```http
GET /v3/system/settings
```

**Description:**
Retrieves the current configuration settings of the R2R system, including prompt configurations and project name.

**Successful Response:**

```json
{
  "results": {
    "config": {
      "setting_key": "setting_value"
    },
    "prompts": {
      "prompt_name": "prompt_template"
    },
    "r2r_project_name": "R2R Project"
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Access denied or invalid request.

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/system/settings" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

#### 4. Server Status

```http
GET /v3/system/status
```

**Description:**
Retrieves the current server status, including uptime and resource usage statistics.

**Successful Response:**

```json
{
  "results": {
    "start_time": "2024-01-01T00:00:00Z",
    "uptime_seconds": 86400,
    "cpu_usage_percent": 75.5,
    "memory_usage_percent": 65.2
  }
}
```

**Error Response:**

- **422 Unprocessable Entity**: Unable to retrieve server status.

**Example cURL:**

```bash
curl -X GET "https://api.example.com/v3/system/status" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Common Use Cases

R2R API is designed to support a wide range of use cases, enabling users to harness the full potential of their data. Here are some common scenarios:

1. **Research and Analysis**
    - **Literature Review:** Ingest and analyze academic papers to extract key entities and relationships.
    - **Document Summarization:** Automatically generate summaries of large documents for quick insights.
    - **Relationship Discovery:** Identify and visualize connections between different entities within a dataset.
    - **Cross-reference Verification:** Ensure consistency and accuracy across related documents.

2. **Question Answering**
    - **Technical Support:** Provide users with accurate and context-aware responses to technical queries.
    - **Educational Assistance:** Develop tutoring systems that assist students with their studies by providing relevant information.
    - **Policy Compliance:** Analyze and respond to queries related to compliance policies within an organization.
    - **Data Exploration:** Enable users to explore datasets through natural language questions.

3. **Content Generation**
    - **Report Writing:** Automatically generate comprehensive reports based on ingested data.
    - **Documentation Creation:** Create detailed documentation for projects, APIs, or processes.
    - **Content Summarization:** Condense lengthy content into concise summaries for easier consumption.
    - **Knowledge Synthesis:** Combine information from multiple sources to create unified knowledge bases.

4. **Conversational Applications**
    - **Interactive Chatbots:** Develop chatbots that engage users in meaningful conversations, leveraging the knowledge graph for accurate responses.
    - **Virtual Assistants:** Create assistants that help users manage tasks, retrieve information, and perform actions based on conversational inputs.
    - **Educational Tutors:** Build systems that provide personalized tutoring and learning experiences.
    - **Research Aids:** Assist researchers in navigating complex datasets and extracting valuable insights through conversation.

---

## Conclusion

This comprehensive documentation provides an in-depth overview of the **R2R API**, encompassing all available endpoints, their functionalities, request and response structures, and practical usage examples. By leveraging the R2R API, you can effectively manage, retrieve, and interact with your document collections, build sophisticated knowledge graphs, and develop intelligent conversational agents.

### Key Highlights:

- **Document Management:** Efficiently ingest, update, and manage various document types, enabling structured retrieval and analysis.
- **Chunking & Indexing:** Optimize your data for semantic search and vector-based operations with robust chunking and indexing mechanisms.
- **Knowledge Graphs:** Build and manage detailed knowledge graphs through entity and relationship extraction, facilitating advanced data exploration.
- **Retrieval Capabilities:** Harness powerful retrieval features including semantic search, RAG, and conversational agents to interact with your data intelligently.
- **User & Collection Management:** Control access and collaboration through granular user and collection management features.
- **System Tools:** Monitor and maintain the health and performance of your R2R system with dedicated system endpoints.

For further assistance, refer to the [R2R Docs](https://r2r-docs.sciphi.ai) or contact our support team.

---

# **R2R Deployment Guidelines**

Welcome to the **R2R Deployment Guidelines**. This comprehensive guide will walk you through deploying the R2R (Retrieval to Riches) application using Docker and Docker Compose. The deployment includes setting up essential services such as PostgreSQL, RabbitMQ, Hatchet, Unstructured, Graph Clustering, R2R itself, R2R Dashboard, and Nginx. By following these guidelines, you will ensure a smooth and efficient deployment of R2R with all necessary configurations.

---

## **Table of Contents**
1. [Prerequisites](#prerequisites)
2. [Deployment Overview](#deployment-overview)
3. [Setting Up Environment Variables](#setting-up-environment-variables)
4. [Dockerfile and Dockerfile.unstructured Overview](#dockerfile-and-dockerfileunstructured-overview)
5. [Docker Compose Configuration](#docker-compose-configuration)
   - [Networks and Volumes](#networks-and-volumes)
   - [Services Breakdown](#services-breakdown)
6. [Building and Running the Deployment](#building-and-running-the-deployment)
   - [Step 1: Clone the Repository](#step-1-clone-the-repository)
   - [Step 2: Configure Environment Variables](#step-2-configure-environment-variables)
   - [Step 3: Build Docker Images](#step-3-build-docker-images)
   - [Step 4: Deploy Services with Docker Compose](#step-4-deploy-services-with-docker-compose)
7. [Initial Setup Steps](#initial-setup-steps)
   - [Creating the Hatchet API Token](#creating-the-hatchet-api-token)
8. [Accessing R2R and Hatchet Dashboard](#accessing-r2r-and-hatchet-dashboard)
9. [Configuring Nginx as a Reverse Proxy](#configuring-nginx-as-a-reverse-proxy)
10. [Configuring R2R](#configuring-r2r)
11. [Maintenance and Scaling](#maintenance-and-scaling)
12. [Security Considerations](#security-considerations)
13. [Troubleshooting](#troubleshooting)
14. [Conclusion](#conclusion)

---

## **Prerequisites**

Before proceeding with the deployment, ensure you have the following prerequisites:

- **Operating System**: Linux, macOS, or Windows with WSL 2 (for Windows users).
- **Docker**: Installed on your system. [Install Docker](https://docs.docker.com/get-docker/).
- **Docker Compose**: Installed and up-to-date. [Install Docker Compose](https://docs.docker.com/compose/install/).
- **Git**: To clone the repository. [Install Git](https://git-scm.com/downloads).
- **Sufficient Resources**: Ensure your system has adequate CPU, memory, and disk space to handle the services.

---

## **Deployment Overview**

The deployment consists of the following key components:

1. **PostgreSQL with pgvector**: Database for storing relational and vector data.
2. **Hatchet Services**: Includes Hatchet Postgres, RabbitMQ, Migration, Setup Config, Engine, and Dashboard.
3. **Unstructured Service**: Handles document processing and parsing.
4. **Graph Clustering Service**: Manages community detection within knowledge graphs.
5. **R2R Application**: The core application providing Retrieval-Augmented Generation (RAG) functionalities.
6. **R2R Dashboard**: User interface for managing R2R.
7. **Nginx**: Acts as a reverse proxy to route traffic to R2R and other services.

The deployment is managed using Docker Compose, orchestrating the interaction between these services.

---

## **Setting Up Environment Variables**

Environment variables are crucial for configuring services. You can set them directly in your shell or use a `.env` file for Docker Compose.

### **Creating a `.env` File**

Create a `.env` file in the root directory of your project with the following content:

```dotenv
# General R2R Settings
R2R_PORT=7272
R2R_HOST=0.0.0.0
R2R_CONFIG_NAME=
R2R_CONFIG_PATH=/app/config
R2R_PROJECT_NAME=r2r_default

# PostgreSQL Settings
R2R_POSTGRES_USER=postgres
R2R_POSTGRES_PASSWORD=postgres
R2R_POSTGRES_HOST=postgres
R2R_POSTGRES_PORT=5432
R2R_POSTGRES_DBNAME=postgres
R2R_POSTGRES_MAX_CONNECTIONS=1024
R2R_POSTGRES_STATEMENT_CACHE_SIZE=100

# Hatchet Settings
HATCHET_POSTGRES_USER=hatchet_user
HATCHET_POSTGRES_PASSWORD=hatchet_password
HATCHET_POSTGRES_DBNAME=hatchet
HATCHET_CLIENT_GRPC_MAX_RECV_MESSAGE_LENGTH=134217728
HATCHET_CLIENT_GRPC_MAX_SEND_MESSAGE_LENGTH=134217728

# RabbitMQ Settings
R2R_RABBITMQ_PORT=5673
R2R_RABBITMQ_MGMT_PORT=15673

# Graph Clustering Settings
R2R_GRAPH_CLUSTERING_PORT=7276

# R2R Dashboard Settings
R2R_DASHBOARD_PORT=7273

# Nginx Settings
R2R_NGINX_PORT=7280

# API Keys and External Services
OPENAI_API_KEY=your_openai_api_key
OPENAI_API_BASE=https://api.openai.com
ANTHROPIC_API_KEY=your_anthropic_api_key
AZURE_API_KEY=your_azure_api_key
AZURE_API_BASE=https://api.azure.com
AZURE_API_VERSION=2023-03-15-preview
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/google/credentials.json
VERTEX_PROJECT=your_vertex_project
VERTEX_LOCATION=your_vertex_location
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION_NAME=your_aws_region
GROQ_API_KEY=your_groq_api_key
COHERE_API_KEY=your_cohere_api_key
ANYSCALE_API_KEY=your_anyscale_api_key
OLLAMA_API_BASE=http://host.docker.internal:11434
HUGGINGFACE_API_BASE=http://host.docker.internal:8080
HUGGINGFACE_API_KEY=your_huggingface_api_key
UNSTRUCTURED_API_KEY=your_unstructured_api_key
UNSTRUCTURED_API_URL=https://api.unstructured.io/general/v0/general
UNSTRUCTURED_SERVICE_URL=http://unstructured:7275
UNSTRUCTURED_NUM_WORKERS=10
CLUSTERING_SERVICE_URL=http://graph_clustering:7276
```

> **Note**: Replace placeholder values (e.g., `your_openai_api_key`) with your actual credentials and configurations. Ensure sensitive information like API keys and passwords are securely stored and managed.

---

## **Dockerfile and Dockerfile.unstructured Overview**

### **Dockerfile**

The `Dockerfile` is used to build the R2R application image.

- **Base Image**: `python:3.12-slim`
- **System Dependencies**: GCC, G++, Musl-dev, Curl, Libffi-dev, Gfortran, Libopenblas-dev, Poppler-utils, Rust (via Rustup)
- **Python Dependencies**: Installed via Poetry with extras `core ingestion-bundle`
- **Final Image**: Copies site-packages and binaries from the builder stage, sets environment variables, exposes the configured port, and runs the application using Uvicorn.

### **Dockerfile.unstructured**

The `Dockerfile.unstructured` builds the Unstructured service image.

- **Base Image**: `python:3.12-slim`
- **System Dependencies**: GCC, G++, Musl-dev, Curl, Libffi-dev, Gfortran, Libopenblas-dev, Tesseract-OCR, Libleptonica-dev, Poppler-utils, Libmagic1, Pandoc, LibreOffice, OpenCV dependencies
- **Python Dependencies**: Installed Unstructured with `unstructured[all-docs]`, Gunicorn, Uvicorn, FastAPI, HTTPX
- **Final Steps**: Copies `main.py`, exposes port `7275`, and runs the application using Uvicorn with 8 workers.

---

## **Docker Compose Configuration**

Docker Compose orchestrates the deployment of all services. There are three main Docker Compose files provided:

1. **compose.yaml**: Basic setup with PostgreSQL and R2R.
2. **compose.full.yaml**: Extends `compose.yaml` by adding Hatchet, RabbitMQ, and related services.
3. **compose.full_with_replicas.yaml**: Further extends `compose.full.yaml` with additional replicas and services.

For a comprehensive deployment, we'll focus on using `compose.full_with_replicas.yaml`.

### **Networks and Volumes**

#### **Networks**

- **r2r-network**: A bridge network facilitating communication between all services.

#### **Volumes**

- **hatchet_certs**: Stores Hatchet SSL certificates.
- **hatchet_config**: Configuration files for Hatchet.
- **hatchet_api_key**: Stores the Hatchet API key.
- **postgres_data**: Persistent storage for PostgreSQL data.
- **hatchet_rabbitmq_data**: Persistent storage for RabbitMQ data.
- **hatchet_rabbitmq_conf**: Configuration files for RabbitMQ.
- **hatchet_postgres_data**: Persistent storage for Hatchet PostgreSQL data.

> **Note**: Volumes ensure data persistence across container restarts and deployments.

### **Services Breakdown**

Below is a detailed overview of each service included in `compose.full_with_replicas.yaml`.

1. **PostgreSQL (`postgres`)**

   - **Image**: `pgvector/pgvector:pg16`
   - **Purpose**: Primary database with vector support for R2R.
   - **Environment Variables**:
     - `POSTGRES_USER`: Database username.
     - `POSTGRES_PASSWORD`: Database password.
     - `POSTGRES_HOST`: Hostname for the database service.
     - `POSTGRES_PORT`: Port number.
     - `POSTGRES_MAX_CONNECTIONS`: Maximum allowed connections.
   - **Volumes**: `postgres_data` for persistent storage.
   - **Ports**: Maps `${R2R_POSTGRES_PORT:-5432}` on the host to `5432` in the container.
   - **Healthcheck**: Ensures PostgreSQL is ready before other services depend on it.
   - **Restart Policy**: `on-failure`

2. **Hatchet PostgreSQL (`hatchet-postgres`)**

   - **Image**: `postgres:latest`
   - **Purpose**: Dedicated PostgreSQL instance for Hatchet.
   - **Environment Variables**:
     - `POSTGRES_DB`: Database name (default `hatchet`).
     - `POSTGRES_USER`: Database username (default `hatchet_user`).
     - `POSTGRES_PASSWORD`: Database password (default `hatchet_password`).
   - **Volumes**: `hatchet_postgres_data` for persistent storage.
   - **Healthcheck**: Ensures Hatchet PostgreSQL is ready.

3. **RabbitMQ (`hatchet-rabbitmq`)**

   - **Image**: `rabbitmq:3-management`
   - **Purpose**: Message broker for Hatchet orchestration.
   - **Environment Variables**:
     - `RABBITMQ_DEFAULT_USER`: Default RabbitMQ user (`user`).
     - `RABBITMQ_DEFAULT_PASS`: Default RabbitMQ password (`password`).
   - **Ports**:
     - `${R2R_RABBITMQ_PORT:-5673}` on the host to `5672` in the container.
     - `${R2R_RABBITMQ_MGMT_PORT:-15673}` on the host to `15672` in the container.
   - **Volumes**:
     - `hatchet_rabbitmq_data`: Persistent storage for RabbitMQ data.
     - `hatchet_rabbitmq_conf`: Configuration files for RabbitMQ.
   - **Healthcheck**: Ensures RabbitMQ is operational.

4. **Hatchet Create DB (`hatchet-create-db`)**

   - **Image**: `postgres:latest`
   - **Purpose**: Initializes the Hatchet database if it doesn't exist.
   - **Command**: Waits for PostgreSQL to be ready and creates the database if absent.
   - **Environment Variables**:
     - `DATABASE_URL`: Connection string for Hatchet PostgreSQL.
   - **Depends On**: `hatchet-postgres`
   - **Networks**: `r2r-network`

5. **Hatchet Migration (`hatchet-migration`)**

   - **Image**: `ghcr.io/hatchet-dev/hatchet/hatchet-migrate:latest`
   - **Purpose**: Applies database migrations for Hatchet.
   - **Environment Variables**:
     - `DATABASE_URL`: Connection string for Hatchet PostgreSQL.
   - **Depends On**: `hatchet-create-db`
   - **Networks**: `r2r-network`

6. **Hatchet Setup Config (`hatchet-setup-config`)**

   - **Image**: `ghcr.io/hatchet-dev/hatchet/hatchet-admin:latest`
   - **Purpose**: Configures Hatchet with initial settings.
   - **Command**: Runs Hatchet admin quickstart with specific options.
   - **Environment Variables**:
     - `DATABASE_URL`: Connection string for Hatchet PostgreSQL.
     - `HATCHET_CLIENT_GRPC_MAX_RECV_MESSAGE_LENGTH`: GRPC settings.
     - Other Hatchet-specific configurations.
   - **Volumes**:
     - `hatchet_certs`: SSL certificates.
     - `hatchet_config`: Configuration files.
   - **Depends On**:
     - `hatchet-migration`
     - `hatchet-rabbitmq`
   - **Networks**: `r2r-network`

7. **Hatchet Engine (`hatchet-engine`)**

   - **Image**: `ghcr.io/hatchet-dev/hatchet/hatchet-engine:latest`
   - **Purpose**: Core engine for Hatchet operations.
   - **Command**: Runs Hatchet engine with specified configuration.
   - **Environment Variables**:
     - `DATABASE_URL`: Connection string for Hatchet PostgreSQL.
     - GRPC settings.
   - **Ports**: Maps `${R2R_HATCHET_ENGINE_PORT:-7077}` on the host to `7077` in the container.
   - **Volumes**:
     - `hatchet_certs`: SSL certificates.
     - `hatchet_config`: Configuration files.
   - **Healthcheck**: Ensures the Hatchet engine is live.
   - **Depends On**: `hatchet-setup-config`
   - **Restart Policy**: `on-failure`

8. **Hatchet Dashboard (`hatchet-dashboard`)**

   - **Image**: `ghcr.io/hatchet-dev/hatchet/hatchet-dashboard:latest`
   - **Purpose**: Web interface for managing Hatchet.
   - **Command**: Runs Hatchet dashboard with specified configuration.
   - **Environment Variables**:
     - `DATABASE_URL`: Connection string for Hatchet PostgreSQL.
   - **Ports**: Maps `${R2R_HATCHET_DASHBOARD_PORT:-7274}` on the host to `80` in the container.
   - **Volumes**:
     - `hatchet_certs`: SSL certificates.
     - `hatchet_config`: Configuration files.
   - **Depends On**: `hatchet-setup-config`
   - **Networks**: `r2r-network`

9. **Setup Token (`setup-token`)**

   - **Image**: `ghcr.io/hatchet-dev/hatchet/hatchet-admin:latest`
   - **Purpose**: Generates and stores the Hatchet API token.
   - **Command**: Executes a shell script to create and validate the API token.
   - **Volumes**:
     - `hatchet_certs`: SSL certificates.
     - `hatchet_config`: Configuration files.
     - `hatchet_api_key`: Stores the generated API key.
   - **Depends On**: `hatchet-setup-config`
   - **Networks**: `r2r-network`

10. **Unstructured (`unstructured`)**

    - **Image**: `${UNSTRUCTURED_IMAGE:-ragtoriches/unst-prod}`
    - **Purpose**: Handles document parsing and processing.
    - **Healthcheck**: Ensures the Unstructured service is operational.
    - **Networks**: `r2r-network`

11. **Graph Clustering (`graph_clustering`)**

    - **Image**: `${GRAPH_CLUSTERING_IMAGE:-ragtoriches/cluster-prod}`
    - **Purpose**: Manages community detection within knowledge graphs.
    - **Ports**: Maps `${R2R_GRAPH_CLUSTERING_PORT:-7276}` on the host to `7276` in the container.
    - **Healthcheck**: Ensures the Graph Clustering service is operational.
    - **Networks**: `r2r-network`

12. **R2R (`r2r`)**

    - **Image**: `${R2R_IMAGE:-ragtoriches/prod:latest}`
    - **Build Context**: Current directory (`.`)
    - **Environment Variables**:
      - General R2R settings (`R2R_PORT`, `R2R_HOST`, etc.).
      - PostgreSQL connection details.
      - API keys for external services (OpenAI, Anthropic, Azure, etc.).
      - Hatchet and Graph Clustering settings.
    - **Command**: Sets the Hatchet API token and starts the R2R application using Uvicorn.
    - **Healthcheck**: Ensures the R2R application is operational.
    - **Restart Policy**: `on-failure`
    - **Volumes**:
      - `${R2R_CONFIG_PATH:-/}`: Configuration directory.
      - `hatchet_api_key`: Read-only access to the Hatchet API key.
    - **Extra Hosts**: Adds `host.docker.internal` to facilitate communication with host services.
    - **Depends On**:
      - `setup-token`
      - `unstructured`
    - **Networks**: `r2r-network`

13. **R2R Dashboard (`r2r-dashboard`)**

    - **Image**: `emrgntcmplxty/r2r-dashboard:latest`
    - **Environment Variables**:
      - `NEXT_PUBLIC_R2R_DEPLOYMENT_URL`: URL to the R2R API.
      - `NEXT_PUBLIC_HATCHET_DASHBOARD_URL`: URL to the Hatchet Dashboard.
    - **Ports**: Maps `${R2R_DASHBOARD_PORT:-7273}` on the host to `3000` in the container.
    - **Networks**: `r2r-network`

14. **Nginx (`nginx`)**

    - **Image**: `nginx:latest`
    - **Purpose**: Acts as a reverse proxy to route traffic to R2R and other services.
    - **Ports**: Maps `${R2R_NGINX_PORT:-7280}` on the host to `80` in the container.
    - **Volumes**: Mounts `nginx.conf` from the host to the container.
    - **Depends On**: `r2r`
    - **Deploy Resources**:
      - Limits CPU to `0.5`
      - Limits memory to `512M`
    - **Healthcheck**: Ensures Nginx is operational.
    - **Networks**: `r2r-network`

> **Note**: Ensure that `nginx.conf` is properly configured to proxy requests to the appropriate services.

---

## **Building and Running the Deployment**

### **Step 1: Clone the Repository**

First, clone the R2R repository containing all necessary deployment files.

```bash
git clone https://github.com/SciPhi-AI/r2r.git
cd r2r
```

> **Note**: Replace the repository URL with the actual URL if different.

### **Step 2: Configure Environment Variables**

Ensure that all necessary environment variables are set. You can use the `.env` file method described earlier.

```bash
cp .env.example .env
# Edit the .env file with your specific configurations
nano .env
```

> **Tip**: Use a text editor of your choice (e.g., `vim`, `nano`) to edit the `.env` file.

### **Step 3: Build Docker Images**

Build the Docker images using the provided `Dockerfile` and `Dockerfile.unstructured`.

```bash
# Build the R2R application image
docker build -t r2r-app -f Dockerfile .

# Build the Unstructured service image
docker build -t unstructured-service -f Dockerfile.unstructured .
```

> **Note**: Ensure Docker is running before executing these commands. The build process may take several minutes.

### **Step 4: Deploy Services with Docker Compose**

Use Docker Compose to deploy all services as defined in `compose.full_with_replicas.yaml`.

```bash
docker-compose -f compose.full_with_replicas.yaml up -d
```

> **Flags Explained**:
> - `-f compose.full_with_replicas.yaml`: Specifies the Docker Compose file to use.
> - `up`: Builds, (re)creates, starts, and attaches to containers for a service.
> - `-d`: Runs containers in the background (detached mode).

> **Monitoring Deployment**:
> You can monitor the status of your services using:
> ```bash
> docker-compose -f compose.full_with_replicas.yaml ps
> ```

---

## **Initial Setup Steps**

After deploying the services, perform the following initial setup steps to configure Hatchet and R2R.

### **Creating the Hatchet API Token**

The `setup-token` service is responsible for generating the Hatchet API token, which R2R uses to communicate with Hatchet.

1. **Ensure `setup-token` Service is Running**

   The `setup-token` service should have already been started by Docker Compose. Verify its status:

   ```bash
   docker-compose -f compose.full_with_replicas.yaml ps
   ```

2. **Verify Token Generation**

   The token is stored in the `hatchet_api_key` volume. To retrieve the token:

   ```bash
   docker exec -it <r2r_container_name> cat /hatchet_api_key/api_key.txt
   ```

   Replace `<r2r_container_name>` with the actual container name, which can be found using:

   ```bash
   docker-compose -f compose.full_with_replicas.yaml ps
   ```

3. **Set Hatchet API Token Environment Variable**

   Ensure that the `HATCHET_CLIENT_TOKEN` environment variable is correctly set in the `r2r` service. This is handled automatically by the `r2r` service command, which reads the token from the `hatchet_api_key` volume.

---

## **Accessing R2R and Hatchet Dashboard**

### **R2R API**

- **URL**: `http://<your-server-ip>:7272`
- **Health Check Endpoint**: `http://<your-server-ip>:7272/v3/health`

### **Hatchet Dashboard**

- **URL**: `http://<your-server-ip>:7274`

### **R2R Dashboard**

- **URL**: `http://<your-server-ip>:7273`

### **Nginx Reverse Proxy**

- **URL**: `http://<your-server-ip>:7280`

> **Note**: Replace `<your-server-ip>` with your server's actual IP address or domain name. Ensure that the specified ports are open and accessible.

---

## **Configuring Nginx as a Reverse Proxy**

Nginx serves as a reverse proxy, directing incoming traffic to the appropriate services based on the configuration in `nginx.conf`.

### **Sample `nginx.conf`**

Ensure you have an `nginx.conf` file in your project root with appropriate proxy settings. Here's a basic example:

```nginx
worker_processes 1;

events { worker_connections 1024; }

http {
    server {
        listen 80;

        location /api/ {
            proxy_pass http://r2r:7272/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /dashboard/ {
            proxy_pass http://r2r-dashboard:3000/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /hatchet-dashboard/ {
            proxy_pass http://hatchet-dashboard:80/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location / {
            proxy_pass http://nginx:80/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

> **Customization**: Modify `nginx.conf` according to your routing needs. Ensure that service names in `proxy_pass` match the service names defined in Docker Compose.

### **Reloading Nginx Configuration**

After updating `nginx.conf`, reload Nginx to apply changes:

```bash
docker-compose -f compose.full_with_replicas.yaml exec nginx nginx -s reload
```

---

## **Configuring R2R**

R2R's behavior is controlled via the `r2r.toml` file. Ensure this file is correctly configured before starting the services.

### **Sample `r2r.toml`**

Below is a sample `r2r.toml` with essential configurations:

```toml
[app]
default_max_documents_per_user = 100
default_max_chunks_per_user = 10000
default_max_collections_per_user = 10

[agent]
rag_agent_static_prompt = "rag_agent"
tools = ["search_file_knowledge"]

  [agent.generation_config]
  model = "openai/gpt-4o"

[auth]
provider = "r2r"
access_token_lifetime_in_minutes = 60
refresh_token_lifetime_in_days = 7
require_authentication = false
require_email_verification = false
default_admin_email = "admin@example.com"
default_admin_password = "change_me_immediately"

[completion]
provider = "litellm"
concurrent_request_limit = 64

  [completion.generation_config]
  model = "openai/gpt-4o"
  temperature = 0.1
  top_p = 1
  max_tokens_to_sample = 1024
  stream = false
  add_generation_kwargs = { }

[crypto]
provider = "bcrypt"

[database]
provider = "postgres"
default_collection_name = "Default"
default_collection_description = "Your default collection."
batch_size = 256

  [database.graph_creation_settings]
    graph_entity_description_prompt = "graph_entity_description"
    entity_types = []
    relation_types = []
    fragment_merge_count = 1
    max_knowledge_relationships = 100
    max_description_input_length = 65536
    generation_config = { model = "openai/gpt-4o-mini" }

  [database.graph_enrichment_settings]
    max_summary_input_length = 65536
    generation_config = { model = "openai/gpt-4o-mini" }
    leiden_params = {}

  [database.graph_search_settings]
    generation_config = { model = "openai/gpt-4o-mini" }

  [database.limits]
    global_per_min = 300
    monthly_limit = 10000

  [database.route_limits]
    "/v3/retrieval/search" = { route_per_min = 120 }
    "/v3/retrieval/rag" = { route_per_min = 30 }

[embedding]
provider = "litellm"
base_model = "openai/text-embedding-3-small"
base_dimension = 512
batch_size = 128
add_title_as_prefix = false
concurrent_request_limit = 256
quantization_settings = { quantization_type = "FP32" }

[file]
provider = "postgres"

[ingestion]
provider = "r2r"
chunking_strategy = "recursive"
chunk_size = 1024
chunk_overlap = 512
excluded_parsers = ["mp4"]
document_summary_model = "openai/gpt-4o-mini"

  [ingestion.chunk_enrichment_settings]
    enable_chunk_enrichment = false
    strategies = ["semantic", "neighborhood"]
    forward_chunks = 3
    backward_chunks = 3
    semantic_neighbors = 10
    semantic_similarity_threshold = 0.7
    generation_config = { model = "openai/gpt-4o-mini" }

  [ingestion.extra_parsers]
    pdf = "zerox"

[logging]
provider = "r2r"
log_table = "logs"
log_info_table = "log_info"

[orchestration]
provider = "simple"

[prompt]
provider = "r2r"

[email]
provider = "console_mock"
```

### **Key Configuration Sections**

- **[app]**: Sets default limits for documents, chunks, and collections per user.
- **[agent]**: Configures the RAG agent, specifying tools and generation models.
- **[auth]**: Authentication settings, including token lifetimes and default admin credentials.
- **[completion]**: Settings for text completion, including provider and generation configurations.
- **[crypto]**: Cryptographic provider.
- **[database]**: PostgreSQL settings, knowledge graph configurations, and rate limits.
- **[embedding]**: Embedding provider configurations.
- **[file]**: File storage provider.
- **[ingestion]**: Data ingestion settings, including chunking strategies and enrichment configurations.
- **[logging]**: Logging provider and tables.
- **[orchestration]**: Orchestration provider settings.
- **[prompt]**: Prompt management provider.
- **[email]**: Email provider settings.

> **Customization**: Adjust the `r2r.toml` file according to your specific requirements. Ensure that all paths, models, and service URLs match your deployment environment.

---

## **Maintenance and Scaling**

### **Vector Indices**

**Do You Need Vector Indices?**

Vector indices enhance search capabilities but are not necessary for all deployments, especially in multi-user environments with user-specific filtering.

**When to Implement Vector Indices:**

- Large-scale searches across hundreds of thousands of documents.
- When query latency becomes a bottleneck.
- Supporting cross-user search functionalities.

**Vector Index Management:**

R2R supports various indexing methods, with HNSW (Hierarchical Navigable Small World) recommended for most use cases.

**Example: Creating and Deleting a Vector Index**

```python
from r2r import R2RClient

client = R2RClient()

# Create vector index
create_response = client.indices.create(
    {
        "table_name": "vectors",
        "index_method": "hnsw",
        "index_measure": "cosine_distance",
        "index_arguments": {
            "m": 16,
            "ef_construction": 64
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

**Important Considerations:**

1. **Pre-warming**: New indices start "cold" and require warming for optimal performance.
2. **Resource Usage**: Index creation is CPU and memory-intensive. Perform during off-peak hours.
3. **Performance Tuning**:
   - **HNSW Parameters**:
     - `m`: 16-64 (higher = better quality, more memory)
     - `ef_construction`: 64-100 (higher = better quality, longer build time)
   - **Distance Measures**:
     - `cosine_distance`: Best for normalized vectors.
     - `l2_distance`: Better for absolute distances.
     - `max_inner_product`: Optimized for dot product similarity.

### **System Updates and Maintenance**

**Version Management**

Check the current R2R version:

```bash
docker-compose -f compose.full_with_replicas.yaml exec r2r r2r version
```

**Update Process**

1. **Prepare for Update**

   ```bash
   docker-compose -f compose.full_with_replicas.yaml exec r2r r2r version
   docker-compose -f compose.full_with_replicas.yaml exec r2r r2r db current
   docker-compose -f compose.full_with_replicas.yaml exec r2r r2r generate-report
   ```

2. **Stop Running Services**

   ```bash
   docker-compose -f compose.full_with_replicas.yaml down
   ```

3. **Update R2R**

   ```bash
   docker-compose -f compose.full_with_replicas.yaml pull
   docker-compose -f compose.full_with_replicas.yaml up -d --build
   ```

4. **Update Database**

   ```bash
   docker-compose -f compose.full_with_replicas.yaml exec r2r r2r db upgrade
   ```

5. **Restart Services**

   ```bash
   docker-compose -f compose.full_with_replicas.yaml up -d
   ```

**Database Migration Management**

Check current migration:

```bash
docker-compose -f compose.full_with_replicas.yaml exec r2r r2r db current
```

Apply migrations:

```bash
docker-compose -f compose.full_with_replicas.yaml exec r2r r2r db upgrade
```

Rollback if necessary:

```bash
docker-compose -f compose.full_with_replicas.yaml exec r2r r2r db downgrade --revision <previous-working-version>
```

### **Managing Multiple Environments**

Use different project names and schemas for development, staging, and production environments.

**Example:**

```bash
# Development
export R2R_PROJECT_NAME=r2r_dev
docker-compose -f compose.full_with_replicas.yaml up -d

# Staging
export R2R_PROJECT_NAME=r2r_staging
docker-compose -f compose.full_with_replicas.yaml up -d

# Production
export R2R_PROJECT_NAME=r2r_prod
docker-compose -f compose.full_with_replicas.yaml up -d
```

---

## **Security Considerations**

Ensuring the security of your deployment is paramount. Follow these best practices to secure your R2R deployment.

1. **Secure Environment Variables**

   - Store sensitive information like API keys and passwords securely.
   - Avoid hardcoding secrets in configuration files. Use environment variables or secret management tools.

2. **Use HTTPS**

   - Configure Nginx to use HTTPS with valid SSL certificates to encrypt data in transit.
   - Update `nginx.conf` to include SSL configurations.

3. **Restrict Access to Services**

   - Limit access to PostgreSQL and RabbitMQ to only necessary services.
   - Use firewall rules to restrict external access to sensitive ports.

4. **Strong Passwords**

   - Use strong, unique passwords for all services, especially for PostgreSQL and RabbitMQ.
   - Regularly update and rotate passwords.

5. **Enable Authentication and Verification**

   - In `r2r.toml`, set `require_authentication = true` and `require_email_verification = true` for production environments.
   - Update default admin credentials immediately after deployment.

6. **Rate Limiting**

   - Configure rate limits in `r2r.toml` to prevent abuse:
     ```toml
     [database.route_limits]
       "/v3/retrieval/search" = { route_per_min = 120 }
       "/v3/retrieval/rag" = { route_per_min = 30 }
     ```

7. **Regular Security Audits**

   - Periodically review logs and monitor for suspicious activities.
   - Keep all services and dependencies updated with the latest security patches.

8. **Secure Nginx Configuration**

   - Ensure Nginx is properly configured to prevent vulnerabilities like open redirects and XSS attacks.
   - Implement security headers:
     ```nginx
     add_header X-Content-Type-Options nosniff;
     add_header X-Frame-Options DENY;
     add_header X-XSS-Protection "1; mode=block";
     add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
     ```

---

## **Troubleshooting**

Deployments can encounter issues. Below are common problems and their solutions.

1. **Service Not Starting**

   - **Check Logs**:
     ```bash
     docker-compose -f compose.full_with_replicas.yaml logs <service_name>
     ```
   - **Example**:
     ```bash
     docker-compose -f compose.full_with_replicas.yaml logs r2r
     ```

2. **Database Connection Issues**

   - **Verify Environment Variables**: Ensure `R2R_POSTGRES_HOST`, `R2R_POSTGRES_PORT`, `R2R_POSTGRES_USER`, and `R2R_POSTGRES_PASSWORD` are correct.
   - **Check Service Status**:
     ```bash
     docker-compose -f compose.full_with_replicas.yaml ps
     ```

3. **Healthchecks Failing**

   - **Inspect Health Status**:
     ```bash
     docker inspect --format='{{json .State.Health}}' <container_name>
     ```
   - **Restart Services**:
     ```bash
     docker-compose -f compose.full_with_replicas.yaml restart <service_name>
     ```

4. **API Not Responding**

   - **Ensure R2R is Running**:
     ```bash
     docker-compose -f compose.full_with_replicas.yaml ps
     ```
   - **Check Network Connectivity**:
     ```bash
     docker-compose -f compose.full_with_replicas.yaml exec r2r ping postgres
     ```

5. **Token Generation Issues**

   - **Verify `setup-token` Service Logs**:
     ```bash
     docker-compose -f compose.full_with_replicas.yaml logs setup-token
     ```
   - **Ensure `hatchet_api_key` Volume is Mounted Correctly**

6. **Nginx Proxy Issues**

   - **Check Nginx Configuration**: Ensure `nginx.conf` correctly routes traffic.
   - **Reload Nginx**:
     ```bash
     docker-compose -f compose.full_with_replicas.yaml exec nginx nginx -s reload
     ```

7. **Unstructured Service Failures**

   - **Check Dependencies**: Ensure all system dependencies are installed.
   - **Inspect Logs**:
     ```bash
     docker-compose -f compose.full_with_replicas.yaml logs unstructured
     ```

---

## **Conclusion**

Deploying R2R involves orchestrating multiple services to work seamlessly together. By following this guide, you should be able to set up a robust and secure R2R deployment tailored to your needs. Remember to regularly update your services, monitor performance, and enforce security best practices to maintain the integrity and efficiency of your R2R application.

For further assistance, refer to the [R2R Comprehensive Documentation](#) or reach out to the [SciPhi AI Support Team](mailto:support@sciphi.ai).

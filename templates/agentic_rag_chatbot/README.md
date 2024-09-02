## Agentic RAG Chatbot
### by SciPhi

[!IMPORTANT]
R2R templates are in beta! We value your feedback and contributions to make them more widely accessible.

| Framework | Python, Next.js |
|-----------|-----------------|
| Use Case  | AI, RAG         |


A boilerplate chatbot that uses the R2R Python SDK to connect to an R2R server. This template offers a simple and clean interfact for users to interact with the chatbot.

### Deploying

First, we can create a Python backend to ingest our data:

```python
from r2r import R2RClient
import time

# Our R2R base URL is the URL of our SciPhi deployed R2R server
client = R2RClient("YOUR_SCIPHI_DEPLOYMENT_URL")

# We'll make sure that we can connect to the server
health_response = client.health()
print(health_response)

# We'll ingest the data from the data folder
file_paths = ["../web-app/public/data"]
t0 = time.time()
ingest_response = client.ingest_files(
    file_paths=file_paths,
)
t1 = time.time()
print(ingest_response)
print(f"Time taken to ingest: {t1 - t0} seconds")
```

```bash
git clone https://github.com/SciPhi-AI/R2R-Templates
cd R2R-Templates/chat/web-app
export NEXT_PUBLIC_DEFAULT_AGENT_URL=YOUR_SCIPHI_DEPLOYMENT_URL
npm run build
npm run start
```

###

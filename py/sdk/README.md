# FUSE Python SDK Documentation

For the complete look at the FUSE Python SDK, [visit our documentation.](https://fuse-docs.sciphi.ai/documentation/python-sdk/introduction)

## Installation

Before starting, make sure you have completed the [FUSE installation](/documentation/installation).

Install the FUSE Python SDK:

```bash
pip install fuse
```

## Getting Started

1. Import the FUSE client:

```python
from fuse import FUSEClient
```

2. Initialize the client:

```python
client = FUSEClient("http://localhost:7272")
```


3. Check if FUSE is running correctly:

```python
health_response = client.health()
# {"status":"ok"}
```

4. Login (Optional):
```python
client.register("me@email.com", "my_password")
# client.verify_email("me@email.com", "my_verification_code")
client.login("me@email.com", "my_password")
```
When using authentication the commands below automatically restrict the scope to a user's available documents.

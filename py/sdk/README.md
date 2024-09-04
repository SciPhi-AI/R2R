# R2R Python SDK Documentation

For the complete look at the R2R Python SDK, [visit our documentation.](https://r2r-docs.sciphi.ai/documentation/python-sdk/introduction)

## Installation

Before starting, make sure you have completed the [R2R installation](/documentation/installation).

Install the R2R Python SDK:

```bash
pip install r2r
```

## Getting Started

1. Import the R2R client:

```python
from r2r import R2RClient
```

2. Initialize the client:

```python
client = R2RClient("http://localhost:7272")
```


3. Check if R2R is running correctly:

```python
health_response = client.health()
# {"status":"ok"}
```

4. Login (Optional):
```python
# client.register("me@email.com", "my_password")
# client.verify_email("me@email.com", "my_verification_code")
client.login("me@email.com", "my_password")
```
When using authentication the commands below automatically restrict the scope to a user's available documents.

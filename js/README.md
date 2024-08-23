# R2R JavaScript SDK Documentation

For the complete R2R JavaScript Documentation, visit here:

## Installation

Before starting, make sure you have completed the [R2R installation](/documentation/installation).

Install the R2R JavaScript SDK:

```bash
npm install r2r-js
```

## Getting Started

1. Import the R2R client:

```javascript
const { r2rClient } = require('r2r-js');
```

2. Initialize the client:

```javascript
const client = new r2rClient('http://localhost:8000');
```

3. Check if R2R is running correctly:

```javascript
const healthResponse = await client.health();
// {"status":"ok"}
```

4. Login (Optional):
```javascript
// client.register("me@email.com", "my_password"),
// client.verify_email("me@email.com", "my_verification_code")
client.login("me@email.com", "my_password")
```
When using authentication the commands below automatically restrict the scope to a user's available documents.

## Additional Documentation

For more detailed information on specific functionalities of R2R, please refer to the following documentation:

- [Document Ingestion](/documentation/python-sdk/ingestion): Learn how to add, retrieve, and manage documents in R2R.
- [Search & RAG](/documentation/python-sdk/retrieval): Explore various querying techniques and Retrieval-Augmented Generation capabilities.
- [Authentication](/documentation/python-sdk/auth): Understand how to manage users and implement authentication in R2R.
- [Observability](/documentation/python-sdk/observability): Learn about analytics and monitoring tools for your R2R system.

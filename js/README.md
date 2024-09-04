# R2R JavaScript SDK Documentation

For the complete look at the R2R JavaScript SDK, [visit our documentation.](https://r2r-docs.sciphi.ai/documentation/js-sdk/introduction)

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
const client = new r2rClient('http://localhost:7272');
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

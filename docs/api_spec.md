# Ellen V2: API Specification

**Version**: 1.0

This document specifies the custom API endpoints required for Ellen V2. The primary custom API is the one that exposes the CrewAI flows. The R2R API is used directly by the frontend and the CrewAI tool, and its specification can be found in the official R2R documentation.

## 1. CrewAI Services API

This is a FastAPI application running at `http://localhost:8001`. It serves as the entry point to the Reasoning Layer.

### Base URL
`/api/v1`

### Authentication
All endpoints on this server should be protected and require a valid JWT token issued by Supabase Auth. The token will be passed in the `Authorization: Bearer <token>` header.

### Endpoints

#### 1.1. Trigger a Flow
- **Endpoint**: `POST /flows/trigger`
- **Description**: Asynchronously starts a CrewAI flow and returns a task ID to track its progress. This is the primary endpoint for initiating complex analysis or entity updates.

##### Request Body
```json
{
  "flow_name": "entity_update_flow",
  "input_data": {
    "entity_name": "Lithium",
    "document_id": "c1b2a3d4-e5f6-7890-1234-567890abcdef"
    // Other inputs specific to the flow
  }
}
```

##### Success Response (202)
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "pending",
  "message": "Flow 'entity_update_flow' has been initiated."
}
```

##### Error Response (400, 404, 500)
```json
{
  "detail": "Flow 'invalid_flow_name' not found."
}
```

#### 1.2. Get Flow Status
- **Endpoint**: `GET /flows/status/{task_id}`
- **Description**: Retrieves the current status and, if completed, the result of a previously triggered flow.

##### Path Parameters
| Parameter | Type   | Description                          |
|-----------|--------|--------------------------------------|
| `task_id` | string | ID returned from `/flows/trigger` |

##### Success Response (200)
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "completed",
  "started_at": "2025-09-20T10:00:00Z",
  "finished_at": "2025-09-20T10:05:00Z",
  "result": {
    "updated_section": "financial_summary",
    "summary": "Revenue increased by 15% in Q3."
  }
}
```

##### Error Response (404)
```json
{
  "detail": "Task with ID '...' not found."
}
```

## 2. Frontend to Backend Interaction
The Next.js frontend will interact with three main APIs:

| API                      | Purpose                                                                 |
|--------------------------|-------------------------------------------------------------------------|
| **Supabase API**         | Authentication, user management, and direct data queries               |
| **R2R API (:7272)**      | RAG-related chat functionalities (document upload, search, streaming)  |
| **CrewAI API (:8001)**   | Triggering advanced multi-step analytical tasks ("Decision Frameworks") |

### Example: Triggering a Flow from Frontend
```javascript
// Next.js API route
export default async function handler(req, res) {
  const { flowName, inputData } = req.body;
  
  // Call CrewAI Services API
  const response = await fetch('http://localhost:8001/api/v1/flows/trigger', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${supabaseToken}`
    },
    body: JSON.stringify({ flow_name: flowName, input_data: inputData })
  });
  
  const result = await response.json();
  res.status(200).json(result);
}
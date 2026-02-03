# PERCIA v2.0 — API Reference

## Base URL
```
http://127.0.0.1:5000
```

## Authentication
All endpoints except `/`, `/api/system/health` require the `X-API-Key` header.

```
X-API-Key: your-api-key-here-minimum-32-characters
```

**Error responses**:
- Missing key: `401 {"code": "AUTH_MISSING", "error": "API key requerida"}`
- Invalid key: `401 {"code": "AUTH_INVALID", "error": "API key invalida"}`

## Rate Limiting
Endpoints are rate-limited. Exceeding the limit returns:
```
429 Too Many Requests
```

## Security Headers
All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), camera=(), microphone=()`
- `Cache-Control: no-store` (API endpoints only)

---

## Endpoints

### GET /
HTML manual page. No authentication required.

### GET /api/system/health
Health check endpoint. No authentication required.

**Response** `200`:
```json
{
  "status": "healthy",
  "components": {
    "lock_manager": true,
    "commit_coordinator": true,
    "validator": true
  },
  "timestamp": "2026-02-03T00:27:43.188Z"
}
```

**Response** `503`: One or more components unhealthy.

### GET /api/system/status
System status with detailed component information. Requires authentication.

**Response** `200`:
```json
{
  "status": "operational",
  "base_path": "/path/to/percia-v2",
  "mcp_dir": "/path/to/percia-v2/mcp-knowledge-base",
  "components": {
    "lock_manager": {"initialized": true, "lock_status": {}},
    "commit_coordinator": {"initialized": true},
    "validator": {"initialized": true}
  }
}
```

### POST /api/bootstrap/create
Create a new governance bootstrap configuration.

**Request Body**:
```json
{
  "name": "Security Review Cycle",
  "participants": ["chatgpt", "claude", "gemini"],
  "threshold": 0.66,
  "rules": {}
}
```

**Response** `201`:
```json
{
  "bootstrap_id": "uuid-here",
  "status": "created",
  "timestamp": "2026-02-03T00:30:00.000Z"
}
```

### GET /api/bootstrap/get
Retrieve current bootstrap configuration.

**Response** `200`: Bootstrap configuration object.
**Response** `404`: No bootstrap configured.

### POST /api/cycle/start
Start a new review cycle.

**Request Body**:
```json
{
  "bootstrap_id": "uuid-here",
  "description": "Review security patches"
}
```

**Response** `201`: Cycle started.

### POST /api/proposal/submit
Submit a code change proposal for review.

**Request Body**:
```json
{
  "cycle_id": "uuid-here",
  "ia_id": "claude",
  "title": "Fix buffer overflow",
  "files_modified": ["src/main.py"],
  "description": "Detailed description of changes",
  "diff": "unified diff content"
}
```

**Response** `201`: Proposal submitted.

### GET /api/proposals/list
List all proposals for the current cycle.

**Query Parameters**:
- `cycle_id` (optional): Filter by cycle

**Response** `200`: Array of proposal objects.

### GET /api/challenges/list
List all challenges against proposals.

**Query Parameters**:
- `proposal_id` (optional): Filter by proposal

**Response** `200`: Array of challenge objects.

### POST /api/governance/decide
Submit a governance decision on a proposal.

**Request Body**:
```json
{
  "proposal_id": "uuid-here",
  "decision": "accept",
  "ia_id": "gemini",
  "reasoning": "Explanation of decision"
}
```

**Response** `200`: Decision recorded.

### GET /api/metrics/get
Retrieve system metrics and audit statistics.

**Response** `200`:
```json
{
  "total_cycles": 5,
  "total_proposals": 23,
  "total_challenges": 8,
  "acceptance_rate": 0.78,
  "timestamp": "2026-02-03T00:35:00.000Z"
}
```

### GET /api/queue/status
Get the current lock queue status.

**Response** `200`:
```json
{
  "queue_length": 2,
  "entries": [
    {"ia_id": "chatgpt", "operation_type": "write", "queued_at": "..."},
    {"ia_id": "gemini", "operation_type": "write", "queued_at": "..."}
  ],
  "timestamp": "2026-02-03T00:36:00.000Z"
}
```

---

## Error Responses

All errors follow this format:
```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "timestamp": "2026-02-03T00:00:00.000Z"
}
```

| Code | HTTP Status | Description |
|------|-------------|-------------|
| AUTH_MISSING | 401 | No X-API-Key header |
| AUTH_INVALID | 401 | Incorrect API key |
| NOT_FOUND | 404 | Endpoint or resource not found |
| RATE_LIMITED | 429 | Too many requests |
| VALIDATION_ERROR | 400 | Invalid request body |
| LOCK_TIMEOUT | 408 | Could not acquire lock |
| INTERNAL_ERROR | 500 | Unexpected server error |

# PERCIA v2.0 — Architecture Guide

## System Overview

PERCIA (Protocol for Evaluation and Review of Code by Intelligences/AIs) is a governance protocol that enables multiple AI systems to collaboratively review and make decisions about code changes through structured review cycles.

## Components

### app.py — REST API Server
The central interface for all PERCIA operations. Built on Flask with security hardening.

**Responsibilities**:
- Expose REST API endpoints for all PERCIA operations
- Authenticate requests via `X-API-Key` header using `hmac.compare_digest`
- Apply rate limiting via `flask-limiter`
- Inject security headers on all responses
- Coordinate between LockManager, CommitCoordinator, and Validator
- Serve HTML manual at root endpoint

**Security Features**:
- Fail-closed API key validation (32+ chars, no defaults)
- debug+remote host detection and blocking
- Rate limiting per endpoint
- Full security header suite (CSP, X-Frame-Options, etc.)
- Constant-time API key comparison

### lock_manager.py — Distributed Lock Manager
Manages exclusive access to shared resources during review cycles.

**Responsibilities**:
- Provide global lock acquisition and release
- Maintain lock queue for waiting AI agents
- Detect and recover from stale locks (dead processes)
- Provide thread-safe queue status reporting

**Key Design Decisions**:
- File-based locks (no external dependencies like Redis)
- PID + `process_start_time` for stale detection (handles OS PID reuse)
- `threading.RLock` for all queue operations
- `lock_context()` context manager with `acquired` flag to prevent unsafe release

### commit_coordinator.py — Git Operations Coordinator
Manages Git operations with input validation, rollback capability, and zombie commit prevention.

**Responsibilities**:
- Stage, commit, and push changes via Git
- Validate all inputs (hashes, branch names, paths) before shell execution
- Provide atomic rollback using `restore_git_state` flag
- Track commit state through lifecycle phases

**Key Design Decisions**:
- `re.fullmatch()` for Git hash validation (not `re.match()`)
- Shell metacharacter rejection on all Git arguments
- Rollback only executes `git reset` when `restore_git_state` is True
- `CommitState` dataclass tracks operation lifecycle

### validator.py — File and Path Validator
Validates file paths, content, and integrity with defense-in-depth protections.

**Responsibilities**:
- Validate file paths are within allowed base directory
- Check file extensions against whitelist
- Detect path traversal attempts (`../`, null bytes, absolute paths)
- Validate file sizes against configurable limits
- Verify content integrity via hashes

**Key Design Decisions**:
- `Path.resolve()` + `Path.relative_to()` for traversal protection
- Explicit extension whitelist (deny by default)
- String sanitization for control characters

## Data Flow

```
Client Request
    │
    ▼
┌──────────┐     ┌─────────────┐
│ app.py   │────▶│ Rate Limiter│
│ (Flask)  │     └─────────────┘
│          │
│ Auth ────│──── hmac.compare_digest(key)
│          │
│ Route ───│──┬─▶ LockManager.acquire/release
│          │  │
│          │  ├─▶ CommitCoordinator.commit/rollback
│          │  │
│          │  └─▶ Validator.validate_file/validate_hash
│          │
│ Response─│──── Security Headers injected
└──────────┘
```

## PERCIA Review Cycle

```
1. Bootstrap    → Define rules, participants, thresholds
2. Cycle Start  → Open a review round
3. Proposal     → AI submits code change proposal
4. Challenge    → Other AIs challenge or support the proposal
5. Governance   → Consensus decision (accept/reject/revise)
6. Metrics      → Record outcomes for future learning
```

Each phase uses the LockManager to ensure exclusive access and the CommitCoordinator to manage Git state atomically.

## Directory Structure

```
percia-v2/
├── src/
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── lock_manager.py
│   │   ├── commit_coordinator.py
│   │   └── validator.py
│   └── web-interface/
│       └── app.py
├── tests/
│   ├── conftest.py
│   ├── test_app_security.py
│   ├── test_lock_manager_security.py
│   ├── test_commit_coordinator_security.py
│   └── test_validator_security.py
├── mcp-knowledge-base/         # Git-initialized data directory
├── docs/
│   ├── SECURITY_AUDIT.md
│   ├── ARCHITECTURE.md
│   ├── API_REFERENCE.md
│   └── OPERATIONS.md
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.10+ |
| Web Framework | Flask | 3.x |
| Rate Limiting | flask-limiter | 4.x |
| Process Info | psutil | 5.x+ |
| Testing | pytest | 9.x |
| Version Control | Git | 2.x |
| OS | Windows / Linux | Any |

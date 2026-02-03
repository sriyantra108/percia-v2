# PERCIA v2.0 — Protocol for Evaluation and Review of Code by Intelligences (AIs)

A governance protocol that coordinates multiple AI systems for critical technical decision-making through structured review cycles with built-in security and consensus mechanisms.

---

## Architecture

```
percia-v2/
├── src/
│   ├── scripts/
│   │   ├── lock_manager.py        # Distributed lock with PID-aware stale detection
│   │   ├── commit_coordinator.py  # Git operations with input validation & rollback
│   │   └── validator.py           # File/path validation with traversal protection
│   └── web-interface/
│       └── app.py                 # REST API server (Flask + security hardening)
├── tests/                         # 63 security tests (pytest)
├── requirements.txt
└── docs/                          # Technical documentation
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install pytest psutil

# 2. Set required environment variables
export PERCIA_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export PERCIA_FLASK_DEBUG=false
export PERCIA_FLASK_HOST=127.0.0.1

# 3. Initialize MCP knowledge base
cd mcp-knowledge-base && git init && cd ..

# 4. Start server
python src/web-interface/app.py

# 5. Run security tests
pytest -v
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | No | HTML manual |
| GET | `/api/system/health` | No | Health check |
| GET | `/api/system/status` | Yes | System status |
| POST | `/api/bootstrap/create` | Yes | Create bootstrap |
| GET | `/api/bootstrap/get` | Yes | Get bootstrap |
| POST | `/api/cycle/start` | Yes | Start review cycle |
| POST | `/api/proposal/submit` | Yes | Submit proposal |
| GET | `/api/proposals/list` | Yes | List proposals |
| GET | `/api/challenges/list` | Yes | List challenges |
| POST | `/api/governance/decide` | Yes | Governance decision |
| GET | `/api/metrics/get` | Yes | Get metrics |
| GET | `/api/queue/status` | Yes | Queue status |

Authentication: `X-API-Key` header with 32+ character key.

## Security

PERCIA v2.0 has undergone a **3-round multi-AI security audit** involving 7 AI platforms (ChatGPT, Claude, Gemini, Grok, Perplexity, Mistral, Copilot). The latest round identified and patched 11 vulnerabilities:

| # | Vulnerability | Severity | Status |
|---|---|---|---|
| 1 | debug=True RCE | CRITICAL | Patched |
| 2 | API Key hardcoded | CRITICAL | Patched |
| 3 | lock_context release bug | CRITICAL | Patched |
| 4 | Missing Security Headers | HIGH | Patched |
| 5 | No Rate Limiting | HIGH | Patched |
| 6 | Timing Attack on API key | HIGH | Patched |
| 7 | Command Injection in Git ops | HIGH | Patched |
| 8 | Zombie Commits on rollback | MEDIUM | Patched |
| 9 | Queue without mutex | MEDIUM | Patched |
| 10 | Path Traversal | LOW | Patched |
| 11 | PID Reuse detection | HIGH | Patched |

All patches are verified by 63 automated tests. See [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) for the full audit report.

## Testing

```bash
pytest -v                    # All 63 tests
pytest -m critical -v        # Critical patches only
pytest -m "patch7" -v        # Specific patch
```

See [tests/README.md](tests/README.md) for full testing documentation.

## Documentation

- [Security Audit Report](docs/SECURITY_AUDIT.md) — Full Ronda 3 multi-AI audit details
- [Architecture Guide](docs/ARCHITECTURE.md) — System design and component interactions
- [API Reference](docs/API_REFERENCE.md) — Endpoint specifications
- [Operations Guide](docs/OPERATIONS.md) — Deployment, configuration, troubleshooting

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PERCIA_API_KEY` | Yes | — | API key (min 32 chars) |
| `PERCIA_FLASK_DEBUG` | No | `false` | Debug mode (blocked with remote host) |
| `PERCIA_FLASK_HOST` | No | `127.0.0.1` | Bind address |
| `PERCIA_FLASK_PORT` | No | `5000` | Port |
| `PYTHONIOENCODING` | No | — | Set to `utf-8` on Windows |

## License

Proprietary. All rights reserved.

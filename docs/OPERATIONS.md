# PERCIA v2.0 — Operations Guide

## Prerequisites

- Python 3.10 or higher
- Git 2.x
- pip (Python package manager)

## Installation

```bash
# Clone repository
git clone https://github.com/sriyantra108/percia-v2.git
cd percia-v2

# Install dependencies
pip install -r requirements.txt
pip install pytest psutil

# Initialize MCP knowledge base
mkdir -p mcp-knowledge-base
cd mcp-knowledge-base && git init && cd ..
```

## Configuration

### Required Environment Variables

```bash
# Generate a secure API key (mandatory, min 32 chars)
export PERCIA_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

### Optional Environment Variables

```bash
export PERCIA_FLASK_DEBUG=false        # Never "true" with remote host
export PERCIA_FLASK_HOST=127.0.0.1     # Bind address
export PERCIA_FLASK_PORT=5000          # Port
export PYTHONIOENCODING=utf-8          # Required on Windows
```

### Windows (PowerShell)

```powershell
# Session variables
$env:PERCIA_API_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:PERCIA_FLASK_DEBUG = "false"
$env:PERCIA_FLASK_HOST = "127.0.0.1"

# Permanent (user level)
[System.Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "User")
```

## Starting the Server

```bash
python src/web-interface/app.py
```

Expected output:
```
INFO - Rate limiting habilitado (storage: memory://)
INFO - LockManager inicializado correctamente
INFO - CommitCoordinator inicializado correctamente
INFO - Validator inicializado correctamente
============================================================
PERCIA v2.0 - API REST Server
============================================================
API Key: configurada (valor oculto)
Rate Limiting: habilitado
Servidor iniciando en http://127.0.0.1:5000 (debug=OFF)
============================================================
```

## Verification

### Health Check
```bash
curl http://127.0.0.1:5000/api/system/health
```

### Authenticated Request
```bash
curl -H "X-API-Key: YOUR_KEY_HERE" http://127.0.0.1:5000/api/system/status
```

### Run Tests
```bash
pytest -v              # All 63 tests
pytest -m critical -v  # Critical patches only
```

## Troubleshooting

### Server won't start: "PERCIA_API_KEY no configurada"
The API key environment variable is not set or is empty.
```bash
export PERCIA_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

### Server won't start: "API key demasiado corta"
The key must be at least 32 characters.
```bash
echo $PERCIA_API_KEY | wc -c   # Should be >= 32
```

### Server won't start: "Configuracion insegura: debug=True con host remoto"
You have `PERCIA_FLASK_DEBUG=true` and `PERCIA_FLASK_HOST=0.0.0.0`. Either disable debug or use localhost:
```bash
export PERCIA_FLASK_DEBUG=false
# OR
export PERCIA_FLASK_HOST=127.0.0.1
```

### UnicodeEncodeError on Windows
Windows terminals use cp1252 encoding by default. Set UTF-8:
```powershell
[System.Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "User")
```
Then restart your terminal.

### CommitCoordinator error: "no es un repositorio Git valido"
The `mcp-knowledge-base` directory needs Git initialization:
```bash
cd mcp-knowledge-base && git init && cd ..
```

### Rate limiting: getting 429 Too Many Requests
This is expected behavior. Wait for the rate limit window to reset, or adjust limits in `app.py` if needed for your use case.

### Tests fail with import errors
Ensure you're running from the repository root:
```bash
cd /path/to/percia-v2
pytest -v
```

## Production Considerations

### Current Limitations
- Uses Flask development server (not production-grade)
- Rate limiting uses in-memory storage (resets on restart)
- Single-process, single-machine deployment

### Recommended Production Stack
```
Client → Nginx (reverse proxy + TLS) → Gunicorn/Waitress → Flask app
```

```bash
# Install production WSGI server
pip install gunicorn    # Linux
pip install waitress    # Windows

# Run with Gunicorn (Linux)
gunicorn -w 4 -b 127.0.0.1:5000 "src.web-interface.app:app"

# Run with Waitress (Windows)
waitress-serve --host=127.0.0.1 --port=5000 src.web-interface.app:app
```

### Production Checklist
- [ ] Use Gunicorn/Waitress instead of Flask dev server
- [ ] Configure HTTPS via reverse proxy (Nginx/Caddy)
- [ ] Use Redis backend for flask-limiter (persistent rate limiting)
- [ ] Set up log rotation
- [ ] Configure firewall rules
- [ ] Store API key in secrets manager (not environment variable)
- [ ] Set up monitoring and alerting
- [ ] Enable GitHub Actions CI for automated testing

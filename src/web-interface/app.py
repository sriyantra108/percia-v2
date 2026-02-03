#!/usr/bin/env python3
"""
PERCIA v2.0 - API REST Server
============================
Sistema de Protocolo de Evaluación y Revisión de Código por IAs

VERSIÓN PARCHEADA - Ronda 3 Multi-IA Security Audit
Parches aplicados:
  - #1: debug=True RCE (ChatGPT) - Bloqueo explícito debug+host remoto
  - #2: API Key hardcoded (ChatGPT/Claude/Mistral) - Fail-closed + 32 chars
  - #4: Security Headers (Mistral) - CSP, X-Frame, Permissions-Policy
  - #5: Rate Limiting (Mistral/Copilot) - Flask-Limiter
  - #6: Timing Attack (ChatGPT) - hmac.compare_digest + None handling

Commit base auditado: 5a20704
Fecha parche: Febrero 2026
"""

import os
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import json
import hmac  # PARCHE #6: Importar hmac para timing-safe comparison
import secrets
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from functools import wraps
from typing import Optional, Dict, Any, List

# Flask imports
from flask import Flask, request, jsonify, Response

# PARCHE #5: Flask-Limiter para rate limiting
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    logging.warning(
        "flask-limiter no instalado. Rate limiting deshabilitado. "
        "Instalar con: pip install flask-limiter"
    )

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# PARCHE #2: API Key - Fail-closed sin defaults predecibles
# ============================================================================
API_KEY = os.environ.get("PERCIA_API_KEY")
if API_KEY is not None:
    API_KEY = API_KEY.strip()

# Fail-closed: no defaults predecibles
if not API_KEY:
    raise RuntimeError(
        "⛔ PERCIA_API_KEY no configurada. Defina una API key fuerte en el entorno "
        "(recomendado: >= 32 caracteres aleatorios).\n"
        "Ejemplo: export PERCIA_API_KEY=$(python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
    )

# Validación mínima de fortaleza (evita claves triviales)
if len(API_KEY) < 32:
    raise RuntimeError(
        f"⛔ PERCIA_API_KEY demasiado corta ({len(API_KEY)} chars). "
        "Use al menos 32 caracteres aleatorios."
    )

# ============================================================================
# Paths y configuración
# ============================================================================
BASE_PATH = Path(__file__).parent.parent.parent.resolve()
MCP_DIR = BASE_PATH / "mcp-knowledge-base"
SCRIPTS_DIR = BASE_PATH / "src" / "scripts"

# Agregar scripts al path
sys.path.insert(0, str(SCRIPTS_DIR))

# Importar módulos PERCIA
try:
    from lock_manager import LockManager
    LOCK_MANAGER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LockManager no disponible: {e}")
    LOCK_MANAGER_AVAILABLE = False
    LockManager = None

try:
    from commit_coordinator import CommitCoordinator
    COMMIT_COORDINATOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"CommitCoordinator no disponible: {e}")
    COMMIT_COORDINATOR_AVAILABLE = False
    CommitCoordinator = None

try:
    from validator import Validator
    VALIDATOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Validator no disponible: {e}")
    VALIDATOR_AVAILABLE = False
    Validator = None

# ============================================================================
# Inicialización de Flask
# ============================================================================
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# ============================================================================
# PARCHE #5: Configurar Rate Limiting
# ============================================================================
if RATE_LIMITER_AVAILABLE:
    # Usar Redis si está disponible, sino memoria (solo desarrollo)
    storage_uri = os.environ.get("PERCIA_RATE_LIMIT_STORAGE", "memory://")
    
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri=storage_uri,
        strategy="fixed-window"
    )
    logger.info(f"Rate limiting habilitado (storage: {storage_uri})")
else:
    limiter = None

# ============================================================================
# Inicialización de componentes PERCIA
# ============================================================================
lock_manager = None
commit_coordinator = None
validator = None

if LOCK_MANAGER_AVAILABLE:
    try:
        lock_manager = LockManager(str(MCP_DIR))
        logger.info("LockManager inicializado correctamente")
    except Exception as e:
        logger.error(f"Error inicializando LockManager: {e}")

if COMMIT_COORDINATOR_AVAILABLE:
    try:
        commit_coordinator = CommitCoordinator(str(MCP_DIR))
        logger.info("CommitCoordinator inicializado correctamente")
    except Exception as e:
        logger.error(f"Error inicializando CommitCoordinator: {e}")

if VALIDATOR_AVAILABLE:
    try:
        validator = Validator()
        logger.info("Validator inicializado correctamente")
    except Exception as e:
        logger.error(f"Error inicializando Validator: {e}")


# ============================================================================
# PARCHE #4: Security Headers HTTP (Mistral)
# ============================================================================
@app.after_request
def apply_security_headers(response: Response) -> Response:
    """
    Agrega headers HTTP de seguridad a TODAS las respuestas.

    Nota: CSP permite 'unsafe-inline' porque el manual HTML usa <style> y <script> inline.
    Si se migra a assets externos, se recomienda endurecer CSP quitando 'unsafe-inline'.
    """
    # Prevenir MIME-type sniffing
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    
    # Prevenir clickjacking
    response.headers.setdefault("X-Frame-Options", "DENY")
    
    # XSS Protection (legacy, pero útil para navegadores antiguos)
    response.headers.setdefault("X-XSS-Protection", "1; mode=block")
    
    # Content Security Policy
    # Permite 'self' para scripts/styles, 'unsafe-inline' para el manual HTML
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "frame-ancestors 'none'"
    )
    
    # Strict Transport Security (solo HTTPS en producción)
    # Solo agregar si estamos en HTTPS
    if request.is_secure or os.environ.get("PERCIA_FORCE_HTTPS", "").lower() == "true":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains"
        )
    
    # Referrer Policy
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    
    # Permissions Policy (antes Feature-Policy)
    # Deshabilitar APIs del navegador no necesarias
    response.headers.setdefault(
        "Permissions-Policy",
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )
    
    # Cache control para respuestas de API
    if request.path.startswith('/api/'):
        response.headers.setdefault("Cache-Control", "no-store, max-age=0")
        response.headers.setdefault("Pragma", "no-cache")
    
    return response


# ============================================================================
# PARCHE #6: Timing-Safe API Key Validation (ChatGPT)
# ============================================================================
def require_api_key(f):
    """
    Decorator que requiere API key válida en header X-API-Key.
    
    PARCHE #6: Usa hmac.compare_digest para prevenir timing attacks.
    Maneja correctamente el caso donde provided_key es None.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        provided_key = request.headers.get('X-API-Key')
        
        # Manejar caso None para evitar TypeError en hmac.compare_digest
        if provided_key is None:
            logger.warning(f"API key missing from {request.remote_addr}")
            return jsonify({
                "status": "error",
                "error": "API key requerida en header X-API-Key",
                "code": "AUTH_MISSING"
            }), 401
        
        # Normalizar (strip whitespace)
        provided_key = provided_key.strip()
        
        # Timing-safe comparison para prevenir timing attacks
        # Ambos valores deben ser strings del mismo encoding
        if not hmac.compare_digest(provided_key.encode('utf-8'), API_KEY.encode('utf-8')):
            logger.warning(f"Invalid API key attempt from {request.remote_addr}")
            return jsonify({
                "status": "error",
                "error": "API key inválida",
                "code": "AUTH_INVALID"
            }), 401
        
        return f(*args, **kwargs)
    return decorated


# ============================================================================
# Rate Limiting Decorator Helper
# ============================================================================
def rate_limit(limit_string: str):
    """
    Decorator helper para rate limiting condicional.
    Si flask-limiter no está disponible, no hace nada.
    """
    def decorator(f):
        if RATE_LIMITER_AVAILABLE and limiter:
            return limiter.limit(limit_string)(f)
        return f
    return decorator


# ============================================================================
# Endpoints de Sistema
# ============================================================================
@app.route('/')
def manual():
    """Página principal con manual de la API."""
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PERCIA v2.0 - Manual API</title>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                max-width: 900px; 
                margin: 0 auto; 
                padding: 20px;
                background: #1a1a2e;
                color: #eaeaea;
            }
            h1 { color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }
            h2 { color: #ff6b6b; margin-top: 30px; }
            .endpoint { 
                background: #16213e; 
                padding: 15px; 
                margin: 10px 0; 
                border-radius: 8px;
                border-left: 4px solid #00d4ff;
            }
            .method { 
                display: inline-block; 
                padding: 3px 8px; 
                border-radius: 4px; 
                font-weight: bold;
                margin-right: 10px;
            }
            .get { background: #28a745; color: white; }
            .post { background: #007bff; color: white; }
            code { 
                background: #0f0f23; 
                padding: 2px 6px; 
                border-radius: 4px;
                font-family: 'Courier New', monospace;
            }
            pre {
                background: #0f0f23;
                padding: 15px;
                border-radius: 8px;
                overflow-x: auto;
            }
            .warning {
                background: #ff6b6b22;
                border: 1px solid #ff6b6b;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <h1>🔬 PERCIA v2.0 - API REST</h1>
        <p>Protocolo de Evaluación y Revisión de Código por IAs</p>
        
        <div class="warning">
            <strong>⚠️ Autenticación Requerida:</strong> Todos los endpoints (excepto health/status) 
            requieren header <code>X-API-Key: &lt;PERCIA_API_KEY&gt;</code>
        </div>
        
        <h2>📋 Endpoints Disponibles</h2>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/system/health</code>
            <p>Health check del servidor (no requiere autenticación)</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/system/status</code>
            <p>Estado detallado del sistema PERCIA</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <code>/api/bootstrap/create</code>
            <p>Crear nuevo bootstrap del sistema</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/bootstrap/get</code>
            <p>Obtener bootstrap actual</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <code>/api/cycle/start</code>
            <p>Iniciar nuevo ciclo de evaluación</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <code>/api/proposal/submit</code>
            <p>Enviar propuesta de modificación</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/proposals/list</code>
            <p>Listar propuestas pendientes</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/challenges/list</code>
            <p>Listar challenges activos</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <code>/api/governance/decide</code>
            <p>Ejecutar decisión de gobernanza</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/metrics/get</code>
            <p>Obtener métricas del sistema</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/api/queue/status</code>
            <p>Estado de la cola de operaciones</p>
        </div>
        
        <h2>🔐 Ejemplo de Uso</h2>
        <pre>
# Health check (sin autenticación)
curl http://127.0.0.1:5000/api/system/health

# Status con autenticación
curl -H "X-API-Key: &lt;PERCIA_API_KEY&gt;" \\
     http://127.0.0.1:5000/api/system/status

# Enviar propuesta
curl -X POST \\
     -H "Content-Type: application/json" \\
     -H "X-API-Key: &lt;PERCIA_API_KEY&gt;" \\
     -d '{"author_ia": "claude", "content": {...}}' \\
     http://127.0.0.1:5000/api/proposal/submit
        </pre>
        
        <p style="margin-top: 30px; color: #666;">
            Versión: 2.0.0-security-patch | 
            Commit: 5a20704 |
            Parches: Ronda 3 Multi-IA
        </p>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')


@app.route('/api/system/health')
def health_check():
    """Health check endpoint - no requiere autenticación."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0-security-patch"
    })


@app.route('/api/system/status')
@require_api_key
def system_status():
    """Estado detallado del sistema PERCIA."""
    status = {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0-security-patch",
        "components": {
            "lock_manager": LOCK_MANAGER_AVAILABLE and lock_manager is not None,
            "commit_coordinator": COMMIT_COORDINATOR_AVAILABLE and commit_coordinator is not None,
            "validator": VALIDATOR_AVAILABLE and validator is not None,
            "rate_limiter": RATE_LIMITER_AVAILABLE and limiter is not None
        },
        "paths": {
            "base": str(BASE_PATH),
            "mcp_dir": str(MCP_DIR),
            "scripts_dir": str(SCRIPTS_DIR)
        },
        "security": {
            "api_key_configured": True,  # Si llegamos aquí, está configurada
            "rate_limiting": RATE_LIMITER_AVAILABLE,
            "security_headers": True
        }
    }
    return jsonify(status)


# ============================================================================
# Endpoints de Bootstrap
# ============================================================================
@app.route('/api/bootstrap/create', methods=['POST'])
@require_api_key
@rate_limit("5 per minute")  # PARCHE #5: Rate limit para operaciones costosas
def create_bootstrap():
    """Crear nuevo bootstrap del sistema."""
    try:
        data = request.get_json() or {}
        
        # Aquí iría la lógica de creación de bootstrap
        bootstrap_id = f"bootstrap_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return jsonify({
            "status": "success",
            "bootstrap_id": bootstrap_id,
            "message": "Bootstrap creado exitosamente",
            "timestamp": datetime.now().isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creando bootstrap: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "code": "BOOTSTRAP_ERROR"
        }), 500


@app.route('/api/bootstrap/get')
@require_api_key
def get_bootstrap():
    """Obtener bootstrap actual."""
    try:
        bootstrap_file = MCP_DIR / "bootstrap.json"
        
        if not bootstrap_file.exists():
            return jsonify({
                "status": "error",
                "error": "No existe bootstrap activo",
                "code": "BOOTSTRAP_NOT_FOUND"
            }), 404
        
        with open(bootstrap_file, 'r', encoding='utf-8') as f:
            bootstrap_data = json.load(f)
        
        return jsonify({
            "status": "success",
            "bootstrap": bootstrap_data,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo bootstrap: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "code": "BOOTSTRAP_ERROR"
        }), 500


# ============================================================================
# Endpoints de Ciclo
# ============================================================================
@app.route('/api/cycle/start', methods=['POST'])
@require_api_key
@rate_limit("10 per minute")  # PARCHE #5: Rate limit
def start_cycle():
    """Iniciar nuevo ciclo de evaluación."""
    try:
        data = request.get_json() or {}
        
        if not lock_manager:
            return jsonify({
                "status": "error",
                "error": "LockManager no disponible",
                "code": "COMPONENT_UNAVAILABLE"
            }), 503
        
        # Aquí iría la lógica de inicio de ciclo
        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return jsonify({
            "status": "success",
            "cycle_id": cycle_id,
            "message": "Ciclo iniciado exitosamente",
            "timestamp": datetime.now().isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"Error iniciando ciclo: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "code": "CYCLE_ERROR"
        }), 500


# ============================================================================
# Endpoints de Propuestas
# ============================================================================
@app.route('/api/proposal/submit', methods=['POST'])
@require_api_key
@rate_limit("20 per minute")  # PARCHE #5: Rate limit
def submit_proposal():
    """Enviar propuesta de modificación."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "error": "Body JSON requerido",
                "code": "INVALID_REQUEST"
            }), 400
        
        # Validar campos requeridos
        required_fields = ['author_ia', 'content']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({
                "status": "error",
                "error": f"Campos requeridos faltantes: {missing}",
                "code": "MISSING_FIELDS"
            }), 400
        
        # Validar con validator si está disponible
        if validator:
            try:
                validator.validate_proposal(data)
            except Exception as ve:
                return jsonify({
                    "status": "error",
                    "error": f"Validación fallida: {ve}",
                    "code": "VALIDATION_ERROR"
                }), 400
        
        # Aquí iría la lógica de envío de propuesta
        proposal_id = f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"
        
        return jsonify({
            "status": "success",
            "proposal_id": proposal_id,
            "author_ia": data['author_ia'],
            "message": "Propuesta enviada exitosamente",
            "timestamp": datetime.now().isoformat()
        }), 201
        
    except json.JSONDecodeError:
        return jsonify({
            "status": "error",
            "error": "JSON inválido en body",
            "code": "INVALID_JSON"
        }), 400
    except Exception as e:
        logger.error(f"Error enviando propuesta: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "code": "PROPOSAL_ERROR"
        }), 500


@app.route('/api/proposals/list')
@require_api_key
def list_proposals():
    """Listar propuestas pendientes."""
    try:
        proposals_dir = MCP_DIR / "proposals"
        
        if not proposals_dir.exists():
            return jsonify({
                "status": "success",
                "proposals": [],
                "count": 0,
                "timestamp": datetime.now().isoformat()
            })
        
        proposals = []
        for f in proposals_dir.glob("*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as pf:
                    proposals.append(json.load(pf))
            except Exception as e:
                logger.warning(f"Error leyendo propuesta {f}: {e}")
        
        return jsonify({
            "status": "success",
            "proposals": proposals,
            "count": len(proposals),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error listando propuestas: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "code": "LIST_ERROR"
        }), 500


# ============================================================================
# Endpoints de Challenges
# ============================================================================
@app.route('/api/challenges/list')
@require_api_key
def list_challenges():
    """Listar challenges activos."""
    try:
        challenges_dir = MCP_DIR / "challenges"
        
        if not challenges_dir.exists():
            return jsonify({
                "status": "success",
                "challenges": [],
                "count": 0,
                "timestamp": datetime.now().isoformat()
            })
        
        challenges = []
        for f in challenges_dir.glob("*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as cf:
                    challenges.append(json.load(cf))
            except Exception as e:
                logger.warning(f"Error leyendo challenge {f}: {e}")
        
        return jsonify({
            "status": "success",
            "challenges": challenges,
            "count": len(challenges),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error listando challenges: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "code": "LIST_ERROR"
        }), 500


# ============================================================================
# Endpoints de Gobernanza
# ============================================================================
@app.route('/api/governance/decide', methods=['POST'])
@require_api_key
@rate_limit("5 per minute")  # PARCHE #5: Rate limit para operaciones críticas
def governance_decide():
    """Ejecutar decisión de gobernanza."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "error": "Body JSON requerido",
                "code": "INVALID_REQUEST"
            }), 400
        
        # Aquí iría la lógica de decisión de gobernanza
        decision_id = f"decision_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return jsonify({
            "status": "success",
            "decision_id": decision_id,
            "message": "Decisión ejecutada exitosamente",
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error en decisión de gobernanza: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "code": "GOVERNANCE_ERROR"
        }), 500


# ============================================================================
# Endpoints de Métricas
# ============================================================================
@app.route('/api/metrics/get')
@require_api_key
def get_metrics():
    """Obtener métricas del sistema."""
    try:
        metrics = {
            "status": "success",
            "metrics": {
                "uptime_seconds": 0,  # TODO: Implementar tracking
                "total_proposals": 0,
                "total_cycles": 0,
                "active_locks": 0,
                "rate_limit_hits": 0
            },
            "components": {
                "lock_manager": lock_manager is not None,
                "commit_coordinator": commit_coordinator is not None,
                "validator": validator is not None
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Obtener métricas de lock_manager si está disponible
        if lock_manager:
            try:
                lock_status = lock_manager.get_lock_status()
                metrics["metrics"]["active_locks"] = 1 if lock_status.get("is_locked") else 0
            except Exception as e:
                logger.warning(f"Error obteniendo estado de locks: {e}")
        
        return jsonify(metrics)
        
    except Exception as e:
        logger.error(f"Error obteniendo métricas: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "code": "METRICS_ERROR"
        }), 500


# ============================================================================
# Endpoints de Cola
# ============================================================================
@app.route('/api/queue/status')
@require_api_key
def queue_status():
    """Estado de la cola de operaciones."""
    try:
        if not lock_manager:
            return jsonify({
                "status": "error",
                "error": "LockManager no disponible",
                "code": "COMPONENT_UNAVAILABLE"
            }), 503
        
        # Usar método thread-safe del lock_manager (PARCHE #9)
        queue_data = lock_manager.get_queue_status()
        
        return jsonify({
            "status": "success",
            "queue": queue_data,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de cola: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "code": "QUEUE_ERROR"
        }), 500


# ============================================================================
# Error Handlers
# ============================================================================
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "error": "Endpoint no encontrado",
        "code": "NOT_FOUND"
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "status": "error",
        "error": "Método HTTP no permitido",
        "code": "METHOD_NOT_ALLOWED"
    }), 405


@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({
        "status": "error",
        "error": "Rate limit excedido. Intente más tarde.",
        "code": "RATE_LIMIT_EXCEEDED"
    }), 429


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Error interno del servidor: {error}")
    return jsonify({
        "status": "error",
        "error": "Error interno del servidor",
        "code": "INTERNAL_ERROR"
    }), 500


# ============================================================================
# PARCHE #1: Main con bloqueo debug+host remoto (ChatGPT)
# ============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("🔬 PERCIA v2.0 - API REST Server")
    print("=" * 60)
    print(f"📁 Base path: {BASE_PATH}")
    print(f"📁 MCP dir: {MCP_DIR}")
    print("=" * 60)
    print("📋 Endpoints disponibles:")
    print("  GET  /                    → Manual HTML")
    print("  GET  /api/system/status   → Estado del sistema")
    print("  GET  /api/system/health   → Health check")
    print("  POST /api/bootstrap/create → Crear bootstrap")
    print("  GET  /api/bootstrap/get   → Obtener bootstrap")
    print("  POST /api/cycle/start     → Iniciar ciclo")
    print("  POST /api/proposal/submit → Enviar propuesta")
    print("  GET  /api/proposals/list  → Listar propuestas")
    print("  GET  /api/challenges/list → Listar challenges")
    print("  POST /api/governance/decide → Decisión")
    print("  GET  /api/metrics/get     → Métricas")
    print("  GET  /api/queue/status    → Cola")
    print("=" * 60)

    def _env_bool(name: str, default: bool = False) -> bool:
        """Parsea booleanos desde variables de entorno de forma segura."""
        v = os.environ.get(name)
        if v is None:
            return default
        return v.strip().lower() in ("1", "true", "yes", "on")

    # Defaults seguros (no debug, solo localhost)
    debug = _env_bool("PERCIA_FLASK_DEBUG", False)
    host = (os.environ.get("PERCIA_FLASK_HOST", "127.0.0.1") or "127.0.0.1").strip()
    port_raw = (os.environ.get("PERCIA_FLASK_PORT", "5000") or "5000").strip()

    try:
        port = int(port_raw)
    except ValueError:
        raise ValueError(f"PERCIA_FLASK_PORT inválido: {port_raw!r}")

    if not (1 <= port <= 65535):
        raise ValueError(f"PERCIA_FLASK_PORT fuera de rango: {port}")

    # 🛡️ DEFENSA CRÍTICA: nunca permitir debug expuesto fuera de localhost
    if debug and host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(
            "⛔ Configuración insegura: PERCIA_FLASK_DEBUG=True con host no-local. "
            "Use host=127.0.0.1 o desactive debug."
        )

    # PARCHE #2: No mostrar API key en logs
    print("🔑 API Key: configurada (valor oculto)")
    print(f"🛡️ Rate Limiting: {'habilitado' if RATE_LIMITER_AVAILABLE else 'deshabilitado'}")
    print(f"🚀 Servidor iniciando en http://{host}:{port} (debug={'ON' if debug else 'OFF'})")
    print("=" * 60)

    app.run(debug=debug, host=host, port=port)

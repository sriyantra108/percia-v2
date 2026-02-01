#!/usr/bin/env python3
"""
PERCIA v2.0 - Flask API REST - Interfaz Web Completa

Implementa 12 endpoints:
1.  GET  /                    → Manual HTML
2.  GET  /api/system/status   → Estado del sistema
3.  GET  /api/system/health   → Health check
4.  POST /api/bootstrap/create → Crear bootstrap
5.  GET  /api/bootstrap/get   → Obtener bootstrap
6.  POST /api/cycle/start     → Iniciar ciclo
7.  POST /api/proposal/submit → Enviar propuesta
8.  GET  /api/proposals/list  → Listar propuestas
9.  GET  /api/challenges/list → Listar challenges
10. POST /api/governance/decide → Decisión gobernanza
11. GET  /api/metrics/get     → Obtener métricas
12. GET  /api/queue/status    → Estado de la cola

Corrige hallazgos:
- CRIT-003 (Copilot): API sin autenticación - añadido API key básico
- HIGH-API-001 (GPT-4o): Endpoints de escritura con lock_context()
- HIGH-API-002 (GPT-4o): save_json_file ahora es atómico
- Gap documentación-código (Grok): Solo 1 de 12 endpoints
"""

import json
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime
from functools import wraps
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify, render_template_string

# Importar módulos PERCIA
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

try:
    from lock_manager import LockManager
    from validator import Validator
    from commit_coordinator import CommitCoordinator
except ImportError as e:
    print(f"Warning: No se pudieron importar módulos PERCIA: {e}")
    LockManager = None
    Validator = None
    CommitCoordinator = None

# Configuración
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

BASE_PATH = Path(__file__).parent.parent
MCP_DIR = BASE_PATH / "mcp"
PERCIA_DIR = BASE_PATH / ".percia"

# API Key simple para autenticación básica (en producción usar JWT)
API_KEY = os.environ.get('PERCIA_API_KEY', 'percia-dev-key-2024')


# ============================================================
# MIDDLEWARE Y HELPERS
# ============================================================

def require_api_key(f):
    """Decorator para requerir API key en endpoints protegidos"""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != API_KEY:
            return jsonify({
                "status": "error",
                "error": "Invalid or missing API key",
                "code": "UNAUTHORIZED"
            }), 401
        return f(*args, **kwargs)
    return decorated


def get_lock_manager() -> Optional[LockManager]:
    """Obtiene instancia del LockManager"""
    if LockManager is None:
        return None
    return LockManager(base_path=str(BASE_PATH))


def get_validator() -> Optional[Validator]:
    """Obtiene instancia del Validator"""
    if Validator is None:
        return None
    return Validator(base_path=str(BASE_PATH))


def get_coordinator() -> Optional[CommitCoordinator]:
    """Obtiene instancia del CommitCoordinator"""
    if CommitCoordinator is None:
        return None
    return CommitCoordinator(base_path=str(BASE_PATH))


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Carga archivo JSON de forma segura"""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


def save_json_file(file_path: Path, data: Dict[str, Any]) -> bool:
    """
    Guarda archivo JSON de forma atómica (HIGH-API-002 fix)
    Usa temp file único + os.replace() para atomicidad
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Crear temp file único para evitar colisiones
        temp_file = file_path.with_name(
            f"{file_path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            # os.replace es atómico en Windows/Linux
            os.replace(temp_file, file_path)
            return True
            
        finally:
            # Limpieza defensiva
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
                
    except Exception as e:
        return False


# ============================================================
# TEMPLATE HTML PARA MANUAL
# ============================================================

MANUAL_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PERCIA v2.0 - API Manual</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 30px; }
        .endpoint { background: white; padding: 15px; margin: 10px 0; border-radius: 8px; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .method { display: inline-block; padding: 4px 12px; border-radius: 4px; 
                  font-weight: bold; margin-right: 10px; }
        .get { background: #27ae60; color: white; }
        .post { background: #3498db; color: white; }
        .path { font-family: monospace; font-size: 14px; color: #2c3e50; }
        .desc { color: #7f8c8d; margin-top: 8px; }
        pre { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px; 
              overflow-x: auto; }
        .status { padding: 20px; background: #27ae60; color: white; border-radius: 8px; 
                  margin-bottom: 20px; }
        .status.error { background: #e74c3c; }
    </style>
</head>
<body>
    <h1>🔬 PERCIA v2.0 - API REST</h1>
    
    <div class="status" id="status">
        Verificando estado del sistema...
    </div>
    
    <h2>📋 Endpoints Disponibles</h2>
    
    <div class="endpoint">
        <span class="method get">GET</span>
        <span class="path">/api/system/status</span>
        <div class="desc">Estado actual del sistema PERCIA</div>
    </div>
    
    <div class="endpoint">
        <span class="method get">GET</span>
        <span class="path">/api/system/health</span>
        <div class="desc">Health check para monitoreo</div>
    </div>
    
    <div class="endpoint">
        <span class="method post">POST</span>
        <span class="path">/api/bootstrap/create</span>
        <div class="desc">Crear nueva configuración bootstrap (requiere API key)</div>
    </div>
    
    <div class="endpoint">
        <span class="method get">GET</span>
        <span class="path">/api/bootstrap/get</span>
        <div class="desc">Obtener configuración bootstrap actual</div>
    </div>
    
    <div class="endpoint">
        <span class="method post">POST</span>
        <span class="path">/api/cycle/start</span>
        <div class="desc">Iniciar nuevo ciclo de decisión (requiere API key)</div>
    </div>
    
    <div class="endpoint">
        <span class="method post">POST</span>
        <span class="path">/api/proposal/submit</span>
        <div class="desc">Enviar propuesta de IA (requiere API key)</div>
    </div>
    
    <div class="endpoint">
        <span class="method get">GET</span>
        <span class="path">/api/proposals/list</span>
        <div class="desc">Listar todas las propuestas</div>
    </div>
    
    <div class="endpoint">
        <span class="method get">GET</span>
        <span class="path">/api/challenges/list</span>
        <div class="desc">Listar todos los challenges</div>
    </div>
    
    <div class="endpoint">
        <span class="method post">POST</span>
        <span class="path">/api/governance/decide</span>
        <div class="desc">Registrar decisión de gobernanza (requiere API key)</div>
    </div>
    
    <div class="endpoint">
        <span class="method get">GET</span>
        <span class="path">/api/metrics/get</span>
        <div class="desc">Obtener métricas del sistema</div>
    </div>
    
    <div class="endpoint">
        <span class="method get">GET</span>
        <span class="path">/api/queue/status</span>
        <div class="desc">Estado de la cola de operaciones</div>
    </div>
    
    <h2>🔐 Autenticación</h2>
    <p>Los endpoints POST requieren header <code>X-API-Key</code></p>
    <pre>curl -H "X-API-Key: your-api-key" -X POST ...</pre>
    
    <h2>📖 Ejemplo de Uso</h2>
    <pre>
# Verificar estado
curl http://localhost:5000/api/system/status

# Enviar propuesta
curl -X POST http://localhost:5000/api/proposal/submit \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: percia-dev-key-2024" \\
  -d '{"author_ia": "ia-example", "content": {"claim": "..."}}'
    </pre>
    
    <script>
        fetch('/api/system/health')
            .then(r => r.json())
            .then(data => {
                const el = document.getElementById('status');
                if (data.status === 'healthy') {
                    el.innerHTML = '✅ Sistema operativo - ' + data.timestamp;
                    el.className = 'status';
                } else {
                    el.innerHTML = '❌ Error: ' + JSON.stringify(data);
                    el.className = 'status error';
                }
            })
            .catch(e => {
                document.getElementById('status').innerHTML = '❌ Error de conexión';
                document.getElementById('status').className = 'status error';
            });
    </script>
</body>
</html>
"""


# ============================================================
# ENDPOINT 1: Manual HTML
# ============================================================

@app.route('/')
def index():
    """Página principal con manual de la API"""
    return render_template_string(MANUAL_HTML)


# ============================================================
# ENDPOINT 2: System Status
# ============================================================

@app.route('/api/system/status')
def api_system_status():
    """Estado completo del sistema"""
    try:
        # Cargar snapshot
        snapshot_file = MCP_DIR / "snapshot.json"
        snapshot = load_json_file(snapshot_file)
        
        # Cargar bootstrap
        bootstrap_file = MCP_DIR / "bootstrap.json"
        bootstrap = load_json_file(bootstrap_file)
        
        # Estado del lock
        lock_status = {"locked": False}
        lock_manager = get_lock_manager()
        if lock_manager:
            lock_status = lock_manager.get_lock_status()
        
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "snapshot": snapshot,
                "bootstrap_loaded": bool(bootstrap),
                "lock_status": lock_status,
                "mcp_dir_exists": MCP_DIR.exists()
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


# ============================================================
# ENDPOINT 3: Health Check
# ============================================================

@app.route('/api/system/health')
def api_health():
    """Health check para monitoreo"""
    checks = {
        "mcp_dir": MCP_DIR.exists(),
        "percia_dir": PERCIA_DIR.exists(),
        "lock_manager": LockManager is not None,
        "validator": Validator is not None,
        "coordinator": CommitCoordinator is not None
    }
    
    all_healthy = all(checks.values())
    
    return jsonify({
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "checks": checks
    }), 200 if all_healthy else 503


# ============================================================
# ENDPOINT 4: Create Bootstrap (con lock_context - HIGH-API-001)
# ============================================================

@app.route('/api/bootstrap/create', methods=['POST'])
@require_api_key
def api_bootstrap_create():
    """Crear nueva configuración bootstrap"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "error": "JSON body required"
            }), 400
        
        # Validar bootstrap (fuera del lock para no bloquear por payload inválido)
        validator = get_validator()
        if validator:
            is_valid, message, confidence = validator.validate_data(data, 'bootstrap')
            if not is_valid:
                return jsonify({
                    "status": "error",
                    "error": f"Validation failed: {message}",
                    "confidence": confidence
                }), 400
        
        # Preparar bootstrap
        bootstrap_file = MCP_DIR / "bootstrap.json"
        data['created_at'] = datetime.now().isoformat()
        
        lock_manager = get_lock_manager()
        if lock_manager:
            try:
                with lock_manager.lock_context(
                    ia_id=data.get("created_by") or data.get("initiated_by") or "api",
                    operation_type="bootstrap"
                ):
                    if save_json_file(bootstrap_file, data):
                        return jsonify({
                            "status": "success",
                            "message": "Bootstrap created",
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        return jsonify({
                            "status": "error",
                            "error": "Failed to save bootstrap"
                        }), 500
            except TimeoutError:
                return jsonify({
                    "status": "error",
                    "error": "System busy: lock timeout",
                    "code": "LOCK_TIMEOUT"
                }), 409
        else:
            # Sin LockManager (fallback)
            if save_json_file(bootstrap_file, data):
                return jsonify({
                    "status": "success",
                    "message": "Bootstrap created",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                return jsonify({
                    "status": "error",
                    "error": "Failed to save bootstrap"
                }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================
# ENDPOINT 5: Get Bootstrap
# ============================================================

@app.route('/api/bootstrap/get')
def api_bootstrap_get():
    """Obtener configuración bootstrap actual"""
    bootstrap_file = MCP_DIR / "bootstrap.json"
    data = load_json_file(bootstrap_file)
    
    if not data:
        return jsonify({
            "status": "not_found",
            "error": "Bootstrap not configured"
        }), 404
    
    return jsonify({
        "status": "ok",
        "data": data
    })


# ============================================================
# ENDPOINT 6: Start Cycle (con lock_context - HIGH-API-001)
# ============================================================

@app.route('/api/cycle/start', methods=['POST'])
@require_api_key
def api_cycle_start():
    """Iniciar nuevo ciclo de decisión"""
    try:
        data = request.get_json() or {}
        
        cycle_id = f"cycle-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
        
        cycle_data = {
            "cycle_id": cycle_id,
            "started_at": datetime.now().isoformat(),
            "status": "open",
            "objective": data.get("objective", ""),
            "initiated_by": data.get("initiated_by", "api")
        }
        
        lock_manager = get_lock_manager()
        if lock_manager:
            try:
                with lock_manager.lock_context(
                    ia_id=cycle_data.get("initiated_by", "api"),
                    operation_type="cycle_start"
                ):
                    # Guardar ciclo
                    cycles_dir = MCP_DIR / "cycles"
                    cycles_dir.mkdir(parents=True, exist_ok=True)
                    
                    cycle_file = cycles_dir / f"{cycle_id}.json"
                    save_json_file(cycle_file, cycle_data)
                    
                    # Actualizar snapshot
                    snapshot_file = MCP_DIR / "snapshot.json"
                    snapshot = load_json_file(snapshot_file) or {
                        "proposals": [], "challenges": [], "decisions": []
                    }
                    snapshot["current_cycle"] = cycle_id
                    snapshot["last_updated"] = datetime.now().isoformat()
                    save_json_file(snapshot_file, snapshot)
                    
            except TimeoutError:
                return jsonify({
                    "status": "error",
                    "error": "System busy: lock timeout",
                    "code": "LOCK_TIMEOUT"
                }), 409
        else:
            # Sin LockManager (fallback)
            cycles_dir = MCP_DIR / "cycles"
            cycles_dir.mkdir(parents=True, exist_ok=True)
            
            cycle_file = cycles_dir / f"{cycle_id}.json"
            save_json_file(cycle_file, cycle_data)
            
            snapshot_file = MCP_DIR / "snapshot.json"
            snapshot = load_json_file(snapshot_file) or {
                "proposals": [], "challenges": [], "decisions": []
            }
            snapshot["current_cycle"] = cycle_id
            snapshot["last_updated"] = datetime.now().isoformat()
            save_json_file(snapshot_file, snapshot)
        
        return jsonify({
            "status": "success",
            "cycle_id": cycle_id,
            "message": "Cycle started",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================
# ENDPOINT 7: Submit Proposal (con lock_context - HIGH-API-001)
# ============================================================

@app.route('/api/proposal/submit', methods=['POST'])
@require_api_key
def api_proposal_submit():
    """Enviar propuesta de IA"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "error": "JSON body required"
            }), 400
        
        # Validar propuesta (fuera del lock para evitar bloquear por payload inválido)
        validator = get_validator()
        if validator:
            is_valid, message, confidence = validator.validate_data(data, 'proposal')
            if not is_valid:
                return jsonify({
                    "status": "error",
                    "error": f"Validation failed: {message}",
                    "confidence": confidence
                }), 400
        
        lock_manager = get_lock_manager()
        ia_id = data.get("author_ia", "api")
        
        if lock_manager:
            try:
                with lock_manager.lock_context(
                    ia_id=ia_id,
                    operation_type="proposal"
                ):
                    # Procesar con coordinator
                    coordinator = get_coordinator()
                    if coordinator:
                        result = coordinator.process_proposal(data)
                        return jsonify(result)
                    else:
                        # Fallback sin coordinator
                        proposal_id = f"prop-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
                        proposals_dir = MCP_DIR / "proposals"
                        proposals_dir.mkdir(parents=True, exist_ok=True)
                        
                        data['proposal_id'] = proposal_id
                        data['submitted_at'] = datetime.now().isoformat()
                        
                        proposal_file = proposals_dir / f"{proposal_id}.json"
                        save_json_file(proposal_file, data)
                        
                        return jsonify({
                            "status": "success",
                            "proposal_id": proposal_id,
                            "message": "Proposal submitted",
                            "timestamp": datetime.now().isoformat()
                        })
            except TimeoutError:
                return jsonify({
                    "status": "error",
                    "error": "System busy: lock timeout",
                    "code": "LOCK_TIMEOUT"
                }), 409
        else:
            # Sin LockManager (fallback)
            coordinator = get_coordinator()
            if coordinator:
                result = coordinator.process_proposal(data)
                return jsonify(result)
            else:
                proposal_id = f"prop-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
                proposals_dir = MCP_DIR / "proposals"
                proposals_dir.mkdir(parents=True, exist_ok=True)
                
                data['proposal_id'] = proposal_id
                data['submitted_at'] = datetime.now().isoformat()
                
                proposal_file = proposals_dir / f"{proposal_id}.json"
                save_json_file(proposal_file, data)
                
                return jsonify({
                    "status": "success",
                    "proposal_id": proposal_id,
                    "message": "Proposal submitted",
                    "timestamp": datetime.now().isoformat()
                })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================
# ENDPOINT 8: List Proposals
# ============================================================

@app.route('/api/proposals/list')
def api_proposals_list():
    """Listar todas las propuestas"""
    try:
        proposals_dir = MCP_DIR / "proposals"
        
        if not proposals_dir.exists():
            return jsonify({
                "status": "ok",
                "count": 0,
                "proposals": []
            })
        
        proposals = []
        for file in proposals_dir.glob("*.json"):
            data = load_json_file(file)
            if data and not data.get('error'):
                proposals.append(data)
        
        # Ordenar por fecha
        proposals.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
        
        return jsonify({
            "status": "ok",
            "count": len(proposals),
            "proposals": proposals
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================
# ENDPOINT 9: List Challenges
# ============================================================

@app.route('/api/challenges/list')
def api_challenges_list():
    """Listar todos los challenges"""
    try:
        challenges_dir = MCP_DIR / "challenges"
        
        if not challenges_dir.exists():
            return jsonify({
                "status": "ok",
                "count": 0,
                "challenges": []
            })
        
        challenges = []
        for file in challenges_dir.glob("*.json"):
            data = load_json_file(file)
            if data and not data.get('error'):
                challenges.append(data)
        
        challenges.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
        
        return jsonify({
            "status": "ok",
            "count": len(challenges),
            "challenges": challenges
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================
# ENDPOINT 10: Governance Decision (con lock_context - HIGH-API-001)
# ============================================================

@app.route('/api/governance/decide', methods=['POST'])
@require_api_key
def api_governance_decide():
    """Registrar decisión de gobernanza"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "error": "JSON body required"
            }), 400
        
        required_fields = ['target_proposal', 'verdict']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "status": "error",
                    "error": f"Missing required field: {field}"
                }), 400
        
        lock_manager = get_lock_manager()
        ia_id = data.get("governance_by", data.get("author_ia", "governance"))
        
        if lock_manager:
            try:
                with lock_manager.lock_context(
                    ia_id=ia_id,
                    operation_type="governance_decide"
                ):
                    # Procesar con coordinator
                    coordinator = get_coordinator()
                    if coordinator:
                        result = coordinator.process_decision(data)
                        return jsonify(result)
                    else:
                        # Fallback
                        decision_id = f"dec-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
                        
                        decisions_file = MCP_DIR / "decisions.json"
                        decisions = load_json_file(decisions_file) or {"decisions": []}
                        
                        data['decision_id'] = decision_id
                        data['timestamp'] = datetime.now().isoformat()
                        decisions['decisions'].append(data)
                        
                        save_json_file(decisions_file, decisions)
                        
                        return jsonify({
                            "status": "success",
                            "decision_id": decision_id,
                            "verdict": data['verdict'],
                            "timestamp": datetime.now().isoformat()
                        })
            except TimeoutError:
                return jsonify({
                    "status": "error",
                    "error": "System busy: lock timeout",
                    "code": "LOCK_TIMEOUT"
                }), 409
        else:
            # Sin LockManager (fallback)
            coordinator = get_coordinator()
            if coordinator:
                result = coordinator.process_decision(data)
                return jsonify(result)
            else:
                decision_id = f"dec-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
                
                decisions_file = MCP_DIR / "decisions.json"
                decisions = load_json_file(decisions_file) or {"decisions": []}
                
                data['decision_id'] = decision_id
                data['timestamp'] = datetime.now().isoformat()
                decisions['decisions'].append(data)
                
                save_json_file(decisions_file, decisions)
                
                return jsonify({
                    "status": "success",
                    "decision_id": decision_id,
                    "verdict": data['verdict'],
                    "timestamp": datetime.now().isoformat()
                })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================
# ENDPOINT 11: Get Metrics
# ============================================================

@app.route('/api/metrics/get')
def api_metrics_get():
    """Obtener métricas del sistema"""
    try:
        # Contar propuestas
        proposals_dir = MCP_DIR / "proposals"
        proposals_count = len(list(proposals_dir.glob("*.json"))) if proposals_dir.exists() else 0
        
        # Contar challenges
        challenges_dir = MCP_DIR / "challenges"
        challenges_count = len(list(challenges_dir.glob("*.json"))) if challenges_dir.exists() else 0
        
        # Contar decisiones
        decisions_file = MCP_DIR / "decisions.json"
        decisions_data = load_json_file(decisions_file)
        decisions_count = len(decisions_data.get('decisions', [])) if decisions_data else 0
        
        # Calcular métricas
        metrics = {
            "total_proposals": proposals_count,
            "total_challenges": challenges_count,
            "total_decisions": decisions_count,
            "challenge_rate": challenges_count / proposals_count if proposals_count > 0 else 0,
            "timestamp": datetime.now().isoformat()
        }
        
        # KPIs objetivo
        metrics["kpis"] = {
            "error_detection_rate_target": 0.60,
            "success_rate_target": 0.85,
            "challenge_validity_target": 0.70,
            "overhead_ratio_target": 5.0
        }
        
        return jsonify({
            "status": "ok",
            "metrics": metrics
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================
# ENDPOINT 12: Queue Status
# ============================================================

@app.route('/api/queue/status')
def api_queue_status():
    """Estado de la cola de operaciones"""
    try:
        lock_manager = get_lock_manager()
        
        if lock_manager:
            queue_status = lock_manager.get_queue_status()
            lock_status = lock_manager.get_lock_status()
            
            return jsonify({
                "status": "ok",
                "queue": queue_status,
                "lock": lock_status,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "status": "ok",
                "queue": {"total": 0, "pending": 0, "items": []},
                "lock": {"locked": False},
                "message": "LockManager not available",
                "timestamp": datetime.now().isoformat()
            })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "status": "error",
        "error": "Endpoint not found",
        "code": "NOT_FOUND"
    }), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({
        "status": "error",
        "error": "Internal server error",
        "code": "INTERNAL_ERROR"
    }), 500


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({
        "status": "error",
        "error": "Method not allowed",
        "code": "METHOD_NOT_ALLOWED"
    }), 405


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🔬 PERCIA v2.0 - API REST Server")
    print("=" * 60)
    print(f"📁 Base path: {BASE_PATH}")
    print(f"📁 MCP dir: {MCP_DIR}")
    print(f"🔑 API Key: {API_KEY[:10]}...")
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
    print("🚀 Servidor iniciando en http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)

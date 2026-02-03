"""
PERCIA v2.0 - Test Fixtures
============================
Fixtures compartidos para el test suite de parches de seguridad Ronda 3.

Uso: pytest ejecuta este archivo automáticamente antes de cada test.
"""

import os
import sys
import json
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ============================================================================
# Configuración de paths
# ============================================================================

# Agregar src/scripts al path para importar módulos PERCIA
REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "src" / "scripts"
WEB_DIR = REPO_ROOT / "src" / "web-interface"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(WEB_DIR))


# ============================================================================
# Fixtures de entorno
# ============================================================================

@pytest.fixture
def api_key():
    """API key válida para tests (>= 32 chars)."""
    return "test-percia-api-key-secure-0123456789abcdef"


@pytest.fixture
def short_api_key():
    """API key inválida (< 32 chars)."""
    return "short-key"


@pytest.fixture(autouse=False)
def env_with_api_key(api_key):
    """Configura variables de entorno con API key válida."""
    original_env = os.environ.copy()
    os.environ["PERCIA_API_KEY"] = api_key
    os.environ["PERCIA_FLASK_DEBUG"] = "false"
    os.environ["PERCIA_FLASK_HOST"] = "127.0.0.1"
    yield api_key
    os.environ.clear()
    os.environ.update(original_env)


# ============================================================================
# Fixtures de directorios temporales
# ============================================================================

@pytest.fixture
def temp_dir():
    """Directorio temporal para tests."""
    d = tempfile.mkdtemp(prefix="percia_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def temp_repo(temp_dir):
    """Directorio temporal con estructura de repo Git simulado."""
    git_dir = temp_dir / ".git"
    git_dir.mkdir()
    mcp_dir = temp_dir / "mcp-knowledge-base"
    mcp_dir.mkdir()
    scripts_dir = temp_dir / "src" / "scripts"
    scripts_dir.mkdir(parents=True)
    percia_dir = temp_dir / ".percia"
    percia_dir.mkdir()
    return temp_dir


@pytest.fixture
def temp_base_path(temp_dir):
    """Directorio base para LockManager y otros componentes."""
    percia_dir = temp_dir / ".percia"
    percia_dir.mkdir(exist_ok=True)
    return temp_dir


# ============================================================================
# Fixtures de Flask app
# ============================================================================

@pytest.fixture
def flask_app(env_with_api_key):
    """
    Crea instancia de Flask app con API key configurada.
    
    IMPORTANTE: Debe importar app DESPUÉS de configurar env vars,
    porque app.py valida PERCIA_API_KEY al importar.
    """
    # Forzar re-importación del módulo app
    for mod_name in list(sys.modules.keys()):
        if 'app' in mod_name and 'test' not in mod_name:
            del sys.modules[mod_name]

    # Importar con env vars configuradas
    import importlib
    spec = importlib.util.spec_from_file_location("app", str(WEB_DIR / "app.py"))
    app_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_module)
    
    app = app_module.app
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(flask_app):
    """Cliente de prueba Flask."""
    return flask_app.test_client()


@pytest.fixture
def auth_headers(api_key):
    """Headers con API key válida."""
    return {"X-API-Key": api_key}


@pytest.fixture
def no_auth_headers():
    """Headers sin API key."""
    return {}


@pytest.fixture
def bad_auth_headers():
    """Headers con API key inválida."""
    return {"X-API-Key": "wrong-key-definitely-not-valid-at-all"}


# ============================================================================
# Fixtures de componentes PERCIA
# ============================================================================

@pytest.fixture
def lock_manager(temp_base_path):
    """Instancia de LockManager para tests."""
    from lock_manager import LockManager
    return LockManager(str(temp_base_path))


@pytest.fixture
def validator(temp_base_path):
    """Instancia de Validator para tests."""
    from validator import Validator
    return Validator(str(temp_base_path))


@pytest.fixture
def commit_coordinator(temp_repo):
    """Instancia de CommitCoordinator para tests."""
    from commit_coordinator import CommitCoordinator
    return CommitCoordinator(str(temp_repo))

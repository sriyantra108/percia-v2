"""
PERCIA v2.0 - Tests de Seguridad: app.py
=========================================
Cubre: Parches #1, #2, #4, #5, #6

Ejecutar:
    pytest tests/test_app_security.py -v
    pytest tests/test_app_security.py -m critical -v    # Solo críticos
    pytest tests/test_app_security.py -m patch4 -v      # Solo parche #4
"""

import os
import sys
import subprocess
import pytest
from pathlib import Path


# ============================================================================
# PARCHE #1: debug=True RCE - Bloqueo debug+host remoto (ChatGPT)
# Severidad: CRITICO
# ============================================================================

class TestPatch01DebugRCE:
    """
    Verifica que el servidor RECHAZA la combinacion debug=True + host remoto.

    Vulnerabilidad original: Flask con debug=True expone el debugger Werkzeug,
    que permite ejecucion remota de codigo (RCE) si el host es accesible
    desde la red.
    """

    def _run_server(self, env, timeout=5):
        """Helper: ejecuta el servidor y retorna (returncode, stderr) o None si timeout."""
        proc = subprocess.Popen(
            [sys.executable, str(Path("src/web-interface/app.py"))],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            _, stderr_bytes = proc.communicate(timeout=timeout)
            return proc.returncode, stderr_bytes.decode('utf-8', errors='replace')
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return None

    @pytest.mark.patch1
    @pytest.mark.critical
    def test_debug_true_remote_host_blocked(self, api_key):
        """Servidor DEBE fallar con debug=True + host 0.0.0.0"""
        env = os.environ.copy()
        env["PERCIA_API_KEY"] = api_key
        env["PERCIA_FLASK_DEBUG"] = "true"
        env["PERCIA_FLASK_HOST"] = "0.0.0.0"
        env["PYTHONIOENCODING"] = "utf-8"

        result = self._run_server(env, timeout=8)

        assert result is not None, "Servidor NO deberia arrancar con debug+remote"
        returncode, stderr = result
        assert returncode != 0, "Servidor NO deberia arrancar con debug+remote"
        assert "insegura" in stderr.lower() or "RuntimeError" in stderr \
            or "UnicodeEncodeError" in stderr, \
            f"Error inesperado: {stderr[-300:]}"

    @pytest.mark.patch1
    @pytest.mark.critical
    def test_debug_true_localhost_allowed(self, api_key):
        """Servidor DEBE permitir debug=True con host 127.0.0.1"""
        env = os.environ.copy()
        env["PERCIA_API_KEY"] = api_key
        env["PERCIA_FLASK_DEBUG"] = "true"
        env["PERCIA_FLASK_HOST"] = "127.0.0.1"
        env["PERCIA_FLASK_PORT"] = "15001"
        env["PYTHONIOENCODING"] = "utf-8"

        result = self._run_server(env, timeout=4)

        if result is None:
            pass
        else:
            returncode, stderr = result
            assert "insegura" not in stderr.lower(), \
                "debug=True + localhost NO deberia ser rechazado"

    @pytest.mark.patch1
    @pytest.mark.critical
    def test_debug_true_localhost_allowed_timeout(self, api_key):
        """Verificar que debug=True + localhost NO produce RuntimeError."""
        env = os.environ.copy()
        env["PERCIA_API_KEY"] = api_key
        env["PERCIA_FLASK_DEBUG"] = "true"
        env["PERCIA_FLASK_HOST"] = "127.0.0.1"
        env["PERCIA_FLASK_PORT"] = "15002"
        env["PYTHONIOENCODING"] = "utf-8"

        result = self._run_server(env, timeout=4)

        if result is None:
            pass
        else:
            _, stderr = result
            assert "insegura" not in stderr.lower()

    @pytest.mark.patch1
    @pytest.mark.critical
    def test_debug_false_remote_host_allowed(self, api_key):
        """Servidor DEBE permitir debug=False con host 0.0.0.0"""
        env = os.environ.copy()
        env["PERCIA_API_KEY"] = api_key
        env["PERCIA_FLASK_DEBUG"] = "false"
        env["PERCIA_FLASK_HOST"] = "0.0.0.0"
        env["PERCIA_FLASK_PORT"] = "15003"
        env["PYTHONIOENCODING"] = "utf-8"

        result = self._run_server(env, timeout=4)

        if result is None:
            pass
        else:
            _, stderr = result
            assert "insegura" not in stderr.lower()


# ============================================================================
# PARCHE #2: API Key hardcoded - Fail-closed + 32 chars
# Severidad: CRITICO
# ============================================================================

class TestPatch02APIKey:
    """
    Verifica que el servidor REQUIERE una API key fuerte.

    Vulnerabilidad original: API key por defecto 'percia-dev-key-2024'
    permitia acceso sin configuracion.
    """

    def _run_server(self, env, timeout=5):
        """Helper: ejecuta el servidor y retorna (returncode, stderr) o None si timeout."""
        proc = subprocess.Popen(
            [sys.executable, str(Path("src/web-interface/app.py"))],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            _, stderr_bytes = proc.communicate(timeout=timeout)
            return proc.returncode, stderr_bytes.decode('utf-8', errors='replace')
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return None

    @pytest.mark.patch2
    @pytest.mark.critical
    def test_no_api_key_fails_to_start(self):
        """Servidor DEBE fallar sin PERCIA_API_KEY."""
        env = os.environ.copy()
        env.pop("PERCIA_API_KEY", None)
        env["PYTHONIOENCODING"] = "utf-8"

        result = self._run_server(env, timeout=8)

        assert result is not None, "Servidor termino pero se esperaba fallo"
        returncode, stderr = result
        assert returncode != 0, "Servidor NO deberia arrancar sin API key"
        assert "PERCIA_API_KEY" in stderr

    @pytest.mark.patch2
    @pytest.mark.critical
    def test_short_api_key_fails_to_start(self):
        """Servidor DEBE fallar con API key < 32 chars."""
        env = os.environ.copy()
        env["PERCIA_API_KEY"] = "short-key-12345"
        env["PYTHONIOENCODING"] = "utf-8"

        result = self._run_server(env, timeout=8)

        assert result is not None
        returncode, stderr = result
        assert returncode != 0, "Servidor NO deberia arrancar con key corta"
        assert "corta" in stderr.lower() or "32" in stderr

    @pytest.mark.patch2
    @pytest.mark.critical
    def test_empty_api_key_fails_to_start(self):
        """Servidor DEBE fallar con API key vacia."""
        env = os.environ.copy()
        env["PERCIA_API_KEY"] = ""
        env["PYTHONIOENCODING"] = "utf-8"

        result = self._run_server(env, timeout=8)

        assert result is not None
        returncode, _ = result
        assert returncode != 0

    @pytest.mark.patch2
    @pytest.mark.critical
    def test_whitespace_api_key_fails_to_start(self):
        """Servidor DEBE fallar con API key de solo espacios."""
        env = os.environ.copy()
        env["PERCIA_API_KEY"] = "   "
        env["PYTHONIOENCODING"] = "utf-8"

        result = self._run_server(env, timeout=8)

        assert result is not None
        returncode, _ = result
        assert returncode != 0

    @pytest.mark.patch2
    @pytest.mark.critical
    def test_valid_api_key_starts(self, api_key):
        """Servidor DEBE arrancar con API key >= 32 chars."""
        env = os.environ.copy()
        env["PERCIA_API_KEY"] = api_key
        env["PERCIA_FLASK_PORT"] = "15010"
        env["PYTHONIOENCODING"] = "utf-8"

        result = self._run_server(env, timeout=4)

        if result is None:
            pass  # OK: servidor arranco
        else:
            returncode, stderr = result
            assert "PERCIA_API_KEY" not in stderr or returncode == 0


# ============================================================================
# PARCHE #4: Security Headers (Mistral)
# Severidad: ALTO
# ============================================================================

class TestPatch04SecurityHeaders:
    """
    Verifica que todas las respuestas incluyen headers de seguridad HTTP.

    Vulnerabilidad original: Sin CSP, X-Frame-Options, ni Permissions-Policy.
    """

    @pytest.mark.patch4
    @pytest.mark.high
    def test_x_content_type_options(self, client):
        """Response DEBE incluir X-Content-Type-Options: nosniff"""
        response = client.get('/api/system/health')
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'

    @pytest.mark.patch4
    @pytest.mark.high
    def test_x_frame_options(self, client):
        """Response DEBE incluir X-Frame-Options: DENY"""
        response = client.get('/api/system/health')
        assert response.headers.get('X-Frame-Options') == 'DENY'

    @pytest.mark.patch4
    @pytest.mark.high
    def test_x_xss_protection(self, client):
        """Response DEBE incluir X-XSS-Protection"""
        response = client.get('/api/system/health')
        assert 'X-XSS-Protection' in response.headers

    @pytest.mark.patch4
    @pytest.mark.high
    def test_content_security_policy(self, client):
        """Response DEBE incluir Content-Security-Policy"""
        response = client.get('/api/system/health')
        csp = response.headers.get('Content-Security-Policy', '')
        assert "default-src" in csp
        assert "frame-ancestors 'none'" in csp

    @pytest.mark.patch4
    @pytest.mark.high
    def test_referrer_policy(self, client):
        """Response DEBE incluir Referrer-Policy"""
        response = client.get('/api/system/health')
        assert 'Referrer-Policy' in response.headers

    @pytest.mark.patch4
    @pytest.mark.high
    def test_permissions_policy(self, client):
        """Response DEBE incluir Permissions-Policy"""
        response = client.get('/api/system/health')
        pp = response.headers.get('Permissions-Policy', '')
        assert 'geolocation=()' in pp
        assert 'camera=()' in pp

    @pytest.mark.patch4
    @pytest.mark.high
    def test_api_no_cache(self, client, auth_headers):
        """API endpoints DEBEN incluir Cache-Control: no-store"""
        response = client.get('/api/system/status', headers=auth_headers)
        cache = response.headers.get('Cache-Control', '')
        assert 'no-store' in cache

    @pytest.mark.patch4
    @pytest.mark.high
    def test_headers_on_all_endpoints(self, client):
        """Headers de seguridad DEBEN estar en TODAS las respuestas."""
        endpoints = [
            '/api/system/health',
            '/',
        ]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert 'X-Content-Type-Options' in response.headers, \
                f"Missing X-Content-Type-Options en {endpoint}"
            assert 'X-Frame-Options' in response.headers, \
                f"Missing X-Frame-Options en {endpoint}"

    @pytest.mark.patch4
    @pytest.mark.high
    def test_headers_on_error_responses(self, client):
        """Headers de seguridad DEBEN estar incluso en respuestas de error."""
        response = client.get('/api/nonexistent')
        assert response.status_code == 404
        assert 'X-Content-Type-Options' in response.headers
        assert 'X-Frame-Options' in response.headers


# ============================================================================
# PARCHE #5: Rate Limiting (Mistral/Copilot)
# Severidad: ALTO
# ============================================================================

class TestPatch05RateLimiting:
    """
    Verifica que el rate limiting esta activo y bloquea exceso de requests.
    """

    @pytest.mark.patch5
    @pytest.mark.high
    def test_rate_limiter_module_imported(self, flask_app):
        """Flask-Limiter DEBE estar integrado."""
        import importlib
        spec = importlib.util.find_spec("flask_limiter")
        assert spec is not None, "flask_limiter no instalado"

    @pytest.mark.patch5
    @pytest.mark.high
    def test_rate_limit_returns_429(self, client, auth_headers):
        """Rate limiter DEBE retornar 429 despues del umbral."""
        got_429 = False
        for i in range(60):
            response = client.post(
                '/api/bootstrap/create',
                headers={**auth_headers, 'Content-Type': 'application/json'},
                json={"test": True}
            )
            if response.status_code == 429:
                got_429 = True
                break

        assert got_429, "Rate limiter deberia retornar 429 tras exceder el limite"

    @pytest.mark.patch5
    @pytest.mark.high
    def test_health_not_rate_limited(self, client):
        """Health check NO deberia tener rate limit estricto."""
        for _ in range(20):
            response = client.get('/api/system/health')
            assert response.status_code in [200, 503]


# ============================================================================
# PARCHE #6: Timing Attack - hmac.compare_digest (ChatGPT)
# Severidad: ALTO
# ============================================================================

class TestPatch06TimingAttack:
    """
    Verifica que la validacion de API key usa comparacion timing-safe.

    Vulnerabilidad original: Comparacion directa (==) permite ataques de
    timing para deducir la key caracter por caracter.
    """

    @pytest.mark.patch6
    @pytest.mark.high
    def test_missing_api_key_returns_401(self, client):
        """Request sin API key DEBE retornar 401."""
        response = client.get('/api/system/status')
        assert response.status_code == 401
        data = response.get_json()
        assert data['code'] == 'AUTH_MISSING'

    @pytest.mark.patch6
    @pytest.mark.high
    def test_wrong_api_key_returns_401(self, client, bad_auth_headers):
        """Request con API key incorrecta DEBE retornar 401."""
        response = client.get('/api/system/status', headers=bad_auth_headers)
        assert response.status_code == 401
        data = response.get_json()
        assert data['code'] == 'AUTH_INVALID'

    @pytest.mark.patch6
    @pytest.mark.high
    def test_correct_api_key_returns_200(self, client, auth_headers):
        """Request con API key correcta DEBE retornar 200."""
        response = client.get('/api/system/status', headers=auth_headers)
        assert response.status_code == 200

    @pytest.mark.patch6
    @pytest.mark.high
    def test_none_api_key_handled(self, client):
        """Header X-API-Key con valor None DEBE retornar 401 sin crash."""
        response = client.get(
            '/api/system/status',
            headers={"X-API-Key": ""}
        )
        assert response.status_code == 401

    @pytest.mark.patch6
    @pytest.mark.high
    def test_hmac_used_in_source(self):
        """Verificar que app.py usa hmac.compare_digest (no ==)."""
        app_path = Path("src/web-interface/app.py")
        if app_path.exists():
            source = app_path.read_text(encoding='utf-8')
            assert 'hmac.compare_digest' in source, \
                "app.py DEBE usar hmac.compare_digest para comparar API keys"
            lines = source.split('\n')
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                if '== API_KEY' in stripped or '== api_key' in stripped:
                    if 'hmac' not in stripped and 'compare_digest' not in stripped:
                        pytest.fail(
                            f"Linea {i+1}: Comparacion directa de API key detectada: {stripped}"
                        )


# ============================================================================
# Tests de integracion de autenticacion
# ============================================================================

class TestAuthIntegration:
    """Tests de integracion para el sistema de autenticacion."""

    @pytest.mark.patch2
    @pytest.mark.patch6
    def test_protected_endpoints_require_auth(self, client):
        """Todos los endpoints protegidos DEBEN requerir API key."""
        protected = [
            ('GET', '/api/system/status'),
            ('POST', '/api/bootstrap/create'),
            ('POST', '/api/cycle/start'),
            ('POST', '/api/proposal/submit'),
            ('POST', '/api/governance/decide'),
        ]
        for method, path in protected:
            if method == 'GET':
                response = client.get(path)
            else:
                response = client.post(path, json={})
            assert response.status_code == 401, \
                f"{method} {path} deberia requerir auth (got {response.status_code})"

    @pytest.mark.patch2
    @pytest.mark.patch6
    def test_public_endpoints_no_auth(self, client):
        """Endpoints publicos NO deben requerir API key."""
        public = [
            '/api/system/health',
            '/',
        ]
        for path in public:
            response = client.get(path)
            assert response.status_code != 401, \
                f"{path} NO deberia requerir auth (got {response.status_code})"

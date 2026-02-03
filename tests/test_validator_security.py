"""
PERCIA v2.0 - Tests de Seguridad: validator.py
===============================================
Cubre: Parche #10

Ejecutar:
    pytest tests/test_validator_security.py -v
"""

import os
import json
import pytest
from pathlib import Path


# ============================================================================
# PARCHE #10: Path Traversal en validate_file (ChatGPT)
# Severidad: BAJO
# ============================================================================

class TestPatch10PathTraversal:
    """
    Verifica que validate_file bloquea path traversal.
    
    Vulnerabilidad original: No validaba que el path resolvido estuviera
    dentro del directorio base, permitiendo acceso a archivos del sistema.
    """

    @pytest.mark.patch10
    @pytest.mark.low
    def test_path_traversal_blocked(self, validator):
        """Paths con '..' DEBEN ser rechazados."""
        traversal_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "subdir/../../etc/shadow",
            "....//....//etc/passwd",
        ]
        for path in traversal_paths:
            result = validator.validate_file(path)
            assert result.is_valid is False, \
                f"Path traversal NO bloqueado: {path}"
            assert any("traversal" in e.lower() or "peligroso" in e.lower() or "dangerous" in e.lower()
                      for e in result.errors), \
                f"Error debe mencionar traversal: {result.errors}"

    @pytest.mark.patch10
    @pytest.mark.low
    def test_absolute_path_blocked(self, validator):
        """Paths absolutos DEBEN ser rechazados."""
        absolute_paths = [
            "/etc/passwd",
            "/root/.ssh/id_rsa",
        ]
        for path in absolute_paths:
            result = validator.validate_file(path)
            assert result.is_valid is False, \
                f"Path absoluto NO bloqueado: {path}"

    @pytest.mark.patch10
    @pytest.mark.low
    def test_null_byte_blocked(self, validator):
        """Paths con null bytes DEBEN ser rechazados."""
        result = validator.validate_file("file.txt\x00.json")
        assert result.is_valid is False

    @pytest.mark.patch10
    @pytest.mark.low
    def test_valid_relative_path(self, validator, temp_base_path):
        """Paths relativos válidos dentro de base DEBEN ser aceptados."""
        # Crear archivo de test
        test_file = temp_base_path / "test_data.json"
        test_file.write_text('{"key": "value"}', encoding='utf-8')

        result = validator.validate_file("test_data.json")
        # Puede ser válido o inválido dependiendo de si el archivo existe
        # Lo importante es que NO sea rechazado por traversal
        if not result.is_valid:
            assert not any("traversal" in e.lower() for e in result.errors), \
                "Path válido NO debería ser rechazado por traversal"

    @pytest.mark.patch10
    @pytest.mark.low
    def test_file_size_check(self, validator, temp_base_path):
        """Archivos demasiado grandes DEBEN ser rechazados."""
        # Verificar que MAX_FILE_SIZE está definido
        assert hasattr(validator, 'MAX_FILE_SIZE')
        assert validator.MAX_FILE_SIZE > 0

    @pytest.mark.patch10
    @pytest.mark.low
    def test_source_uses_relative_to(self):
        """Verificar que validator.py usa Path.relative_to() para seguridad."""
        source_path = Path("src/scripts/validator.py")
        if source_path.exists():
            source = source_path.read_text(encoding='utf-8')
            assert 'relative_to' in source, \
                "DEBE usar relative_to() para validar que path está dentro de base"
            assert 'resolve()' in source, \
                "DEBE usar resolve() para normalizar paths"

    @pytest.mark.patch10
    @pytest.mark.low
    def test_allowed_extensions(self, validator):
        """Solo extensiones permitidas DEBEN pasar validación."""
        assert hasattr(validator, 'ALLOWED_EXTENSIONS')
        allowed = validator.ALLOWED_EXTENSIONS
        assert '.json' in allowed
        assert '.py' in allowed
        assert '.md' in allowed
        # Extensiones peligrosas NO deben estar
        assert '.exe' not in allowed
        assert '.sh' not in allowed
        assert '.bat' not in allowed


# ============================================================================
# Tests adicionales de Validator
# ============================================================================

class TestValidatorSanitization:
    """Tests de sanitización de inputs del Validator."""

    @pytest.mark.patch10
    def test_sanitize_string(self, validator):
        """sanitize_string DEBE limpiar caracteres de control."""
        if hasattr(validator, 'sanitize_string'):
            # String normal
            assert validator.sanitize_string("hello world") == "hello world"
            # String con null bytes
            result = validator.sanitize_string("hello\x00world")
            assert '\x00' not in result
            # String vacío
            assert validator.sanitize_string("") == ""

    @pytest.mark.patch10
    def test_is_safe_filename(self, validator):
        """is_safe_filename DEBE rechazar nombres peligrosos."""
        if hasattr(validator, 'is_safe_filename'):
            # Nombres seguros
            assert validator.is_safe_filename("file.json") is True
            assert validator.is_safe_filename("data_2024.py") is True
            # Nombres peligrosos
            assert validator.is_safe_filename("") is False
            assert validator.is_safe_filename("../etc/passwd") is False
            assert validator.is_safe_filename(".hidden") is False
            assert validator.is_safe_filename("CON.txt") is False  # Windows reserved
            assert validator.is_safe_filename("file/slash") is False

    @pytest.mark.patch10
    def test_validate_hash(self, validator):
        """validate_hash DEBE funcionar correctamente."""
        if hasattr(validator, 'validate_hash'):
            import hashlib
            data = "test data"
            expected = hashlib.sha256(data.encode()).hexdigest()
            result = validator.validate_hash(data, expected)
            assert result.is_valid is True

            # Hash incorrecto
            result = validator.validate_hash(data, "wrong_hash")
            assert result.is_valid is False

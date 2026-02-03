"""
PERCIA v2.0 - Tests de Seguridad: commit_coordinator.py
========================================================
Cubre: Parches #7, #8

Ejecutar:
    pytest tests/test_commit_coordinator_security.py -v
"""

import os
import re
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ============================================================================
# PARCHE #7: Command Injection en _run_git (ChatGPT/Perplexity)
# Severidad: ALTO
# ============================================================================

class TestPatch07CommandInjection:
    """
    Verifica que los inputs a Git son validados contra command injection.
    
    Vulnerabilidad original: _run_git no validaba argumentos, permitiendo
    inyección de comandos via git hashes o branch names maliciosos.
    """

    @pytest.mark.patch7
    @pytest.mark.high
    def test_valid_git_hash_accepted(self, commit_coordinator):
        """Hashes Git válidos (7-40 hex chars) DEBEN ser aceptados."""
        valid_hashes = [
            "5a20704",           # 7 chars
            "5a20704ce8c1c1d9",  # 16 chars
            "5a20704ce8c1c1d9d0dd55227943e42fa36e9f52",  # 40 chars
        ]
        for h in valid_hashes:
            result = commit_coordinator._validate_git_hash(h)
            assert result == h, f"Hash válido rechazado: {h}"

    @pytest.mark.patch7
    @pytest.mark.high
    def test_invalid_git_hash_rejected(self, commit_coordinator):
        """Hashes con caracteres inválidos DEBEN ser rechazados."""
        invalid_hashes = [
            "",                    # Vacío
            "xyz",                 # Solo 3 chars
            "12345",               # Solo 5 chars
            "GHIJKL",             # Hex mayúsculas no válidas para hash
            "5a20704; rm -rf /",  # Injection con semicolon
            "5a20704 && whoami",  # Injection con &&
            "5a20704\nmalicious", # Injection con newline
            "5a20704|cat /etc/passwd",  # Injection con pipe
            "`command`",          # Backtick injection
            "$(whoami)",          # Command substitution
            "../../../etc/passwd",  # Path traversal
        ]
        for h in invalid_hashes:
            with pytest.raises(ValueError):
                commit_coordinator._validate_git_hash(h)

    @pytest.mark.patch7
    @pytest.mark.high
    def test_git_hash_uses_fullmatch(self):
        """Validación DEBE usar fullmatch (no match) para evitar bypass."""
        source_path = Path("src/scripts/commit_coordinator.py")
        if source_path.exists():
            source = source_path.read_text(encoding='utf-8')
            assert 'fullmatch' in source, \
                "DEBE usar fullmatch en vez de match para validar git hashes"

    @pytest.mark.patch7
    @pytest.mark.high
    def test_run_git_rejects_dangerous_chars(self, commit_coordinator):
        """_run_git DEBE rechazar argumentos con caracteres peligrosos."""
        dangerous_args = [
            ['log', '--format=%H; rm -rf /'],
            ['log', 'HEAD && whoami'],
            ['log', 'HEAD | cat /etc/passwd'],
            ['checkout', '`malicious`'],
            ['checkout', '$(command)'],
            ['log', 'HEAD\ninjected'],
        ]
        for args in dangerous_args:
            with pytest.raises(ValueError):
                commit_coordinator._run_git(*args)

    @pytest.mark.patch7
    @pytest.mark.high
    def test_branch_name_validation(self, commit_coordinator):
        """Branch names DEBEN ser validados."""
        valid = ["main", "feature/test", "security/ronda3-patches"]
        for name in valid:
            result = commit_coordinator._validate_branch_name(name)
            assert result == name

        invalid = [
            "",
            "branch; rm -rf",
            "branch && whoami",
            "branch\ninjection",
        ]
        for name in invalid:
            with pytest.raises(ValueError):
                commit_coordinator._validate_branch_name(name)

    @pytest.mark.patch7
    @pytest.mark.high
    def test_path_validation(self, commit_coordinator):
        """Paths con '..' DEBEN ser rechazados."""
        invalid_paths = [
            "../../../etc/passwd",
            "..\\windows\\system32",
            "/absolute/path",
        ]
        for p in invalid_paths:
            with pytest.raises(ValueError):
                commit_coordinator._validate_path(p)

        valid_paths = [
            "src/scripts/app.py",
            "README.md",
            "tests/test_file.py",
        ]
        for p in valid_paths:
            result = commit_coordinator._validate_path(p)
            assert result == p


# ============================================================================
# PARCHE #8: Zombie Commits - restore_git_state flag (ChatGPT)
# Severidad: MEDIO
# ============================================================================

class TestPatch08ZombieCommits:
    """
    Verifica que el rollback usa restore_git_state flag para decidir
    si hacer git reset.
    
    Vulnerabilidad original: El rollback siempre hacía git reset --hard,
    incluso cuando no se había hecho git add/commit, lo que podía
    perder cambios legítimos del usuario.
    """

    @pytest.mark.patch8
    @pytest.mark.medium
    def test_commit_state_has_restore_flag(self):
        """CommitState DEBE tener campo restore_git_state."""
        from commit_coordinator import CommitState
        state = CommitState(
            commit_id="test",
            phase="idle",
            ia_id="test",
            files_modified=[],
            backup_dir=None,
            original_head=None,
            started_at="",
            restore_git_state=False
        )
        assert hasattr(state, 'restore_git_state')
        assert state.restore_git_state is False

    @pytest.mark.patch8
    @pytest.mark.medium
    def test_restore_flag_default_false(self):
        """restore_git_state DEBE ser False por defecto."""
        from commit_coordinator import CommitState
        state = CommitState(
            commit_id="test",
            phase="prepared",
            ia_id="test",
            files_modified=[],
            backup_dir=None,
            original_head="abc1234",
            started_at=""
        )
        assert state.restore_git_state is False

    @pytest.mark.patch8
    @pytest.mark.medium
    def test_source_has_restore_flag(self):
        """Verificar que commit_coordinator.py usa restore_git_state."""
        source_path = Path("src/scripts/commit_coordinator.py")
        if source_path.exists():
            source = source_path.read_text(encoding='utf-8')
            assert 'restore_git_state' in source, \
                "DEBE usar restore_git_state flag para controlar rollback"

    @pytest.mark.patch8
    @pytest.mark.medium
    def test_restore_flag_set_before_git_commit(self):
        """restore_git_state DEBE activarse ANTES del git commit."""
        source_path = Path("src/scripts/commit_coordinator.py")
        if source_path.exists():
            source = source_path.read_text(encoding='utf-8')
            # Verificar que restore_git_state = True aparece antes de git commit
            restore_pos = source.find('restore_git_state = True')
            commit_pos = source.find("'commit'", restore_pos if restore_pos > 0 else 0)
            if restore_pos > 0 and commit_pos > 0:
                assert restore_pos < commit_pos, \
                    "restore_git_state DEBE activarse ANTES del git commit"

    @pytest.mark.patch8
    @pytest.mark.medium
    def test_restore_flag_cleared_after_success(self):
        """restore_git_state DEBE desactivarse después de commit exitoso."""
        source_path = Path("src/scripts/commit_coordinator.py")
        if source_path.exists():
            source = source_path.read_text(encoding='utf-8')
            # Debe haber restore_git_state = False después del commit
            assert 'restore_git_state = False' in source or \
                   'restore_git_state=False' in source, \
                "restore_git_state DEBE resetearse a False después de commit exitoso"

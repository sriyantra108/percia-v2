"""
PERCIA v2.0 - Tests de Seguridad: lock_manager.py
===================================================
Cubre: Parches #3, #9, #11

Ejecutar:
    pytest tests/test_lock_manager_security.py -v
    pytest tests/test_lock_manager_security.py -m patch11 -v
"""

import os
import time
import json
import threading
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


# ============================================================================
# PARCHE #3: lock_context() release sin acquire (ChatGPT)
# Severidad: CRÍTICO
# ============================================================================

class TestPatch03LockContextRelease:
    """
    Verifica que lock_context() solo libera el lock si fue adquirido.
    
    Vulnerabilidad original: El finally block siempre llamaba release_global_lock(),
    incluso si acquire_global_lock() lanzaba TimeoutError, lo que podía liberar
    el lock de OTRO proceso legítimo.
    """

    @pytest.mark.patch3
    @pytest.mark.critical
    def test_lock_context_releases_on_success(self, lock_manager):
        """lock_context DEBE liberar el lock después de uso exitoso."""
        with lock_manager.lock_context("ia-test", "write"):
            status = lock_manager.get_lock_status()
            assert status["is_locked"] is True

        # Después del context, debe estar libre
        status = lock_manager.get_lock_status()
        assert status["is_locked"] is False

    @pytest.mark.patch3
    @pytest.mark.critical
    def test_lock_context_no_release_on_acquire_failure(self, lock_manager):
        """lock_context NO DEBE liberar si acquire falló."""
        # Simular que otro proceso tiene el lock
        from lock_manager import LockInfo
        other_lock = LockInfo(
            ia_id="ia-other",
            operation_type="write",
            acquired_at=datetime.now().isoformat(),
            ttl_seconds=300,
            pid=os.getpid(),  # Mismo PID para que no sea detectado como stale
            process_start_time=0.0
        )
        lock_manager._write_lock_info(other_lock)

        # Intentar lock_context con timeout corto - debería fallar
        # Pero NO debe liberar el lock del otro proceso
        try:
            with lock_manager.lock_context("ia-attacker", "write"):
                pytest.fail("No debería llegar aquí")
        except (TimeoutError, Exception):
            pass

        # El lock original DEBE seguir activo
        status = lock_manager.get_lock_status()
        assert status["is_locked"] is True
        assert status["holder"]["ia_id"] == "ia-other"

    @pytest.mark.patch3
    @pytest.mark.critical
    def test_lock_context_source_has_acquired_flag(self):
        """Verificar que lock_context usa flag 'acquired' en el código fuente."""
        source_path = Path("src/scripts/lock_manager.py")
        if source_path.exists():
            source = source_path.read_text(encoding='utf-8')
            assert 'acquired' in source, \
                "lock_context DEBE usar flag 'acquired' para controlar release"


# ============================================================================
# PARCHE #9: Cola sin mutex - threading.RLock (Todas las IAs)
# Severidad: MEDIO
# ============================================================================

class TestPatch09QueueMutex:
    """
    Verifica que las operaciones de cola son thread-safe.
    
    Vulnerabilidad original: get_queue_status() no usaba mutex,
    permitiendo lecturas inconsistentes durante escrituras concurrentes.
    """

    @pytest.mark.patch9
    @pytest.mark.medium
    def test_queue_has_mutex(self, lock_manager):
        """LockManager DEBE tener _queue_mutex como RLock."""
        assert hasattr(lock_manager, '_queue_mutex')
        import threading
        assert isinstance(lock_manager._queue_mutex, type(threading.RLock()))

    @pytest.mark.patch9
    @pytest.mark.medium
    def test_get_queue_status_thread_safe(self, lock_manager):
        """get_queue_status DEBE ser callable desde múltiples threads sin crash."""
        results = []
        errors = []

        def read_queue():
            try:
                for _ in range(50):
                    status = lock_manager.get_queue_status()
                    results.append(status)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=read_queue) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Errores en acceso concurrente: {errors}"
        assert len(results) == 250  # 5 threads × 50 reads

    @pytest.mark.patch9
    @pytest.mark.medium
    def test_concurrent_queue_read_write(self, lock_manager):
        """Lecturas y escrituras concurrentes NO deben causar corrupción."""
        errors = []

        def writer():
            try:
                for i in range(20):
                    lock_manager._add_to_queue(f"ia-writer-{i}", "write")
            except Exception as e:
                errors.append(f"writer: {e}")

        def reader():
            try:
                for _ in range(20):
                    lock_manager.get_queue_status()
            except Exception as e:
                errors.append(f"reader: {e}")

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(errors) == 0, f"Errores de concurrencia: {errors}"

    @pytest.mark.patch9
    @pytest.mark.medium
    def test_queue_status_returns_valid_structure(self, lock_manager):
        """get_queue_status DEBE retornar estructura válida."""
        status = lock_manager.get_queue_status()
        assert "queue_length" in status
        assert "entries" in status
        assert "timestamp" in status
        assert isinstance(status["entries"], list)
        assert isinstance(status["queue_length"], int)


# ============================================================================
# PARCHE #11: PID Reuse - process_start_time (Gemini)
# Severidad: ALTO
# ============================================================================

class TestPatch11PIDReuse:
    """
    Verifica que LockManager detecta PID reutilizados.
    
    Vulnerabilidad original: Solo verificaba si el PID existía via os.kill(pid, 0),
    pero si el OS reutiliza el PID para otro proceso, el lock nunca se liberaba.
    Gemini propuso comparar process_start_time para detectar reutilización.
    """

    @pytest.mark.patch11
    @pytest.mark.high
    def test_lock_info_has_process_start_time(self, lock_manager):
        """LockInfo DEBE incluir campo process_start_time."""
        lock_manager.acquire_global_lock("ia-test", "write")
        status = lock_manager.get_lock_status()
        assert "process_start_time" in status["holder"]
        lock_manager.release_global_lock()

    @pytest.mark.patch11
    @pytest.mark.high
    def test_process_start_time_is_set(self, lock_manager):
        """process_start_time DEBE ser > 0 cuando psutil está disponible."""
        lock_manager.acquire_global_lock("ia-test", "write")
        status = lock_manager.get_lock_status()
        
        try:
            import psutil
            assert status["holder"]["process_start_time"] > 0, \
                "process_start_time debe ser positivo con psutil"
        except ImportError:
            # Sin psutil, puede ser 0.0 (fallback)
            assert status["holder"]["process_start_time"] >= 0

        lock_manager.release_global_lock()

    @pytest.mark.patch11
    @pytest.mark.high
    def test_is_process_alive_detects_pid_reuse(self, lock_manager):
        """_is_process_alive DEBE detectar PID reutilizado."""
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil requerido para este test")

        current_pid = os.getpid()
        current_start = psutil.Process(current_pid).create_time()

        # Mismo PID pero start_time muy diferente = PID reutilizado
        fake_start_time = current_start - 100000  # 100000 segundos antes
        result = lock_manager._is_process_alive(current_pid, fake_start_time)
        assert result is False, "Debería detectar PID reutilizado"

    @pytest.mark.patch11
    @pytest.mark.high
    def test_is_process_alive_accepts_correct_process(self, lock_manager):
        """_is_process_alive DEBE aceptar proceso con start_time correcto."""
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil requerido para este test")

        current_pid = os.getpid()
        current_start = psutil.Process(current_pid).create_time()

        result = lock_manager._is_process_alive(current_pid, current_start)
        assert result is True, "Debería aceptar proceso con start_time correcto"

    @pytest.mark.patch11
    @pytest.mark.high
    def test_is_process_alive_nonexistent_pid(self, lock_manager):
        """_is_process_alive DEBE retornar False para PID inexistente."""
        # PID muy alto que probablemente no existe
        result = lock_manager._is_process_alive(999999, 0.0)
        assert result is False

    @pytest.mark.patch11
    @pytest.mark.high
    def test_stale_lock_detected_with_pid_reuse(self, lock_manager):
        """Lock con PID reutilizado DEBE ser detectado como stale."""
        from lock_manager import LockInfo

        # Crear lock con PID existente pero start_time falso
        fake_lock = LockInfo(
            ia_id="ia-dead",
            operation_type="write",
            acquired_at=datetime.now().isoformat(),
            ttl_seconds=300,
            pid=os.getpid(),
            process_start_time=1.0  # Start time falso (muy antiguo)
        )

        is_stale = lock_manager._is_lock_stale(fake_lock)
        
        try:
            import psutil
            # Con psutil, debería detectar que start_time no coincide
            assert is_stale is True, "Lock con PID reutilizado debe ser stale"
        except ImportError:
            # Sin psutil, el proceso parece vivo (fallback limitado)
            pass

    @pytest.mark.patch11
    @pytest.mark.high
    def test_source_has_process_start_time(self):
        """Verificar que LockInfo incluye process_start_time en el código fuente."""
        source_path = Path("src/scripts/lock_manager.py")
        if source_path.exists():
            source = source_path.read_text(encoding='utf-8')
            assert 'process_start_time' in source, \
                "LockInfo DEBE tener campo process_start_time"

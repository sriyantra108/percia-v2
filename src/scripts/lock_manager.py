#!/usr/bin/env python3
"""
PERCIA v2.0 - Lock Manager
==========================
Gestión de locks globales para coordinación multi-IA

VERSIÓN PARCHEADA - Ronda 3 Multi-IA Security Audit
Parches aplicados:
  - #3: lock_context() libera sin acquire (ChatGPT) - Flag acquired + try/except
  - #9: Cola sin mutex (Todas) - Wrapper thread-safe para get_queue_status
  - #11: PID Reuse (Gemini) - process_start_time para identidad de proceso

Commit base auditado: 5a20704
Fecha parche: Febrero 2026
"""

import os
import sys
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

# Para locks cross-platform
try:
    import portalocker
    PORTALOCKER_AVAILABLE = True
except ImportError:
    PORTALOCKER_AVAILABLE = False
    logging.warning("portalocker no instalado. Usando fallback con threading.Lock")

# Para verificación de procesos (PARCHE #11)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil no instalado. Verificación de PID limitada.")

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# PARCHE #11: Agregar process_start_time a LockInfo (Gemini)
# ============================================================================
@dataclass
class LockInfo:
    """Información de un lock activo."""
    ia_id: str
    operation_type: str
    acquired_at: str
    ttl_seconds: int
    pid: int
    process_start_time: float = 0.0  # PARCHE #11: Tiempo de inicio del proceso


@dataclass
class QueueEntry:
    """Entrada en la cola de espera."""
    ia_id: str
    operation_type: str
    queued_at: str
    priority: int = 0
    processing_by: Optional[str] = None  # Trazabilidad (Copilot)


class LockManager:
    """
    Gestor de locks globales para PERCIA.
    
    Características:
    - Lock global exclusivo para operaciones críticas
    - Cola de espera con prioridades
    - Watchdog para TTL y procesos muertos
    - Thread-safe para operaciones de cola
    - Detección de PID reuse (PARCHE #11)
    """
    
    DEFAULT_TTL = 300  # 5 minutos
    WATCHDOG_INTERVAL = 30  # segundos
    LOCK_FILE_NAME = ".percia_global.lock"
    LOCK_INFO_FILE = ".percia_lock_info.json"
    QUEUE_FILE = ".percia_queue.json"
    
    def __init__(self, base_path: str, default_ttl: int = None):
        """
        Inicializa el LockManager.
        
        Args:
            base_path: Directorio base para archivos de lock
            default_ttl: TTL por defecto en segundos
        """
        self.base_path = Path(base_path)
        self.default_ttl = default_ttl or self.DEFAULT_TTL
        
        # Archivos de estado
        self.lock_file = self.base_path / self.LOCK_FILE_NAME
        self.lock_info_file = self.base_path / self.LOCK_INFO_FILE
        self.queue_file = self.base_path / self.QUEUE_FILE
        
        # PARCHE #9: Mutex para operaciones de cola
        self._queue_mutex = threading.RLock()
        
        # Lock local para operaciones internas
        self._internal_lock = threading.RLock()
        
        # Estado del watchdog
        self._watchdog_thread = None
        self._watchdog_running = False
        
        # Asegurar que el directorio existe
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"LockManager inicializado en {self.base_path}")
    
    # ========================================================================
    # Métodos principales de lock
    # ========================================================================
    
    def acquire_global_lock(self, ia_id: str, operation_type: str, 
                           ttl: int = None, timeout: float = 30.0) -> bool:
        """
        Adquiere el lock global exclusivo.
        
        Args:
            ia_id: Identificador de la IA solicitante
            operation_type: Tipo de operación a realizar
            ttl: Time-to-live en segundos (opcional)
            timeout: Tiempo máximo de espera en segundos
        
        Returns:
            True si se adquirió el lock, False si no
        
        Raises:
            TimeoutError: Si no se puede adquirir en el tiempo especificado
        """
        start_time = time.time()
        ttl = ttl or self.default_ttl
        
        while time.time() - start_time < timeout:
            with self._internal_lock:
                # Verificar si hay lock existente
                existing_lock = self._read_lock_info()
                
                if existing_lock:
                    # Verificar si el lock expiró o el proceso murió
                    if self._is_lock_stale(existing_lock):
                        logger.warning(
                            f"Lock stale detectado (holder: {existing_lock.ia_id}, "
                            f"pid: {existing_lock.pid}). Limpiando..."
                        )
                        self._cleanup_stale_lock()
                    else:
                        # Lock válido de otro proceso, esperar
                        time.sleep(0.5)
                        continue
                
                # Intentar crear lock file
                try:
                    # PARCHE #11: Obtener process_start_time
                    try:
                        current_process = psutil.Process(os.getpid()) if PSUTIL_AVAILABLE else None
                        process_start_time = current_process.create_time() if current_process else 0.0
                    except Exception:
                        process_start_time = 0.0
                    
                    lock_info = LockInfo(
                        ia_id=ia_id,
                        operation_type=operation_type,
                        acquired_at=datetime.now().isoformat(),
                        ttl_seconds=ttl,
                        pid=os.getpid(),
                        process_start_time=process_start_time  # PARCHE #11
                    )
                    
                    # Crear archivo de lock (atómico)
                    self._write_lock_info(lock_info)
                    
                    # Verificar que somos el holder
                    time.sleep(0.1)  # Pequeña espera para race conditions
                    current = self._read_lock_info()
                    
                    if current and current.pid == os.getpid():
                        logger.info(
                            f"Lock adquirido por {ia_id} para {operation_type} "
                            f"(TTL: {ttl}s, PID: {os.getpid()})"
                        )
                        
                        # Remover de cola si estaba
                        self._remove_from_queue(ia_id)
                        
                        return True
                    else:
                        # Otro proceso ganó la race
                        continue
                        
                except Exception as e:
                    logger.error(f"Error adquiriendo lock: {e}")
                    time.sleep(0.5)
                    continue
        
        # Timeout - agregar a cola
        self._add_to_queue(ia_id, operation_type)
        raise TimeoutError(f"No se pudo adquirir lock en {timeout}s")
    
    def release_global_lock(self, force: bool = False) -> bool:
        """
        Libera el lock global.
        
        Args:
            force: Si True, libera aunque no seamos el holder
        
        Returns:
            True si se liberó, False si no había lock o no éramos holder
        """
        with self._internal_lock:
            current = self._read_lock_info()
            
            if not current:
                logger.warning("Intento de liberar lock inexistente")
                return False
            
            if not force and current.pid != os.getpid():
                logger.warning(
                    f"Intento de liberar lock ajeno (holder PID: {current.pid}, "
                    f"caller PID: {os.getpid()})"
                )
                return False
            
            try:
                # Eliminar archivos de lock
                if self.lock_info_file.exists():
                    self.lock_info_file.unlink()
                if self.lock_file.exists():
                    self.lock_file.unlink()
                
                logger.info(f"Lock liberado por PID {os.getpid()}")
                return True
                
            except Exception as e:
                logger.error(f"Error liberando lock: {e}")
                return False
    
    # ========================================================================
    # PARCHE #3: lock_context corregido (ChatGPT)
    # ========================================================================
    @contextmanager
    def lock_context(self, ia_id: str, operation_type: str, ttl: int = None):
        """
        Context manager para usar locks de forma segura.

        CORREGIDO (PARCHE #3):
        - Solo libera el lock si fue adquirido exitosamente.
        - Evita liberar un lock ajeno cuando acquire_global_lock() falla.
        - Maneja errores en el release.
        """
        acquired = False
        try:
            acquired = bool(self.acquire_global_lock(ia_id, operation_type, ttl))
            if not acquired:
                # Defensa extra: acquire_global_lock debería lanzar TimeoutError
                raise TimeoutError("No se pudo adquirir el lock global")
            yield
        finally:
            if acquired:
                try:
                    self.release_global_lock()
                except Exception as e:
                    logger.error(f"Error liberando lock en lock_context: {e}")
    
    # ========================================================================
    # PARCHE #11: _is_process_alive con detección de PID reuse (Gemini)
    # ========================================================================
    def _is_process_alive(self, pid: int, expected_start_time: float = 0.0) -> bool:
        """
        Verifica si un proceso está vivo Y es el proceso original.
        
        CORREGIDO (PARCHE #11): Valida process_start_time para detectar PID reuse.
        
        Args:
            pid: PID del proceso a verificar
            expected_start_time: Tiempo de inicio esperado del proceso
        
        Returns:
            True si el proceso está vivo y es el original, False en caso contrario
        """
        if not PSUTIL_AVAILABLE:
            # Sin psutil, solo podemos verificar existencia básica
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False
        
        try:
            proc = psutil.Process(pid)
            
            # Verificar que está corriendo y no es zombie
            if not (proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE):
                return False
            
            # 🛡️ PARCHE #11: VALIDACIÓN DE IDENTIDAD
            # Si el tiempo de inicio difiere, es un PID reutilizado
            if expected_start_time > 0:
                actual_start_time = proc.create_time()
                # Tolerancia de 1 segundo por imprecisión de timestamps
                if abs(actual_start_time - expected_start_time) > 1.0:
                    logger.warning(
                        f"PID {pid} reutilizado detectado. "
                        f"Expected start: {expected_start_time:.2f}, "
                        f"Actual: {actual_start_time:.2f}"
                    )
                    return False  # El proceso original murió, este es otro proceso
            
            return True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    
    def _is_lock_stale(self, lock_info: LockInfo) -> bool:
        """
        Verifica si un lock está obsoleto (expirado o proceso muerto).
        
        Args:
            lock_info: Información del lock a verificar
        
        Returns:
            True si el lock está obsoleto, False si es válido
        """
        # Verificar TTL
        acquired_at = datetime.fromisoformat(lock_info.acquired_at)
        expires_at = acquired_at + timedelta(seconds=lock_info.ttl_seconds)
        
        if datetime.now() > expires_at:
            logger.info(f"Lock expirado (TTL: {lock_info.ttl_seconds}s)")
            return True
        
        # PARCHE #11: Verificar proceso con start_time
        if not self._is_process_alive(lock_info.pid, lock_info.process_start_time):
            logger.info(f"Proceso holder muerto o reemplazado (PID: {lock_info.pid})")
            return True
        
        return False
    
    def _cleanup_stale_lock(self):
        """Limpia un lock obsoleto."""
        try:
            if self.lock_info_file.exists():
                self.lock_info_file.unlink()
            if self.lock_file.exists():
                self.lock_file.unlink()
            logger.info("Lock stale limpiado")
        except Exception as e:
            logger.error(f"Error limpiando lock stale: {e}")
    
    # ========================================================================
    # Operaciones de archivo (atómicas)
    # ========================================================================
    
    def _read_lock_info(self) -> Optional[LockInfo]:
        """Lee la información del lock actual."""
        if not self.lock_info_file.exists():
            return None
        
        try:
            with open(self.lock_info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return LockInfo(**data)
        except Exception as e:
            logger.warning(f"Error leyendo lock info: {e}")
            return None
    
    def _write_lock_info(self, lock_info: LockInfo):
        """Escribe información de lock de forma atómica."""
        temp_file = self.lock_info_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(lock_info), f, indent=2)
            # Rename atómico
            os.replace(temp_file, self.lock_info_file)
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise e
    
    # ========================================================================
    # PARCHE #9: Operaciones de cola thread-safe (Todas)
    # ========================================================================
    
    def _add_to_queue(self, ia_id: str, operation_type: str, priority: int = 0):
        """Agrega una IA a la cola de espera (thread-safe)."""
        with self._queue_mutex:  # PARCHE #9
            queue = self._read_queue()
            
            # Evitar duplicados
            if any(e.ia_id == ia_id for e in queue):
                logger.debug(f"{ia_id} ya está en cola")
                return
            
            entry = QueueEntry(
                ia_id=ia_id,
                operation_type=operation_type,
                queued_at=datetime.now().isoformat(),
                priority=priority
            )
            queue.append(entry)
            
            # Ordenar por prioridad (mayor primero)
            queue.sort(key=lambda x: x.priority, reverse=True)
            
            self._write_queue(queue)
            logger.info(f"{ia_id} agregada a cola (posición: {len(queue)})")
    
    def _remove_from_queue(self, ia_id: str):
        """Remueve una IA de la cola (thread-safe)."""
        with self._queue_mutex:  # PARCHE #9
            queue = self._read_queue()
            original_len = len(queue)
            queue = [e for e in queue if e.ia_id != ia_id]
            
            if len(queue) < original_len:
                self._write_queue(queue)
                logger.debug(f"{ia_id} removida de cola")
    
    def _read_queue(self) -> List[QueueEntry]:
        """Lee la cola de espera."""
        if not self.queue_file.exists():
            return []
        
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [QueueEntry(**e) for e in data]
        except Exception as e:
            logger.warning(f"Error leyendo cola: {e}")
            return []
    
    def _write_queue(self, queue: List[QueueEntry]):
        """Escribe la cola de forma atómica."""
        temp_file = self.queue_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump([asdict(e) for e in queue], f, indent=2)
            os.replace(temp_file, self.queue_file)
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise e
    
    # ========================================================================
    # PARCHE #9: get_queue_status thread-safe (Todas)
    # ========================================================================
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual de la cola.
        
        CORREGIDO (PARCHE #9): Thread-safe con mutex.
        
        Returns:
            Dict con información de la cola
        """
        with self._queue_mutex:  # PARCHE #9: Protección con mutex
            queue = self._read_queue()
            
            return {
                "queue_length": len(queue),
                "entries": [asdict(e) for e in queue],
                "timestamp": datetime.now().isoformat()
            }
    
    def get_lock_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual del lock.
        
        Returns:
            Dict con información del lock
        """
        with self._internal_lock:
            lock_info = self._read_lock_info()
            
            if not lock_info:
                return {
                    "is_locked": False,
                    "holder": None,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Verificar si está stale
            is_stale = self._is_lock_stale(lock_info)
            
            acquired_at = datetime.fromisoformat(lock_info.acquired_at)
            expires_at = acquired_at + timedelta(seconds=lock_info.ttl_seconds)
            remaining_ttl = max(0, (expires_at - datetime.now()).total_seconds())
            
            return {
                "is_locked": not is_stale,
                "is_stale": is_stale,
                "holder": {
                    "ia_id": lock_info.ia_id,
                    "operation_type": lock_info.operation_type,
                    "pid": lock_info.pid,
                    "process_start_time": lock_info.process_start_time,
                    "acquired_at": lock_info.acquired_at,
                    "ttl_seconds": lock_info.ttl_seconds,
                    "remaining_ttl": remaining_ttl
                },
                "timestamp": datetime.now().isoformat()
            }
    
    # ========================================================================
    # Watchdog
    # ========================================================================
    
    def start_watchdog(self):
        """Inicia el watchdog en background."""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            logger.warning("Watchdog ya está corriendo")
            return
        
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="LockManager-Watchdog"
        )
        self._watchdog_thread.start()
        logger.info("Watchdog iniciado")
    
    def stop_watchdog(self):
        """Detiene el watchdog."""
        self._watchdog_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5)
        logger.info("Watchdog detenido")
    
    def _watchdog_loop(self):
        """Loop principal del watchdog."""
        while self._watchdog_running:
            try:
                self._watchdog_check()
            except Exception as e:
                logger.error(f"Error en watchdog: {e}")
            
            time.sleep(self.WATCHDOG_INTERVAL)
    
    def _watchdog_check(self):
        """Verifica y limpia locks obsoletos."""
        with self._internal_lock:
            lock_info = self._read_lock_info()
            
            if lock_info and self._is_lock_stale(lock_info):
                logger.info(f"Watchdog: limpiando lock stale de {lock_info.ia_id}")
                self._cleanup_stale_lock()
                
                # Notificar al siguiente en cola (si implementado)
                # self._notify_next_in_queue()


# ============================================================================
# CLI para testing
# ============================================================================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='PERCIA Lock Manager CLI')
    parser.add_argument('--base-path', default='.', help='Directorio base')
    parser.add_argument('--acquire', metavar='IA_ID', help='Adquirir lock')
    parser.add_argument('--release', action='store_true', help='Liberar lock')
    parser.add_argument('--status', action='store_true', help='Mostrar estado')
    parser.add_argument('--queue', action='store_true', help='Mostrar cola')
    
    args = parser.parse_args()
    
    lm = LockManager(args.base_path)
    
    if args.acquire:
        try:
            lm.acquire_global_lock(args.acquire, 'cli_test', timeout=5)
            print(f"✅ Lock adquirido por {args.acquire}")
        except TimeoutError:
            print("❌ Timeout adquiriendo lock")
    
    elif args.release:
        if lm.release_global_lock():
            print("✅ Lock liberado")
        else:
            print("❌ No se pudo liberar lock")
    
    elif args.status:
        status = lm.get_lock_status()
        print(json.dumps(status, indent=2))
    
    elif args.queue:
        queue = lm.get_queue_status()
        print(json.dumps(queue, indent=2))
    
    else:
        parser.print_help()

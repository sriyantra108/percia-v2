#!/usr/bin/env python3
"""
PERCIA v2.0 - Lock Manager - Gestor de Concurrencia Robusto

Implementa:
- Lock global con TTL (Time-To-Live) para evitar deadlocks
- Watchdog para detectar procesos muertos
- Limpieza automática de locks huérfanos
- Cola FIFO para orden de operaciones
- Owner tracking con ID único + timestamp
- Mutex cross-platform con portalocker (Windows/Linux)

Corrige hallazgos:
- CRIT-001 (Grok): Locks huérfanos
- CRIT-001 (Copilot): Riesgo de deadlock
- CRIT-LOCK-001 (GPT-4o): Temp file único + os.replace atómico
- CRIT-LOCK-002 (GPT-4o): Lock atómico con mutex cross-platform
- HIGH-LOCK-004 (GPT-4o): _save_queue con temp único

REQUISITO: pip install portalocker
"""

import json
import time
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import threading
import logging

# Cross-platform file locking (Windows + Linux)
try:
    import portalocker
except ImportError:  # pragma: no cover
    portalocker = None

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PERCIA.LockManager')


@dataclass
class LockInfo:
    """Información del lock actual"""
    owner_id: str
    ia_id: str
    pid: int
    hostname: str
    acquired_at: str
    expires_at: str
    operation_type: str
    
    def is_expired(self) -> bool:
        """Verifica si el lock ha expirado"""
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now() > expires
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LockInfo':
        return cls(**data)


@dataclass
class QueueItem:
    """Item en la cola FIFO"""
    queue_id: str
    ia_id: str
    operation_type: str
    file_path: str
    priority: int
    enqueued_at: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueItem':
        return cls(**data)


class LockManager:
    """
    Gestor de locks con garantías ACID para PERCIA v2.0
    
    Características:
    - Lock global con TTL configurable (default: 30s)
    - Watchdog thread para limpieza de locks expirados
    - Cola FIFO para operaciones pendientes
    - Detección de procesos muertos via PID
    - Logging completo para auditoría
    - Mutex cross-platform con portalocker
    """
    
    DEFAULT_TTL_SECONDS = 30
    WATCHDOG_INTERVAL_SECONDS = 5
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY_SECONDS = 0.5
    
    def __init__(self, base_path: str = ".", ttl_seconds: int = None):
        self.base_path = Path(base_path)
        self.ttl_seconds = ttl_seconds or self.DEFAULT_TTL_SECONDS
        
        # Archivos de control
        self.percia_dir = self.base_path / ".percia"
        self.lock_file = self.percia_dir / "lock.json"
        self.queue_file = self.percia_dir / "queue.json"
        self.lock_history_file = self.percia_dir / "lock_history.json"
        
        # Estado interno
        self._owner_id: Optional[str] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_running = False
        
        # Asegurar que existe el directorio
        self.percia_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializar cola si no existe
        if not self.queue_file.exists():
            self._save_queue([])
        
        logger.info(f"LockManager inicializado en {self.base_path}")

    @contextmanager
    def _mutex(self, timeout: float = 10.0):
        """
        Sección crítica cross-platform (Windows/Linux) para proteger operaciones sobre
        archivos compartidos (.percia/lock.json, .percia/queue.json, etc.).

        Requiere la dependencia: portalocker (pip install portalocker).
        """
        if portalocker is None:
            raise RuntimeError(
                "portalocker no está instalado. Instálalo con: pip install portalocker"
            )

        mutex_file = self.percia_dir / "mutex.lock"
        # 'a+' crea el archivo si no existe.
        with portalocker.Lock(str(mutex_file), mode="a+", timeout=timeout):
            yield

    def _generate_owner_id(self) -> str:
        """Genera ID único para el owner del lock"""
        return str(uuid.uuid4())
    
    def _get_hostname(self) -> str:
        """Obtiene el hostname de forma segura"""
        try:
            import socket
            return socket.gethostname()
        except:
            return "unknown"
    
    def _is_process_alive(self, pid: int) -> bool:
        """Verifica si un proceso está vivo"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
        except:
            # En Windows, usar método alternativo
            try:
                import subprocess
                result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                       capture_output=True, text=True)
                return str(pid) in result.stdout
            except:
                return True  # Asumir vivo si no podemos verificar
    
    def _read_lock(self) -> Optional[LockInfo]:
        """Lee información del lock actual"""
        if not self.lock_file.exists():
            return None
        
        try:
            with open(self.lock_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return LockInfo.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Lock file corrupto, eliminando: {e}")
            self._force_release_lock()
            return None
    
    def _write_lock(self, lock_info: LockInfo) -> None:
        """Escribe información del lock de forma atómica (temp único + os.replace)."""
        # Temp file único (evita colisiones concurrentes como lock.tmp)
        temp_file = self.lock_file.with_name(
            f"{self.lock_file.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(lock_info.to_dict(), f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            # os.replace es atómico y funciona en Windows/Linux
            os.replace(temp_file, self.lock_file)
        finally:
            # Limpieza defensiva si algo falló antes del replace
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
    
    def _force_release_lock(self) -> None:
        """Libera el lock de forma forzada"""
        if self.lock_file.exists():
            try:
                self.lock_file.unlink()
                logger.info("Lock liberado forzadamente")
            except Exception as e:
                logger.error(f"Error liberando lock: {e}")
    
    def _load_queue(self) -> List[QueueItem]:
        """Carga la cola de operaciones"""
        if not self.queue_file.exists():
            return []
        
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [QueueItem.from_dict(item) for item in data]
        except Exception as e:
            logger.error(f"Error cargando cola: {e}")
            return []
    
    def _save_queue(self, queue: List[QueueItem]) -> None:
        """Guarda la cola de forma atómica (temp único + os.replace)."""
        temp_file = self.queue_file.with_name(
            f"{self.queue_file.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump([item.to_dict() for item in queue], f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, self.queue_file)
        finally:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
    
    def _log_lock_event(self, event_type: str, lock_info: Optional[LockInfo], details: str = "") -> None:
        """Registra eventos de lock para auditoría"""
        history = []
        if self.lock_history_file.exists():
            try:
                with open(self.lock_history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except:
                history = []
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "lock_info": lock_info.to_dict() if lock_info else None,
            "details": details
        }
        
        history.append(event)
        
        # Mantener solo últimos 1000 eventos
        if len(history) > 1000:
            history = history[-1000:]
        
        with open(self.lock_history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
    
    def acquire_global_lock(
        self,
        ia_id: str = "unknown",
        operation_type: str = "unknown",
        timeout: int = None,
        force_if_expired: bool = True
    ) -> bool:
        """
        Adquiere lock global del sistema con TTL, usando una sección crítica (mutex)
        cross-platform para que el check+write sea atómico (evita TOCTOU).

        Nota: Este método asume que todos los procesos usan el mismo LockManager,
        ya que la atomicidad se garantiza con el mutex (.percia/mutex.lock).
        """
        if portalocker is None:
            raise RuntimeError(
                "portalocker no está instalado. Instálalo con: pip install portalocker"
            )

        timeout = timeout or self.ttl_seconds
        start_time = time.time()
        attempts = 0

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.error(f"Timeout adquiriendo lock para {ia_id}")
                raise TimeoutError(f"No se pudo adquirir lock en {timeout}s")

            remaining = max(0.0, timeout - elapsed)
            # No bloquear demasiado tiempo la sección crítica: intentos cortos y loop externo.
            mutex_timeout = min(1.0, remaining) if remaining > 0 else 0.0

            acquired = False
            try:
                with self._mutex(timeout=mutex_timeout):
                    current_lock = self._read_lock()

                    # Re-entrante (mismo proceso/owner): renovar y retornar True
                    if (
                        current_lock is not None
                        and self._owner_id
                        and current_lock.owner_id == self._owner_id
                        and current_lock.pid == os.getpid()
                    ):
                        new_expires = datetime.now() + timedelta(seconds=self.ttl_seconds)
                        current_lock.expires_at = new_expires.isoformat()
                        self._write_lock(current_lock)
                        logger.debug(f"Lock ya adquirido; TTL renovado hasta {new_expires}")
                        return True

                    # Si no hay lock, adquirir
                    if current_lock is None:
                        acquired = True
                    else:
                        # Si expiró y se permite, liberar y adquirir
                        if current_lock.is_expired() and force_if_expired:
                            logger.warning(
                                f"Lock expirado de {current_lock.ia_id}, liberando..."
                            )
                            self._log_lock_event(
                                "expired_release",
                                current_lock,
                                "Lock expirado y liberado"
                            )
                            self._force_release_lock()
                            acquired = True

                        # Si el proceso murió, liberar y adquirir
                        elif not self._is_process_alive(current_lock.pid):
                            logger.warning(
                                f"Proceso {current_lock.pid} muerto, liberando lock huérfano..."
                            )
                            self._log_lock_event(
                                "orphan_release",
                                current_lock,
                                "Proceso muerto detectado"
                            )
                            self._force_release_lock()
                            acquired = True

                    if acquired:
                        # HIGH-LOCK-001 (Gemini): Usar variable temporal
                        # No asignar a self._owner_id hasta confirmar escritura exitosa
                        new_owner_id = self._generate_owner_id()
                        now = datetime.now()
                        expires = now + timedelta(seconds=self.ttl_seconds)

                        lock_info = LockInfo(
                            owner_id=new_owner_id,
                            ia_id=ia_id,
                            pid=os.getpid(),
                            hostname=self._get_hostname(),
                            acquired_at=now.isoformat(),
                            expires_at=expires.isoformat(),
                            operation_type=operation_type
                        )

                        self._write_lock(lock_info)
                        
                        # Solo asignar a self._owner_id DESPUÉS de escritura exitosa
                        self._owner_id = new_owner_id
                        self._log_lock_event("acquired", lock_info)
                        logger.info(
                            f"Lock adquirido por {ia_id} (owner: {self._owner_id})"
                        )
                        return True

            except Exception as e:
                # Si el mutex está ocupado o hay contención, seguimos intentando hasta timeout
                logger.debug(f"No se pudo entrar a sección crítica (mutex): {e}")

            # Lock ocupado por otro: esperar y reintentar
            attempts += 1
            logger.debug(f"Lock ocupado, reintento {attempts}...")
            time.sleep(self.RETRY_DELAY_SECONDS)
    
    def release_global_lock(self, force: bool = False) -> bool:
        """
        Libera el lock global de forma segura (bajo mutex).

        Args:
            force: Si True, libera aunque no sea el owner.
        """
        try:
            # Sección crítica para evitar carreras con acquire/refresh/watchdog
            with self._mutex(timeout=5.0):
                current_lock = self._read_lock()

                if current_lock is None:
                    logger.debug("No hay lock que liberar")
                    self._owner_id = None
                    return True

                # Verificar ownership (a menos que sea force)
                if (
                    not force
                    and self._owner_id
                    and current_lock.owner_id != self._owner_id
                ):
                    logger.warning("Intento de liberar lock ajeno")
                    return False

                self._log_lock_event("released", current_lock)
                self._force_release_lock()
                self._owner_id = None

                logger.info("Lock liberado correctamente")
                return True

        except Exception as e:
            logger.error(f"Error liberando lock: {e}")
            return False
    
    def refresh_lock(self) -> bool:
        """Renueva el TTL del lock actual (heartbeat) de forma segura (bajo mutex)."""
        try:
            with self._mutex(timeout=5.0):
                current_lock = self._read_lock()

                if current_lock is None:
                    logger.warning("No hay lock para renovar")
                    return False

                if current_lock.owner_id != self._owner_id:
                    logger.warning("No se puede renovar lock ajeno")
                    return False

                new_expires = datetime.now() + timedelta(seconds=self.ttl_seconds)
                current_lock.expires_at = new_expires.isoformat()

                self._write_lock(current_lock)
                logger.debug(f"Lock renovado hasta {new_expires}")
                return True

        except Exception as e:
            logger.error(f"Error renovando lock: {e}")
            return False
    
    @contextmanager
    def lock_context(self, ia_id: str, operation_type: str):
        """Context manager para usar locks de forma segura"""
        try:
            self.acquire_global_lock(ia_id=ia_id, operation_type=operation_type)
            yield
        finally:
            self.release_global_lock()
    
    def enqueue_operation(
        self, 
        ia_id: str, 
        operation_type: str, 
        file_path: str,
        priority: int = 5
    ) -> str:
        """Añade operación a la cola FIFO"""
        queue = self._load_queue()
        
        queue_item = QueueItem(
            queue_id=f"q-{uuid.uuid4().hex[:12]}",
            ia_id=ia_id,
            operation_type=operation_type,
            file_path=file_path,
            priority=priority,
            enqueued_at=datetime.now().isoformat(),
            status="pending"
        )
        
        queue.append(queue_item)
        queue.sort(key=lambda x: (x.priority, x.enqueued_at))
        self._save_queue(queue)
        
        logger.info(f"Operación {queue_item.queue_id} añadida a la cola")
        return queue_item.queue_id
    
    def dequeue_operation(self) -> Optional[QueueItem]:
        """Obtiene y procesa la siguiente operación de la cola"""
        queue = self._load_queue()
        
        for item in queue:
            if item.status == "pending":
                item.status = "processing"
                self._save_queue(queue)
                logger.info(f"Procesando operación {item.queue_id}")
                return item
        
        return None
    
    def complete_operation(self, queue_id: str, success: bool = True) -> bool:
        """Marca una operación como completada"""
        queue = self._load_queue()
        
        for item in queue:
            if item.queue_id == queue_id:
                item.status = "completed" if success else "failed"
                self._save_queue(queue)
                logger.info(f"Operación {queue_id} marcada como {item.status}")
                return True
        
        logger.warning(f"Operación {queue_id} no encontrada")
        return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Obtiene estado actual de la cola"""
        queue = self._load_queue()
        
        return {
            "total": len(queue),
            "pending": len([q for q in queue if q.status == "pending"]),
            "processing": len([q for q in queue if q.status == "processing"]),
            "completed": len([q for q in queue if q.status == "completed"]),
            "failed": len([q for q in queue if q.status == "failed"]),
            "items": [q.to_dict() for q in queue]
        }
    
    def get_lock_status(self) -> Dict[str, Any]:
        """Obtiene estado actual del lock"""
        current_lock = self._read_lock()
        
        if current_lock is None:
            return {"locked": False, "lock_info": None}
        
        return {
            "locked": True,
            "lock_info": current_lock.to_dict(),
            "is_expired": current_lock.is_expired(),
            "process_alive": self._is_process_alive(current_lock.pid)
        }
    
    def start_watchdog(self) -> None:
        """Inicia thread watchdog para limpiar locks expirados"""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            logger.warning("Watchdog ya está corriendo")
            return
        
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="PERCIA-LockWatchdog"
        )
        self._watchdog_thread.start()
        logger.info("Watchdog iniciado")
    
    def stop_watchdog(self) -> None:
        """Detiene el thread watchdog"""
        self._watchdog_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=2)
        logger.info("Watchdog detenido")
    
    def _watchdog_loop(self) -> None:
        """Loop del watchdog para limpiar locks expirados / huérfanos (bajo mutex)."""
        while self._watchdog_running:
            try:
                # Intento corto para no bloquear el sistema si hay contención
                with self._mutex(timeout=1.0):
                    current_lock = self._read_lock()

                    if current_lock:
                        if current_lock.is_expired():
                            logger.warning(
                                f"Watchdog: Lock expirado de {current_lock.ia_id}"
                            )
                            self._log_lock_event("watchdog_expired", current_lock)
                            self._force_release_lock()

                        elif not self._is_process_alive(current_lock.pid):
                            logger.warning(
                                f"Watchdog: Proceso {current_lock.pid} muerto"
                            )
                            self._log_lock_event("watchdog_orphan", current_lock)
                            self._force_release_lock()

            except Exception as e:
                # Si no se pudo adquirir mutex o cualquier error, se registra y continúa
                logger.error(f"Error en watchdog: {e}")

            time.sleep(self.WATCHDOG_INTERVAL_SECONDS)
    
    def submit_operation(self, ia_id: str, operation_type: str, file_path: str = None) -> Dict[str, Any]:
        """Procesa envío de propuesta o challenge con lock y cola"""
        queue_id = None
        try:
            queue_id = self.enqueue_operation(
                ia_id=ia_id,
                operation_type=operation_type,
                file_path=file_path or "",
                priority=5
            )
            
            with self.lock_context(ia_id, operation_type):
                logger.info(f"✅ {operation_type} de {ia_id} procesado")
                self.complete_operation(queue_id, success=True)
                
                return {
                    "status": "SUCCESS",
                    "queue_id": queue_id,
                    "ia_id": ia_id,
                    "operation_type": operation_type,
                    "timestamp": datetime.now().isoformat()
                }
        
        except TimeoutError as e:
            if queue_id:
                self.complete_operation(queue_id, success=False)
            return {"status": "TIMEOUT", "error": str(e)}
        
        except Exception as e:
            logger.error(f"Error procesando operación: {e}")
            return {"status": "ERROR", "error": str(e)}


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='PERCIA Lock Manager CLI')
    parser.add_argument('command', choices=[
        'status', 'acquire', 'release', 'unlock', 'queue', 'submit', 'watchdog'
    ])
    parser.add_argument('--ia-id', default='cli-user')
    parser.add_argument('--type', default='manual')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--ttl', type=int, default=30)
    parser.add_argument('--base-path', default='.')
    
    args = parser.parse_args()
    manager = LockManager(base_path=args.base_path, ttl_seconds=args.ttl)
    
    if args.command == 'status':
        print(json.dumps({
            "lock": manager.get_lock_status(),
            "queue": manager.get_queue_status()
        }, indent=2))
    
    elif args.command == 'acquire':
        try:
            manager.acquire_global_lock(ia_id=args.ia_id, operation_type=args.type)
            print(f"✅ Lock adquirido por {args.ia_id}")
        except TimeoutError as e:
            print(f"❌ {e}")
            sys.exit(1)
    
    elif args.command == 'release':
        if manager.release_global_lock(force=args.force):
            print("✅ Lock liberado")
        else:
            print("❌ No se pudo liberar el lock")
            sys.exit(1)
    
    elif args.command == 'unlock':
        if args.force:
            manager._force_release_lock()
            print("✅ Lock liberado forzadamente")
        else:
            print("Use --force para liberar forzadamente")
            sys.exit(1)
    
    elif args.command == 'queue':
        print(json.dumps(manager.get_queue_status(), indent=2))
    
    elif args.command == 'submit':
        result = manager.submit_operation(ia_id=args.ia_id, operation_type=args.type)
        print(json.dumps(result, indent=2))
    
    elif args.command == 'watchdog':
        print("Iniciando watchdog (Ctrl+C para detener)...")
        manager.start_watchdog()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            manager.stop_watchdog()
            print("\nWatchdog detenido")

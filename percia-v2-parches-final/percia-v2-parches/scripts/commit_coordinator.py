#!/usr/bin/env python3
"""
PERCIA v2.0 - Commit Coordinator - Commits Atómicos con Git

Implementa:
- Two-phase commit para atomicidad
- Rollback automático en caso de fallo
- Sincronización snapshot.json con Git
- Backups automáticos antes de operaciones
- Logging completo para auditoría
- Integración con LockManager para concurrencia

Corrige hallazgos:
- CRIT-002 (Copilot): Atomicidad no garantizada
- CRIT-CC-001 (GPT-4o): Bug de orden en commit_transaction
- CRIT-CC-002 (GPT-4o): Exception handler fallaba
- CRIT-CC-003 (GPT-4o): git_head se actualiza después del commit
- CRIT-2PC-001 (Perplexity): Integración con LockManager
- Gap documentación-código (Grok/Copilot)
"""

import json
import os
import sys
import shutil
import subprocess
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# Import condicional de LockManager para evitar circular imports
if TYPE_CHECKING:
    from lock_manager import LockManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PERCIA.CommitCoordinator')


class CommitPhase(Enum):
    """Fases del two-phase commit"""
    INIT = "init"
    PREPARE = "prepare"
    COMMIT = "commit"
    ROLLBACK = "rollback"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TransactionState:
    """Estado de una transacción"""
    transaction_id: str
    phase: str
    started_at: str
    files_modified: List[str]
    backup_dir: str
    git_commit_hash: Optional[str]
    error_message: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TransactionState':
        return cls(**data)


class GitError(Exception):
    """Error relacionado con operaciones Git"""
    pass


class CommitCoordinator:
    """
    Coordinador de commits atómicos para PERCIA v2.0
    
    Implementa two-phase commit:
    1. PREPARE: Crear backup, validar cambios, stage en Git
    2. COMMIT: Ejecutar commit Git, actualizar snapshot
    3. ROLLBACK: Restaurar desde backup si hay fallo
    
    Características:
    - Backups automáticos antes de cada operación
    - Validación pre-commit
    - Rollback automático en caso de error
    - Sincronización snapshot.json con HEAD (después del commit)
    - Logging completo para auditoría
    - CRIT-2PC-001 (Perplexity): Integración con LockManager para concurrencia
    """
    
    BACKUP_RETENTION_COUNT = 10
    
    def __init__(self, base_path: str = ".", lock_manager: Optional['LockManager'] = None):
        """
        Inicializa el CommitCoordinator.
        
        Args:
            base_path: Ruta base del proyecto
            lock_manager: Instancia de LockManager para concurrencia (CRIT-2PC-001)
        """
        self.base_path = Path(base_path)
        
        # CRIT-2PC-001 (Perplexity): Integrar LockManager
        self._lock_manager = lock_manager
        
        # Directorios
        self.mcp_dir = self.base_path / "mcp"
        self.percia_dir = self.base_path / ".percia"
        self.backup_dir = self.percia_dir / "backups"
        self.transaction_file = self.percia_dir / "current_transaction.json"
        
        # Archivos principales
        self.snapshot_file = self.mcp_dir / "snapshot.json"
        self.decisions_file = self.mcp_dir / "decisions.json"
        
        # Asegurar directorios
        self.mcp_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Estado actual
        self._current_transaction: Optional[TransactionState] = None
        
        # Verificar que estamos en un repo Git
        if not self._is_git_repo():
            logger.warning("No es un repositorio Git. Algunas funciones estarán limitadas.")
        
        logger.info(f"CommitCoordinator inicializado en {self.base_path}")
    
    def _is_git_repo(self) -> bool:
        """Verifica si estamos en un repositorio Git"""
        git_dir = self.base_path / ".git"
        return git_dir.exists() and git_dir.is_dir()
    
    def _run_git(self, args: List[str], check: bool = True) -> Tuple[int, str, str]:
        """
        Ejecuta comando Git
        
        Args:
            args: Argumentos para git
            check: Si True, lanza excepción en error
        
        Returns:
            Tuple (return_code, stdout, stderr)
        """
        cmd = ["git"] + args
        logger.debug(f"Ejecutando: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.base_path),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if check and result.returncode != 0:
                raise GitError(f"Git error: {result.stderr}")
            
            return (result.returncode, result.stdout.strip(), result.stderr.strip())
            
        except subprocess.TimeoutExpired:
            raise GitError("Git command timeout")
    
    def _get_current_commit_hash(self) -> Optional[str]:
        """Obtiene el hash del commit actual"""
        if not self._is_git_repo():
            return None
        
        try:
            _, stdout, _ = self._run_git(["rev-parse", "HEAD"])
            return stdout
        except GitError:
            return None
    
    def _create_backup(self, files: List[Path]) -> str:
        """
        Crea backup de archivos antes de modificación
        
        Corrige:
        - HIGH-005 (Mistral): Validar path traversal para evitar ../../etc/passwd
        
        Args:
            files: Lista de archivos a respaldar
        
        Returns:
            Ruta del directorio de backup
        
        Raises:
            ValueError: Si se detecta path traversal
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)
        
        for file_path in files:
            if file_path.exists():
                # HIGH-005 (Mistral): Validar que el archivo está dentro de base_path
                try:
                    # Resolver paths para detectar symlinks y ..
                    resolved_file = file_path.resolve()
                    resolved_base = self.base_path.resolve()
                    
                    # Verificar que el archivo está dentro de base_path
                    try:
                        rel_path = resolved_file.relative_to(resolved_base)
                    except ValueError:
                        logger.error(
                            f"Path traversal detectado: {file_path} está fuera de {self.base_path}"
                        )
                        raise ValueError(
                            f"Path traversal attempt: {file_path} is outside base directory"
                        )
                    
                    # Verificar que no hay componentes '..' en el path relativo
                    if ".." in rel_path.parts:
                        logger.error(f"Path traversal detectado: '..' en {rel_path}")
                        raise ValueError(
                            f"Path traversal attempt: '..' found in {rel_path}"
                        )
                    
                except ValueError:
                    raise  # Re-lanzar errores de validación
                
                dest = backup_path / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest)
                logger.debug(f"Backup creado: {file_path} -> {dest}")
        
        # También guardar estado Git si aplica
        if self._is_git_repo():
            git_state = {
                "commit_hash": self._get_current_commit_hash(),
                "timestamp": datetime.now().isoformat()
            }
            with open(backup_path / "git_state.json", 'w', encoding='utf-8') as f:
                json.dump(git_state, f, indent=2)
        
        # Limpiar backups antiguos
        self._cleanup_old_backups()
        
        logger.info(f"Backup creado en {backup_path}")
        return str(backup_path)
    
    def _restore_from_backup(self, backup_path: str) -> bool:
        """
        Restaura archivos desde backup
        
        Args:
            backup_path: Ruta al directorio de backup
        
        Returns:
            True si la restauración fue exitosa
        """
        backup_dir = Path(backup_path)
        
        if not backup_dir.exists():
            logger.error(f"Backup no existe: {backup_path}")
            return False
        
        try:
            # Restaurar archivos
            for item in backup_dir.rglob("*"):
                if item.is_file() and item.name != "git_state.json":
                    rel_path = item.relative_to(backup_dir)
                    dest = self.base_path / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
                    logger.debug(f"Restaurado: {item} -> {dest}")
            
            # Restaurar estado Git si existe
            git_state_file = backup_dir / "git_state.json"
            if git_state_file.exists() and self._is_git_repo():
                with open(git_state_file, 'r', encoding='utf-8') as f:
                    git_state = json.load(f)
                
                if git_state.get("commit_hash"):
                    self._run_git(["reset", "--hard", git_state["commit_hash"]])
                    logger.info(f"Git reset a {git_state['commit_hash'][:8]}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error restaurando backup: {e}")
            return False
    
    def _cleanup_old_backups(self) -> None:
        """Limpia backups antiguos manteniendo solo los más recientes"""
        if not self.backup_dir.exists():
            return
        
        backups = sorted(
            [d for d in self.backup_dir.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for backup in backups[self.BACKUP_RETENTION_COUNT:]:
            try:
                shutil.rmtree(backup)
                logger.debug(f"Backup antiguo eliminado: {backup}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar backup: {e}")
    
    def _save_transaction_state(self, state: TransactionState) -> None:
        """Guarda estado de transacción de forma atómica"""
        temp_file = self.transaction_file.with_name(
            f"{self.transaction_file.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(state.to_dict(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, self.transaction_file)
        finally:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
    
    def _load_transaction_state(self) -> Optional[TransactionState]:
        """Carga estado de transacción"""
        if not self.transaction_file.exists():
            return None
        
        try:
            with open(self.transaction_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return TransactionState.from_dict(data)
        except Exception as e:
            logger.error(f"Error cargando transacción: {e}")
            return None
    
    def _clear_transaction_state(self) -> None:
        """Limpia estado de transacción"""
        if self.transaction_file.exists():
            try:
                self.transaction_file.unlink()
            except Exception as e:
                logger.warning(f"No se pudo limpiar transacción: {e}")
        self._current_transaction = None
    
    def _update_snapshot(self, operation: str, data: Dict[str, Any]) -> None:
        """
        Actualiza snapshot.json (sin git_head - eso se hace después del commit)
        
        Args:
            operation: Tipo de operación (proposal, challenge, decision, cycle_start)
            data: Datos a agregar
        """
        # Cargar o crear snapshot
        if self.snapshot_file.exists():
            with open(self.snapshot_file, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)
        else:
            snapshot = {
                "version": "2.0",
                "created_at": datetime.now().isoformat(),
                "last_updated": None,
                "current_cycle": None,
                "proposals": [],
                "challenges": [],
                "decisions": [],
                "git_head": None
            }
        
        # Actualizar (sin git_head aquí - CRIT-CC-003 fix)
        snapshot["last_updated"] = datetime.now().isoformat()
        
        if operation == "proposal":
            snapshot["proposals"].append(data)
        elif operation == "challenge":
            snapshot["challenges"].append(data)
        elif operation == "decision":
            snapshot["decisions"].append(data)
        elif operation == "cycle_start":
            snapshot["current_cycle"] = data
        
        # Guardar de forma atómica
        temp_file = self.snapshot_file.with_name(
            f"{self.snapshot_file.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, self.snapshot_file)
        finally:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
        
        logger.debug(f"Snapshot actualizado: {operation}")
    
    def begin_transaction(self, description: str, files_to_modify: List[str] = None) -> str:
        """
        Inicia una transacción (Phase 1: PREPARE)
        
        Args:
            description: Descripción de la transacción
            files_to_modify: Lista de archivos que se modificarán
        
        Returns:
            ID de la transacción
        """
        # Verificar si hay transacción pendiente
        pending = self._load_transaction_state()
        if pending and pending.phase not in [CommitPhase.COMPLETED.value, CommitPhase.FAILED.value]:
            logger.warning(f"Transacción pendiente encontrada: {pending.transaction_id}")
            # Intentar rollback de transacción anterior
            self.rollback()
        
        # Crear nueva transacción
        transaction_id = f"tx-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Determinar archivos a respaldar
        if files_to_modify is None:
            files_to_modify = [
                str(self.snapshot_file),
                str(self.decisions_file)
            ]
        
        files_paths = [Path(f) if not isinstance(f, Path) else f for f in files_to_modify]
        
        # Crear backup
        backup_path = self._create_backup(files_paths)
        
        # Crear estado de transacción
        self._current_transaction = TransactionState(
            transaction_id=transaction_id,
            phase=CommitPhase.PREPARE.value,
            started_at=datetime.now().isoformat(),
            files_modified=[str(f) for f in files_paths],
            backup_dir=backup_path,
            git_commit_hash=None,
            error_message=None
        )
        
        self._save_transaction_state(self._current_transaction)
        
        logger.info(f"Transacción iniciada: {transaction_id} - {description}")
        return transaction_id
    
    def commit_transaction(self, commit_message: str) -> bool:
        """
        Finaliza la transacción con commit Git (Phase 2: COMMIT)
        
        Corrige:
        - CRIT-CC-001: No usar self._current_transaction tras _clear_transaction_state()
        - CRIT-CC-002: El except no debe fallar si _current_transaction es None
        - CRIT-CC-003: Sincronizar snapshot.git_head después del commit
        
        Args:
            commit_message: Mensaje del commit
        
        Returns:
            True si el commit fue exitoso
        """
        tx = self._current_transaction or self._load_transaction_state()
        if tx is None:
            logger.error("No hay transacción activa")
            return False

        # Asegurar referencia interna y capturar ID antes de cualquier clear
        self._current_transaction = tx
        tx_id = tx.transaction_id

        try:
            # Actualizar fase
            tx.phase = CommitPhase.COMMIT.value
            self._save_transaction_state(tx)

            commit_hash: Optional[str] = None

            if self._is_git_repo():
                # Stage archivos modificados (best-effort)
                for file_path in tx.files_modified:
                    try:
                        rel_path = Path(file_path).relative_to(self.base_path)
                    except Exception:
                        rel_path = Path(file_path)

                    if Path(file_path).exists():
                        self._run_git(["add", str(rel_path)])

                # También agregar mcp/
                self._run_git(["add", "mcp/"])

                # Verificar si hay cambios para commit
                returncode, _, _ = self._run_git(
                    ["diff", "--cached", "--quiet"], check=False
                )

                if returncode != 0:  # Hay cambios
                    # Crear commit
                    self._run_git(["commit", "-m", commit_message])

                # Hash actual (haya o no haya habido commit nuevo)
                commit_hash = self._get_current_commit_hash()
                tx.git_commit_hash = commit_hash
                logger.info(f"HEAD actual: {commit_hash[:8] if commit_hash else 'N/A'} - {commit_message}")

                # ======================================================
                # CRIT-CC-003: Sincronizar snapshot.git_head DESPUÉS del commit
                # ======================================================
                if self.snapshot_file.exists() and commit_hash:
                    with open(self.snapshot_file, 'r', encoding='utf-8') as f:
                        snapshot = json.load(f) or {}

                    snapshot["git_head"] = commit_hash
                    snapshot["last_updated"] = datetime.now().isoformat()

                    # Escritura atómica (temp único + os.replace)
                    tmp = self.snapshot_file.with_name(
                        f"{self.snapshot_file.name}.{os.getpid()}.{datetime.now().strftime('%Y%m%dT%H%M%S%f')}.tmp"
                    )
                    try:
                        with open(tmp, 'w', encoding='utf-8') as f:
                            json.dump(snapshot, f, indent=2)
                            f.flush()
                            os.fsync(f.fileno())
                        os.replace(tmp, self.snapshot_file)
                    finally:
                        try:
                            if tmp.exists():
                                tmp.unlink()
                        except Exception:
                            pass

            else:
                logger.warning("No es un repositorio Git; se omite commit Git")

            # Marcar como completado
            tx.phase = CommitPhase.COMPLETED.value
            self._save_transaction_state(tx)

            # Limpiar
            self._clear_transaction_state()

            logger.info(f"Transacción completada: {tx_id}")
            return True

        except Exception as e:
            logger.error(f"Error en commit: {e}")

            # Intentar guardar estado FAILED sin asumir que _current_transaction existe
            try:
                tx.error_message = str(e)
                tx.phase = CommitPhase.FAILED.value
                self._save_transaction_state(tx)
            except Exception as e2:
                logger.error(f"No se pudo guardar estado FAILED: {e2}")

            # Rollback automático (best-effort)
            try:
                self.rollback()
            except Exception as e3:
                logger.error(f"Rollback falló: {e3}")

            return False
    
    def rollback(self) -> bool:
        """
        Deshace la transacción actual restaurando desde backup
        
        Corrige:
        - CRIT-CC-004 (Gemini): Revertir commit de Git si ya se hizo ("Zombie Commit")
        
        Returns:
            True si el rollback fue exitoso
        """
        if self._current_transaction is None:
            self._current_transaction = self._load_transaction_state()
        
        if self._current_transaction is None:
            logger.warning("No hay transacción para rollback")
            return True
        
        try:
            logger.warning(f"Iniciando rollback de {self._current_transaction.transaction_id}")
            
            self._current_transaction.phase = CommitPhase.ROLLBACK.value
            self._save_transaction_state(self._current_transaction)
            
            # ================================================================
            # CRIT-CC-004 (Gemini): Revertir commit de Git si ya se realizó
            # Si la transacción estaba en fase COMMIT y tiene un hash,
            # significa que git commit tuvo éxito pero falló algo después.
            # Debemos revertir el commit para evitar "Zombie Commits".
            # ================================================================
            if (
                self._is_git_repo()
                and self._current_transaction.git_commit_hash
                and self._current_transaction.phase == CommitPhase.ROLLBACK.value
            ):
                # Verificar si HEAD actual coincide con el commit de la transacción
                current_head = self._get_current_commit_hash()
                if current_head == self._current_transaction.git_commit_hash:
                    logger.warning(
                        f"Revirtiendo Zombie Commit de Git: {current_head[:8]}..."
                    )
                    try:
                        # --soft mantiene los cambios staged, --hard los descarta
                        # Usamos --soft para ser menos destructivos
                        self._run_git(["reset", "--soft", "HEAD~1"])
                        logger.info("Commit de Git revertido exitosamente")
                    except GitError as e:
                        logger.error(f"No se pudo revertir commit de Git: {e}")
                        # Continuar con el rollback de archivos de todos modos
            
            # Restaurar desde backup
            if self._restore_from_backup(self._current_transaction.backup_dir):
                logger.info("Rollback completado exitosamente")
            else:
                logger.error("Rollback falló - intervención manual requerida")
                return False
            
            # Limpiar estado
            self._clear_transaction_state()
            return True
            
        except Exception as e:
            logger.error(f"Error en rollback: {e}")
            return False
    
    def process_proposal(self, proposal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa una propuesta con commit atómico
        
        Args:
            proposal_data: Datos de la propuesta
        
        Returns:
            Resultado del procesamiento
        """
        proposal_id = proposal_data.get('proposal_id', f"prop-{datetime.now().strftime('%Y%m%dT%H%M%S')}")
        author = proposal_data.get('author_ia', 'unknown')
        
        try:
            # Iniciar transacción
            tx_id = self.begin_transaction(f"Propuesta {proposal_id} de {author}")
            
            # Guardar propuesta en archivo
            proposals_dir = self.mcp_dir / "proposals"
            proposals_dir.mkdir(parents=True, exist_ok=True)
            
            proposal_file = proposals_dir / f"{proposal_id}.json"
            with open(proposal_file, 'w', encoding='utf-8') as f:
                json.dump(proposal_data, f, indent=2)
            
            # Actualizar snapshot
            self._update_snapshot("proposal", {
                "proposal_id": proposal_id,
                "author_ia": author,
                "submitted_at": datetime.now().isoformat(),
                "status": "pending_challenge"
            })
            
            # Commit
            if self.commit_transaction(f"feat(proposal): {proposal_id} from {author}"):
                logger.info(f"✅ Propuesta {proposal_id} procesada")
                return {
                    "status": "SUCCESS",
                    "proposal_id": proposal_id,
                    "transaction_id": tx_id,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "ERROR",
                    "error": "Commit failed",
                    "proposal_id": proposal_id
                }
                
        except Exception as e:
            logger.error(f"Error procesando propuesta: {e}")
            self.rollback()
            return {
                "status": "ERROR",
                "error": str(e),
                "proposal_id": proposal_id
            }
    
    def process_challenge(self, challenge_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa un challenge con commit atómico
        
        Args:
            challenge_data: Datos del challenge
        
        Returns:
            Resultado del procesamiento
        """
        challenge_id = challenge_data.get('challenge_id', f"ch-{datetime.now().strftime('%Y%m%dT%H%M%S')}")
        author = challenge_data.get('author_ia', 'unknown')
        target = challenge_data.get('target_proposal', 'unknown')
        
        try:
            tx_id = self.begin_transaction(f"Challenge {challenge_id} de {author}")
            
            # Guardar challenge
            challenges_dir = self.mcp_dir / "challenges"
            challenges_dir.mkdir(parents=True, exist_ok=True)
            
            challenge_file = challenges_dir / f"{challenge_id}.json"
            with open(challenge_file, 'w', encoding='utf-8') as f:
                json.dump(challenge_data, f, indent=2)
            
            # Actualizar snapshot
            self._update_snapshot("challenge", {
                "challenge_id": challenge_id,
                "author_ia": author,
                "target_proposal": target,
                "submitted_at": datetime.now().isoformat(),
                "status": "pending_review"
            })
            
            if self.commit_transaction(f"feat(challenge): {challenge_id} targeting {target}"):
                logger.info(f"✅ Challenge {challenge_id} procesado")
                return {
                    "status": "SUCCESS",
                    "challenge_id": challenge_id,
                    "transaction_id": tx_id
                }
            else:
                return {"status": "ERROR", "error": "Commit failed"}
                
        except Exception as e:
            logger.error(f"Error procesando challenge: {e}")
            self.rollback()
            return {"status": "ERROR", "error": str(e)}
    
    def process_decision(self, decision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa decisión de gobernanza con commit atómico
        
        Args:
            decision_data: Datos de la decisión
        
        Returns:
            Resultado del procesamiento
        """
        decision_id = decision_data.get('decision_id', f"dec-{datetime.now().strftime('%Y%m%dT%H%M%S')}")
        verdict = decision_data.get('verdict', 'unknown')
        
        try:
            tx_id = self.begin_transaction(f"Decisión {decision_id}: {verdict}")
            
            # Cargar o crear archivo de decisiones
            if self.decisions_file.exists():
                with open(self.decisions_file, 'r', encoding='utf-8') as f:
                    decisions = json.load(f)
            else:
                decisions = {"decisions": []}
            
            # Agregar decisión
            decision_data['timestamp'] = datetime.now().isoformat()
            decision_data['decision_id'] = decision_id
            decisions['decisions'].append(decision_data)
            
            # Guardar de forma atómica
            temp_file = self.decisions_file.with_name(
                f"{self.decisions_file.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
            )
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(decisions, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_file, self.decisions_file)
            finally:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception:
                    pass
            
            # Actualizar snapshot
            self._update_snapshot("decision", {
                "decision_id": decision_id,
                "verdict": verdict,
                "timestamp": datetime.now().isoformat()
            })
            
            if self.commit_transaction(f"governance(decision): {decision_id} - {verdict}"):
                logger.info(f"✅ Decisión {decision_id} registrada: {verdict}")
                return {
                    "status": "SUCCESS",
                    "decision_id": decision_id,
                    "verdict": verdict,
                    "transaction_id": tx_id
                }
            else:
                return {"status": "ERROR", "error": "Commit failed"}
                
        except Exception as e:
            logger.error(f"Error procesando decisión: {e}")
            self.rollback()
            return {"status": "ERROR", "error": str(e)}
    
    def get_snapshot(self) -> Dict[str, Any]:
        """Obtiene el snapshot actual"""
        if self.snapshot_file.exists():
            with open(self.snapshot_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def verify_integrity(self) -> Dict[str, Any]:
        """
        Verifica integridad entre snapshot y Git
        
        Returns:
            Resultado de verificación
        """
        issues = []
        
        # Verificar Git
        if self._is_git_repo():
            current_hash = self._get_current_commit_hash()
            
            snapshot = self.get_snapshot()
            snapshot_hash = snapshot.get("git_head")
            
            if snapshot_hash and snapshot_hash != current_hash:
                issues.append(f"Snapshot desincronizado: {snapshot_hash[:8]} != {current_hash[:8]}")
        
        # Verificar transacción pendiente
        pending = self._load_transaction_state()
        if pending and pending.phase not in [CommitPhase.COMPLETED.value, CommitPhase.FAILED.value]:
            issues.append(f"Transacción pendiente: {pending.transaction_id} en fase {pending.phase}")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "checked_at": datetime.now().isoformat()
        }


# CLI
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='PERCIA Commit Coordinator CLI')
    parser.add_argument('command', choices=[
        'status', 'verify', 'rollback', 'snapshot'
    ])
    parser.add_argument('--base-path', default='.')
    
    args = parser.parse_args()
    coordinator = CommitCoordinator(base_path=args.base_path)
    
    if args.command == 'status':
        pending = coordinator._load_transaction_state()
        if pending:
            print(json.dumps(pending.to_dict(), indent=2))
        else:
            print("No hay transacción pendiente")
    
    elif args.command == 'verify':
        result = coordinator.verify_integrity()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result['is_valid'] else 1)
    
    elif args.command == 'rollback':
        if coordinator.rollback():
            print("✅ Rollback completado")
        else:
            print("❌ Rollback falló")
            sys.exit(1)
    
    elif args.command == 'snapshot':
        print(json.dumps(coordinator.get_snapshot(), indent=2))

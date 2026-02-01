#!/usr/bin/env python3
"""
PERCIA v2.0 - Commit Coordinator - Commits Atómicos con Git

Implementa:
- Two-phase commit para atomicidad
- Rollback automático en caso de fallo
- Sincronización snapshot.json con Git
- Backups automáticos antes de operaciones
- Logging completo para auditoría

Corrige hallazgos:
- CRIT-002 (Copilot): Atomicidad no garantizada
- Gap documentación-código (Grok/Copilot)
"""

import json
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

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
    - Sincronización snapshot.json con HEAD
    - Logging completo para auditoría
    """
    
    BACKUP_RETENTION_COUNT = 10
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        
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
        except FileNotFoundError:
            raise GitError("Git no está instalado")
    
    def _get_current_commit_hash(self) -> Optional[str]:
        """Obtiene hash del commit actual"""
        try:
            _, stdout, _ = self._run_git(["rev-parse", "HEAD"])
            return stdout
        except GitError:
            return None
    
    def _create_backup(self, files: List[Path]) -> str:
        """
        Crea backup de archivos antes de modificar
        
        Args:
            files: Lista de archivos a respaldar
        
        Returns:
            Ruta del directorio de backup
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)
        
        for file_path in files:
            if file_path.exists():
                rel_path = file_path.relative_to(self.base_path)
                dest = backup_path / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest)
                logger.debug(f"Backup: {file_path} -> {dest}")
        
        # Guardar estado Git
        commit_hash = self._get_current_commit_hash()
        if commit_hash:
            with open(backup_path / "git_state.json", 'w') as f:
                json.dump({
                    "commit_hash": commit_hash,
                    "timestamp": timestamp,
                    "files": [str(f) for f in files]
                }, f, indent=2)
        
        logger.info(f"Backup creado: {backup_path}")
        self._cleanup_old_backups()
        
        return str(backup_path)
    
    def _restore_from_backup(self, backup_path: str) -> bool:
        """
        Restaura archivos desde backup
        
        Args:
            backup_path: Ruta al directorio de backup
        
        Returns:
            True si se restauró correctamente
        """
        backup_dir = Path(backup_path)
        
        if not backup_dir.exists():
            logger.error(f"Backup no encontrado: {backup_path}")
            return False
        
        try:
            # Restaurar archivos
            for backup_file in backup_dir.rglob("*"):
                if backup_file.is_file() and backup_file.name != "git_state.json":
                    rel_path = backup_file.relative_to(backup_dir)
                    dest = self.base_path / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, dest)
                    logger.debug(f"Restaurado: {backup_file} -> {dest}")
            
            # Restaurar estado Git si es posible
            git_state_file = backup_dir / "git_state.json"
            if git_state_file.exists():
                with open(git_state_file, 'r') as f:
                    git_state = json.load(f)
                
                # Reset Git al commit del backup
                commit_hash = git_state.get("commit_hash")
                if commit_hash and self._is_git_repo():
                    try:
                        self._run_git(["reset", "--hard", commit_hash])
                        logger.info(f"Git reset a {commit_hash}")
                    except GitError as e:
                        logger.warning(f"No se pudo resetear Git: {e}")
            
            logger.info(f"Backup restaurado desde {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error restaurando backup: {e}")
            return False
    
    def _cleanup_old_backups(self) -> None:
        """Elimina backups antiguos manteniendo los últimos N"""
        backups = sorted(
            [d for d in self.backup_dir.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for old_backup in backups[self.BACKUP_RETENTION_COUNT:]:
            try:
                shutil.rmtree(old_backup)
                logger.debug(f"Backup eliminado: {old_backup}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar backup {old_backup}: {e}")
    
    def _save_transaction_state(self, state: TransactionState) -> None:
        """Guarda estado de transacción actual"""
        with open(self.transaction_file, 'w') as f:
            json.dump(state.to_dict(), f, indent=2)
    
    def _load_transaction_state(self) -> Optional[TransactionState]:
        """Carga estado de transacción pendiente"""
        if not self.transaction_file.exists():
            return None
        
        try:
            with open(self.transaction_file, 'r') as f:
                data = json.load(f)
            return TransactionState.from_dict(data)
        except Exception as e:
            logger.error(f"Error cargando transacción: {e}")
            return None
    
    def _clear_transaction_state(self) -> None:
        """Limpia estado de transacción"""
        if self.transaction_file.exists():
            self.transaction_file.unlink()
        self._current_transaction = None
    
    def _update_snapshot(self, operation: str, data: Dict[str, Any]) -> None:
        """
        Actualiza snapshot.json con la operación realizada
        
        Args:
            operation: Tipo de operación
            data: Datos de la operación
        """
        # Cargar o crear snapshot
        if self.snapshot_file.exists():
            with open(self.snapshot_file, 'r') as f:
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
        
        # Actualizar
        snapshot["last_updated"] = datetime.now().isoformat()
        snapshot["git_head"] = self._get_current_commit_hash()
        
        if operation == "proposal":
            snapshot["proposals"].append(data)
        elif operation == "challenge":
            snapshot["challenges"].append(data)
        elif operation == "decision":
            snapshot["decisions"].append(data)
        elif operation == "cycle_start":
            snapshot["current_cycle"] = data
        
        # Guardar
        with open(self.snapshot_file, 'w') as f:
            json.dump(snapshot, f, indent=2)
        
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
        
        Args:
            commit_message: Mensaje del commit
        
        Returns:
            True si el commit fue exitoso
        """
        if self._current_transaction is None:
            self._current_transaction = self._load_transaction_state()
        
        if self._current_transaction is None:
            logger.error("No hay transacción activa")
            return False
        
        try:
            # Actualizar fase
            self._current_transaction.phase = CommitPhase.COMMIT.value
            self._save_transaction_state(self._current_transaction)
            
            if self._is_git_repo():
                # Stage archivos modificados
                for file_path in self._current_transaction.files_modified:
                    rel_path = Path(file_path).relative_to(self.base_path)
                    if Path(file_path).exists():
                        self._run_git(["add", str(rel_path)])
                
                # También agregar mcp/
                self._run_git(["add", "mcp/"])
                
                # Verificar si hay cambios para commit
                returncode, _, _ = self._run_git(["diff", "--cached", "--quiet"], check=False)
                
                if returncode != 0:  # Hay cambios
                    # Crear commit
                    self._run_git(["commit", "-m", commit_message])
                    
                    # Obtener hash del commit
                    commit_hash = self._get_current_commit_hash()
                    self._current_transaction.git_commit_hash = commit_hash
                    
                    logger.info(f"Commit creado: {commit_hash[:8]} - {commit_message}")
                else:
                    logger.info("Sin cambios para commit")
            
            # Marcar como completado
            self._current_transaction.phase = CommitPhase.COMPLETED.value
            self._save_transaction_state(self._current_transaction)
            
            # Limpiar
            self._clear_transaction_state()
            
            logger.info(f"Transacción completada: {self._current_transaction.transaction_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error en commit: {e}")
            self._current_transaction.error_message = str(e)
            self._current_transaction.phase = CommitPhase.FAILED.value
            self._save_transaction_state(self._current_transaction)
            
            # Rollback automático
            self.rollback()
            return False
    
    def rollback(self) -> bool:
        """
        Deshace la transacción actual restaurando desde backup
        
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
            with open(proposal_file, 'w') as f:
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
            with open(challenge_file, 'w') as f:
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
                with open(self.decisions_file, 'r') as f:
                    decisions = json.load(f)
            else:
                decisions = {"decisions": []}
            
            # Agregar decisión
            decision_data['timestamp'] = datetime.now().isoformat()
            decision_data['decision_id'] = decision_id
            decisions['decisions'].append(decision_data)
            
            # Guardar
            with open(self.decisions_file, 'w') as f:
                json.dump(decisions, f, indent=2)
            
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
            with open(self.snapshot_file, 'r') as f:
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

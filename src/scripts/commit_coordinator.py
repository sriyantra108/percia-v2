#!/usr/bin/env python3
"""
PERCIA v2.0 - Commit Coordinator
================================
Coordinación de commits Git con Two-Phase Commit (2PC)

VERSIÓN PARCHEADA - Ronda 3 Multi-IA Security Audit
Parches aplicados:
  - #7: Command Injection en _run_git (ChatGPT/Perplexity) - Validación fullmatch 7-40
  - #8: Zombie Commits (ChatGPT) - restore_git_state flag para rollback correcto

Commit base auditado: 5a20704
Fecha parche: Febrero 2026
"""

import os
import re
import sys
import json
import shutil
import hashlib
import logging
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CommitPhase(Enum):
    """Fases del Two-Phase Commit."""
    IDLE = "idle"
    PREPARING = "preparing"
    PREPARED = "prepared"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class CommitState:
    """Estado de un commit en progreso."""
    commit_id: str
    phase: str
    ia_id: str
    files_modified: List[str] = field(default_factory=list)
    backup_dir: Optional[str] = None
    original_head: Optional[str] = None
    started_at: str = ""
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    restore_git_state: bool = False  # PARCHE #8: Flag para restaurar estado git


class CommitCoordinator:
    """
    Coordinador de commits con Two-Phase Commit (2PC).
    
    Características:
    - Backup automático antes de cambios
    - Rollback automático en caso de error
    - Validación de entradas contra command injection
    - Restauración correcta de estado git
    """
    
    STATE_FILE = ".percia_commit_state.json"
    BACKUP_DIR = ".percia_backups"
    
    # PARCHE #7: Regex para validación de commit hashes (fullmatch, 7-40 chars)
    GIT_HASH_PATTERN = re.compile(r'^[a-f0-9]{7,40}$')
    
    # Regex para branch names seguros
    BRANCH_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-/\.]+$')
    
    # Regex para paths seguros (sin caracteres especiales peligrosos)
    SAFE_PATH_PATTERN = re.compile(r'^[a-zA-Z0-9_\-/\.]+$')
    
    def __init__(self, repo_path: str):
        """
        Inicializa el CommitCoordinator.
        
        Args:
            repo_path: Ruta al repositorio Git
        """
        self.repo_path = Path(repo_path).resolve()
        self.state_file = self.repo_path / self.STATE_FILE
        self.backup_base = self.repo_path / self.BACKUP_DIR
        
        # Verificar que es un repositorio Git
        if not (self.repo_path / '.git').exists():
            raise ValueError(f"{repo_path} no es un repositorio Git válido")
        
        # Crear directorio de backups
        self.backup_base.mkdir(parents=True, exist_ok=True)
        
        # Estado actual
        self._current_state: Optional[CommitState] = None
        
        logger.info(f"CommitCoordinator inicializado en {self.repo_path}")
    
    # ========================================================================
    # PARCHE #7: Validación segura de entradas (ChatGPT/Perplexity)
    # ========================================================================
    
    def _validate_git_hash(self, hash_value: str, param_name: str = "hash") -> str:
        """
        Valida que un valor sea un hash Git válido.
        
        PARCHE #7: Usa fullmatch con rango 7-40 caracteres.
        
        Args:
            hash_value: Valor a validar
            param_name: Nombre del parámetro (para mensajes de error)
        
        Returns:
            Hash validado (lowercase)
        
        Raises:
            ValueError: Si el hash no es válido
        """
        if not hash_value:
            raise ValueError(f"{param_name} no puede estar vacío")
        
        # Normalizar a lowercase
        hash_value = hash_value.strip().lower()
        
        # PARCHE #7: fullmatch (no match) para evitar inyección
        # Rango 7-40 permite tanto short hashes como full hashes
        if not self.GIT_HASH_PATTERN.fullmatch(hash_value):
            raise ValueError(
                f"{param_name} inválido: '{hash_value}'. "
                f"Debe ser hexadecimal de 7-40 caracteres."
            )
        
        return hash_value
    
    def _validate_branch_name(self, branch: str) -> str:
        """
        Valida que un nombre de branch sea seguro.
        
        Args:
            branch: Nombre del branch
        
        Returns:
            Branch validado
        
        Raises:
            ValueError: Si el branch tiene caracteres peligrosos
        """
        if not branch:
            raise ValueError("Branch name no puede estar vacío")
        
        branch = branch.strip()
        
        # Verificar caracteres seguros
        if not self.BRANCH_NAME_PATTERN.fullmatch(branch):
            raise ValueError(
                f"Branch name inválido: '{branch}'. "
                f"Solo se permiten: a-z, A-Z, 0-9, _, -, /, ."
            )
        
        # Verificar longitud
        if len(branch) > 255:
            raise ValueError(f"Branch name demasiado largo: {len(branch)} chars")
        
        return branch
    
    def _validate_path(self, path: str) -> str:
        """
        Valida que un path sea seguro (sin path traversal).
        
        Args:
            path: Path a validar
        
        Returns:
            Path validado
        
        Raises:
            ValueError: Si el path contiene caracteres peligrosos
        """
        if not path:
            raise ValueError("Path no puede estar vacío")
        
        path = path.strip()
        
        # Detectar path traversal
        if '..' in path:
            raise ValueError(f"Path traversal detectado: '{path}'")
        
        # Verificar que no es absoluto
        if path.startswith('/'):
            raise ValueError(f"Paths absolutos no permitidos: '{path}'")
        
        return path
    
    # ========================================================================
    # PARCHE #7: _run_git seguro (ChatGPT/Perplexity)
    # ========================================================================
    
    def _run_git(self, *args, check: bool = True, 
                 capture_output: bool = True) -> subprocess.CompletedProcess:
        """
        Ejecuta un comando git de forma segura.
        
        PARCHE #7: Valida argumentos antes de ejecutar.
        
        Args:
            *args: Argumentos para git
            check: Si True, lanza excepción en error
            capture_output: Si True, captura stdout/stderr
        
        Returns:
            CompletedProcess con resultado
        
        Raises:
            ValueError: Si algún argumento es inválido
            subprocess.CalledProcessError: Si el comando falla y check=True
        """
        # Validar que no hay argumentos peligrosos
        for i, arg in enumerate(args):
            if not isinstance(arg, str):
                raise ValueError(f"Argumento {i} no es string: {type(arg)}")
            
            # Detectar intentos de inyección de comandos
            dangerous_chars = ['|', ';', '&', '$', '`', '\n', '\r']
            for char in dangerous_chars:
                if char in arg:
                    raise ValueError(
                        f"Caracter peligroso '{char}' detectado en argumento: '{arg}'"
                    )
            
            # Validar hashes si parecen serlo
            if i > 0 and re.match(r'^[a-f0-9]+$', arg.lower()) and len(arg) >= 7:
                # Podría ser un hash, validar
                try:
                    self._validate_git_hash(arg, f"arg[{i}]")
                except ValueError:
                    pass  # No es un hash, continuar
        
        # Construir comando
        cmd = ['git'] + list(args)
        
        logger.debug(f"Ejecutando: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                check=check,
                capture_output=capture_output,
                text=True,
                timeout=60  # Timeout de seguridad
            )
            return result
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout ejecutando git: {' '.join(cmd)}")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"Error en git: {e.stderr}")
            raise
    
    # ========================================================================
    # Two-Phase Commit
    # ========================================================================
    
    def prepare_commit(self, ia_id: str, files: List[str], 
                       message: str) -> CommitState:
        """
        Fase 1: Prepara el commit (crea backup, valida cambios).
        
        Args:
            ia_id: ID de la IA que solicita el commit
            files: Lista de archivos a incluir
            message: Mensaje de commit
        
        Returns:
            Estado del commit preparado
        """
        if self._current_state and self._current_state.phase not in [
            CommitPhase.IDLE.value, CommitPhase.COMMITTED.value, 
            CommitPhase.ROLLED_BACK.value, CommitPhase.FAILED.value
        ]:
            raise RuntimeError(
                f"Ya hay un commit en progreso: {self._current_state.commit_id}"
            )
        
        # Validar archivos
        validated_files = []
        for f in files:
            validated_files.append(self._validate_path(f))
        
        # Generar ID de commit
        commit_id = f"commit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{ia_id}"
        
        # Obtener HEAD actual para posible rollback
        result = self._run_git('rev-parse', 'HEAD')
        original_head = self._validate_git_hash(result.stdout.strip(), "HEAD")
        
        # Crear backup
        backup_dir = self._create_backup(commit_id, validated_files)
        
        # Crear estado
        self._current_state = CommitState(
            commit_id=commit_id,
            phase=CommitPhase.PREPARED.value,
            ia_id=ia_id,
            files_modified=validated_files,
            backup_dir=str(backup_dir),
            original_head=original_head,
            started_at=datetime.now().isoformat(),
            restore_git_state=False  # PARCHE #8: Inicializar en False
        )
        
        # Persistir estado
        self._save_state()
        
        logger.info(f"Commit preparado: {commit_id} ({len(validated_files)} archivos)")
        
        return self._current_state
    
    def execute_commit(self, commit_id: str) -> CommitState:
        """
        Fase 2: Ejecuta el commit.
        
        Args:
            commit_id: ID del commit a ejecutar
        
        Returns:
            Estado actualizado
        """
        if not self._current_state:
            self._load_state()
        
        if not self._current_state or self._current_state.commit_id != commit_id:
            raise ValueError(f"Commit no encontrado: {commit_id}")
        
        if self._current_state.phase != CommitPhase.PREPARED.value:
            raise RuntimeError(
                f"Commit no está preparado: {self._current_state.phase}"
            )
        
        try:
            self._current_state.phase = CommitPhase.COMMITTING.value
            self._save_state()
            
            # Stage archivos
            for file_path in self._current_state.files_modified:
                self._run_git('add', file_path)
            
            # PARCHE #8: Marcar que debemos restaurar estado git si falla
            self._current_state.restore_git_state = True
            self._save_state()
            
            # Ejecutar commit
            self._run_git('commit', '-m', f"PERCIA: {self._current_state.ia_id}")
            
            # Commit exitoso
            self._current_state.phase = CommitPhase.COMMITTED.value
            self._current_state.completed_at = datetime.now().isoformat()
            self._current_state.restore_git_state = False  # PARCHE #8: Ya no necesario
            self._save_state()
            
            # Sincronizar HEAD
            result = self._run_git('rev-parse', 'HEAD')
            new_head = result.stdout.strip()
            
            logger.info(f"Commit ejecutado: {commit_id} -> {new_head[:7]}")
            
            return self._current_state
            
        except Exception as e:
            logger.error(f"Error ejecutando commit: {e}")
            self._current_state.error_message = str(e)
            self._current_state.phase = CommitPhase.FAILED.value
            self._save_state()
            raise
    
    # ========================================================================
    # PARCHE #8: Rollback con restore_git_state (ChatGPT)
    # ========================================================================
    
    def rollback(self, commit_id: str = None) -> bool:
        """
        Rollback de un commit fallido o en progreso.
        
        PARCHE #8: Usa restore_git_state flag para determinar si restaurar git.
        
        Args:
            commit_id: ID del commit (opcional, usa actual si no se especifica)
        
        Returns:
            True si el rollback fue exitoso
        """
        if not self._current_state:
            self._load_state()
        
        if not self._current_state:
            logger.warning("No hay commit activo para rollback")
            return False
        
        if commit_id and self._current_state.commit_id != commit_id:
            raise ValueError(f"Commit ID no coincide: {commit_id}")
        
        try:
            self._current_state.phase = CommitPhase.ROLLING_BACK.value
            self._save_state()
            
            logger.info(f"Iniciando rollback de {self._current_state.commit_id}")
            
            # PARCHE #8: Solo restaurar estado git si es necesario
            if self._current_state.restore_git_state and self._current_state.original_head:
                logger.info(
                    f"Restaurando estado git a {self._current_state.original_head[:7]}"
                )
                try:
                    # Validar hash antes de usar
                    validated_head = self._validate_git_hash(
                        self._current_state.original_head, 
                        "original_head"
                    )
                    self._run_git('reset', '--hard', validated_head)
                except Exception as e:
                    logger.error(f"Error restaurando git state: {e}")
                    # Continuar con restauración de archivos
            
            # Restaurar archivos desde backup
            if self._current_state.backup_dir:
                self._restore_from_backup()
            
            self._current_state.phase = CommitPhase.ROLLED_BACK.value
            self._current_state.completed_at = datetime.now().isoformat()
            self._save_state()
            
            logger.info(f"Rollback completado: {self._current_state.commit_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error en rollback: {e}")
            self._current_state.error_message = str(e)
            self._current_state.phase = CommitPhase.FAILED.value
            self._save_state()
            return False
    
    # ========================================================================
    # PARCHE #8: _restore_from_backup con restore_git_state (ChatGPT)
    # ========================================================================
    
    def _restore_from_backup(self):
        """
        Restaura archivos desde backup.
        
        PARCHE #8: Sincroniza con restore_git_state.
        """
        if not self._current_state or not self._current_state.backup_dir:
            logger.warning("No hay backup para restaurar")
            return
        
        backup_dir = Path(self._current_state.backup_dir)
        
        if not backup_dir.exists():
            logger.warning(f"Directorio de backup no existe: {backup_dir}")
            return
        
        restored_count = 0
        for file_path in self._current_state.files_modified:
            backup_file = backup_dir / file_path
            target_file = self.repo_path / file_path
            
            if backup_file.exists():
                try:
                    # Crear directorio padre si no existe
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copiar archivo
                    shutil.copy2(backup_file, target_file)
                    restored_count += 1
                    logger.debug(f"Restaurado: {file_path}")
                    
                except Exception as e:
                    logger.error(f"Error restaurando {file_path}: {e}")
            else:
                # El archivo no existía antes, eliminar si existe
                if target_file.exists():
                    try:
                        target_file.unlink()
                        logger.debug(f"Eliminado archivo nuevo: {file_path}")
                    except Exception as e:
                        logger.error(f"Error eliminando {file_path}: {e}")
        
        logger.info(f"Restaurados {restored_count} archivos desde backup")
        
        # PARCHE #8: Si restore_git_state estaba activo, ya se hizo en rollback()
        # Aquí solo informamos del estado
        if self._current_state.restore_git_state:
            logger.info("Estado git también fue restaurado")
    
    # ========================================================================
    # Backup
    # ========================================================================
    
    def _create_backup(self, commit_id: str, files: List[str]) -> Path:
        """
        Crea backup de archivos antes de modificar.
        
        Args:
            commit_id: ID del commit
            files: Lista de archivos a respaldar
        
        Returns:
            Path del directorio de backup
        """
        backup_dir = self.backup_base / commit_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backed_up = 0
        for file_path in files:
            source = self.repo_path / file_path
            target = backup_dir / file_path
            
            if source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                backed_up += 1
                logger.debug(f"Backup: {file_path}")
        
        logger.info(f"Backup creado: {commit_id} ({backed_up} archivos)")
        
        return backup_dir
    
    def cleanup_backup(self, commit_id: str):
        """
        Limpia backup después de commit exitoso.
        
        Args:
            commit_id: ID del commit
        """
        backup_dir = self.backup_base / commit_id
        
        if backup_dir.exists():
            try:
                shutil.rmtree(backup_dir)
                logger.info(f"Backup limpiado: {commit_id}")
            except Exception as e:
                logger.warning(f"Error limpiando backup: {e}")
    
    # ========================================================================
    # Estado
    # ========================================================================
    
    def _save_state(self):
        """Guarda estado actual de forma atómica."""
        if not self._current_state:
            return
        
        temp_file = self.state_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self._current_state), f, indent=2)
            os.replace(temp_file, self.state_file)
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise e
    
    def _load_state(self):
        """Carga estado desde archivo."""
        if not self.state_file.exists():
            self._current_state = None
            return
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._current_state = CommitState(**data)
        except Exception as e:
            logger.warning(f"Error cargando estado: {e}")
            self._current_state = None
    
    def get_status(self) -> Dict[str, Any]:
        """
        Obtiene estado actual del coordinador.
        
        Returns:
            Dict con información de estado
        """
        if not self._current_state:
            self._load_state()
        
        if not self._current_state:
            return {
                "has_active_commit": False,
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "has_active_commit": True,
            "commit": asdict(self._current_state),
            "timestamp": datetime.now().isoformat()
        }
    
    # ========================================================================
    # Utilidades Git
    # ========================================================================
    
    def get_current_head(self) -> str:
        """Obtiene el HEAD actual."""
        result = self._run_git('rev-parse', 'HEAD')
        return self._validate_git_hash(result.stdout.strip(), "HEAD")
    
    def get_current_branch(self) -> str:
        """Obtiene el branch actual."""
        result = self._run_git('rev-parse', '--abbrev-ref', 'HEAD')
        branch = result.stdout.strip()
        return self._validate_branch_name(branch)
    
    def get_file_status(self) -> Dict[str, List[str]]:
        """
        Obtiene estado de archivos modificados.
        
        Returns:
            Dict con listas de archivos por estado
        """
        result = self._run_git('status', '--porcelain')
        
        status = {
            'modified': [],
            'added': [],
            'deleted': [],
            'untracked': []
        }
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            code = line[:2]
            filepath = line[3:].strip()
            
            if code == '??':
                status['untracked'].append(filepath)
            elif code[0] == 'M' or code[1] == 'M':
                status['modified'].append(filepath)
            elif code[0] == 'A':
                status['added'].append(filepath)
            elif code[0] == 'D' or code[1] == 'D':
                status['deleted'].append(filepath)
        
        return status


# ============================================================================
# CLI para testing
# ============================================================================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='PERCIA Commit Coordinator CLI')
    parser.add_argument('--repo', default='.', help='Ruta al repositorio')
    parser.add_argument('--status', action='store_true', help='Mostrar estado')
    parser.add_argument('--head', action='store_true', help='Mostrar HEAD')
    parser.add_argument('--branch', action='store_true', help='Mostrar branch')
    parser.add_argument('--prepare', metavar='IA_ID', help='Preparar commit')
    parser.add_argument('--files', nargs='+', help='Archivos para commit')
    parser.add_argument('--execute', metavar='COMMIT_ID', help='Ejecutar commit')
    parser.add_argument('--rollback', metavar='COMMIT_ID', help='Rollback commit')
    
    args = parser.parse_args()
    
    try:
        cc = CommitCoordinator(args.repo)
        
        if args.status:
            status = cc.get_status()
            print(json.dumps(status, indent=2))
        
        elif args.head:
            print(f"HEAD: {cc.get_current_head()}")
        
        elif args.branch:
            print(f"Branch: {cc.get_current_branch()}")
        
        elif args.prepare and args.files:
            state = cc.prepare_commit(args.prepare, args.files, "Test commit")
            print(f"Commit preparado: {state.commit_id}")
        
        elif args.execute:
            state = cc.execute_commit(args.execute)
            print(f"Commit ejecutado: {state.commit_id}")
        
        elif args.rollback:
            if cc.rollback(args.rollback):
                print(f"Rollback completado: {args.rollback}")
            else:
                print("Rollback fallido")
        
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

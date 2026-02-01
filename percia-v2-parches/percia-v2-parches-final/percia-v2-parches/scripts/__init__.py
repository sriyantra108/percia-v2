"""
PERCIA v2.0 - Scripts Package

Módulos principales:
- lock_manager: Gestión de locks con mutex cross-platform (portalocker)
- validator: Validación JSON Schema + reglas de negocio
- commit_coordinator: Commits atómicos con two-phase commit

Parches aplicados (GPT-4o audit):
- CRIT-LOCK-001: Temp file único + os.replace atómico
- CRIT-LOCK-002: Lock atómico con mutex cross-platform
- CRIT-CC-001/002: Fix bug en commit_transaction
- CRIT-CC-003: git_head después del commit
- HIGH-LOCK-004: _save_queue atómico
- HIGH-API-001: Endpoints con lock_context
- HIGH-API-002: save_json_file atómico

REQUISITO: pip install portalocker
"""

from .lock_manager import LockManager, LockInfo, QueueItem
from .validator import Validator, ValidationResult
from .commit_coordinator import CommitCoordinator, CommitPhase, TransactionState

__version__ = "2.0.1"
__all__ = [
    'LockManager', 'LockInfo', 'QueueItem',
    'Validator', 'ValidationResult',
    'CommitCoordinator', 'CommitPhase', 'TransactionState'
]

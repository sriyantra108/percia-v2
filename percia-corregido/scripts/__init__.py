"""
PERCIA v2.0 - Scripts Package

Protocol for Evidence-based Reasoning and Cooperative Intelligence Assessment

Módulos incluidos:
- lock_manager: Gestión de concurrencia con TTL y watchdog
- validator: Validación JSON Schema + reglas de negocio
- commit_coordinator: Commits atómicos con two-phase commit
"""

from .lock_manager import LockManager, LockInfo, QueueItem
from .validator import Validator, ValidationResult, BusinessRules
from .commit_coordinator import CommitCoordinator, TransactionState, CommitPhase

__version__ = "2.0.0"
__author__ = "PERCIA Team"

__all__ = [
    'LockManager',
    'LockInfo', 
    'QueueItem',
    'Validator',
    'ValidationResult',
    'BusinessRules',
    'CommitCoordinator',
    'TransactionState',
    'CommitPhase'
]

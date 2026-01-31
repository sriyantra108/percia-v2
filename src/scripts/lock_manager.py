#!/usr/bin/env python3
"""PERCIA v2.0 - Lock Manager - Gestor de concurrencia"""
import json, time, os, sys
from pathlib import Path
from datetime import datetime

class LockManager:
    def __init__(self, base_path="."):
        self.base_path = Path(base_path)
        self.lock_file = self.base_path / ".percia" / "lock.json"
    
    def acquire_global_lock(self, timeout=30):
        """Adquiere lock global del sistema"""
        start = time.time()
        while True:
            if self.lock_file.exists():
                if time.time() - start > timeout:
                    raise TimeoutError("Lock timeout")
                time.sleep(0.1)
                continue
            
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.lock_file, 'w') as f:
                json.dump({"timestamp": datetime.now().isoformat(), "pid": os.getpid()}, f)
            return True
    
    def release_global_lock(self):
        """Libera lock global"""
        if self.lock_file.exists():
            self.lock_file.unlink()
    
    def submit_operation(self, ia_id, operation_type):
        """Procesa envío de propuesta o challenge"""
        try:
            self.acquire_global_lock()
            print(f"✅ {operation_type} de {ia_id} procesado")
            return {"status": "SUCCESS"}
        finally:
            self.release_global_lock()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['submit', 'unlock'])
    parser.add_argument('--ia-id')
    parser.add_argument('--type')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    
    manager = LockManager()
    if args.command == 'unlock' and args.force:
        manager.release_global_lock()
        print("✅ Lock liberado")

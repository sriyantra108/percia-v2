#!/usr/bin/env python3
"""PERCIA v2.0 - Validator"""
import json, sys
from pathlib import Path
from jsonschema import validate, ValidationError

class Validator:
    def __init__(self, base_path="."):
        self.base_path = Path(base_path)
    
    def validate_file(self, file_path, schema_type):
        """Valida archivo contra schema"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            schema_file = self.base_path / ".percia" / "validators" / f"{schema_type}_schema.json"
            with open(schema_file, 'r') as f:
                schema = json.load(f)
            
            validate(instance=data, schema=schema)
            return (True, "Válido", 1.0)
        except ValidationError as e:
            return (False, str(e.message), 1.0)
        except Exception as e:
            return (False, str(e), 1.0)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--schema', required=True)
    args = parser.parse_args()
    
    validator = Validator()
    is_valid, reason, _ = validator.validate_file(args.file, args.schema)
    print(f"{'✅ VÁLIDO' if is_valid else '❌ INVÁLIDO'}: {reason}")
    sys.exit(0 if is_valid else 1)

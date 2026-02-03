#!/usr/bin/env python3
"""
PERCIA v2.0 - Validator
=======================
Validación de propuestas, esquemas y archivos

VERSIÓN PARCHEADA - Ronda 3 Multi-IA Security Audit
Parches aplicados:
  - #10: Path Traversal en validate_file (ChatGPT) - relative_to + size check

Commit base auditado: 5a20704
Fecha parche: Febrero 2026
"""

import os
import re
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Union

# Validación de JSON Schema
try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    logging.warning("jsonschema no instalado. Validación de esquemas limitada.")

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Esquemas de validación
# ============================================================================

PROPOSAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["author_ia", "content"],
    "properties": {
        "author_ia": {
            "type": "string",
            "minLength": 1,
            "maxLength": 64,
            "pattern": "^[a-zA-Z0-9_-]+$"
        },
        "content": {
            "type": "object",
            "required": ["claim"],
            "properties": {
                "claim": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 10000
                },
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "references": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "priority": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 10
                },
                "category": {
                    "type": "string",
                    "enum": ["correction", "enhancement", "security", "documentation"]
                }
            }
        }
    }
}

BOOTSTRAP_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["version", "created_at", "config"],
    "properties": {
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$"
        },
        "created_at": {
            "type": "string",
            "format": "date-time"
        },
        "config": {
            "type": "object"
        }
    }
}


@dataclass
class ValidationResult:
    """Resultado de una validación."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]


class Validator:
    """
    Validador de PERCIA.
    
    Características:
    - Validación de esquemas JSON
    - Validación de propuestas
    - Validación de archivos con protección path traversal
    - Validación de hashes y firmas
    """
    
    # Límites de archivos
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {'.json', '.md', '.txt', '.py', '.yaml', '.yml'}
    
    # PARCHE #10: Patrones peligrosos para paths
    DANGEROUS_PATH_PATTERNS = [
        r'\.\.',           # Path traversal
        r'^/',             # Rutas absolutas
        r'[<>:"|?*]',      # Caracteres inválidos en Windows
        r'\x00',           # Null bytes
    ]
    
    def __init__(self, base_path: str = None):
        """
        Inicializa el Validator.
        
        Args:
            base_path: Directorio base para validación de archivos
        """
        self.base_path = Path(base_path).resolve() if base_path else None
        
        # Compilar patrones peligrosos
        self._dangerous_patterns = [
            re.compile(p) for p in self.DANGEROUS_PATH_PATTERNS
        ]
        
        logger.info(f"Validator inicializado (base_path: {self.base_path})")
    
    # ========================================================================
    # Validación de esquemas JSON
    # ========================================================================
    
    def validate_json_schema(self, data: Dict, schema: Dict) -> ValidationResult:
        """
        Valida datos contra un esquema JSON.
        
        Args:
            data: Datos a validar
            schema: Esquema JSON
        
        Returns:
            ValidationResult con resultado
        """
        errors = []
        warnings = []
        
        if not JSONSCHEMA_AVAILABLE:
            warnings.append("jsonschema no disponible, validación limitada")
            # Validación básica sin jsonschema
            if not isinstance(data, dict):
                errors.append("Los datos deben ser un objeto JSON")
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                metadata={"validation_type": "basic"}
            )
        
        try:
            validator = Draft7Validator(schema)
            validation_errors = list(validator.iter_errors(data))
            
            for error in validation_errors:
                path = ".".join(str(p) for p in error.absolute_path)
                if path:
                    errors.append(f"{path}: {error.message}")
                else:
                    errors.append(error.message)
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                metadata={
                    "validation_type": "jsonschema",
                    "schema_version": schema.get("$schema", "unknown")
                }
            )
            
        except Exception as e:
            errors.append(f"Error de validación: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                metadata={"validation_type": "error"}
            )
    
    def validate_proposal(self, proposal: Dict) -> ValidationResult:
        """
        Valida una propuesta contra el esquema de propuestas.
        
        Args:
            proposal: Propuesta a validar
        
        Returns:
            ValidationResult
        """
        result = self.validate_json_schema(proposal, PROPOSAL_SCHEMA)
        
        # Validaciones adicionales
        if result.is_valid:
            # Verificar que author_ia no contiene caracteres peligrosos
            author = proposal.get('author_ia', '')
            if not re.match(r'^[a-zA-Z0-9_-]+$', author):
                result.errors.append(
                    f"author_ia contiene caracteres inválidos: {author}"
                )
                result.is_valid = False
            
            # Verificar tamaño del contenido
            content = proposal.get('content', {})
            claim = content.get('claim', '')
            if len(claim) > 10000:
                result.warnings.append(
                    f"Claim muy largo ({len(claim)} chars), considere resumir"
                )
        
        result.metadata['proposal_type'] = 'standard'
        return result
    
    def validate_bootstrap(self, bootstrap: Dict) -> ValidationResult:
        """
        Valida un bootstrap contra el esquema.
        
        Args:
            bootstrap: Bootstrap a validar
        
        Returns:
            ValidationResult
        """
        return self.validate_json_schema(bootstrap, BOOTSTRAP_SCHEMA)
    
    # ========================================================================
    # PARCHE #10: Validación de archivos con protección path traversal (ChatGPT)
    # ========================================================================
    
    def validate_file(self, file_path: str, 
                      allowed_base: str = None) -> ValidationResult:
        """
        Valida que un archivo sea seguro para procesar.
        
        PARCHE #10: Implementa protección contra path traversal usando
        Path.resolve() y relative_to(), más validación de tamaño.
        
        Args:
            file_path: Ruta del archivo a validar
            allowed_base: Directorio base permitido (opcional)
        
        Returns:
            ValidationResult con resultado de validación
        """
        errors = []
        warnings = []
        metadata = {}
        
        # Usar base_path si no se especifica allowed_base
        base_dir = Path(allowed_base).resolve() if allowed_base else self.base_path
        
        if not base_dir:
            errors.append("No se especificó directorio base para validación")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                metadata=metadata
            )
        
        # ================================================================
        # PARCHE #10: Validación de path traversal
        # ================================================================
        
        # 1. Verificar patrones peligrosos en el path original
        for pattern in self._dangerous_patterns:
            if pattern.search(file_path):
                errors.append(
                    f"Path contiene patrón peligroso: '{file_path}'"
                )
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    metadata={"rejected_reason": "dangerous_pattern"}
                )
        
        # 2. Resolver path y verificar que está dentro del directorio base
        try:
            # Construir path completo y resolver symlinks
            if Path(file_path).is_absolute():
                resolved_path = Path(file_path).resolve()
            else:
                resolved_path = (base_dir / file_path).resolve()
            
            # Verificar que está dentro del directorio base
            try:
                resolved_path.relative_to(base_dir)
            except ValueError:
                # El archivo está fuera del directorio base
                errors.append(
                    f"Path traversal detectado: '{file_path}' resuelve a "
                    f"'{resolved_path}' que está fuera de '{base_dir}'"
                )
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    metadata={
                        "rejected_reason": "path_traversal",
                        "resolved_path": str(resolved_path),
                        "base_dir": str(base_dir)
                    }
                )
            
            metadata['resolved_path'] = str(resolved_path)
            metadata['relative_path'] = str(resolved_path.relative_to(base_dir))
            
        except Exception as e:
            errors.append(f"Error resolviendo path: {e}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                metadata={"rejected_reason": "path_resolution_error"}
            )
        
        # 3. Verificar existencia
        if not resolved_path.exists():
            errors.append(f"Archivo no existe: {resolved_path}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                metadata=metadata
            )
        
        # 4. Verificar que es un archivo (no directorio ni symlink roto)
        if not resolved_path.is_file():
            errors.append(f"No es un archivo regular: {resolved_path}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                metadata=metadata
            )
        
        # 5. PARCHE #10: Verificar tamaño del archivo
        try:
            file_size = resolved_path.stat().st_size
            metadata['file_size'] = file_size
            
            if file_size > self.MAX_FILE_SIZE:
                errors.append(
                    f"Archivo demasiado grande: {file_size} bytes "
                    f"(máximo: {self.MAX_FILE_SIZE} bytes)"
                )
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    metadata=metadata
                )
            
            if file_size == 0:
                warnings.append("Archivo vacío")
                
        except Exception as e:
            errors.append(f"Error obteniendo tamaño: {e}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                metadata=metadata
            )
        
        # 6. Verificar extensión
        suffix = resolved_path.suffix.lower()
        metadata['extension'] = suffix
        
        if suffix not in self.ALLOWED_EXTENSIONS:
            errors.append(
                f"Extensión no permitida: '{suffix}'. "
                f"Permitidas: {', '.join(sorted(self.ALLOWED_EXTENSIONS))}"
            )
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                metadata=metadata
            )
        
        # 7. Verificaciones adicionales por tipo de archivo
        if suffix == '.json':
            try:
                with open(resolved_path, 'r', encoding='utf-8') as f:
                    json.load(f)
                metadata['json_valid'] = True
            except json.JSONDecodeError as e:
                errors.append(f"JSON inválido: {e}")
                metadata['json_valid'] = False
            except Exception as e:
                warnings.append(f"No se pudo validar JSON: {e}")
        
        # Validación exitosa
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )
    
    # ========================================================================
    # Validación de hashes
    # ========================================================================
    
    def validate_hash(self, data: Union[str, bytes], 
                      expected_hash: str,
                      algorithm: str = 'sha256') -> ValidationResult:
        """
        Valida que un hash coincida.
        
        Args:
            data: Datos a hashear
            expected_hash: Hash esperado
            algorithm: Algoritmo de hash
        
        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        metadata = {'algorithm': algorithm}
        
        try:
            # Convertir a bytes si es string
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Calcular hash
            hasher = hashlib.new(algorithm)
            hasher.update(data)
            actual_hash = hasher.hexdigest()
            
            metadata['actual_hash'] = actual_hash
            metadata['expected_hash'] = expected_hash
            
            # Comparar
            if actual_hash.lower() != expected_hash.lower():
                errors.append(
                    f"Hash no coincide. Esperado: {expected_hash[:16]}..., "
                    f"Actual: {actual_hash[:16]}..."
                )
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                metadata=metadata
            )
            
        except Exception as e:
            errors.append(f"Error calculando hash: {e}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                metadata=metadata
            )
    
    def calculate_file_hash(self, file_path: str, 
                           algorithm: str = 'sha256') -> Optional[str]:
        """
        Calcula el hash de un archivo.
        
        Args:
            file_path: Ruta del archivo
            algorithm: Algoritmo de hash
        
        Returns:
            Hash en hexadecimal o None si hay error
        """
        # Primero validar el archivo
        result = self.validate_file(file_path)
        if not result.is_valid:
            logger.error(f"Archivo inválido para hash: {result.errors}")
            return None
        
        resolved_path = Path(result.metadata.get('resolved_path', file_path))
        
        try:
            hasher = hashlib.new(algorithm)
            
            # Leer en chunks para archivos grandes
            with open(resolved_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            
            return hasher.hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculando hash de {file_path}: {e}")
            return None
    
    # ========================================================================
    # Utilidades
    # ========================================================================
    
    def sanitize_string(self, value: str, max_length: int = 1000,
                        allowed_pattern: str = r'^[\w\s\-_.,:;!?@#$%&*()+=\[\]{}|\\/<>]+$'
                        ) -> str:
        """
        Sanitiza un string removiendo caracteres peligrosos.
        
        Args:
            value: String a sanitizar
            max_length: Longitud máxima
            allowed_pattern: Patrón regex de caracteres permitidos
        
        Returns:
            String sanitizado
        """
        if not value:
            return ""
        
        # Truncar
        value = value[:max_length]
        
        # Remover caracteres de control
        value = ''.join(c for c in value if ord(c) >= 32 or c in '\n\r\t')
        
        # Validar contra patrón
        if not re.match(allowed_pattern, value):
            # Remover caracteres no permitidos
            value = re.sub(r'[^\w\s\-_.,:;!?@#$%&*()+=\[\]{}|\\/<>]', '', value)
        
        return value.strip()
    
    def is_safe_filename(self, filename: str) -> bool:
        """
        Verifica si un nombre de archivo es seguro.
        
        Args:
            filename: Nombre del archivo
        
        Returns:
            True si es seguro
        """
        if not filename:
            return False
        
        # No permitir paths, solo nombres
        if '/' in filename or '\\' in filename:
            return False
        
        # No permitir caracteres especiales
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', filename):
            return False
        
        # No permitir nombres reservados
        reserved = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT1'}
        name_upper = filename.upper().split('.')[0]
        if name_upper in reserved:
            return False
        
        # No empezar con punto (archivos ocultos)
        if filename.startswith('.'):
            return False
        
        return True


# ============================================================================
# CLI para testing
# ============================================================================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='PERCIA Validator CLI')
    parser.add_argument('--base-path', default='.', help='Directorio base')
    parser.add_argument('--validate-file', metavar='FILE', help='Validar archivo')
    parser.add_argument('--validate-json', metavar='FILE', help='Validar JSON')
    parser.add_argument('--hash', metavar='FILE', help='Calcular hash de archivo')
    
    args = parser.parse_args()
    
    v = Validator(args.base_path)
    
    if args.validate_file:
        result = v.validate_file(args.validate_file)
        print(f"Válido: {result.is_valid}")
        if result.errors:
            print(f"Errores: {result.errors}")
        if result.warnings:
            print(f"Advertencias: {result.warnings}")
        print(f"Metadata: {json.dumps(result.metadata, indent=2)}")
    
    elif args.validate_json:
        try:
            with open(args.validate_json, 'r') as f:
                data = json.load(f)
            result = v.validate_proposal(data)
            print(f"Válido: {result.is_valid}")
            if result.errors:
                print(f"Errores: {result.errors}")
        except Exception as e:
            print(f"Error: {e}")
    
    elif args.hash:
        h = v.calculate_file_hash(args.hash)
        if h:
            print(f"SHA256: {h}")
        else:
            print("Error calculando hash")
    
    else:
        parser.print_help()

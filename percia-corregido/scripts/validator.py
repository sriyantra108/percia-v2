#!/usr/bin/env python3
"""
PERCIA v2.0 - Validator - Validación Completa con Reglas de Negocio

Implementa:
- Validación JSON Schema
- Reglas de negocio adicionales (claims, justifications)
- Validación semántica de propuestas y challenges
- Logging detallado de errores

Corrige hallazgos:
- HIGH-001 (Copilot): Cobertura parcial del schema
- MED-003 (Copilot): Funciones documentadas que no aparecen
"""

import json
import sys
import re
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
import logging

try:
    from jsonschema import validate, ValidationError, Draft7Validator
except ImportError:
    print("ERROR: jsonschema no instalado. Ejecute: pip install jsonschema")
    sys.exit(1)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PERCIA.Validator')


@dataclass
class ValidationResult:
    """Resultado de validación"""
    is_valid: bool
    message: str
    confidence: float
    errors: List[str]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "message": self.message,
            "confidence": self.confidence,
            "errors": self.errors,
            "warnings": self.warnings
        }


class BusinessRules:
    """Reglas de negocio para validación semántica"""
    
    # Longitudes mínimas
    MIN_CLAIM_LENGTH = 50
    MIN_JUSTIFICATION_LENGTH = 20
    MIN_JUSTIFICATION_COUNT = 2
    MIN_RISK_DESCRIPTION_LENGTH = 10
    MIN_MITIGATION_LENGTH = 10
    
    # Patrones de ID
    IA_ID_PATTERN = r'^ia-[a-z0-9-]+$'
    PROPOSAL_ID_PATTERN = r'^prop-[a-z0-9-]+-\d{8}T\d{6}$'
    CHALLENGE_ID_PATTERN = r'^challenge-[a-z0-9-]+-\d{8}T\d{6}$'
    
    # Taxonomía de challenges válidos
    VALID_CHALLENGE_TYPES = [
        'logical',           # Errores lógicos o contradicciones
        'empirical',         # Falta de evidencia empírica
        'architectural',     # Problemas de diseño/arquitectura
        'constraint_violation',  # Violación de restricciones
        'risk'               # Riesgos no considerados
    ]
    
    # Performativos válidos
    VALID_PERFORMATIVES = ['PROPOSE', 'CHALLENGE', 'NO_CHALLENGE', 'ACCEPT', 'REJECT']


class Validator:
    """
    Validador completo para PERCIA v2.0
    
    Características:
    - Validación JSON Schema (Draft-07)
    - Reglas de negocio configurables
    - Validación semántica de contenido
    - Múltiples niveles de severidad
    - Logging detallado
    """
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.validators_dir = self.base_path / ".percia" / "validators"
        self.rules = BusinessRules()
        self._schema_cache: Dict[str, dict] = {}
        
        logger.info(f"Validator inicializado en {self.base_path}")
    
    def _load_schema(self, schema_type: str) -> Optional[dict]:
        """Carga schema desde archivo con cache"""
        if schema_type in self._schema_cache:
            return self._schema_cache[schema_type]
        
        schema_file = self.validators_dir / f"{schema_type}_schema.json"
        
        if not schema_file.exists():
            logger.error(f"Schema no encontrado: {schema_file}")
            return None
        
        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            self._schema_cache[schema_type] = schema
            return schema
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing schema {schema_file}: {e}")
            return None
    
    def validate_json_schema(self, data: dict, schema_type: str) -> ValidationResult:
        """
        Valida datos contra JSON Schema
        
        Args:
            data: Datos a validar
            schema_type: Tipo de schema (proposal, challenge, bootstrap)
        
        Returns:
            ValidationResult con resultado de validación
        """
        errors = []
        warnings = []
        
        schema = self._load_schema(schema_type)
        if schema is None:
            return ValidationResult(
                is_valid=False,
                message=f"Schema '{schema_type}' no encontrado",
                confidence=0.0,
                errors=[f"Schema '{schema_type}' no existe"],
                warnings=[]
            )
        
        try:
            # Usar Draft7Validator para mejor compatibilidad
            validator = Draft7Validator(schema)
            schema_errors = list(validator.iter_errors(data))
            
            if schema_errors:
                for error in schema_errors:
                    error_path = " -> ".join(str(p) for p in error.absolute_path)
                    error_msg = f"{error_path}: {error.message}" if error_path else error.message
                    errors.append(error_msg)
                
                return ValidationResult(
                    is_valid=False,
                    message="Validación de schema fallida",
                    confidence=0.0,
                    errors=errors,
                    warnings=warnings
                )
            
            return ValidationResult(
                is_valid=True,
                message="Schema válido",
                confidence=1.0,
                errors=[],
                warnings=[]
            )
            
        except Exception as e:
            logger.error(f"Error validando schema: {e}")
            return ValidationResult(
                is_valid=False,
                message=f"Error de validación: {str(e)}",
                confidence=0.0,
                errors=[str(e)],
                warnings=[]
            )
    
    def validate_proposal_business_rules(self, data: dict) -> ValidationResult:
        """
        Valida reglas de negocio específicas para propuestas
        
        Reglas:
        - Claim debe tener mínimo 50 caracteres
        - Debe haber mínimo 2 justifications
        - Cada justification debe tener mínimo 20 caracteres
        - Si hay riesgos, cada uno debe tener descripción y mitigación
        """
        errors = []
        warnings = []
        
        # Validar author_ia format
        author_ia = data.get('author_ia', '')
        if not re.match(self.rules.IA_ID_PATTERN, author_ia):
            errors.append(f"author_ia '{author_ia}' no cumple patrón 'ia-[a-z0-9-]+'")
        
        content = data.get('content', {})
        
        # Validar claim
        claim = content.get('claim', '')
        if len(claim) < self.rules.MIN_CLAIM_LENGTH:
            errors.append(
                f"Claim muy corto ({len(claim)} chars). "
                f"Mínimo: {self.rules.MIN_CLAIM_LENGTH} caracteres"
            )
        
        # Validar justifications
        justifications = content.get('justification', [])
        if len(justifications) < self.rules.MIN_JUSTIFICATION_COUNT:
            errors.append(
                f"Insuficientes justificaciones ({len(justifications)}). "
                f"Mínimo: {self.rules.MIN_JUSTIFICATION_COUNT}"
            )
        
        for i, justification in enumerate(justifications):
            if len(justification) < self.rules.MIN_JUSTIFICATION_LENGTH:
                warnings.append(
                    f"Justificación {i+1} muy corta ({len(justification)} chars). "
                    f"Recomendado: {self.rules.MIN_JUSTIFICATION_LENGTH}+ caracteres"
                )
        
        # Validar riesgos (si existen)
        risks = content.get('risks', [])
        for i, risk in enumerate(risks):
            risk_desc = risk.get('risk', '')
            mitigation = risk.get('mitigation', '')
            
            if len(risk_desc) < self.rules.MIN_RISK_DESCRIPTION_LENGTH:
                warnings.append(f"Riesgo {i+1}: descripción muy corta")
            
            if len(mitigation) < self.rules.MIN_MITIGATION_LENGTH:
                warnings.append(f"Riesgo {i+1}: mitigación muy corta")
        
        is_valid = len(errors) == 0
        confidence = 1.0 - (len(errors) * 0.2 + len(warnings) * 0.05)
        confidence = max(0.0, min(1.0, confidence))
        
        return ValidationResult(
            is_valid=is_valid,
            message="Reglas de negocio validadas" if is_valid else "Violaciones de reglas de negocio",
            confidence=confidence,
            errors=errors,
            warnings=warnings
        )
    
    def validate_challenge_business_rules(self, data: dict) -> ValidationResult:
        """
        Valida reglas de negocio específicas para challenges
        
        Reglas:
        - Debe referenciar una propuesta válida
        - El tipo de challenge debe estar en la taxonomía
        - Debe tener argumentos sustanciales
        """
        errors = []
        warnings = []
        
        # Validar author_ia
        author_ia = data.get('author_ia', '')
        if not re.match(self.rules.IA_ID_PATTERN, author_ia):
            errors.append(f"author_ia '{author_ia}' no cumple patrón esperado")
        
        # Validar target_proposal
        target = data.get('target_proposal', '')
        if not target:
            errors.append("target_proposal es requerido")
        
        content = data.get('content', {})
        
        # Validar tipo de challenge
        challenge_type = content.get('challenge_type', '')
        if challenge_type not in self.rules.VALID_CHALLENGE_TYPES:
            errors.append(
                f"Tipo de challenge '{challenge_type}' inválido. "
                f"Válidos: {', '.join(self.rules.VALID_CHALLENGE_TYPES)}"
            )
        
        # Validar argumentos
        arguments = content.get('arguments', [])
        if len(arguments) < 1:
            errors.append("Debe proporcionar al menos un argumento")
        
        for i, arg in enumerate(arguments):
            if len(arg) < 20:
                warnings.append(f"Argumento {i+1} muy corto ({len(arg)} chars)")
        
        # Validar evidencia (si existe)
        evidence = content.get('evidence', [])
        if not evidence and challenge_type == 'empirical':
            warnings.append("Challenge empírico sin evidencia adjunta")
        
        is_valid = len(errors) == 0
        confidence = 1.0 - (len(errors) * 0.2 + len(warnings) * 0.05)
        confidence = max(0.0, min(1.0, confidence))
        
        return ValidationResult(
            is_valid=is_valid,
            message="Challenge válido" if is_valid else "Challenge inválido",
            confidence=confidence,
            errors=errors,
            warnings=warnings
        )
    
    def validate_bootstrap_business_rules(self, data: dict) -> ValidationResult:
        """
        Valida reglas de negocio para configuración bootstrap
        
        Reglas:
        - Debe tener versión de protocolo
        - Debe definir gobernanza con al menos un governor
        - Timeouts deben ser razonables (1-168 horas)
        """
        errors = []
        warnings = []
        
        # Validar versión
        version = data.get('protocol_version', '')
        if not version.startswith('PERCIA-'):
            errors.append(f"Versión de protocolo inválida: {version}")
        
        # Validar gobernanza
        governance = data.get('governance', {})
        
        primary_governor = governance.get('primary_governor', {})
        if not primary_governor.get('human_id'):
            errors.append("primary_governor.human_id es requerido")
        
        # Validar timeouts
        timeouts = governance.get('timeouts', {})
        challenge_window = timeouts.get('challenge_window_hours', 0)
        decision_timeout = timeouts.get('decision_timeout_hours', 0)
        
        if challenge_window < 1 or challenge_window > 168:
            warnings.append(f"challenge_window_hours ({challenge_window}) fuera de rango recomendado (1-168)")
        
        if decision_timeout < 1 or decision_timeout > 168:
            warnings.append(f"decision_timeout_hours ({decision_timeout}) fuera de rango recomendado (1-168)")
        
        # Validar agentes
        agents = data.get('agents', [])
        if len(agents) < 2:
            warnings.append("Se recomiendan al menos 2 agentes IA para consenso efectivo")
        
        is_valid = len(errors) == 0
        confidence = 1.0 - (len(errors) * 0.2 + len(warnings) * 0.05)
        confidence = max(0.0, min(1.0, confidence))
        
        return ValidationResult(
            is_valid=is_valid,
            message="Bootstrap válido" if is_valid else "Bootstrap inválido",
            confidence=confidence,
            errors=errors,
            warnings=warnings
        )
    
    def validate_file(self, file_path: str, schema_type: str) -> Tuple[bool, str, float]:
        """
        Valida archivo completo (schema + reglas de negocio)
        
        Args:
            file_path: Ruta al archivo JSON
            schema_type: Tipo de schema (proposal, challenge, bootstrap)
        
        Returns:
            Tuple (is_valid, message, confidence)
        """
        # Cargar archivo
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            return (False, f"Archivo no encontrado: {file_path}", 0.0)
        except json.JSONDecodeError as e:
            return (False, f"JSON inválido: {e}", 0.0)
        
        return self.validate_data(data, schema_type)
    
    def validate_data(self, data: dict, schema_type: str) -> Tuple[bool, str, float]:
        """
        Valida datos (schema + reglas de negocio)
        
        Args:
            data: Datos a validar
            schema_type: Tipo de schema
        
        Returns:
            Tuple (is_valid, message, confidence)
        """
        all_errors = []
        all_warnings = []
        
        # 1. Validar JSON Schema
        schema_result = self.validate_json_schema(data, schema_type)
        all_errors.extend(schema_result.errors)
        all_warnings.extend(schema_result.warnings)
        
        # Si el schema falla, no continuar con reglas de negocio
        if not schema_result.is_valid:
            message = f"Schema inválido: {'; '.join(schema_result.errors)}"
            return (False, message, 0.0)
        
        # 2. Validar reglas de negocio según tipo
        business_result = None
        if schema_type == 'proposal':
            business_result = self.validate_proposal_business_rules(data)
        elif schema_type == 'challenge':
            business_result = self.validate_challenge_business_rules(data)
        elif schema_type == 'bootstrap':
            business_result = self.validate_bootstrap_business_rules(data)
        
        if business_result:
            all_errors.extend(business_result.errors)
            all_warnings.extend(business_result.warnings)
        
        # Calcular resultado final
        is_valid = len(all_errors) == 0
        confidence = 1.0 - (len(all_errors) * 0.2 + len(all_warnings) * 0.05)
        confidence = max(0.0, min(1.0, confidence))
        
        if is_valid:
            if all_warnings:
                message = f"Válido con {len(all_warnings)} advertencias"
            else:
                message = "Válido"
        else:
            message = f"Inválido: {'; '.join(all_errors[:3])}"  # Primeros 3 errores
            if len(all_errors) > 3:
                message += f" (+{len(all_errors) - 3} más)"
        
        logger.info(f"Validación {schema_type}: {message} (confidence: {confidence:.2f})")
        return (is_valid, message, confidence)
    
    def validate_all(self, data: dict, schema_type: str) -> ValidationResult:
        """
        Validación completa retornando objeto ValidationResult
        
        Args:
            data: Datos a validar
            schema_type: Tipo de schema
        
        Returns:
            ValidationResult completo
        """
        all_errors = []
        all_warnings = []
        
        # Schema validation
        schema_result = self.validate_json_schema(data, schema_type)
        all_errors.extend(schema_result.errors)
        all_warnings.extend(schema_result.warnings)
        
        if schema_result.is_valid:
            # Business rules validation
            if schema_type == 'proposal':
                br_result = self.validate_proposal_business_rules(data)
            elif schema_type == 'challenge':
                br_result = self.validate_challenge_business_rules(data)
            elif schema_type == 'bootstrap':
                br_result = self.validate_bootstrap_business_rules(data)
            else:
                br_result = None
            
            if br_result:
                all_errors.extend(br_result.errors)
                all_warnings.extend(br_result.warnings)
        
        is_valid = len(all_errors) == 0
        confidence = 1.0 - (len(all_errors) * 0.2 + len(all_warnings) * 0.05)
        confidence = max(0.0, min(1.0, confidence))
        
        return ValidationResult(
            is_valid=is_valid,
            message="Validación exitosa" if is_valid else "Validación fallida",
            confidence=confidence,
            errors=all_errors,
            warnings=all_warnings
        )


# CLI
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='PERCIA Validator CLI')
    parser.add_argument('--file', required=True, help='Archivo JSON a validar')
    parser.add_argument('--schema', required=True, 
                       choices=['proposal', 'challenge', 'bootstrap'],
                       help='Tipo de schema')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Mostrar detalles completos')
    parser.add_argument('--base-path', default='.', help='Ruta base del proyecto')
    
    args = parser.parse_args()
    
    validator = Validator(base_path=args.base_path)
    
    if args.verbose:
        # Cargar datos para validación detallada
        try:
            with open(args.file, 'r') as f:
                data = json.load(f)
            result = validator.validate_all(data, args.schema)
            
            print(f"\n{'='*60}")
            print(f"VALIDACIÓN: {args.file}")
            print(f"SCHEMA: {args.schema}")
            print(f"{'='*60}")
            print(f"RESULTADO: {'✅ VÁLIDO' if result.is_valid else '❌ INVÁLIDO'}")
            print(f"CONFIANZA: {result.confidence:.2%}")
            
            if result.errors:
                print(f"\n🔴 ERRORES ({len(result.errors)}):")
                for err in result.errors:
                    print(f"  - {err}")
            
            if result.warnings:
                print(f"\n🟡 ADVERTENCIAS ({len(result.warnings)}):")
                for warn in result.warnings:
                    print(f"  - {warn}")
            
            print(f"\n{'='*60}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    else:
        is_valid, reason, confidence = validator.validate_file(args.file, args.schema)
        print(f"{'✅ VÁLIDO' if is_valid else '❌ INVÁLIDO'}: {reason}")
        print(f"Confianza: {confidence:.2%}")
    
    sys.exit(0 if is_valid else 1)

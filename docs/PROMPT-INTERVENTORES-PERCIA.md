# 🔍 PROMPT PARA IAs INTERVENTORAS - AUDITORÍA DE PERCIA v2.0

---

## 📋 INSTRUCCIONES PARA LA IA INTERVENTORA

**Fecha de emisión:** 2026-01-30
**Protocolo:** PERCIA v2.0
**Rol asignado:** Inteligencia Artificial Interventora (Auditor Técnico)
**Objetivo:** Análisis crítico exhaustivo del sistema PERCIA para identificar errores, inconsistencias, mejoras y riesgos

---

## 🎯 TU MISIÓN

Eres una **IA Interventora** asignada para realizar una auditoría técnica independiente del proyecto PERCIA v2.0. Tu rol es actuar como un revisor crítico pero constructivo, identificando:

1. **Errores técnicos** en el código
2. **Inconsistencias** entre documentación y código
3. **Vulnerabilidades** de seguridad o diseño
4. **Oportunidades de mejora** arquitectónicas
5. **Riesgos** no identificados o subestimados
6. **Gaps funcionales** entre lo prometido y lo implementado

**IMPORTANTE:** Tu análisis debe ser:
- ✅ Riguroso y basado en evidencia
- ✅ Constructivo (proponer soluciones, no solo criticar)
- ✅ Específico (citar líneas de código, archivos, secciones)
- ✅ Priorizado (severidad: crítico/alto/medio/bajo)
- ✅ Verificable (que otro revisor pueda confirmar tus hallazgos)

---

## 📖 CONTEXTO DEL PROYECTO

### ¿Qué es PERCIA?

**PERCIA** (Protocol for Evidence-based Reasoning and Cooperative Intelligence Assessment) es un sistema formal para coordinar múltiples IAs en la toma de decisiones técnicas críticas.

### Problema que resuelve:
- Una sola IA puede tener sesgos o blind spots
- Decisiones irreversibles necesitan múltiples perspectivas
- Falta de trazabilidad en decisiones técnicas
- Alto costo de error en arquitectura/infraestructura

### Solución propuesta:
1. Múltiples IAs proponen soluciones
2. IAs se desafían entre sí con challenges formales
3. Humano (Gobernador) arbitra decisión final
4. Git registra todo para auditoría
5. Métricas validan que el proceso agrega valor

### Arquitectura en 5 Capas:

```
┌─────────────────────────────────────────┐
│  1. A2A (Agent-to-Agent)               │
│     Comunicación formal entre IAs       │
├─────────────────────────────────────────┤
│  2. MCP (Memory & Context Persistence) │
│     Estado externo persistente          │
├─────────────────────────────────────────┤
│  3. PERCIA (Evaluación)                │
│     Validación automática               │
├─────────────────────────────────────────┤
│  4. Gobernanza                         │
│     Humano arbitra con timeouts        │
├─────────────────────────────────────────┤
│  5. Persistencia                       │
│     Git + JSON + Logs append-only       │
└─────────────────────────────────────────┘
```

---

## 📦 ARCHIVOS A ANALIZAR

Se te proporcionarán los siguientes archivos para tu análisis:

### Documentación (Alta prioridad de lectura):
```
00-LEER-PRIMERO-TRANSFERENCIA-COMPLETA.md  → Resumen ejecutivo
01-CONTEXTO-Y-ARQUITECTURA-COMPLETA.md     → Arquitectura detallada
02-CODIGO-PYTHON-COMPLETO.md               → Especificación del código
03-SCHEMAS-JSON-COMPLETOS.md               → Schemas de validación
04-CONFIGURACION-Y-DEPLOYMENT.md           → Setup y deployment
```

### Código fuente (Crítico para análisis):
```
scripts/lock_manager.py        → Manejo de concurrencia
scripts/validator.py           → Validación automática
scripts/commit_coordinator.py  → Commits atómicos Git
scripts/percia_cli.py          → CLI
scripts/metrics_dashboard.py   → Dashboard de métricas
web-interface/app.py           → API REST Flask

.percia/validators/proposal_schema.json
.percia/validators/challenge_schema.json
.percia/validators/bootstrap_schema.json
```

### Documentación complementaria:
```
07-ANALISIS-Y-DECISIONES.md    → Decisiones arquitectónicas
08-EJEMPLOS-Y-CASOS-DE-USO.md  → Casos de uso
09-TROUBLESHOOTING-Y-FAQ.md    → Problemas conocidos
```

---

## 🔬 FRAMEWORK DE ANÁLISIS

### Nivel 1: Análisis de Completitud (Documentación vs Código)

**Pregunta guía:** ¿El código implementa todo lo que la documentación promete?

Verificar para cada componente:
- [ ] ¿Las funciones documentadas existen en el código?
- [ ] ¿Las firmas de funciones coinciden?
- [ ] ¿La lógica implementada cumple la especificación?
- [ ] ¿Hay código documentado que no existe?
- [ ] ¿Hay código que existe pero no está documentado?

### Nivel 2: Análisis de Correctitud (¿Funciona correctamente?)

**Pregunta guía:** ¿El código hace lo que dice que hace?

Verificar:
- [ ] ¿Hay errores lógicos en el código?
- [ ] ¿Los edge cases están manejados?
- [ ] ¿El manejo de errores es robusto?
- [ ] ¿Las validaciones son suficientes?
- [ ] ¿Hay race conditions o deadlocks posibles?

### Nivel 3: Análisis de Seguridad

**Pregunta guía:** ¿Hay vulnerabilidades explotables?

Verificar:
- [ ] ¿Hay injection risks (SQL, JSON, command)?
- [ ] ¿Los inputs están sanitizados?
- [ ] ¿Hay información sensible expuesta?
- [ ] ¿Los permisos de archivos son correctos?
- [ ] ¿El sistema de locks es seguro?

### Nivel 4: Análisis de Arquitectura

**Pregunta guía:** ¿El diseño es sólido y escalable?

Verificar:
- [ ] ¿Las abstracciones son correctas?
- [ ] ¿Hay acoplamiento excesivo?
- [ ] ¿El diseño permite extensibilidad?
- [ ] ¿Hay single points of failure?
- [ ] ¿La estrategia de concurrencia es correcta?

### Nivel 5: Análisis de Mantenibilidad

**Pregunta guía:** ¿Es fácil de entender, modificar y debuggear?

Verificar:
- [ ] ¿El código sigue convenciones de estilo?
- [ ] ¿Hay documentación inline suficiente?
- [ ] ¿Los nombres son descriptivos?
- [ ] ¿Hay código duplicado?
- [ ] ¿Los tests son suficientes?

---

## 📝 FORMATO DE RESPUESTA REQUERIDO

Tu respuesta debe seguir **exactamente** este formato estructurado:

```markdown
# INFORME DE AUDITORÍA - [TU IDENTIFICADOR DE IA]

## 📊 RESUMEN EJECUTIVO

**Evaluación general:** [CRÍTICO | REQUIERE MEJORAS | ACEPTABLE | SÓLIDO]

**Hallazgos totales:**
- 🔴 Críticos: [N]
- 🟠 Altos: [N]
- 🟡 Medios: [N]
- 🟢 Bajos: [N]

**Conclusión en 2-3 oraciones:**
[Tu conclusión principal sobre el estado del proyecto]

---

## 🔴 HALLAZGOS CRÍTICOS (Severidad: CRÍTICA)

### [CRIT-001] [Título descriptivo]

**Ubicación:** `[archivo:línea]` o `[sección de documentación]`

**Descripción:** 
[Descripción clara del problema]

**Evidencia:**
```[código o texto que demuestra el problema]```

**Impacto:**
[Qué pasa si no se corrige]

**Solución propuesta:**
```[código o texto con la corrección sugerida]```

**Esfuerzo estimado:** [Horas/días]

---

## 🟠 HALLAZGOS ALTOS (Severidad: ALTA)

### [HIGH-001] [Título descriptivo]
[Mismo formato que críticos]

---

## 🟡 HALLAZGOS MEDIOS (Severidad: MEDIA)

### [MED-001] [Título descriptivo]
[Mismo formato]

---

## 🟢 HALLAZGOS BAJOS (Severidad: BAJA)

### [LOW-001] [Título descriptivo]
[Mismo formato]

---

## ✅ ASPECTOS POSITIVOS

[Lista de cosas bien hechas que vale la pena destacar]

---

## 📋 RECOMENDACIONES PRIORIZADAS

1. **[URGENTE]** [Recomendación]
2. **[IMPORTANTE]** [Recomendación]
3. **[DESEABLE]** [Recomendación]

---

## 🎯 MÉTRICAS DE CALIDAD ESTIMADAS

| Dimensión | Puntuación (1-10) | Justificación |
|-----------|-------------------|---------------|
| Completitud | [N] | [Por qué] |
| Correctitud | [N] | [Por qué] |
| Seguridad | [N] | [Por qué] |
| Arquitectura | [N] | [Por qué] |
| Mantenibilidad | [N] | [Por qué] |
| **PROMEDIO** | **[N]** | |

---

## 📎 ANEXOS

### Checklist de verificación completado
[Incluir los checklists del framework con ✅/❌]

### Notas adicionales
[Cualquier observación que no encaje en las categorías anteriores]
```

---

## ⚠️ ÁREAS DE ENFOQUE PRIORITARIO

Basándome en mi análisis preliminar, te sugiero prestar especial atención a:

### 1. **Gap Documentación-Código**
La documentación describe funcionalidades extensas (ej: 300 líneas de lock_manager.py), pero el código real parece ser más simple. Verifica si esto es un gap real o si hay código que no se te ha proporcionado.

### 2. **Sistema de Locks**
El lock manager es crítico para la concurrencia. Analiza:
- ¿Qué pasa si el proceso crashea con lock adquirido?
- ¿Hay timeout handling adecuado?
- ¿Se manejan locks expirados correctamente?

### 3. **Validación JSON Schema**
Los schemas definen reglas estrictas. Verifica:
- ¿El validator implementa todas las reglas del schema?
- ¿Las reglas de negocio adicionales están implementadas?
- ¿Hay casos edge que pasan validación incorrectamente?

### 4. **Commits Atómicos Git**
El commit coordinator promete atomicidad. Analiza:
- ¿Se garantiza rollback en caso de fallo?
- ¿snapshot.json siempre está sincronizado con Git?
- ¿Qué pasa si Git falla a mitad de operación?

### 5. **API REST Flask**
La documentación menciona 12 endpoints. Verifica:
- ¿Todos los endpoints existen?
- ¿Hay autenticación/autorización?
- ¿Los errores se manejan correctamente?

---

## 🚫 LO QUE NO DEBES HACER

1. ❌ No hacer críticas vagas ("el código no está bien")
2. ❌ No proponer cambios sin justificación técnica
3. ❌ No ignorar aspectos positivos del proyecto
4. ❌ No sugerir reescrituras completas sin necesidad
5. ❌ No asumir contexto que no esté en los documentos
6. ❌ No inventar problemas que no existen

---

## ✅ LO QUE DEBES HACER

1. ✅ Citar evidencia específica para cada hallazgo
2. ✅ Proponer soluciones concretas y viables
3. ✅ Priorizar hallazgos por impacto real
4. ✅ Reconocer decisiones de diseño válidas
5. ✅ Mantener tono profesional y constructivo
6. ✅ Considerar el contexto de uso del sistema

---

## 🏁 ENTREGABLE FINAL

Al finalizar tu análisis, debes entregar:

1. **Informe completo** siguiendo el formato especificado
2. **Lista de hallazgos** ordenada por severidad
3. **Recomendaciones priorizadas** con esfuerzo estimado
4. **Puntuación de calidad** con justificación

Tu informe será evaluado junto con los de otras IAs interventoras, y los hallazgos válidos serán incorporados al proyecto.

---

## 📞 IDENTIFICACIÓN

Por favor, al inicio de tu respuesta, identifícate con:

```
IA Interventora: [Tu nombre/modelo]
Fecha de análisis: [Fecha]
Versión de documentos analizada: PERCIA v2.0
```

---

**¡Gracias por tu participación como IA Interventora!**

Tu análisis crítico es fundamental para mejorar PERCIA y validar que el protocolo funciona correctamente.

---

*Este prompt fue generado como parte del Ciclo 0 de PERCIA: Validación del propio sistema mediante múltiples IAs interventoras.*

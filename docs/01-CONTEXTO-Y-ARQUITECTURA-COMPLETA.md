# CONTEXTO Y ARQUITECTURA COMPLETA - PERCIA v2.0

## ORIGEN DEL PROYECTO

PERCIA nació de la necesidad de tomar decisiones técnicas críticas con múltiples perspectivas de IA, evitando sesgos individuales y garantizando trazabilidad total.

---

## PROBLEMA QUE RESUELVE

### Sin PERCIA:
- ❌ Una sola IA puede tener blind spots
- ❌ Decisiones tomadas sin registro formal
- ❌ No hay proceso de challenge estructurado
- ❌ Difícil auditar por qué se tomó una decisión
- ❌ Costo alto de error en decisiones irreversibles

### Con PERCIA:
- ✅ Múltiples IAs proponen y se desafían
- ✅ Git registra TODO (auditabilidad total)
- ✅ Taxonomía formal de challenges
- ✅ Gobernanza humana con fallbacks
- ✅ Métricas validan que agrega valor

---

## ARQUITECTURA EN 5 CAPAS (DETALLE)

### Capa 1: A2A (Agent-to-Agent)

**Función:** Comunicación formal entre IAs

**Performativos soportados:**
- `PROPOSE` - Enviar propuesta
- `CHALLENGE` - Desafiar propuesta
- `NO_CHALLENGE` - Aceptar propuesta sin objeciones

**Formato de mensaje:**
```json
{
  "performative": "PROPOSE",
  "sender": "ia-gpt-5-2",
  "timestamp": "2026-01-30T10:00:00Z",
  "content": { ... }
}
```

### Capa 2: MCP (Memory & Context Persistence)

**Función:** Estado externo que sobrevive a conversaciones

**Archivos clave:**
- `snapshot.json` - Estado actual del ciclo
- `bootstrap.json` - Configuración del sistema
- `decisions.json` - Registro de decisiones
- `metrics.json` - Métricas del sistema

**Por qué:** Las IAs no tienen memoria entre sesiones. MCP es la fuente de verdad.

### Capa 3: PERCIA (Evaluación)

**Función:** Validación automática

**Componentes:**
- JSON Schema (validación formal)
- Reglas de negocio (heurísticas)
- Confidence scoring

**Tipos de validación:**
1. Structural (schema)
2. Business rules (claim ≥50 chars)
3. Semantic (duplicates detection)

### Capa 4: Gobernanza

**Función:** Humano arbitra decisión final

**Flujo de timeout:**
```
T=0h:   Propuesta emitida
T=6h:   Cierra ventana challenges
T=6-24h: Gobernador primary decide
T=24h:  Escala a co-gobernador
T=48h:  TIMEOUT → Decisión por defecto
```

**Políticas por defecto:**
- `REJECT_AND_NEW_CYCLE` (default seguro)
- `ACCEPT_IF_NO_VALID_CHALLENGE` (optimista)
- `HALT_SYSTEM` (conservador)

### Capa 5: Persistencia

**Función:** Git como única fuente de verdad

**Garantías ACID:**
- **Atomicidad:** Commit completo o rollback
- **Consistencia:** snapshot.json = Git HEAD
- **Aislamiento:** Lock global previene conflicts
- **Durabilidad:** Git + logs append-only

---

## FLUJO DE CONCURRENCIA (CRÍTICO)

### Problema:
Múltiples IAs escribiendo simultáneamente a `mcp/` causan merge conflicts.

### Solución:
1. **Staging area** - IAs escriben a `staging/ia-{id}/`
2. **Lock global** - Solo 1 IA procesa a la vez
3. **Cola FIFO** - Procesamiento en orden de llegada
4. **Commits atómicos** - Todo o nada

### Diagrama de flujo:
```
[IA-1] → staging/ia-1/pending_proposal.json
[IA-2] → staging/ia-2/pending_challenge.json  (simultáneo)
[IA-3] → staging/ia-3/pending_proposal.json   (simultáneo)
          ↓
    [Lock Manager]
          ↓
    Adquiere lock
          ↓
    Procesa IA-1 (FIFO)
          ↓
    Git commit
          ↓
    Libera lock
          ↓
    Procesa IA-2 (FIFO)
          ↓
    Git commit
          ↓
    Libera lock
          ↓
    Procesa IA-3 (FIFO)
          ↓
    Git commit
          ↓
    ZERO conflictos ✅
```

---

## DECISIONES ARQUITECTÓNICAS

### ¿Por qué JSON y no SQL?

**Decisión:** JSON files en Git  
**Razón:**
- ✅ Auditabilidad total (Git history)
- ✅ No requiere DB server
- ✅ Fácil de inspeccionar manualmente
- ✅ Compatible con control de versiones
- ❌ No escala a 1M+ registros (pero no es el caso de uso)

### ¿Por qué locks en lugar de Git branches?

**Decisión:** Lock global + main branch  
**Razón:**
- ✅ Más simple que merge automático
- ✅ Previene conflicts 100%
- ✅ Orden de procesamiento garantizado (FIFO)
- ❌ Throughput limitado (pero decisiones no son high-frequency)

### ¿Por qué Python y no Go/Rust?

**Decisión:** Python 3.9+  
**Razón:**
- ✅ Ecosistema ML/AI rico
- ✅ Fácil integración con IAs
- ✅ jsonschema, gitpython maduros
- ❌ Performance (pero no es bottleneck)

### ¿Por qué Flask y no FastAPI?

**Decisión:** Flask 3.0  
**Razón:**
- ✅ Más simple para este caso
- ✅ No requiere async (operaciones son sync)
- ✅ Menos boilerplate
- ❌ Menos features (pero no se necesitan)

---

## MÉTRICAS DE DISEÑO

### Error Detection Rate

**Definición:** % de errores críticos detectados pre-implementación

**Cálculo:**
```
Error Detection Rate = 
  Errores detectados en PERCIA / Total errores en implementación real
```

**Objetivo:** ≥60%

**Ejemplo:**
- PERCIA detecta 3 errores críticos
- Implementación real tuvo 4 errores totales
- Rate = 3/4 = 75% ✅

### Success Rate

**Definición:** % de decisiones que NO requieren reversión

**Cálculo:**
```
Success Rate = 
  Decisiones implementadas exitosamente / Total decisiones
```

**Objetivo:** ≥85%

**Ejemplo:**
- 10 decisiones tomadas con PERCIA
- 9 implementadas sin reversión
- 1 requirió ajuste menor
- Rate = 9/10 = 90% ✅

### Challenge Validity Rate

**Definición:** % de challenges técnicamente válidos

**Cálculo:**
```
Challenge Validity Rate = 
  Challenges válidos / Total challenges emitidos
```

**Objetivo:** ≥70%

**Ejemplo:**
- 10 challenges emitidos
- 7 fueron válidos
- 3 fueron rechazados (vagas, duplicados)
- Rate = 7/10 = 70% ✅

---

## CASOS DE USO VÁLIDOS E INVÁLIDOS

### ✅ USAR PERCIA:

1. **Elegir stack tecnológico para 10M usuarios**
   - Irreversible: Migrar es costoso
   - Impacto crítico: Performance/costo
   - Complejidad alta: Trade-offs no obvios

2. **Diseño de arquitectura de microservicios**
   - Irreversible: Refactor es caro
   - Impacto crítico: Escalabilidad
   - Complejidad alta: Muchos componentes

3. **Migración de monolito a microservicios**
   - Irreversible: No hay vuelta atrás
   - Impacto crítico: Downtime riesgo
   - Complejidad alta: Estrategia de migración

### ❌ NO USAR PERCIA:

1. **Nombrar una variable**
   - Reversible: Rename es trivial
   - Impacto bajo: Solo legibilidad
   - Complejidad baja: Convenciones claras

2. **Elegir librería de logging**
   - Reversible: Swap es fácil
   - Impacto bajo: No crítico
   - Complejidad baja: Muchas opciones equivalentes

3. **Color de botón en UI**
   - Reversible: CSS change
   - Impacto bajo: Solo estética
   - Complejidad baja: Preferencia personal

---

## LIMITACIONES CONOCIDAS

### 1. Throughput

**Limitación:** Lock global limita a ~1 operación/segundo  
**Impacto:** No apto para high-frequency decisions  
**Mitigación:** No es el caso de uso objetivo

### 2. Escalabilidad de almacenamiento

**Limitación:** JSON files no escalan a millones de registros  
**Impacto:** Después de ~10k decisiones, performance degrada  
**Mitigación:** Archivar decisiones antiguas a DB

### 3. No soporta decisiones en tiempo real

**Limitación:** Ciclos requieren ≥2 horas  
**Impacto:** No apto para decisiones urgentes  
**Mitigación:** Usar para decisiones con 2-6h disponibles

---

## ROADMAP FUTURO (v3.0)

### Features pendientes:

1. **Autenticación:** flask-jwt-extended
2. **Notificaciones:** Slack/email webhooks
3. **Métricas avanzadas:** Prometheus + Grafana
4. **Multi-tenancy:** Soporte para múltiples equipos
5. **API pública:** Para integraciones externas
6. **ML scoring:** Predicción de calidad de propuestas

---

Este documento proporciona el contexto arquitectónico completo del proyecto.

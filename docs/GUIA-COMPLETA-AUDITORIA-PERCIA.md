# 📘 GUÍA COMPLETA: AUDITORÍA DE PERCIA CON IAs INTERVENTORAS

---

## 📋 ÍNDICE

1. [Visión General del Proceso](#1-visión-general-del-proceso)
2. [Fase 1: Preparación del Repositorio GitHub](#2-fase-1-preparación-del-repositorio-github)
3. [Fase 2: Preparación de Materiales para IAs](#3-fase-2-preparación-de-materiales-para-ias)
4. [Fase 3: Envío a IAs Interventoras](#4-fase-3-envío-a-ias-interventoras)
5. [Fase 4: Recolección de Respuestas](#5-fase-4-recolección-de-respuestas)
6. [Fase 5: Evaluación y Consolidación](#6-fase-5-evaluación-y-consolidación)
7. [Fase 6: Implementación de Correcciones](#7-fase-6-implementación-de-correcciones)
8. [Fase 7: Puesta en Uso del Protocolo](#8-fase-7-puesta-en-uso-del-protocolo)
9. [Anexos](#9-anexos)

---

## 1. VISIÓN GENERAL DEL PROCESO

### Diagrama de Flujo

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        CICLO 0: META-AUDITORÍA                           │
│                   (Validar PERCIA usando PERCIA)                         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FASE 1: PREPARACIÓN                                                     │
│  ├── Crear repositorio GitHub                                            │
│  ├── Subir código y documentación                                        │
│  └── Organizar archivos para distribución                                │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FASE 2: ENVÍO A IAs INTERVENTORAS                                       │
│  ├── Claude (Anthropic) - Opus/Sonnet                                    │
│  ├── GPT-4/GPT-4o (OpenAI)                                               │
│  ├── Gemini Pro/Ultra (Google)                                           │
│  ├── Llama 3 (Meta)                                                      │
│  └── [Otras IAs disponibles]                                             │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FASE 3: RECOLECCIÓN Y CONSOLIDACIÓN                                     │
│  ├── Recibir informes de auditoría                                       │
│  ├── Consolidar hallazgos                                                │
│  ├── Priorizar por consenso                                              │
│  └── Identificar conflictos/coincidencias                                │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FASE 4: EVALUACIÓN (TÚ ARBITRAS)                                        │
│  ├── Claude evalúa hallazgos de otras IAs                                │
│  ├── Clasifica: ACEPTAR / RECHAZAR / MODIFICAR                           │
│  ├── Documenta rationale para cada decisión                              │
│  └── Genera plan de correcciones                                         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FASE 5: IMPLEMENTACIÓN                                                  │
│  ├── Aplicar correcciones al código                                      │
│  ├── Actualizar documentación                                            │
│  ├── Commit atómicos con referencias a hallazgos                         │
│  └── Release v2.1 corregida                                              │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FASE 6: PUESTA EN USO DEL PROTOCOLO                                     │
│  ├── Seleccionar decisión técnica real                                   │
│  ├── Asignar roles a IAs (proponentes/challengeadores)                   │
│  ├── Ejecutar ciclo completo de PERCIA                                   │
│  └── Medir métricas y validar KPIs                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

### Tiempo Estimado Total: 8-16 horas

| Fase | Tiempo Estimado | Responsable |
|------|-----------------|-------------|
| 1. Preparación GitHub | 1-2 horas | John |
| 2. Preparación materiales | 30 min | John |
| 3. Envío a IAs | 2-4 horas | John |
| 4. Recolección | 1-2 horas | John |
| 5. Evaluación | 2-4 horas | Claude + John |
| 6. Implementación | 2-4 horas | Claude |
| 7. Puesta en uso | Variable | Todos |

---

## 2. FASE 1: PREPARACIÓN DEL REPOSITORIO GITHUB

### Paso 1.1: Crear cuenta GitHub (si no tienes)

1. Ve a https://github.com
2. Click en "Sign up"
3. Completa el registro con tu email
4. Verifica tu email
5. Elige el plan gratuito

### Paso 1.2: Crear repositorio nuevo

1. **Login** en GitHub
2. Click en el botón **"+"** (esquina superior derecha)
3. Selecciona **"New repository"**
4. Completa los campos:

```
Repository name: percia-v2
Description: Protocol for Evidence-based Reasoning and Cooperative Intelligence Assessment
Public/Private: Public (recomendado para transparencia)
✅ Add a README file
✅ Add .gitignore → Python
License: MIT License (recomendado)
```

5. Click **"Create repository"**

### Paso 1.3: Clonar repositorio localmente

Abre tu terminal y ejecuta:

```bash
# Opción 1: Con HTTPS (más fácil)
git clone https://github.com/TU_USUARIO/percia-v2.git

# Opción 2: Con SSH (si tienes configurado)
git clone git@github.com:TU_USUARIO/percia-v2.git

# Entrar al directorio
cd percia-v2
```

### Paso 1.4: Estructura de carpetas a crear

```bash
# Crear estructura de directorios
mkdir -p docs/{arquitectura,decisiones,auditorias}
mkdir -p src/scripts
mkdir -p src/web-interface
mkdir -p src/.percia/validators
mkdir -p templates
mkdir -p examples
mkdir -p auditorias/{ciclo-0-meta,ciclo-1-real}
```

### Paso 1.5: Copiar archivos del proyecto

```bash
# Desde la carpeta donde descomprimiste PERCIA
# Asumiendo que estás en percia-v2/

# Copiar documentación
cp /ruta/a/percia/*.md docs/

# Copiar código
cp /ruta/a/percia/proyecto/scripts/*.py src/scripts/
cp /ruta/a/percia/proyecto/web-interface/*.py src/web-interface/
cp /ruta/a/percia/proyecto/.percia/validators/*.json src/.percia/validators/

# Copiar requirements
cp /ruta/a/percia/proyecto/requirements.txt .

# Copiar manual HTML
cp -r /ruta/a/percia/proyecto/manual/ src/manual/
```

### Paso 1.6: Crear archivo README.md principal

Crea el archivo `README.md` en la raíz:

```markdown
# PERCIA v2.0

**Protocol for Evidence-based Reasoning and Cooperative Intelligence Assessment**

## 🎯 ¿Qué es PERCIA?

Sistema formal para coordinar múltiples IAs en la toma de decisiones técnicas críticas.

## 📁 Estructura del Repositorio

```
percia-v2/
├── docs/                    # Documentación completa
│   ├── arquitectura/        # Diseño y arquitectura
│   ├── decisiones/          # ADRs (Architecture Decision Records)
│   └── auditorias/          # Informes de auditoría
├── src/                     # Código fuente
│   ├── scripts/             # Core Python
│   ├── web-interface/       # API Flask
│   └── .percia/             # Schemas y configuración
├── auditorias/              # Auditorías por ciclo
│   ├── ciclo-0-meta/        # Meta-auditoría del sistema
│   └── ciclo-1-real/        # Primera auditoría real
├── examples/                # Ejemplos de uso
└── templates/               # Plantillas
```

## 🚀 Quick Start

```bash
# Clonar
git clone https://github.com/TU_USUARIO/percia-v2.git
cd percia-v2

# Instalar dependencias
pip install -r requirements.txt

# Verificar instalación
python src/scripts/verify_dependencies.py
```

## 📖 Documentación

- [Arquitectura](docs/01-CONTEXTO-Y-ARQUITECTURA-COMPLETA.md)
- [Código](docs/02-CODIGO-PYTHON-COMPLETO.md)
- [Deployment](docs/04-CONFIGURACION-Y-DEPLOYMENT.md)

## 📋 Estado del Proyecto

- **Versión:** 2.0.0
- **Estado:** En auditoría (Ciclo 0)
- **Licencia:** MIT

## 🤝 Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md)
```

### Paso 1.7: Primer commit y push

```bash
# Agregar todos los archivos
git add .

# Crear commit inicial
git commit -m "feat: Initial commit - PERCIA v2.0 complete project

- Added complete documentation (00-09 documents)
- Added Python source code (scripts, web-interface)
- Added JSON schemas for validation
- Added HTML manual
- Ready for Cycle 0 meta-audit"

# Subir a GitHub
git push origin main
```

### Paso 1.8: Crear carpeta para auditorías

```bash
# Crear carpeta para Ciclo 0
mkdir -p auditorias/ciclo-0-meta/informes-ia

# Crear README para la auditoría
cat > auditorias/ciclo-0-meta/README.md << 'EOF'
# Ciclo 0: Meta-Auditoría de PERCIA

## Objetivo
Validar el sistema PERCIA usando múltiples IAs interventoras.

## IAs Participantes
- [ ] Claude (Anthropic)
- [ ] GPT-4 (OpenAI)
- [ ] Gemini (Google)
- [ ] Llama 3 (Meta)
- [ ] [Otras]

## Estado
- [ ] Envío de prompt a IAs
- [ ] Recolección de informes
- [ ] Consolidación de hallazgos
- [ ] Implementación de correcciones
- [ ] Validación final

## Informes
Ver carpeta `informes-ia/`
EOF

git add .
git commit -m "chore: Setup Cycle 0 meta-audit structure"
git push origin main
```

---

## 3. FASE 2: PREPARACIÓN DE MATERIALES PARA IAs

### Paso 2.1: Crear paquete de distribución

Necesitas preparar un ZIP con todo lo necesario para cada IA:

```bash
# Crear carpeta temporal
mkdir -p /tmp/percia-audit-package

# Copiar prompt de interventores
cp PROMPT-INTERVENTORES-PERCIA.md /tmp/percia-audit-package/

# Copiar documentación esencial
cp docs/00-LEER-PRIMERO-TRANSFERENCIA-COMPLETA.md /tmp/percia-audit-package/
cp docs/01-CONTEXTO-Y-ARQUITECTURA-COMPLETA.md /tmp/percia-audit-package/
cp docs/02-CODIGO-PYTHON-COMPLETO.md /tmp/percia-audit-package/
cp docs/03-SCHEMAS-JSON-COMPLETOS.md /tmp/percia-audit-package/
cp docs/07-ANALISIS-Y-DECISIONES.md /tmp/percia-audit-package/

# Copiar código fuente
cp -r src/scripts/ /tmp/percia-audit-package/
cp -r src/.percia/ /tmp/percia-audit-package/
cp src/web-interface/app.py /tmp/percia-audit-package/

# Crear ZIP
cd /tmp
zip -r percia-audit-package.zip percia-audit-package/
```

### Paso 2.2: Lista de archivos a enviar

| Archivo | Propósito | Prioridad |
|---------|-----------|-----------|
| PROMPT-INTERVENTORES-PERCIA.md | Instrucciones para la IA | **CRÍTICO** |
| 00-LEER-PRIMERO.md | Contexto general | Alta |
| 01-CONTEXTO-Y-ARQUITECTURA.md | Arquitectura | Alta |
| 02-CODIGO-PYTHON-COMPLETO.md | Especificación | Alta |
| scripts/*.py | Código real | **CRÍTICO** |
| .percia/validators/*.json | Schemas | Alta |
| app.py | API REST | Media |

---

## 4. FASE 3: ENVÍO A IAs INTERVENTORAS

### Paso 3.1: Lista de IAs a contactar

| IA | Plataforma | URL | Modelo Recomendado |
|----|------------|-----|-------------------|
| Claude | Anthropic | claude.ai | Opus 4.5 / Sonnet 4.5 |
| GPT-4 | OpenAI | chat.openai.com | GPT-4o |
| Gemini | Google | gemini.google.com | Gemini 1.5 Pro |
| Llama | Meta | llama.meta.com | Llama 3.1 70B |
| Mistral | Mistral AI | chat.mistral.ai | Mistral Large |
| Perplexity | Perplexity | perplexity.ai | Default |

### Paso 3.2: Mensaje de introducción (copiar para cada IA)

```
Hola! Te voy a asignar un rol de IA Interventora para realizar una auditoría técnica del proyecto PERCIA v2.0.

PERCIA es un sistema formal para coordinar múltiples IAs en la toma de decisiones técnicas críticas.

Te voy a compartir:
1. Un prompt detallado con instrucciones de auditoría
2. La documentación completa del proyecto
3. El código fuente para analizar

Por favor lee primero el archivo "PROMPT-INTERVENTORES-PERCIA.md" que contiene todas las instrucciones y el formato de respuesta esperado.

¿Estás listo/a para comenzar la auditoría?
```

### Paso 3.3: Proceso de envío para cada IA

**Para Claude (Anthropic):**
1. Abrir nueva conversación en claude.ai
2. Escribir mensaje de introducción
3. Adjuntar archivos (arrastrar ZIP o archivos individuales)
4. Esperar respuesta de confirmación
5. Si necesario, enviar archivos adicionales

**Para GPT-4 (OpenAI):**
1. Abrir nueva conversación en chat.openai.com
2. Escribir mensaje de introducción
3. Usar el botón de adjuntar para subir archivos
4. Nota: GPT-4 tiene límites de archivos, puede necesitar dividir

**Para Gemini (Google):**
1. Abrir Gemini en gemini.google.com
2. Escribir mensaje de introducción
3. Adjuntar archivos
4. Nota: Verificar límites de contexto

**Para otras IAs:**
- Seguir proceso similar
- Adaptar según limitaciones de cada plataforma

### Paso 3.4: Tracking de envíos

Crear archivo `auditorias/ciclo-0-meta/tracking.md`:

```markdown
# Tracking de Envíos - Ciclo 0

| IA | Fecha Envío | Archivos Enviados | Respuesta Recibida | Informe Completo |
|----|-------------|-------------------|--------------------|--------------------|
| Claude | 2026-01-30 | ✅ Todos | ⏳ Pendiente | ❌ |
| GPT-4 | | | | |
| Gemini | | | | |
| Llama | | | | |
| Mistral | | | | |
```

---

## 5. FASE 4: RECOLECCIÓN DE RESPUESTAS

### Paso 4.1: Guardar cada informe

Por cada IA que responda:

```bash
# Crear archivo con el informe
# Usar formato: informe-[ia]-[fecha].md

# Ejemplo:
cat > auditorias/ciclo-0-meta/informes-ia/informe-gpt4-20260130.md << 'EOF'
# Informe de Auditoría - GPT-4

[Pegar aquí el contenido completo del informe]
EOF
```

### Paso 4.2: Formato de nombre de archivos

```
informe-[modelo]-[fecha].md

Ejemplos:
- informe-claude-opus-20260130.md
- informe-gpt4o-20260130.md
- informe-gemini-pro-20260130.md
- informe-llama3-70b-20260130.md
```

### Paso 4.3: Commit cada informe

```bash
git add auditorias/ciclo-0-meta/informes-ia/
git commit -m "docs: Add audit report from [IA_NAME]

- Hallazgos críticos: N
- Hallazgos altos: N
- Hallazgos medios: N
- Hallazgos bajos: N"
git push origin main
```

---

## 6. FASE 5: EVALUACIÓN Y CONSOLIDACIÓN

### Paso 5.1: Crear matriz de hallazgos

Una vez tengas todos los informes, créame esta matriz para consolidar:

```markdown
# Matriz de Hallazgos Consolidados

| ID | Título | Reportado Por | Severidad | Consenso | Decisión |
|----|--------|---------------|-----------|----------|----------|
| H-001 | [Título] | Claude, GPT-4 | CRÍTICO | 2/4 IAs | PENDIENTE |
| H-002 | [Título] | Gemini | ALTO | 1/4 IAs | PENDIENTE |
```

### Paso 5.2: Compartir informes conmigo

Cuando tengas los informes de las IAs, compártelos conmigo con este mensaje:

```
Claude, aquí están los informes de auditoría de las IAs interventoras:

1. [Pegar o adjuntar informe de IA 1]
2. [Pegar o adjuntar informe de IA 2]
...

Por favor:
1. Evalúa cada hallazgo
2. Determina si es válido/inválido
3. Prioriza las correcciones
4. Genera el código corregido
```

### Paso 5.3: Mi proceso de evaluación

Yo (Claude) realizaré:

1. **Validación de hallazgos:**
   - ¿El hallazgo es técnicamente correcto?
   - ¿La evidencia soporta la conclusión?
   - ¿El impacto está bien evaluado?

2. **Clasificación:**
   - ✅ ACEPTAR: Hallazgo válido, implementar corrección
   - ❌ RECHAZAR: Hallazgo inválido o fuera de alcance
   - 🔄 MODIFICAR: Hallazgo parcialmente válido, ajustar

3. **Priorización:**
   - Severidad + Consenso entre IAs + Esfuerzo

4. **Plan de correcciones:**
   - Código corregido
   - Tests añadidos
   - Documentación actualizada

---

## 7. FASE 6: IMPLEMENTACIÓN DE CORRECCIONES

### Paso 6.1: Crear branch de correcciones

```bash
git checkout -b fix/cycle-0-audit-findings
```

### Paso 6.2: Implementar correcciones

Por cada hallazgo aceptado, yo generaré:

1. **Código corregido** con comentarios explicativos
2. **Tests** que verifiquen la corrección
3. **Documentación** actualizada

### Paso 6.3: Commits semánticos

```bash
# Formato de commits
git commit -m "fix(component): [H-XXX] Brief description

Resolves audit finding H-XXX: [Title]
Reported by: [IA names]
Severity: [CRITICAL/HIGH/MEDIUM/LOW]

Changes:
- [Change 1]
- [Change 2]"
```

### Paso 6.4: Pull Request

```bash
# Push branch
git push origin fix/cycle-0-audit-findings

# Crear PR en GitHub
# Título: "fix: Cycle 0 Audit Findings Resolution"
# Descripción: Lista de todos los hallazgos resueltos
```

### Paso 6.5: Merge y release

```bash
# Después de revisión
git checkout main
git merge fix/cycle-0-audit-findings
git tag -a v2.1.0 -m "Release v2.1.0 - Post Cycle 0 audit fixes"
git push origin main --tags
```

---

## 8. FASE 7: PUESTA EN USO DEL PROTOCOLO

### Paso 7.1: Seleccionar decisión técnica real

Ejemplos de decisiones adecuadas para PERCIA:

| Decisión | Complejidad | Tiempo | Adecuada |
|----------|-------------|--------|----------|
| Elegir base de datos para proyecto | Alta | 4-6h | ✅ Sí |
| Arquitectura de microservicios | Alta | 4-8h | ✅ Sí |
| Nombrar una variable | Baja | 5min | ❌ No |
| Estrategia de caching | Media | 2-4h | ✅ Sí |

### Paso 7.2: Asignar roles

```
GOBERNADOR: John (tú)
  - Arbitras la decisión final
  - Defines timeouts y políticas

IA PROPONENTE 1: Claude
  - Genera propuesta inicial

IA CHALLENGER 1: GPT-4
  - Desafía la propuesta de Claude

IA CHALLENGER 2: Gemini
  - Segundo challenger independiente
```

### Paso 7.3: Ejecutar ciclo

1. **Crear bootstrap.json** con el objetivo
2. **Abrir ciclo** vía CLI o API
3. **IA proponente** genera proposal
4. **IAs challengers** emiten challenges
5. **Gobernador** (tú) decide
6. **Registrar** decisión en Git
7. **Medir** métricas

### Paso 7.4: Template de bootstrap para ciclo real

```json
{
  "protocol_version": "PERCIA-2.0",
  "system_id": "decision-[nombre]-001",
  "created_at": "[fecha ISO]",
  "governance": {
    "primary_governor": {
      "human_id": "john@example.com",
      "authority": ["cycle_open", "cycle_close", "final_decision"]
    },
    "timeouts": {
      "challenge_window_hours": 6,
      "decision_timeout_hours": 24,
      "default_action_on_timeout": "REJECT_AND_NEW_CYCLE"
    }
  },
  "agents": [
    {"ia_id": "ia-claude-opus", "provider": "anthropic", "model": "opus-4.5", "role": "proposer"},
    {"ia_id": "ia-gpt4o", "provider": "openai", "model": "gpt-4o", "role": "challenger"},
    {"ia_id": "ia-gemini", "provider": "google", "model": "gemini-1.5-pro", "role": "challenger"}
  ],
  "objective": {
    "description": "[Descripción de la decisión]",
    "acceptance_criteria": [
      "[Criterio 1]",
      "[Criterio 2]",
      "[Criterio 3]"
    ]
  }
}
```

---

## 9. ANEXOS

### Anexo A: Checklist de Progreso

```markdown
## Checklist General

### Fase 1: Preparación GitHub
- [ ] Cuenta GitHub creada
- [ ] Repositorio creado
- [ ] Estructura de carpetas creada
- [ ] Código subido
- [ ] Documentación subida
- [ ] README actualizado

### Fase 2: Preparación Materiales
- [ ] ZIP de distribución creado
- [ ] Prompt de interventores incluido
- [ ] Documentación esencial incluida
- [ ] Código fuente incluido

### Fase 3: Envío a IAs
- [ ] Claude contactado
- [ ] GPT-4 contactado
- [ ] Gemini contactado
- [ ] Otras IAs contactadas
- [ ] Tracking actualizado

### Fase 4: Recolección
- [ ] Informe Claude recibido
- [ ] Informe GPT-4 recibido
- [ ] Informe Gemini recibido
- [ ] Otros informes recibidos
- [ ] Todos guardados en repositorio

### Fase 5: Evaluación
- [ ] Informes compartidos con Claude
- [ ] Matriz de hallazgos creada
- [ ] Hallazgos validados
- [ ] Decisiones documentadas
- [ ] Plan de correcciones generado

### Fase 6: Implementación
- [ ] Branch creado
- [ ] Correcciones implementadas
- [ ] Tests añadidos
- [ ] Documentación actualizada
- [ ] PR creado y mergeado
- [ ] Release v2.1 creado

### Fase 7: Uso del Protocolo
- [ ] Decisión real seleccionada
- [ ] Bootstrap creado
- [ ] Ciclo ejecutado
- [ ] Métricas medidas
- [ ] KPIs validados
```

### Anexo B: Comandos Git Rápidos

```bash
# Estado del repositorio
git status

# Ver cambios
git diff

# Agregar todos los cambios
git add .

# Commit con mensaje
git commit -m "mensaje"

# Push a GitHub
git push origin main

# Crear branch
git checkout -b nombre-branch

# Cambiar de branch
git checkout main

# Merge branch
git merge nombre-branch

# Ver historial
git log --oneline

# Crear tag
git tag -a v2.1.0 -m "mensaje"

# Push tags
git push origin --tags
```

### Anexo C: Plantilla de Mensaje para IAs

```
=== MENSAJE DE INICIO ===

Hola! Te asigno el rol de IA Interventora para auditar PERCIA v2.0.

Adjunto encontrarás:
1. PROMPT-INTERVENTORES-PERCIA.md - Instrucciones detalladas
2. Documentación del proyecto (archivos 00-09)
3. Código fuente (carpeta scripts/)

Por favor:
1. Lee primero el PROMPT-INTERVENTORES-PERCIA.md
2. Analiza el proyecto completo
3. Genera tu informe siguiendo el formato especificado

¿Comenzamos?

=== FIN MENSAJE ===
```

### Anexo D: Estructura Final del Repositorio

```
percia-v2/
├── .github/
│   └── workflows/
│       └── verify.yml           # CI/CD
├── docs/
│   ├── 00-LEER-PRIMERO.md
│   ├── 01-CONTEXTO-Y-ARQUITECTURA.md
│   ├── 02-CODIGO-PYTHON-COMPLETO.md
│   ├── 03-SCHEMAS-JSON-COMPLETOS.md
│   ├── 04-CONFIGURACION-Y-DEPLOYMENT.md
│   ├── 05-INTERFAZ-WEB-COMPLETA.md
│   ├── 06-CONVERSACION-COMPLETA.txt
│   ├── 07-ANALISIS-Y-DECISIONES.md
│   ├── 08-EJEMPLOS-Y-CASOS-DE-USO.md
│   └── 09-TROUBLESHOOTING-Y-FAQ.md
├── src/
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── lock_manager.py
│   │   ├── validator.py
│   │   ├── commit_coordinator.py
│   │   ├── percia_cli.py
│   │   └── metrics_dashboard.py
│   ├── web-interface/
│   │   └── app.py
│   ├── .percia/
│   │   └── validators/
│   │       ├── proposal_schema.json
│   │       ├── challenge_schema.json
│   │       └── bootstrap_schema.json
│   └── manual/
│       └── index.html
├── auditorias/
│   ├── ciclo-0-meta/
│   │   ├── README.md
│   │   ├── tracking.md
│   │   ├── informes-ia/
│   │   │   ├── informe-claude-opus.md
│   │   │   ├── informe-gpt4o.md
│   │   │   └── informe-gemini.md
│   │   └── consolidacion/
│   │       ├── matriz-hallazgos.md
│   │       └── decisiones-gobernador.md
│   └── ciclo-1-real/
│       └── [similar estructura]
├── templates/
│   └── bootstrap_template.json
├── examples/
│   └── queue_example.json
├── requirements.txt
├── README.md
├── CONTRIBUTING.md
├── LICENSE
└── .gitignore
```

---

## 🎯 PRÓXIMO PASO INMEDIATO

**John, tu siguiente acción es:**

1. ✅ Crear el repositorio en GitHub siguiendo la Fase 1
2. ✅ Subir los archivos del proyecto
3. ✅ Contactar a las IAs interventoras con el prompt y materiales
4. ✅ Recopilar sus informes
5. ✅ Compartir los informes conmigo para evaluación

**¿Comenzamos con la Fase 1 (crear el repositorio GitHub)?**

---

*Documento generado: 2026-01-30*
*Versión: 1.0*
*Para: PERCIA v2.0 Meta-Auditoría*

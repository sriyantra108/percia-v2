# PERCIA v2.0 - Parches GPT-4o + Gemini + Claude + Mistral + Perplexity

## 📋 Hallazgos Corregidos

### Parches GPT-4o:
| ID | Severidad | Descripción | Archivo |
|----|-----------|-------------|---------|
| CRIT-LOCK-001 | 🔴 Crítico | Temp file fijo causa race condition | lock_manager.py |
| CRIT-LOCK-002 | 🔴 Crítico | Lock no era atómico (TOCTOU) | lock_manager.py |
| CRIT-CC-001 | 🔴 Crítico | Bug de orden en commit_transaction | commit_coordinator.py |
| CRIT-CC-002 | 🔴 Crítico | Exception handler fallaba | commit_coordinator.py |
| CRIT-CC-003 | 🔴 Crítico | git_head antes del commit | commit_coordinator.py |
| HIGH-LOCK-004 | 🟠 Alto | _save_queue mismo problema | lock_manager.py |
| HIGH-API-001 | 🟠 Alto | Endpoints sin lock | app.py |
| HIGH-API-002 | 🟠 Alto | save_json_file no atómico | app.py |

### Parches Gemini:
| ID | Severidad | Descripción | Archivo |
|----|-----------|-------------|---------|
| CRIT-CC-004 | 🔴 Crítico | "Zombie Commit" - Rollback no revertía Git | commit_coordinator.py |
| CRIT-API-001 | 🔴 Crítico | "Fail-Open" - API escribía sin lock | app.py |
| HIGH-LOCK-001 | 🟠 Alto | _owner_id se asignaba antes de escritura | lock_manager.py |

### Parches Claude:
| ID | Severidad | Descripción | Archivo |
|----|-----------|-------------|---------|
| CRIT-CLAUDE-001 | 🔴 Crítico | Race condition post-write - lock huérfano si falla entre _write_lock y asignación | lock_manager.py |

### Parches Mistral (NUEVOS):
| ID | Severidad | Descripción | Archivo |
|----|-----------|-------------|---------|
| CRIT-003 | 🔴 Crítico | PID reuse en Windows - ahora usa psutil | lock_manager.py |
| HIGH-005 | 🟠 Alto | Path traversal en backups - validación de paths | commit_coordinator.py |

### Parches Perplexity (NUEVOS):
| ID | Severidad | Descripción | Archivo |
|----|-----------|-------------|---------|
| CRIT-LOCK-003 | 🔴 Crítico | Sin verificación post-os.replace() | lock_manager.py |
| CRIT-2PC-001 | 🔴 Crítico | CommitCoordinator no usaba LockManager | commit_coordinator.py |

## 🔧 Instalación

### 1. Instalar dependencia nueva
```bash
pip install portalocker
```

### 2. Copiar archivos a tu repositorio
```bash
# Desde el directorio donde extrajiste el ZIP:
cp scripts/* ../percia-v2/src/scripts/
cp web-interface/* ../percia-v2/src/web-interface/
```

### 3. Commit y push
```bash
cd ../percia-v2
git add .
git commit -m "fix: Apply GPT-4o audit patches (CRIT-LOCK, CRIT-CC, HIGH-API)"
git push origin main
```

## 📁 Archivos incluidos

```
percia-v2-parches/
├── requirements.txt           # Dependencias (incluye portalocker)
├── README.md                  # Este archivo
├── scripts/
│   ├── __init__.py           # Package init
│   ├── lock_manager.py       # ✅ CRIT-LOCK-001, CRIT-LOCK-002, HIGH-LOCK-004
│   ├── commit_coordinator.py # ✅ CRIT-CC-001, CRIT-CC-002, CRIT-CC-003
│   └── validator.py          # Sin cambios críticos
└── web-interface/
    └── app.py                # ✅ HIGH-API-001, HIGH-API-002
```

## 🔬 Cambios principales

### lock_manager.py
- Añadido `portalocker` para mutex cross-platform
- `_write_lock()` usa temp file único + `os.replace()`
- `acquire_global_lock()` usa mutex para atomicidad
- `release_global_lock()`, `refresh_lock()`, `_watchdog_loop()` también usan mutex
- `_save_queue()` usa temp file único

### commit_coordinator.py
- `commit_transaction()` captura `tx_id` antes de `_clear_transaction_state()`
- Exception handler no asume que `_current_transaction` existe
- `snapshot.git_head` se actualiza DESPUÉS del commit Git
- Escrituras atómicas con temp file único

### app.py
- 4 endpoints de escritura usan `lock_context()`
- `save_json_file()` es ahora atómico
- Retorna 409 si hay lock timeout

## ✅ Verificación

Después de aplicar los parches, verifica:

```bash
# Verificar que portalocker está instalado
python -c "import portalocker; print('OK')"

# Verificar sintaxis de los archivos
python -m py_compile src/scripts/lock_manager.py
python -m py_compile src/scripts/commit_coordinator.py
python -m py_compile src/web-interface/app.py
```

## 📊 Auditoría

Estos parches fueron generados basándose en las auditorías de **7 IAs diferentes** del repositorio PERCIA v2.0.

Auditorías completadas:
- ✅ Grok (5.2/10)
- ✅ Copilot (5.6/10)  
- ✅ GPT-4o (code review línea por línea)
- ✅ Gemini (7.6/10) - Detectó Zombie Commit y Fail-Open
- ✅ Claude (7.8/10) - Detectó race condition post-write
- ✅ Mistral - Detectó PID reuse y path traversal
- ✅ Perplexity (6.8/10) - Detectó falta de verificación post-write y 2PC sin lock

# 🧪 PERCIA v2.0 - Security Test Suite

## Ronda 3 Multi-IA Audit - Test de Verificación de Parches

Suite de tests automatizados que verifica que los **11 parches de seguridad** 
aplicados en la Ronda 3 funcionan correctamente.

---

## Instalación

```powershell
cd C:\Users\Administrador\percia-v2
pip install pytest
```

---

## Ejecución

### Ejecutar TODOS los tests
```powershell
pytest -v
```

### Ejecutar por severidad
```powershell
pytest -m critical -v     # Solo parches CRÍTICOS (#1, #2, #3)
pytest -m high -v         # Solo parches ALTOS (#4, #5, #6, #7, #11)
pytest -m medium -v       # Solo parches MEDIOS (#8, #9)
pytest -m low -v          # Solo parches BAJOS (#10)
```

### Ejecutar por parche individual
```powershell
pytest -m patch1 -v       # Parche #1: debug=True RCE
pytest -m patch2 -v       # Parche #2: API Key hardcoded
pytest -m patch3 -v       # Parche #3: lock_context release
pytest -m patch4 -v       # Parche #4: Security Headers
pytest -m patch5 -v       # Parche #5: Rate Limiting
pytest -m patch6 -v       # Parche #6: Timing Attack
pytest -m patch7 -v       # Parche #7: Command Injection
pytest -m patch8 -v       # Parche #8: Zombie Commits
pytest -m patch9 -v       # Parche #9: Queue Mutex
pytest -m patch10 -v      # Parche #10: Path Traversal
pytest -m patch11 -v      # Parche #11: PID Reuse
```

### Ejecutar por componente
```powershell
pytest tests/test_app_security.py -v                  # app.py
pytest tests/test_lock_manager_security.py -v          # lock_manager.py
pytest tests/test_commit_coordinator_security.py -v    # commit_coordinator.py
pytest tests/test_validator_security.py -v             # validator.py
```

### Ejecutar con reporte detallado
```powershell
pytest -v --tb=long       # Tracebacks completos
pytest -v -s              # Ver output de print/logging
```

---

## Estructura de Tests

```
tests/
├── conftest.py                         # Fixtures compartidos
├── test_app_security.py                # Parches #1, #2, #4, #5, #6
│   ├── TestPatch01DebugRCE             # 4 tests
│   ├── TestPatch02APIKey               # 5 tests
│   ├── TestPatch04SecurityHeaders      # 9 tests
│   ├── TestPatch05RateLimiting         # 3 tests
│   ├── TestPatch06TimingAttack         # 5 tests
│   └── TestAuthIntegration             # 2 tests
├── test_lock_manager_security.py       # Parches #3, #9, #11
│   ├── TestPatch03LockContextRelease   # 3 tests
│   ├── TestPatch09QueueMutex           # 4 tests
│   └── TestPatch11PIDReuse             # 7 tests
├── test_commit_coordinator_security.py # Parches #7, #8
│   ├── TestPatch07CommandInjection     # 6 tests
│   └── TestPatch08ZombieCommits        # 5 tests
└── test_validator_security.py          # Parche #10
    ├── TestPatch10PathTraversal        # 7 tests
    └── TestValidatorSanitization       # 3 tests
```

**Total: ~56 tests cubriendo 11 parches**

---

## Mapeo Test → Parche → Vulnerabilidad

| Test Class | Parche | Vulnerabilidad | Severidad | IA Origen |
|---|---|---|---|---|
| TestPatch01DebugRCE | #1 | debug=True RCE | 🔴 CRITICAL | ChatGPT |
| TestPatch02APIKey | #2 | API Key hardcoded | 🔴 CRITICAL | ChatGPT/Claude/Mistral |
| TestPatch03LockContextRelease | #3 | lock_context release | 🔴 CRITICAL | ChatGPT |
| TestPatch04SecurityHeaders | #4 | Missing Headers | 🟠 HIGH | Mistral |
| TestPatch05RateLimiting | #5 | No Rate Limiting | 🟠 HIGH | Mistral/Copilot |
| TestPatch06TimingAttack | #6 | Timing Attack | 🟠 HIGH | ChatGPT |
| TestPatch07CommandInjection | #7 | Command Injection | 🟠 HIGH | ChatGPT/Perplexity |
| TestPatch08ZombieCommits | #8 | Zombie Commits | 🟡 MEDIUM | ChatGPT |
| TestPatch09QueueMutex | #9 | Queue no thread-safe | 🟡 MEDIUM | All |
| TestPatch10PathTraversal | #10 | Path Traversal | 🔵 LOW | ChatGPT |
| TestPatch11PIDReuse | #11 | PID Reuse | 🟠 HIGH | Gemini |

---

## Requisitos

- Python 3.10+
- pytest >= 7.0
- psutil (para tests de Parche #11)
- flask-limiter (para tests de Parche #5)

---

## Integración CI/CD (GitHub Actions)

Archivo `.github/workflows/security-tests.yml`:

```yaml
name: PERCIA Security Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest psutil
      - name: Run security tests
        env:
          PERCIA_API_KEY: ${{ secrets.PERCIA_API_KEY }}
        run: pytest -v --tb=short
```

---

## Notas

- Los tests de **Parche #1 y #2** usan subprocess para verificar que el 
  servidor falla al arrancar con configuración insegura.
- Los tests de **Parche #11** requieren `psutil` para funcionalidad completa.
- Los tests de **Parche #5** pueden ser lentos ya que prueban rate limiting.
- El `conftest.py` maneja la configuración de variables de entorno para que
  los tests sean independientes del entorno del desarrollador.

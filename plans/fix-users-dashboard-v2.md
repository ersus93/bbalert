# Plan: Corrección y Mejora del Comando `/users` — Dashboard v2

**Rama propuesta:** `feature/users-dashboard-v2`  
**Estado:** En planificación  
**Tipo:** `fix` + `feat`  

---

## 🔍 1. Análisis de Causa Raíz

### Bugs Identificados

#### BUG-1: Cálculo incorrecto de "Activos (24h)"
**Archivo:** [`handlers/admin.py`](../handlers/admin.py:451)  
```python
# ANTES (INCORRECTO):
if (now - last_dt).days < 1:   # .days solo cuenta días COMPLETOS

# DESPUÉS (CORRECTO):
if (now - last_dt).total_seconds() < 86400  # 24h exactas en segundos
```
**Impacto:** Un usuario cuya última alerta fue hace 25 horas tiene `timedelta.days = 1`, por lo que NO se cuenta como activo aunque es muy reciente.

---

#### BUG-2: `last_alert_timestamp` no refleja actividad real del usuario
**Archivo:** [`core/loops.py`](../core/loops.py:355) / [`utils/file_manager.py`](../utils/file_manager.py:582)  
- `last_alert_timestamp` solo se actualiza cuando el **loop de alertas de precio** envía una notificación.
- Un usuario que usa `/ver`, `/tasa`, `/ta` sin tener alertas activas **NUNCA es contado como activo**.
- **Fix:** Agregar campo `last_seen` que se actualice en `registrar_uso_comando()`.

---

#### BUG-3: `registrar_uso_comando('tasa')` está comentado
**Archivo:** [`handlers/tasa.py`](../handlers/tasa.py:34)  
```python
# ANTES (COMENTADO — nunca se ejecuta):
#    registrar_uso_comando(chat_id, 'tasa')

# DESPUÉS (DESCOMENTADO):
registrar_uso_comando(chat_id, 'tasa')
```
**Impacto:** El contador de uso del comando `/tasa` en el dashboard siempre muestra `0`, aunque el bot sí aplica el límite de acceso.

---

#### BUG-4: `registrar_uso_comando('ta')` nunca se llama
**Archivo:** [`handlers/ta.py`](../handlers/ta.py:18)  
- `registrar_uso_comando` está importado pero **no hay ninguna llamada** en `ta_command()`.
- **Fix:** Agregar `registrar_uso_comando(user_id, 'ta')` al inicio de `ta_command()`.

---

#### BUG-5: Doble creación de `psutil.Process()`
**Archivo:** [`handlers/admin.py`](../handlers/admin.py:522)  
```python
# ANTES (creado en línea 522 y 530, ineficiente):
process = psutil.Process(os.getpid())  # línea 522
...
process = psutil.Process(os.getpid())  # línea 530 — INNECESARIO

# DESPUÉS: Eliminar la segunda instancia, reusar la variable
```

---

## 📐 2. Mejoras Planificadas

### MEJORA-1: Nuevo campo `last_seen` (actividad real del usuario)

**Archivos:** [`utils/file_manager.py`](../utils/file_manager.py)

- Agregar `"last_seen": null` en la estructura de `registrar_usuario()`
- Agregar `"last_seen": null` en `obtener_datos_usuario_seguro()`
- **Actualizar `last_seen`** en `registrar_uso_comando()` antes de guardar
- Esto resuelve también el BUG-2

---

### MEJORA-2: Campo `registered_at` para nuevos usuarios

**Archivos:** [`utils/file_manager.py`](../utils/file_manager.py:589)

- Agregar `"registered_at": "YYYY-MM-DD HH:MM:SS"` al momento de registrar un nuevo usuario en `registrar_usuario()`
- Los usuarios existentes sin este campo mostrarán `"N/A"`

---

### MEJORA-3: Expandir `daily_usage` (tracking completo de comandos)

**Archivos:** [`utils/file_manager.py`](../utils/file_manager.py:257)

Agregar las claves que faltan en la inicialización de la estructura:
```python
'daily_usage': {
    'date': today_str,
    'ver': 0,
    'tasa': 0,    # Ya existía pero no se incrementaba
    'ta': 0,      # Ya existía pero no se incrementaba  
    'temp_changes': 0,
    # NUEVAS CLAVES:
    'reminders': 0,
    'weather': 0,
    'btc': 0,
}
```

---

### MEJORA-4: Métricas de retención en el Dashboard

**Archivo:** [`handlers/admin.py`](../handlers/admin.py:341)

Agregar contadores en el loop de análisis de usuarios:
```python
active_7d = 0   # Activos en los últimos 7 días
active_30d = 0  # Activos en los últimos 30 días
```
Basados en el nuevo campo `last_seen`.

---

### MEJORA-5: Estadísticas de nuevos usuarios

**Archivo:** [`handlers/admin.py`](../handlers/admin.py:341)

```python
new_today = 0   # Registros del día de hoy
new_7d = 0      # Registros esta semana
new_30d = 0     # Registros este mes
```
Basados en el nuevo campo `registered_at`.

---

### MEJORA-6: Suscripciones próximas a vencer (7 días)

**Archivo:** [`handlers/admin.py`](../handlers/admin.py:341)

```python
subs_expiring_soon = 0  # Subs que vencen en próximos 7 días
```

---

### MEJORA-7: Top 5 comandos más usados hoy

**Archivo:** [`handlers/admin.py`](../handlers/admin.py:341)

Mostrar ranking de comandos en el dashboard:
```
📊 TOP COMANDOS HOY:
1. /ver (245 usos)
2. /tasa (180 usos)
3. /ta (95 usos)
```

---

## 📊 3. Arquitectura del Nuevo Dashboard

```mermaid
graph TD
    A[/users admin] --> B[Carga de Datos]
    B --> C[Cálculo de Métricas]
    C --> D1[Métricas de Sistema]
    C --> D2[Métricas de Usuarios]
    C --> D3[Métricas de Negocio]
    C --> D4[Métricas de Servicios]
    C --> D5[Tendencias de Mercado]
    D2 --> E1[Total usuarios]
    D2 --> E2[Activos 24h basado en last_seen]
    D2 --> E3[Activos 7d]
    D2 --> E4[Activos 30d]
    D2 --> E5[Nuevos hoy/semana/mes]
    D3 --> F1[Suscripciones activas]
    D3 --> F2[Próximas a vencer en 7d]
    D5 --> G1[Top comandos hoy]
    D5 --> G2[Top monedas vigiladas]
```

---

## 🗂️ 4. Archivos Afectados

| Archivo | Tipo de Cambio |
|---------|---------------|
| `handlers/admin.py` | Fix BUG-1, BUG-5 + Mejoras Dashboard |
| `handlers/tasa.py` | Fix BUG-3 |
| `handlers/ta.py` | Fix BUG-4 |
| `utils/file_manager.py` | Mejoras 1, 2, 3 |
| `tests/test_users_dashboard.py` | NUEVO: Tests unitarios |

---

## 🧪 5. Test Unitario Plan

Crear `tests/test_users_dashboard.py`:

```python
# Tests para verificar:
# 1. active_24h con timedelta correcto (total_seconds)
# 2. active_24h NO cuenta usuarios > 24h  
# 3. last_seen se actualiza en registrar_uso_comando
# 4. registered_at se guarda al crear usuario nuevo
# 5. daily_usage registra 'tasa' y 'ta' correctamente
```

---

## 🔐 6. Protocolo de Seguridad (Pre-commit)

- ✅ Ningún valor real de `.env` en el código
- ✅ IDs de chat hardcodeados → NO (se leen de variables de entorno)
- ✅ Claves API → NO incluidas
- ✅ Archivos de datos (`data/*.json`) → ignorados por `.gitignore`

---

## 🚀 7. Git Flow

```
dev
 └── feature/users-dashboard-v2
      ├── fix(admin): correct active_24h calculation using total_seconds
      ├── fix(tasa): uncomment registrar_uso_comando call
      ├── fix(ta): add missing registrar_uso_comando call
      ├── fix(admin): remove duplicate psutil.Process instantiation
      ├── feat(file_manager): add last_seen and registered_at fields
      ├── feat(admin): add retention metrics and expiring subs to dashboard
      └── test: add unit tests for users dashboard metrics
```

**Commit final al mergear:**  
`fix+feat: fix users dashboard metrics and add retention stats (#ISSUE_ID)`

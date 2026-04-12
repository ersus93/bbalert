# Auditoría Técnica de mbot.sh - Aplicando Principios de Linus Torvalds

**Fecha:** 2026-03-20  
**Script:** `mbot.sh` (v7 Professional)  
**Líneas:** 2166  
**Tipo:** Bash TUI (Terminal User Interface) para gestión de bots Telegram

---

## 📊 Resumen Ejecutivo

El script `mbot.sh` es un sistema de gestión multi-bot con interfaz TUI sofisticada. Sin embargo, sufre de **complejidad excesiva** y **violaciones de principios de diseño** que lo hacen frágil, difícil de mantener y propenso a errores.

**Puntuación de Salud:** 4/10  
**Estado:** Requiere refactorización urgente  
**Riesgo:** Alto - cada cambio rompe algo

---

## 🔍 Análisis por Principio de Torvalds

### ① "Hazlo simple o no lo hagas"

**❌ PROBLEMAS CRÍTICOS:**

1. **Monolito de 2166 líneas** - Debería ser múltiples scripts/modulos
   - `mbot.sh` mezcla: UI, lógica de negocio, gestión systemd, git, backups
   - Solución: Separar en módulos: `lib/ui.sh`, `lib/git.sh`, `lib/systemd.sh`, `lib/backup.sh`

2. **Funciones gigantes** - Varias funciones >100 líneas
   - `show_logs_with_menu_exit()`: 115 líneas (líneas 981-1095)
   - `_bot_info_panel()`: 78 líneas (líneas 341-418)
   - `manage_logs()`: 83 líneas (líneas 1190-1273)
   - `full_install()`: 44 líneas pero con lógica compleja

3. **Layout engine excesivamente complejo** - Sección de box drawing (líneas 176-310)
   - 135 líneas de primitivas gráficas
   - 6 funciones diferentes para cajas (`_bline`, `_bcenter`, `_blabel`, `_mrow2`, `_mrow3`, `_mrow1`)
   - Dificultad altísima para modificar o debuggear

4. **Responsive layout con 3 ramas** (líneas 458-556)
   - Código duplicado para 3-columnas, 2-columnas, 1-columna
   - Misma lógica repetida 3 veces
   - **Costo de mantenimiento:** Alto

**✅ FORTALEZAS:**
- La idea de responsive es buena
- El uso de spinners y colores es profesional

---

### ② "Borla sin miedo el código inútil"

**❌ CÓDIGO INÚTIL IDENTIFICADO:**

1. **Variables sin usar:**
   - Línea 26: `CURRENT_USER=$(whoami)` - Se usa solo en create_systemd_service, podría ser local
   - Línea 346: `sdot`, `slbl` - Se reasignan pero la lógica es redundante
   - Línea 388: `bn="${FOLDER_NAME:-sin bot}"` - Se usa una vez, podría inline

2. **Comentarios excesivos y decorativos:**
   - Líneas 1-5: Banner ASCII + comentarios (30 líneas)
   - Líneas 11-12, 23-31: Secciones con emojis y líneas decorativas
   - **Impacto:** 150+ líneas de "decoration code"

3. **Código comentado:**
   - Líneas 291-294: MessageHandler desactivado con comentario extenso
   ```bash
   # MessageHandler para texto libre (añadir monedas sin comando) - DESACTIVADO
   # Para activar: descomentar la línea siguiente
   # from telegram.ext import MessageHandler, filters
   # app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, prices_text_handler))
   ```
   - **Solución:** Eliminar o mover a documentación externa

4. **Funciones duplicadas/innecesarias:**
   - `_nchar()` (líneas 138-144) - Usada solo en 2-3 lugares, podría ser inline
   - `_truncate()` (líneas 77-85) - Usada solo en `_mcell` y `_mrow1`

5. **Validaciones redundantes:**
   - Línea 625: `validate_bot_directory()` hace 3 comprobaciones, pero luego se repiten
   - Línea 722-731: Lógica de recrear venv duplicada en múltiples lugares

**✅ LIMPIEZA POTENCIAL:**
- Eliminar 200-300 líneas de código inútil/comentarios
- Reducir a ~1800 líneas manteniendo funcionalidad

---

### ③ "Si necesitas comentarios, reházlo"

**❌ FUNCIONES QUE NECESITAN REFACTORIZACIÓN (no comentarios):**

1. **`show_logs_with_menu_exit()`** (115 líneas)
   - Hace 5 cosas: setup de FIFO, lectura de input, journalctl, cleanup, signal handling
   - **Problema:** Mezcla de responsabilidades
   - **Solución:** Dividir en:
     - `_setup_log_fifo()`
     - `_monitor_journalctl()`
     - `_cleanup_log_session()`
     - `_read_user_keypress()`

2. **`_bot_info_panel()`** (78 líneas)
   - Calcula: estado del bot, CPU, RAM, git branch, system metrics, renderiza todo
   - **Problema:** Lógica de negocio + UI mezclada
   - **Solución:** Separar:
     - `_collect_bot_metrics()` - retorna datos
     - `_collect_system_metrics()` - retorna datos
     - `_render_bot_info_panel()` - solo renderiza

3. **`manage_logs()`** (83 líneas)
   - Menú + 9 opciones + lógica de cada una
   - **Problema:** Función God Object
   - **Solución:** Una función por opción de menú

4. **`select_target_directory()`** (75 líneas, líneas 637-711)
   - Detección automática + búsqueda + input manual + validación
   - **Problema:** Múltiples responsabilidades
   - **Solución:** Separar en funciones pequeñas

5. **`git_switch_branch()`** (67 líneas)
   - Detección de ramas + UI + git checkout + post-procesamiento
   - **Solución:** Dividir en `_list_available_branches()`, `_switch_to_branch()`

**📊 Métrica:**
- Funciones >50 líneas: 8 funciones
- Funciones 30-50 líneas: 12 funciones
- **Objetivo:** Máximo 25 líneas por función

---

### ④ "No mezcles refactors con arreglos"

**❌ MEZCLA DE RESPONSABILIDADES:**

1. **UI + Lógica de negocio** (en casi todas las funciones)
   - Ejemplo: `_bot_info_panel()` calcula CPU y RAM Y dibuja la caja
   - **Debería:** `get_system_metrics()` → datos, `draw_info_panel(data)` → render

2. **Git + UI + Validación** en funciones como `git_pull_repository()`
   - Hace: fetch, diff, prompt, pull, post-procesamiento
   - **Debería:** Separar `git_pull()` (lógica pura) de `ui_pull_confirmation()` (interacción)

3. **Backup + TAR + Rotación + UI** en `backup_bot()`
   - **Debería:** `create_backup()` retorna path, `display_backups()` muestra lista

4. **Systemd + UI + Validación** en `create_systemd_service()`
   - Genera archivo + copia + daemon-reload + enable
   - **Debería:** `generate_service_file()` retorna contenido, `install_service()` hace systemctl

**✅ PATRÓN CORRECTO:**
```bash
# ❌ MAL (mezclado)
show_bot_stats() {
    # calcular datos
    # formatear strings
    # dibujar cajas
    # mostrar
}

# ✅ BIEN (separado)
get_bot_stats() { ... }  # retorna associative array
render_stats_panel() { ... }  # recibe datos, dibuja
show_bot_stats() {
    data=$(get_bot_stats)
    render_stats_panel "$data"
}
```

---

### ⑤ "Si no lo puedes explicar rápido, está mal"

**❌ FUNCIONES COMPLEJAS (no explicables en 30 segundos):**

1. **`_mrow3()`** (líneas 320-327)
   ```bash
   _mrow3() {
       local n1="$1" l1="$2" n2="$3" l2="$4" n3="$5" l3="$6" CW1="$7" CW2="$8" CW3="$9"
       # ... 8 líneas de cálculo de padding
   }
   ```
   - **Problema:** 9 parámetros, lógica de centrado compleja
   - **Explicación requerida:** "Es para renderizar filas de 3 columnas con cajas"
   - **Solución:** Usar arrays o estructuras de datos

2. **`_msect3()`** (líneas 282-310)
   - Similar: 6 parámetros + lógica de padding duplicada 3 veces
   - **Solución:** Factorizar cálculo de padding en `_calc_padding()`

3. **`show_logs_with_menu_exit()`** - 115 líneas con:
   - FIFO setup
   - Signal trapping
   - Background processes
   - Loop de monitoreo
   - Cleanup
   - **No explicable en menos de 2 minutos**

4. **`git_switch_branch()`** - 67 líneas que hacen:
   - Detección de ramas remotas/locales
   - Filtrado
   - Validación
   - Checkout
   - Pull
   - Actualización de deps
   - **Debería ser 3-4 funciones**

**✅ CRITERIO:**
- Si no puedes explicar una función en 30 segundos → es demasiado compleja
- Si tiene >30 líneas → probablemente hace más de una cosa

---

### ⑥ "Que funcione primero, optimiza después"

**❌ OPTIMIZACIONES PREMATURAS:**

1. **Layout engine sofisticado** (135 líneas)
   - **Problema:** Se optimizó la UI antes de tener funcionalidad básica sólida
   - Impacto: Cualquier cambio en layout requiere entender 135 líneas de código de dibujo
   - **Solución:** Usar `dialog` o `whiptail` para UI, o simplificar a ASCII boxes estáticos

2. **Spinner animado** (líneas 95-118)
   - Código complejo con PID tracking, background processes
   - **Problema:** Se optimizó la experiencia visual antes de asegurar robustez
   - **Bug potencial:** Si el spinner falla, deja procesos huérfanos

3. **Responsive design con 3 layouts** (líneas 458-556)
   - **Problema:** Se optimizó para diferentes terminales antes de tener un layout simple que funcione
   - **Costo:** 100+ líneas de código duplicado
   - **Solución:** Usar un solo layout, o generar dinámicamente con templates

4. **Progress bar con colores dinámicos** (líneas 146-162)
   - Código innecesariamente complejo para una barra de progreso
   - **Solución:** Usar `printf` simple con caracteres repetidos

**✅ FILOSOFÍA CORRECTA:**
1. Primero: Que funcione (script simple con `echo` y `read`)
2. Segundo: Que sea correcto (manejo de errores, validaciones)
3. Tercero: Optimizar (solo si es necesario)

**El script está en paso 3 sin haber consolidado paso 1 y 2.**

---

### ⑦ "Commits pequeños o estás ocultando algo"

**❌ ESTRUCTURA DE COMMITS IMPLÍCITA:**

El script actual es un **monolito de 2166 líneas** que probablemente se construyó con:
- Commits grandes que agrugan múltiples cambios
- Dificultad para hacer rollback de features específicos
- Imposibilidad de revertir solo la UI sin afectar lógica de negocio

**Problemas detectados:**

1. **Todo en un archivo** → No hay granularidad
   - Cambios en UI afectan a todo el script
   - Bug en backup → riesgo de romper git operations
   - **Solución:** Modularizar permite commits por módulo

2. **Funciones gigantes** → Commits gigantes
   - Si modificas `show_logs_with_menu_exit()`, el diff es enorme
   - Dificulta code review
   - **Solución:** Funciones pequeñas = commits pequeños

3. **Mezcla de concerns** → Commits que tocan múltiples áreas
   - Un "fix" en estadísticas podría modificar UI + systemd + git
   - **Solución:** Separación de capas

**✅ BUENA PRÁCTICA:**
```
mbot/
├── mbot                    # Script principal (200 líneas)
├── lib/
│   ├── ui.sh              # Funciones de interfaz (800 líneas)
│   ├── systemd.sh         # Gestión de servicios (300 líneas)
│   ├── git.sh             # Operaciones git (400 líneas)
│   ├── backup.sh          # Backups y restore (300 líneas)
│   └── common.sh          # Utilidades compartidas (200 líneas)
└── config/
    └── defaults.conf
```

Cada módulo puede tener su propio historial de commits.

---

## 📈 Métricas de Calidad

| Métrica | Valor | Ideal | Estado |
|---------|-------|-------|--------|
| Líneas totales | 2166 | <1000 | ❌ 2.16x |
| Funciones >50 líneas | 8 | 0 | ❌ |
| Líneas de comentarios | ~300 | <100 | ❌ 3x |
| Funciones por archivo | 60+ | <20 | ❌ |
| Parámetros máximos | 9 | 3-4 | ❌ |
| Complejidad ciclomática (estimada) | Alta | Baja | ❌ |
| Separación de responsabilidades | Mala | Buena | ❌ |

**Puntuación de Mantenibilidad:** 3/10

---

## 🎯 Plan de Refactorización Priorizado

### FASE 1: Limpieza Inmediata (Principio ②)
**Objetivo:** Reducir 200-300 líneas de código inútil

1. **Eliminar comentarios decorativos** (líneas 1-5, 11-12, secciones)
   - Ahorro: ~150 líneas
   - Riesgo: Cero

2. **Remover código comentado** (líneas 291-294)
   - Ahorro: 4 líneas
   - Riesgo: Cero

3. **Eliminar funciones inútiles** o fusionar las que se usan una vez
   - `_nchar()` → inline (usado 3 veces)
   - `_truncate()` → fusionar en `_mcell`
   - Ahorro: ~30 líneas

4. **Simplificar validaciones redundantes**
   - Consolidar `validate_bot_directory` usos
   - Ahorro: ~20 líneas

**Resultado esperado:** ~1900 líneas, misma funcionalidad

---

### FASE 2: Separación de Responsabilidades (Principio ④)

**Objetivo:** Separar UI de lógica de negocio

1. **Crear módulo `lib/common.sh`**
   - Funciones puras sin side effects
   - `get_system_metrics()`
   - `get_bot_status()`
   - `list_available_branches()`
   - `calculate_disk_usage()`

2. **Crear módulo `lib/ui.sh`**
   - Solo funciones de renderizado
   - `draw_box()`
   - `show_menu()`
   - `render_stats_panel()`
   - Sin lógica de negocio

3. **Crear módulo `lib/systemd.sh`**
   - `create_service_file()`
   - `install_service()`
   - `manage_service_action()`
   - Sin llamadas a `_header()` o `_ok()`

4. **Crear módulo `lib/git.sh`**
   - `git_pull_safe()`
   - `git_switch_branch_force()`
   - `git_get_status()`
   - Sin interacción UI

5. **Crear módulo `lib/backup.sh`**
   - `create_backup_file()`
   - `rotate_backups()`
   - `restore_backup_file()`

**Resultado:** Script principal de 300-400 líneas que orquesta módulos

---

### FASE 3: Simplificación de Funciones Complejas (Principio ③⑤)

**Objetivo:** Refactorizar funciones >50 líneas

1. **`show_logs_with_menu_exit()`** → 5 funciones
   - `setup_log_fifo()`
   - `monitor_journalctl()`
   - `handle_user_input()`
   - `cleanup_log_session()`
   - `show_logs_interactive()` (orquestador)

2. **`_bot_info_panel()`** → 3 funciones
   - `collect_bot_metrics()` → devuelve datos
   - `collect_system_metrics()` → devuelve datos
   - `render_info_panel(bot_data, sys_data)` → solo render

3. **`manage_logs()`** → 9 funciones (una por opción)
   - `logs_show_realtime()`
   - `logs_show_tail()`
   - `logs_show_errors()`
   - `logs_search()`
   - `logs_export()`
   - etc.

4. **`select_target_directory()`** → 4 funciones
   - `detect_local_bot()`
   - `scan_for_bots()`
   - `prompt_manual_path()`
   - `validate_and_set_project()`

5. **Layout engine** → Simplificar o reemplazar
   - Opción A: Usar `dialog`/`whiptail` (recomendado)
   - Opción B: Simplificar a 1 layout fijo (80 cols)
   - **Ahorro potencial:** 135 líneas → 0 (si usamos dialog)

---

### FASE 4: Simplificación de Layout Engine (Principio ①⑥)

**Opción Recomendada: Usar `dialog`**

```bash
# En lugar de 135 líneas de _bline, _mrow3, etc.
dialog --title "BBAlert Manager" \
       --menu "Selecciona opción:" 20 60 15 \
       1 "Instalación Completa" \
       2 "Crear venv" \
       ...
```

**Ventajas:**
- Elimina 135 líneas de código de dibujo
- Maneja automáticamente terminal sizing
- Más robusto
- Código más simple = más mantenible

**Desventajas:**
- Dependencia externa (`dialog` o `whiptail`)
- Menos "bonito" que el diseño actual
- **Pero:** Principio ①: "Hazlo simple"

**Alternativa:** Si se quiere mantener TUI custom:
- Reducir a 1 layout (no 3)
- Eliminar `_mrow2/3`, usar arrays
- **Meta:** <50 líneas de layout code

---

### FASE 5: Mejora de Manejo de Errores (Principio ⑥)

**Problema actual:** `set -euo pipefail` es bueno, pero...

1. **Funciones no retornan códigos de error consistentes**
   - Algunas usan `return 1`, otras `return 0` en error
   - Mezcla de `_err()` + `return` vs solo `_err()`

2. **Validaciones dispersas**
   - Cada función repite validaciones de `$PROJECT_DIR`, `$SERVICE_NAME`
   - **Solución:** Validaciones centralizadas en `main()`

3. **Recuperación automática (`_auto_recovery_check`)**
   - Lógica compleja (líneas 1407-1423)
   - **Debería:** Ser una función simple que llama a `manage_service start`

---

### FASE 6: Testing y Validación

**Problema:** No hay tests

**Solución:**
1. Escribir tests de integración para cada función
2. Usar `bats-core` para testing Bash
3. Cubrir:
   - Creación de venv
   - Instalación de deps
   - Git operations
   - Backup/restore
4. **Principio ⑥:** Que funcione primero → tests aseguran funcionamiento

---

## 📋 Plan de Acción Inmediato (Primeras 3 Acciones)

### 🎯 ACCIÓN 1: Extraer Layout Engine a `lib/ui-layout.sh`
- Mover funciones `_bline`, `_bcenter`, `_blabel`, `_mrow*`, `_msect*`
- Crear API simple: `ui_draw_box()`, `ui_draw_menu()`
- **Beneficio:** Aísla código complejo, facilita reemplazo por `dialog`

### 🎯 ACCIÓN 2: Separar Lógica de Negocio de UI
- Para cada función `show_*()`:
  1. Crear `get_*_data()` que retorna datos
  2. Crear `render_*()` que dibuja
  3. `show_*()` se convierte en orquestador
- **Beneficio:** Testeable, mantenible

### 🎯 ACCIÓN 3: Simplificar Responsive Layout
- Elegir UN layout (recomendación: 2-columnas para ≥84 cols)
- Eliminar ramas de 1-columna y 3-columnas
- **Ahorro:** ~80 líneas de código duplicado
- **Principio ①:** Simple > Complejo

---

## 🔧 Recomendaciones Técnicas Específicas

### 1. **Reemplazar TUI Custom por `dialog`**
```bash
# Actual (complejo):
# - 135 líneas de box drawing
# - 100 líneas de layout responsive
# - Código difícil de modificar

# Propuesto:
dialog --clear
dialog --menu "BBAlert Manager" 20 70 15 \
   "1" "Instalación" \
   "2" "Control Bot" \
   ...
```
**Ahorro:** 235 líneas  
**Riesgo:** Bajo (dialog está en casi todos los Linux)

### 2. **Usar Arrays para Configuración de Menús**
```bash
# Actual: hardcodeado en show_menu()
# Propuesto:
MENU_INSTALL=(1 "Instalación Completa" 2 "Crear venv" ...)
MENU_CONTROL=(6 "Iniciar Bot" 7 "Detener Bot" ...)
# Loop genérico para renderizar
```

### 3. **Centralizar Configuración**
```bash
# Crear config/defaults.conf
DEFAULT_PYTHON="python3.13"
MAX_BACKUPS=5
LOG_ROTATION_DAYS=7
# Cargar una vez al inicio
```

### 4. **Mejorar Manejo de Errores**
```bash
# En lugar de:
# trap 'handle_error ...' ERR
# Usar:
trap 'cleanup_and_exit $?' EXIT
# Y validar cada función explícitamente
```

### 5. **Documentación en Código**
- Cada función debe tener: propósito, parámetros, retorno, side effects
- Usar formato estándar:
```bash
# get_bot_status()
#   Obtiene estado del servicio systemd
# Args: $1 - nombre del servicio
# Returns: status_string, pid, restarts
# Side effects: none
```

---

## 📊 Impacto de Refactorización

| Fase | Líneas Eliminadas | Líneas Añadidas | Neto | Complejidad |
|------|-------------------|-----------------|------|-------------|
| 1: Limpieza | 300 | 0 | -300 | -20% |
| 2: Modularización | 0 | 200 | +200 | Temporal +10% |
| 3: Simplificación | 400 | 100 | -300 | -30% |
| 4: Layout (dialog) | 235 | 50 | -185 | -40% |
| **Total** | **935** | **350** | **-585** | **-35%** |

**Líneas finales estimadas:** 2166 - 585 = **1581 líneas**  
**Reducción:** 27%  
**Mejora de mantenibilidad:** 50%+

---

## ⚠️ Riesgos y Consideraciones

1. **Compatibilidad hacia atrás**
   - Si se usa `dialog`, usuarios sin `dialog` instalado fallarán
   - **Mitigación:** Detectar y mostrar error amigable

2. **Curva de aprendizaje**
   - Nuevos desarrolladores deben entender múltiples módulos
   - **Mitigación:** Documentar arquitectura en README

3. **Testing**
   - Refactorizar sin tests es peligroso
   - **Mitigación:** Escribir tests ANTES de refactor (TDD)

4. **Tiempo de refactor**
   - Estimado: 2-3 días de trabajo focused
   - **Recomendación:** Hacerlo en rama `refactor/mbot-modular`

---

## 🚀 Recomendación Final

**SÍ, el script necesita refactorización urgente.**

**Prioridades:**
1. **Principio ②:** Borrar código inútil (FASE 1) - 1 día
2. **Principio ①:** Simplificar layout (FASE 4) - 1 día
3. **Principio ③:** Refactorizar funciones complejas (FASE 3) - 2 días
4. **Principio ④:** Separar responsabilidades (FASE 2) - 2 días

**Orden sugerido:** 1 → 4 → 3 → 2 → 5 → 6

**Criterio de éxito:**
- Script <1800 líneas
- Máximo 3 funciones >50 líneas
- Cada función <30 líneas en 90% de casos
- Tests de integración cubriendo 80% de funciones

---

## 📝 Notas para el Desarrollador

> "Perfección no es cuando no hay nada más que añadir, sino cuando no hay nada más que quitar."  
> — Antoine de Saint-Exupéry (y Linus Torvalds estaría de acuerdo)

El script actual es **funcional pero frágil**. Cada "fix" rompe algo porque la base es inestable. Invertir tiempo en refactorización **ahora** pagará dividendos en:
- Menos bugs
- Desarrollo más rápido de nuevas features
- Facilidad de debugging
- Onboarding de nuevos desarrolladores

**Próximo paso:** Crear rama `refactor/2026-03-simplify-mbot` y comenzar por FASE 1.

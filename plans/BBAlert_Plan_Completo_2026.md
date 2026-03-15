# BBAlert — Plan Completo de Implementación

> *"La simplicidad es la sofisticación suprema."*

**Fecha:** 14 marzo 2026 · **Versión objetivo:** 1.2.x → 1.3.x · **Rama de trabajo:** `test → dev → main`

---

## Resumen ejecutivo

| Categoría | Estado | Veredicto |
|---|---|---|
| Arquitectura modular | 52 archivos separados por dominio | ✅ Correcto — no tocar |
| Comandos registrados | 33+ handlers activos | ✅ Necesarios — no eliminar |
| Funcionalidad | 8/10 | ✅ Sólida |
| Bugs de navegación UX | 4 críticos + 2 menores | ❌ Corregir esta semana |
| Exposición admin a usuarios | HELP_FULL muestra /users /logs a todos | ❌ Corregir esta semana |
| Loops concurrentes | 11 activos simultáneamente | ⚠️ Optimizar recursos |
| Presentación de respuestas | Bloques densos sin jerarquía | ⚠️ Mejorar |

**El problema no es la cantidad de comandos ni de archivos. Es cómo se presentan al usuario y 4 bugs concretos que cortan el flujo de navegación.**

---

## Principios de implementación

| ❌ NO hacer | ✅ SÍ hacer |
|---|---|
| Eliminar comandos funcionales | Mejorar cómo se presentan |
| Fusionar archivos de módulo | Corregir bugs en archivos existentes |
| Refactorizar la arquitectura | Cambios quirúrgicos de 5-20 líneas |
| Reescribir lógica de negocio | Arreglar la navegación de callbacks |
| Romper funcionalidad existente | Cero impacto en usuario durante deploy |

---

## Lo que está bien — no tocar

- **Arquitectura modular** — `handlers/` `utils/` `core/` son dominios aislados. Si `sp_handlers.py` falla, el resto del bot sigue operando.
- **Modularidad de archivos** — 52 archivos = 52 módulos reemplazables individualmente. Esto protege al usuario de impactos colaterales durante reparaciones.
- **Comandos de Telegram** — Los 33+ comandos son necesarios para la funcionalidad completa. El reto es la presentación, no la existencia.
- **Error handler global** — Fallback Markdown → texto plano automático. `NetworkError` ignorado. `RetryAfter` respetado. Completo y correcto.
- **Inyección de dependencias** — `set_*_sender`, `set_admin_util` — módulos independientes sin acoplamiento directo al bot.
- **ConversationHandlers en orden correcto** — `weather_conv → ms_conv → reminders_conv → comandos → callbacks`. Sin conflictos.
- **i18n implementado** — `_()` en toda la UI, soporte ES/EN con Babel/gettext.

---

---

# Sección 2 — Auditoría de bugs

Los siguientes problemas se identificaron leyendo el código fuente directamente. Cada uno tiene archivo, línea aproximada y corrección exacta.

---

## Bug #1 — CRÍTICO: `start_help` callback llama método inexistente

**Archivo:** `handlers/general.py` — función `start_button_callback` ~L82

**El problema:** Cuando el usuario toca "📚 Ayuda" en `/start`, el callback ejecuta `await help_command(update, context)`. Pero `help_command` usa `update.message.reply_text()` — que **no existe** en un `CallbackQuery` update. El usuario toca "Ayuda" y **no pasa nada visible**. Error silencioso.

```diff
  # CÓDIGO ACTUAL (roto)
  elif data == "start_help":
-     await help_command(update, context)

  # CORRECCIÓN
  elif data == "start_help":
+     datos_usuario = obtener_datos_usuario(user_id)
+     lang = datos_usuario.get("language", "es")
+     if lang not in ["es", "en"]: lang = "es"
+     texto = HELP_MSG.get(lang, HELP_MSG["es"])
+     keyboard = [
+         [InlineKeyboardButton("🚨 Alertas", callback_data="help_alerts")],
+         [InlineKeyboardButton("📊 Trading", callback_data="help_trading")],
+         [InlineKeyboardButton("🌤️ Clima", callback_data="help_weather")],
+         [InlineKeyboardButton("⚙️ Ajustes", callback_data="help_settings")],
+         [InlineKeyboardButton("📋 Ver todos", callback_data="help_all")]
+     ]
+     await query.edit_message_text(
+         texto, reply_markup=InlineKeyboardMarkup(keyboard),
+         parse_mode=ParseMode.MARKDOWN
+     )
```

---

## Bug #2 — CRÍTICO: `help_back_callback` envía mensaje nuevo en vez de editar

**Archivo:** `handlers/general.py` — función `help_back_callback` ~L257

**El problema:** `help_back_callback` llama `await help_command(update, context)`. Esa función ejecuta `update.message.reply_text()` — envía un mensaje **nuevo** en el chat. Cada vez que el usuario toca "← Volver", el chat acumula otro mensaje de /help.

```diff
  # CÓDIGO ACTUAL (roto)
  async def help_back_callback(update, context):
      query = update.callback_query
      await query.answer()
-     await help_command(update, context)  # ← envía mensaje NUEVO

  # CORRECCIÓN
  async def help_back_callback(update, context):
+     query = update.callback_query
+     await query.answer()
+     user_id = query.from_user.id
+     datos_usuario = obtener_datos_usuario(user_id)
+     lang = datos_usuario.get("language", "es")
+     if lang not in ["es", "en"]: lang = "es"
+     texto = HELP_MSG.get(lang, HELP_MSG["es"])
+     keyboard = [
+         [InlineKeyboardButton("🚨 Alertas", callback_data="help_alerts")],
+         [InlineKeyboardButton("📊 Trading", callback_data="help_trading")],
+         [InlineKeyboardButton("🌤️ Clima", callback_data="help_weather")],
+         [InlineKeyboardButton("⚙️ Ajustes", callback_data="help_settings")],
+         [InlineKeyboardButton("📋 Ver todos", callback_data="help_all")]
+     ]
+     await query.edit_message_text(
+         texto, reply_markup=InlineKeyboardMarkup(keyboard),
+         parse_mode=ParseMode.MARKDOWN
+     )
```

---

## Bug #3 — CRÍTICO: `help_all` muestra placeholder vacío

**Archivo:** `locales/texts.py` — clave `"help_all"` en `HELP_CATEGORIES` / `handlers/general.py` — `help_category_callback`

**El problema:** El botón "📋 Ver TODOS los comandos" envía callback `"help_all"`. El handler busca esa clave en `HELP_CATEGORIES` y encuentra: *"Usa /help para ver ayuda por categorías."* — un mensaje que le dice al usuario que use /help cuando ya está dentro de /help. `HELP_FULL` ya existe en `texts.py` pero no está conectado.

```diff
  # EN help_category_callback — agregar caso especial para help_all
  async def help_category_callback(update, context):
      query = update.callback_query
      await query.answer()
      data = query.data
      user_id = query.from_user.id

+     # Caso especial: mostrar ayuda completa filtrada por rol
+     if data == "help_all":
+         datos_usuario = obtener_datos_usuario(user_id)
+         lang = datos_usuario.get("language", "es")
+         if lang not in ["es", "en"]: lang = "es"
+         is_admin = user_id in ADMIN_CHAT_IDS
+         texto = _build_full_help(lang, is_admin)
+         keyboard = [[InlineKeyboardButton("← Volver", callback_data="help_back")]]
+         await query.edit_message_text(
+             texto, reply_markup=InlineKeyboardMarkup(keyboard),
+             parse_mode=ParseMode.MARKDOWN,
+             disable_web_page_preview=True
+         )
+         return

      # resto del handler sin cambios...
```

---

## Bug #4 — CRÍTICO: `HELP_FULL` expone comandos admin a usuarios normales

**Archivo:** `locales/texts.py` — `HELP_FULL` (ES y EN) / `handlers/general.py` — `show_full_help`

**El problema:** `HELP_FULL` incluye la sección *"🔑 Comandos de Administrador"* con `/users`, `/logs`, `/ms`, `/ad` visible para **cualquier usuario**. Un usuario normal ve comandos que no puede ejecutar, los intenta, recibe silencio o error, y pierde confianza en el bot.

```diff
  # NUEVA FUNCIÓN en handlers/general.py
+ def _build_full_help(lang: str, is_admin: bool) -> str:
+     """Construye HELP_FULL dinámico según rol del usuario."""
+     from locales.texts import HELP_FULL, HELP_FULL_ADMIN
+     base = HELP_FULL.get(lang, HELP_FULL["es"])
+     if is_admin:
+         admin_section = HELP_FULL_ADMIN.get(lang, HELP_FULL_ADMIN["es"])
+         return base + admin_section
+     return base

  # EN locales/texts.py — separar sección admin en su propia variable
  # HELP_FULL: eliminar la sección "🔑 Comandos de Administrador"
  # NUEVO:
+ HELP_FULL_ADMIN = {
+     "es": (
+         "\n🔑 *Comandos de Administrador*\n"
+         "  • `/users` — Estadísticas de usuarios\n"
+         "  • `/logs [N]` — Últimas líneas del log\n"
+         "  • `/ms` — Mensaje masivo a todos\n"
+         "  • `/ad` — Gestionar anuncios\n"
+         "  • `/free` — Otorgar acceso free\n"
+     ),
+     "en": (
+         "\n🔑 *Admin Commands*\n"
+         "  • `/users` — User statistics\n"
+         "  • `/logs [N]` — Last log lines\n"
+         "  • `/ms` — Broadcast message\n"
+         "  • `/ad` — Manage ads\n"
+         "  • `/free` — Grant free access\n"
+     ),
+ }
```

---

## Bug #5 — MENOR: texto `[← Volver]` duplicado en `HELP_CATEGORIES`

**Archivo:** `locales/texts.py` — todas las claves en `HELP_CATEGORIES` (ES y EN)

**El problema:** Cada cadena termina con `"[← Volver]"` como texto plano. Ya existe un botón inline "← Volver" que maneja la navegación. El texto no hace nada — es ruido visual.

```diff
  "help_alerts": (
      "🚨 *Alertas*\n\n"
      "/alerta MONEDA PRECIO - Crear alerta\n"
      "/misalertas - Ver tus alertas\n"
      "/monedas BTC,ETH - Configurar lista\n"
      "/temp 2.5 - Intervalo de alertas\n"
-     "/parar - Detener alertas\n\n"
-     "[← Volver]"
+     "/parar - Detener alertas"
  ),
  # Aplicar lo mismo a: help_trading, help_weather, help_settings, help_all
```

---

## Bug #6 — MENOR: `show_full_help` usa `update.message` en contexto ambiguo

**Archivo:** `handlers/general.py` — función `show_full_help` ~L262 (última línea)

**El problema:** `show_full_help` usa `await update.message.reply_text()`. Tras corregir Bug #3, esta función será invocada desde un callback — donde `update.message` no existe. Mismo patrón que Bug #1.

```diff
  async def show_full_help(update, context):
      ...
-     await update.message.reply_text(
-         text=texto, reply_markup=keyboard, parse_mode=...
-     )
+     # Detectar contexto: callback vs comando directo
+     if update.callback_query:
+         await update.callback_query.edit_message_text(
+             text=texto, reply_markup=keyboard,
+             parse_mode=ParseMode.MARKDOWN,
+             disable_web_page_preview=True
+         )
+     else:
+         await update.message.reply_text(
+             text=texto, reply_markup=keyboard,
+             parse_mode=ParseMode.MARKDOWN,
+             disable_web_page_preview=True
+         )
```

---

---

# Sección 3 — Plan por fases

---

## Fase 1 — Corrección de bugs de navegación UX

**Urgencia:** CRÍTICO · **Estimado:** 3-4 horas · **Rama:** `test` · **Impacto en producción:** ninguno hasta merge

**Criterio de completitud:** El flujo completo funciona sin errores silenciosos. Usuario toca "Ayuda" en /start → ve menú de categorías → toca categoría → ve comandos → toca "← Volver" → regresa sin mensaje nuevo → toca "Ver todos" → ve lista filtrada por rol.

| # | Qué | Por qué | Archivos | Impacto |
|---|---|---|---|---|
| T1.1 | Corregir `start_help` callback | Botón "Ayuda" no hace nada | `handlers/general.py : start_button_callback ~L82` | Botón funciona correctamente |
| T1.2 | Corregir `help_back_callback` | "← Volver" duplica mensajes | `handlers/general.py : help_back_callback ~L257` | Edita el mensaje existente |
| T1.3 | Conectar `help_all` al `HELP_FULL` real | "Ver todos" muestra placeholder vacío | `handlers/general.py : help_category_callback` + `locales/texts.py` | Muestra lista completa real |
| T1.4 | Filtrar sección admin en `HELP_FULL` | Usuarios normales ven comandos que no pueden usar | `locales/texts.py` + `handlers/general.py` | Cada rol ve solo sus comandos |
| T1.5 | Refactorizar `show_full_help` para callback context | Fallará al ser invocada desde callback (tras T1.3) | `handlers/general.py : show_full_help ~L262` | Funciona desde comando y desde callback |
| T1.6 | Limpiar texto `[← Volver]` de `HELP_CATEGORIES` | Texto decorativo duplica el botón real | `locales/texts.py : HELP_CATEGORIES — ES y EN` | Mensajes de categoría limpios |

---

## Fase 2 — Verificación de consistencia documentación vs código

**Urgencia:** IMPORTANTE · **Estimado:** 1-2 horas · **Rama:** `test`

| # | Qué | Por qué | Archivos | Impacto |
|---|---|---|---|---|
| T2.1 | Auditar `/weather_sub` en `bbalert.py` vs README | README documenta el comando pero no está en `CommandHandler` | `bbalert.py` sección CLIMA + `handlers/weather.py` + `README.md` | Sin discrepancias entre docs y código |
| T2.2 | Verificar que `HELP_CATEGORIES` refleje solo comandos registrados | El menú no debe documentar comandos fantasma | `locales/texts.py : HELP_CATEGORIES` vs `bbalert.py` lista de handlers | Sin comandos ficticios en el menú de ayuda |
| T2.3 | Sincronizar README con estado real | Secciones de Roadmap y Comandos pueden estar desactualizadas | `README.md` — Comandos Principales + Roadmap | README refleja fielmente el estado actual |

---

## Fase 3 — Optimización de loops (recursos del servidor)

**Urgencia:** IMPORTANTE · **Estimado:** 4-6 horas · **Rama:** `test` · **Requiere pruebas en staging**

> **Principio:** Los 11 loops son funcionalmente correctos. La optimización es de **eficiencia de recursos**, no de corrección. No tocar la lógica interna de ningún loop — solo la coordinación entre ellos en `post_init`.

| # | Qué | Por qué | Archivos | Impacto |
|---|---|---|---|---|
| T3.1 | Escalonar arranque de loops con offset inicial | Los 11 loops arrancando simultáneamente generan burst de llamadas API | `bbalert.py : post_init` — `asyncio.sleep(N)` antes de cada `create_task` | -60% llamadas API simultáneas en arranque |
| T3.2 | Evaluar consolidación `weather_alerts_loop` + `weather_daily_summary_loop` | Mismo módulo, mismo dominio — candidatos a un loop con doble ciclo interno | `core/weather_loop_v2.py` — revisar compatibilidad de intervalos | -1 task activo · -5-10 MB RAM estimado |
| T3.3 | Implementar health check interno de loops | Un loop muerto silenciosamente = funcionalidad caída sin alarma | `bbalert.py : post_init` + `utils/logger.py` — wrapper de monitoring | Admin recibe notificación si un loop se detiene |
| T3.4 | Revisar intervalos de polling — ajustar a lo necesario | Loops con sleep muy corto consumen CPU sin beneficio real | `core/btc_loop.py` / `core/sp_loop.py` / `core/loops.py` — revisar cada `sleep()` | -15-20% CPU idle estimado |

---

## Fase 4 — Densidad de respuestas en comandos de análisis

**Urgencia:** MEJORA · **Estimado:** 1-2 horas por comando · **Modular, sin orden estricto**

**Patrón de respuesta ideal para comandos de análisis pesado (`/ta`, `/sp`, `/btcalerts`, `/valerts`):**

1. **Primer mensaje:** resumen en 3-5 líneas con dato principal + señal
2. **Botón inline:** "📊 Ver análisis completo" → expande con el detalle técnico
3. **Resultado:** el usuario ve la señal de inmediato, el detalle está disponible con un toque

| # | Qué | Por qué | Archivos | Impacto |
|---|---|---|---|---|
| T4.1 | Patrón resumen+detalle en `/ta` | Análisis técnico emite bloque denso; la señal queda enterrada | `handlers/ta.py : ta_command` + `core/ai_logic.py` | Señal visible en 2 segundos |
| T4.2 | Patrón resumen+detalle en `/sp` (SmartSignals) | Señal de entrada queda enterrada en el análisis extenso | `handlers/sp_handlers.py : sp_command` | Señal principal al tope, detalles con un toque |
| T4.3 | Revisar densidad de alertas automáticas de loops | Alertas deben ser concisas y accionables | `core/btc_loop.py` / `core/valerts_loop.py` / `core/sp_loop.py` — formato de mensaje | Alertas: qué pasó + qué hacer. Sin relleno. |
| T4.4 | Vista simple en `/p` por defecto | `/p` con datos extensos confunde usuarios que solo quieren el precio | `handlers/trading.py : p_command` | Vista compacta por defecto, botón "Ver detalle" |

---

## Fase 5 — Seguridad y solidez del sistema

**Urgencia:** IMPORTANTE · **Estimado:** 1 semana · **Rama:** `test → dev`

| # | Qué | Por qué | Archivos | Impacto |
|---|---|---|---|---|
| T5.1 | Rate limiting por usuario en comandos pesados | Sin rate limit, un usuario puede saturar las APIs externas | `utils/` — nuevo `validate.py` o función en `file_manager.py` | Seguridad APIs; experiencia normal no afectada |
| T5.2 | Centralizar validación de inputs | Cada handler valida ad-hoc — código duplicado y gaps de seguridad | `utils/validate.py` (nuevo) + `handlers/*.py` | Validación consistente, menos código duplicado |
| T5.3 | Tests automáticos para flujo `/start → /help` | Los bugs de F1 corregidos deben tener tests para evitar regresiones | `tests/test_start_flow.py` + `tests/test_help_flow.py` (nuevos) | Los bugs de navegación no pueden volver sin que un test lo detecte |
| T5.4 | Documentar en `agent.md` el patrón correcto de callback handlers | Bug #1 y #2 surgieron por no tener documentado cuándo usar `query.edit` vs `message.reply` | `agent.md` — nueva sección "Patrones de handlers Telegram" | Evitar el mismo tipo de bug en nuevos features |

---

## Fase 6 — Mejora continua (proceso permanente)

**Urgencia:** CONTINUO · **Cadencia:** trimestral · **Rama:** `dev`

| # | Qué | Por qué | Archivos | Impacto |
|---|---|---|---|---|
| T6.1 | UX metrics tracking (`utils/ux_metrics.py`) | Sin métricas no hay datos para decisiones — intuición no es suficiente | `utils/ux_metrics.py` (nuevo) + integrar en `handlers/alerts.py` | Baseline medible: tiempo al primer valor, tasa de éxito por comando |
| T6.2 | Auditoría trimestral de comandos sin uso | Features sin uso acumulan deuda de complejidad | `utils/ux_metrics.py : get_unused_commands(days=90)` | Proceso formal de deprecación basado en datos reales |
| T6.3 | Dashboard admin de métricas (`/stats`) | Los admins necesitan visibilidad del estado sin acceso SSH | `handlers/admin.py` — nuevo comando `/stats` solo para admins | Métricas de uso, loops activos, errores recientes desde Telegram |
| T6.4 | Evaluación trimestral de migración JSON → SQLite | El almacenamiento JSON escala mal con muchos usuarios | `data/*.json` — evaluar volumen cuando sea necesario | Preparación para escala, sin urgencia inmediata |

---

---

# Sección 4 — KPIs y métricas de éxito

| Métrica | Actual | Objetivo 90 días | Responsable |
|---|---|---|---|
| Botón "Ayuda" en /start funciona | ❌ Roto | ✅ 100% | F1 · T1.1 |
| "← Volver" edita sin duplicar mensajes | ❌ Roto | ✅ 100% | F1 · T1.2 |
| "Ver todos" muestra HELP_FULL real | ❌ Roto | ✅ 100% | F1 · T1.3 |
| Sección admin oculta a usuarios normales | ❌ Visible | ✅ Oculta | F1 · T1.4 |
| Tiempo al primer valor percibido | ~8 min | < 1 min | F1 + F4 |
| Loops activos en memoria | 11 | 9-10 | F3 · T3.2 |
| Llamadas API en arranque (primer ciclo) | Burst ×11 | Escalonadas | F3 · T3.1 |
| Comandos con patrón resumen+detalle | 0 de 6 | 6 de 6 | F4 |
| Tests de flujo /start → /help | 0 | 5+ tests | F5 · T5.3 |
| Discrepancias README vs código | Desconocidas | 0 | F2 · T2.3 |

---

# Sección 5 — Flujo de trabajo

## 5.1 Ramas Git

| Rama | Propósito | Flujo |
|---|---|---|
| `test` | Desarrollo e implementación F1–F5 | Desarrollar aquí, deploy en staging |
| `dev` | Integración y validación | PR desde `test` tras QA manual |
| `main` | Producción — versión etiquetada | Merge desde `dev` · tag `vX.X.X` · deploy VPS |

## 5.2 Proceso por tarea

1. Leer el archivo a modificar con Desktop Commander
2. Hacer el cambio mínimo — verificar que no rompe imports ni llamadas desde `bbalert.py`
3. Commit: `git commit -m "fix(ux): descripción concreta (#Tarea)"`
4. Probar en staging: iniciar bot en test, ejecutar el flujo manualmente
5. Si pasa QA manual → PR a `dev` con checklist de cambios

## 5.3 Orden cronológico recomendado

- **Semana 1:** F1 completo (T1.1 → T1.6) + F2 (T2.1 → T2.3)
- **Semana 2:** F3 (T3.1 → T3.4) con pruebas de carga en staging
- **Semanas 3-4:** F4 comando a comando — sin prisa, módulo por módulo
- **Mes 2:** F5 (seguridad y tests)
- **Trimestral:** F6 como proceso permanente

---

# Sección 6 — Principio rector

> *"La perfección se alcanza no cuando no hay nada más que añadir, sino cuando no hay nada más que quitar."*
> — Antoine de Saint-Exupéry

BBAlert tiene la base técnica correcta. Los comandos son necesarios. Los módulos separados son una fortaleza. El código es mantenible.

Lo que requiere atención son **cuatro bugs de navegación** que llevan al usuario a un callejón sin salida, y la **forma en que se presenta la información** en los comandos de análisis.

El plan está ordenado por impacto real: lo que rompe la experiencia hoy va primero, lo que la mejora va después, lo que la perfecciona va al final.

---

*BBAlert © 2026 · Plan generado el 14-03-2026*

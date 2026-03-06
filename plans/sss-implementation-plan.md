# Plan de Implementación: SmartSignals Strategy (SSS)

**Versión:** 1.0  
**Fecha:** 2026-03-06  
**Estado:** ✅ Listo para implementar

---

## 1. Resumen ejecutivo

El módulo **SmartSignals Strategy (SSS)** transforma el comando `/sp` de un monitor de señales a un **ecosistema completo de trading** donde las estrategias actúan como _skills_ personalizables. Cada usuario premium puede seleccionar su estrategia activa y recibir señales enriquecidas con niveles de entrada/salida, gestión de capital y apalancamiento calculados con la lógica exacta de esa estrategia.

El sistema es **hot-reload**: las estrategias se cargan desde `data/sss/strategies/*.json` sin reiniciar el bot, y los administradores o usuarios premium pueden añadir sus propias estrategias subiendo el fichero JSON.

---

## 2. Arquitectura del sistema

```
data/sss/                          ← Gitignored (contenido premium)
  strategies/
    base_sasas.json                ← SASAS Pro (Supertrend + ASH)
    base_momentum.json             ← Momentum Scalper (RSI + MACD)
    base_swing.json                ← Swing Wave (EMA + CCI)
    [user_estrategia].json         ← Estrategias subidas por usuarios
  user_prefs.json                  ← Estrategia activa por usuario (auto-generado)

utils/sss_manager.py               ← Motor central del sistema SSS
utils/sp_manager.py                ← + queue_quick_notify / pop_quick_notify
core/sp_loop.py                    ← + Aplicación de estrategias + quick-notify
handlers/sp_handlers.py            ← + Submenú de estrategias (4 nuevos callbacks)
```

---

## 3. Flujo de datos

```
Usuario activa alerta  →  toggle_sp_subscription()
                       →  queue_quick_notify()  ← NUEVO: señal inmediata

Loop 45s               →  _process_pair()
  ├─ SPSignalEngine.analyze()         ← señal base (sin cambios)
  ├─ pop_quick_notify()               ← NUEVO: usuarios recién suscritos
  ├─ Por cada grupo de suscriptores:
  │   ├─ get_user_strategy(uid)
  │   ├─ compute_extended_indicators()  ← Supertrend, ASH, ADX bajo demanda
  │   ├─ apply_strategy_filter()        ← Filtro de entrada de la estrategia
  │   ├─ enrich_signal()               ← TP1/TP2/TP3, SL, apalancamiento
  │   └─ Mensaje personalizado por grupo
  └─ _check_pre_alert()               ← sin cambios
```

---

## 4. Estrategias base incluidas

### 4.1 SASAS Pro (`base_sasas.json`)
- **Inspiración:** Estrategia Freqtrade SASAS v2.9.0 (Supertrend + ASH)
- **Estilo:** Swing trading
- **TF recomendados:** 5m, 15m, 1h
- **Condiciones de entrada:** Score ≥5.5 + Supertrend alineado + ASH signal + ADX >20
- **Gestión de riesgo:** SL=1.5×ATR, TP1=2×ATR (50%), TP2=3.5×ATR (30%), TP3=5.5×ATR (20%)
- **Trailing:** Supertrend tras TP1
- **Apalancamiento:** 5x (max 20x, reduce a 10x en alta volatilidad)
- **Capital <$22:** Salida total en TP1 (R:R 1:1)

### 4.2 Momentum Scalper (`base_momentum.json`)
- **Estilo:** Scalping
- **TF recomendados:** 1m, 5m, 15m
- **Condiciones de entrada:** Score ≥4.5 + cruce MACD + spike de volumen ×1.5
- **Gestión de riesgo:** SL=1×ATR, TP1=1.2×ATR (60%), TP2=2×ATR (30%), TP3=3×ATR (10%)
- **Apalancamiento:** 10x (max 25x)

### 4.3 Swing Wave (`base_swing.json`)
- **Estilo:** Position trading
- **TF recomendados:** 1h, 4h
- **Condiciones de entrada:** Score ≥6.0 + ADX >25 + EMA cross + RSI zona neutral
- **Gestión de riesgo:** SL=2×ATR, TP1=3×ATR (40%), TP2=5×ATR (35%), TP3=8×ATR (25%)
- **Trailing:** EMA tras TP1
- **Apalancamiento:** 3x (max 10x, reduce a 5x en alta volatilidad)

---

## 5. Formato JSON de estrategias

```json
{
  "id": "mi_estrategia",
  "name": "Nombre visible",
  "version": "1.0.0",
  "author": "Usuario",
  "tier": "base",          // base | premium | admin
  "style": "swing",        // scalping | swing | position
  "emoji": "⚡",
  "description": "...",
  "timeframes": ["5m", "15m", "1h"],
  "entry_filter": {
    "min_score": 5.5,
    "supertrend_align": true,
    "ash_signal": true,
    "volume_spike": false,
    "volume_spike_mult": 1.5,
    "adx_min": 20,
    "adx_di_confirm": true,
    "macd_cross_required": false,
    "rsi_oversold_buy": 100,
    "rsi_overbought_sell": 0
  },
  "risk": {
    "sl_type": "atr",
    "sl_atr_mult": 1.5,
    "tp1_atr_mult": 2.0,   "tp1_close_pct": 50,
    "tp2_atr_mult": 3.5,   "tp2_close_pct": 30,
    "tp3_atr_mult": 5.5,   "tp3_close_pct": 20,
    "trailing_after_tp1": true,
    "trailing_type": "supertrend"  // supertrend | ema | null
  },
  "leverage": {
    "default": 5,
    "max": 20,
    "volatile_reduce": true,
    "volatile_threshold": 0.03,
    "volatile_max": 10
  },
  "capital": {
    "small_threshold": 22,
    "small_exit": "full_tp1",
    "large_exit": "partial_trail"
  },
  "meta": {
    "win_rate_est": "55-65%",
    "rr_ratio": "1:2 / 1:3.5",
    "best_markets": "...",
    "avoid_markets": "..."
  }
}
```

---

## 6. Tiers de acceso

| Tier     | Quién tiene acceso           | Estrategias disponibles       |
|----------|------------------------------|-------------------------------|
| `base`   | Todos los suscriptores sp    | base_sasas, base_momentum, base_swing |
| `premium`| Suscriptores con plan pagado | Estrategias premium adicionales |
| `admin`  | IDs en ADMIN_CHAT_IDS        | Todas sin restricción          |

Las estrategias con `tier: "admin"` no aparecen en el menú de usuarios normales. Se usan para estrategias experimentales o en desarrollo.

---

## 7. Nuevos callbacks registrados

| Callback pattern           | Función                        | Descripción                          |
|----------------------------|--------------------------------|--------------------------------------|
| `sp_strategies`            | `sp_strategies_callback`       | Menú principal de estrategias        |
| `sp_strat_detail\|ID`      | `sp_strat_detail_callback`     | Detalle y descripción de estrategia  |
| `sp_strat_activate\|ID`    | `sp_strat_activate_callback`   | Activar estrategia                   |
| `sp_strat_deactivate`      | `sp_strat_deactivate_callback` | Desactivar estrategia activa         |

---

## 8. Bug fixes incluidos en esta versión

### Problema: "/sp no notifica al primer uso"
**Causa:** El loop solo envía cuando `can_send_signal()` devuelve True. Al suscribirse, si ya se envió una señal reciente ese par/TF, el cooldown bloquea la siguiente hasta que expire.  
**Fix:** `queue_quick_notify()` marca al usuario para recibir señal inmediata en el próximo ciclo (ignora cooldown, es un one-shot informativo).

### Botones que no funcionaban correctamente
Los 11 bugs originales ya estaban corregidos en la versión anterior del código. Los 4 nuevos callbacks SSS funcionan con el mismo patrón probado.

---

## 9. Impacto en archivos existentes

| Archivo                       | Tipo de cambio | Líneas aprox. |
|-------------------------------|----------------|---------------|
| `utils/sss_manager.py`        | **NUEVO**      | ~380          |
| `data/sss/strategies/*.json`  | **NUEVO** (×3) | ~50 c/u       |
| `utils/sp_manager.py`         | Adición        | +40           |
| `core/sp_loop.py`             | Refactor       | +100          |
| `handlers/sp_handlers.py`     | Adición        | +180          |

---

## 10. .gitignore — añadir entrada

```gitignore
# SSS — Estrategias premium (contenido de pago, no publicar)
data/sss/
```

---

## 11. Implementación futura (roadmap)

### v1.1 — Subida de estrategias por usuarios
- Comando `/sp upload` para enviar un fichero JSON
- Validación del esquema en sss_manager
- Almacenamiento en `data/sss/strategies/user_{uid}_{name}.json`
- Los admins aprueban antes de que sean visibles para todos

### v1.2 — Tracking de resultados por estrategia
- Registrar precio de entrada y niveles TP/SL al enviar señal
- Comparar precio de cierre de vela con niveles
- Estadísticas acumuladas: win rate real, PnL simulado

### v1.3 — Notificaciones de SL hit / TP hit
- Loop secundario que monitorea señales abiertas
- Compara precio actual con SL/TP de la estrategia activa
- Envía notificación: "🔴 Stop Loss alcanzado en BTC/5m — SL: $X"

### v1.4 — Estrategias por moneda/TF
- En lugar de una estrategia global, el usuario puede asignar una estrategia diferente a cada par/TF
- Almacenado como `{"BTCUSDT_5m": "base_sasas", "ETHUSDT_1h": "base_swing"}`

---

## 12. Notas técnicas

- **Hot-reload:** `sss_manager` usa `os.path.getmtime()` para detectar cambios en los ficheros JSON. Recarga automáticamente cada 60 segundos o cuando detecta modificaciones. No requiere reinicio.
- **Seguridad:** Solo se ejecuta JSON. No hay `eval()` ni importación dinámica de código Python. Las estrategias de usuario no pueden ejecutar código arbitrario.
- **Fallback gracioso:** Todo el sistema SSS está envuelto en `try/except ImportError`. Si `sss_manager.py` no existe, el bot funciona exactamente igual que antes.
- **Indicadores extendidos:** Supertrend y ASH solo se calculan cuando la estrategia activa los requiere. No hay costo computacional para usuarios sin estrategia activa.

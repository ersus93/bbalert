# 📡 Plan Técnico: Módulo SmartSignals (`/sp`)
### BitBread Alert Bot — Documento de Diseño e Implementación
**Versión:** 1.0 | **Fecha:** 2025 | **Estado:** Pre-desarrollo

---

## 1. 🎯 Visión General

**SmartSignals** es un módulo de señales de trading en tiempo real que combina análisis técnico multi-indicador con detección predictiva de patrones, alertando al usuario **entre 10 y 30 segundos antes** de que una señal de compra o venta se confirme en vela cerrada.

A diferencia de `/ta` (snapshot manual) y `/valert` (alertas de cruce de precio), SmartSignals actúa como un **radar continuo** que observa el mercado en ciclos de 45 segundos, detecta confluencia de indicadores en tiempo real, y anuncia la oportunidad con tiempo suficiente para actuar.

### Diferenciadores clave vs. módulos existentes

| Característica | `/ta` | `/valert` | `/sp` SmartSignals |
|---|---|---|---|
| Modo | Snapshot manual | Alerta de cruce de precio | **Radar continuo predictivo** |
| Ciclo | Bajo demanda | ~5 min | **45 segundos** |
| Tipo señal | Análisis actual | Precio cruza nivel | **BUY/SELL anticipado** |
| Gráfico | Estático OHLCV | No | **Predictivo con zonas** |
| Pre-aviso | No | No | **10–30s antes** |
| Acceso | Pago TA Pro | Gratuito/pago | **Exclusivo 200 ⭐** |

---

## 2. 📁 Arquitectura de Archivos (Nuevos + Modificados)

```
bbalert/
│
├── handlers/
│   └── sp_handlers.py          ← NUEVO: Comando /sp, menús, callbacks
│
├── core/
│   └── sp_loop.py              ← NUEVO: Bucle de 45s, motor de señales
│
├── utils/
│   ├── sp_manager.py           ← NUEVO: Suscripciones, estados, historial
│   └── sp_chart.py             ← NUEVO: Gráfico predictivo con zonas de entrada
│
├── handlers/
│   └── pay.py                  ← MODIFICAR: Agregar producto SP (200 ⭐)
│
└── utils/
    └── file_manager.py         ← MODIFICAR: Agregar 'sp_signals' a subscriptions
│
└── bbalert.py                  ← MODIFICAR: Registrar handlers y loop de sp
```

**Archivos que NO se tocan:** `btc_advanced_analysis.py`, `valerts_manager.py`, `chart_generator.py`, `ta.py` — solo se importan.

---

## 3. 💰 Sistema de Pago — Integración con `pay.py`

### 3.1 Nuevo Producto en la Tienda

```python
# En handlers/pay.py

PRICE_SP_SIGNALS = 200   # 200 Telegram Stars ⭐

# Agregar al diccionario products en shop_callback():
"buy_sp": {
    "title": "📡 SmartSignals Pro (30 días)",
    "description": (
        "Alertas predictivas de compra/venta con gráfico. "
        "Ciclo 45s. Pre-aviso 10-30s antes. BTC + Altcoins."
    ),
    "payload": "sub_sp_signals",
    "price": PRICE_SP_SIGNALS,
    "item_name": "📡 SmartSignals Pro"
}
```

### 3.2 Botón en el Menú de la Tienda

```python
# En shop_command(), agregar al keyboard:
[InlineKeyboardButton(f"📡 SmartSignals Pro - {PRICE_SP_SIGNALS} ⭐", callback_data="buy_sp")],
```

### 3.3 Activación en `successful_payment_callback()`

```python
elif payload == "sub_sp_signals":
    add_subscription_days(chat_id, "sp_signals", days=30)
    item_name = "📡 SmartSignals Pro"
```

### 3.4 Estructura en `file_manager.py`

Agregar `sp_signals` a la función `obtener_datos_usuario_seguro()`:

```python
# En el bloque de subscriptions:
usuario['subscriptions'] = {
    # ... existentes ...
    'sp_signals': {'active': False, 'expires': None}   # ← NUEVO
}
```

### 3.5 Función de verificación de acceso

```python
# En check_feature_access() — nuevo caso:
elif feature_type == 'sp_signals':
    if chat_id in ADMIN_CHAT_IDS:
        return True, "Admin Mode"
    sub = subs.get('sp_signals', {})
    if is_active('sp_signals'):
        return True, "OK"
    return False, "❌ SmartSignals es exclusivo para suscriptores.\nEscribe /shop para obtenerlo."
```

---

## 4. 📡 Motor de Señales — `core/sp_loop.py`

### 4.1 Ciclo Óptimo de Ejecución

Después de analizar los timeframes de Binance y el trade-off velocidad/calidad:

| Timeframe suscripción | Ciclo de loop | Justificación |
|---|---|---|
| **1m** | **45 segundos** | Captura cambios antes del cierre de vela |
| **5m** | 2 minutos | Suficiente resolución |
| **15m** | 5 minutos | Filtrar ruido |
| **1h** | 15 minutos | Señales de mayor calidad |

El **ciclo por defecto y recomendado es 45 segundos** (modo 1m y 5m activos por defecto).

### 4.2 Sistema de Scoring Multi-Indicador

La señal se genera cuando hay **confluencia de al menos 5/8 indicadores** en la misma dirección:

```
╔══════════════════════════════════════════════════════════╗
║          MOTOR DE CONFLUENCIA SmartSignals               ║
╠══════════════════════════════════════════════════════════╣
║  GRUPO 1 — MOMENTUM (peso 2x)                           ║
║  ├── RSI < 30 → BUY signal / RSI > 70 → SELL signal     ║
║  ├── Stochastic K cruza D (abajo→BUY / arriba→SELL)      ║
║  └── CCI cruzando -100/+100                              ║
║                                                          ║
║  GRUPO 2 — TENDENCIA (peso 1.5x)                        ║
║  ├── MACD histograma cambia de signo                     ║
║  ├── Precio vs EMA9, EMA20, EMA50 (alineación)           ║
║  └── ADX > 25 (tendencia fuerte confirmada)              ║
║                                                          ║
║  GRUPO 3 — VOLUMEN (peso 1.5x)                          ║
║  ├── OBV pendiente vs precio                             ║
║  └── MFI < 20 / > 80 (presión de dinero)                ║
║                                                          ║
║  GRUPO 4 — ESTRUCTURA (peso 1x)                         ║
║  ├── Bollinger Bands: precio toca banda inferior/superior║
║  ├── Soporte/Resistencia dinámica (Kijun Ichimoku)       ║
║  └── Fibonacci 0.618 — nivel actual                      ║
╠══════════════════════════════════════════════════════════╣
║  UMBRAL: ≥ 5 puntos = SEÑAL VÁLIDA                       ║
║  UMBRAL: ≥ 7 puntos = SEÑAL FUERTE                       ║
╚══════════════════════════════════════════════════════════╝
```

### 4.3 Lógica de Pre-aviso (el corazón del módulo)

La magia del módulo es anticipar la señal **antes de que la vela cierre**:

```python
class SPSignalEngine:
    
    def analyze_pre_signal(self, df: pd.DataFrame, symbol: str) -> dict:
        """
        Analiza señales en formación ANTES del cierre de vela.
        
        Técnica: Compara el estado actual (vela abierta) con el histórico de
        las últimas 3 velas cerradas. Si la confluencia está en formación,
        emite pre-alerta.
        """
        
        # 1. Velas cerradas (para indicadores confiables)
        df_closed = df.iloc[:-1]  
        
        # 2. Vela actual en formación
        current_candle = df.iloc[-1]
        
        # 3. Calcular indicadores sobre velas cerradas
        score_closed = self._calculate_score(df_closed)
        
        # 4. Proyectar indicadores con vela actual parcial
        df_with_current = df.copy()
        score_projected = self._calculate_score(df_with_current)
        
        # 5. Detectar si la confluencia está AUMENTANDO
        building_up = score_projected > score_closed
        delta = score_projected - score_closed
        
        # Tiempo restante estimado hasta cierre de vela
        time_to_close = self._estimate_time_to_candle_close(
            current_candle['open_time'], 
            self.interval
        )
        
        return {
            'score': score_projected,
            'pre_signal': building_up and delta >= 1.5,
            'time_to_close': time_to_close,  # segundos
            'is_urgent': time_to_close <= 30,
            'direction': 'BUY' if score_projected > 0 else 'SELL',
            'strength': self._classify_strength(abs(score_projected))
        }
    
    def _estimate_time_to_candle_close(self, open_time_ms, interval) -> int:
        """Calcula segundos hasta que cierra la vela actual."""
        interval_seconds = {
            '1m': 60, '3m': 180, '5m': 300, 
            '15m': 900, '1h': 3600, '4h': 14400
        }
        duration = interval_seconds.get(interval, 3600)
        elapsed = (time.time() * 1000 - open_time_ms) / 1000
        return max(0, int(duration - elapsed))
```

### 4.4 Sistema Anti-Spam y Cooldown

Para evitar fatiga de alertas:

```python
# Reglas de throttling en sp_manager.py
SIGNAL_COOLDOWN = {
    '1m':  {'min_gap': 300,   'max_day': 48},  # 5 min entre señales, máx 48/día
    '5m':  {'min_gap': 600,   'max_day': 24},
    '15m': {'min_gap': 1800,  'max_day': 12},
    '1h':  {'min_gap': 7200,  'max_day': 6},
}

# Una señal fuerte puede "resetear" el cooldown de la anterior
# del mismo tipo si la anterior fue de dirección contraria
```

---

## 5. 🖼️ Gráfico Predictivo — `utils/sp_chart.py`

El gráfico del módulo SP es diferente al de `/graf`. No es solo OHLCV histórico, sino un **gráfico de contexto + zona de acción**.

### 5.1 Componentes del Gráfico

```
╔══════════════════════════════════════════════════════════╗
║  PANEL SUPERIOR (60%) — Velas OHLCV + Indicadores       ║
║  ┌────────────────────────────────────────────────────┐  ║
║  │  [VELAS] últimas 50 velas en temporalidad elegida  │  ║
║  │  [EMA9 amarillo] [EMA20 azul] [EMA50 naranja]      │  ║
║  │  [Bollinger Bands] zona superior/inferior           │  ║
║  │  ════════════════════════════════                   │  ║
║  │  ► ZONA RESALTADA: zona de entrada sugerida        │  ║
║  │    (rectángulo verde translúcido o rojo)            │  ║
║  │  ► FLECHA en el precio actual indicando dirección  │  ║
║  └────────────────────────────────────────────────────┘  ║
║                                                          ║
║  PANEL MEDIO (20%) — RSI con zonas OB/OS               ║
║  ┌────────────────────────────────────────────────────┐  ║
║  │  RSI (14) + líneas 30/70 + valor actual destacado  │  ║
║  └────────────────────────────────────────────────────┘  ║
║                                                          ║
║  PANEL INFERIOR (20%) — MACD                           ║
║  ┌────────────────────────────────────────────────────┐  ║
║  │  MACD línea + señal + histograma coloreado          │  ║
║  │  ► Marca visual donde cruzó/está cruzando           │  ║
║  └────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════╝
```

### 5.2 Elementos Únicos del Gráfico SP

1. **Zona de entrada predicha**: Rectángulo translúcido verde (BUY) o rojo (SELL) en el rango de precio sugerido para entrar
2. **Target y Stop-Loss**: Líneas punteadas horizontales calculadas como:
   - **Target**: Próxima resistencia dinámica (R1 o EMA más cercana por arriba)
   - **Stop-Loss**: Soporte más cercano por debajo (S1 o EMA)
3. **Flecha de señal**: En la última vela, flecha grande apuntando ↑ (BUY) o ↓ (SELL)
4. **Badge de fuerza**: Texto en esquina "🔥 FUERTE" / "⚡ MODERADA" / "👀 DÉBIL"
5. **Barra de countdown**: Representación visual del tiempo hasta cierre de vela

---

## 6. 💬 Mensajes del Bot — Diseño UX

### 6.1 Mensaje de Señal (calmado pero informativo)

```
📡 SmartSignals — BTCUSDT (5m)
————————————————————

🟢 SEÑAL DE COMPRA
⚡ Fuerza: MODERADA (6/8 indicadores)

💰 Precio actual: $98,450.00
🎯 Zona de entrada: $98,200 – $98,600
🛡 Stop sugerido: $97,800 (-0.66%)
📈 Objetivo 1: $99,100 (+0.66%)
📈 Objetivo 2: $99,800 (+1.37%)

📊 Indicadores activos:
  RSI 28.4 ← Zona de sobreventa
  MACD cruzando al alza
  Stoch K cruza D (oversold)
  Bollinger toque inferior
  OBV con divergencia alcista
  CCI -112 (zona de rebote)

⏱ Vela cierra en: 23 segundos

—————————————————
💡 Esta es una señal informativa.
   Evalúa siempre el contexto del mercado.
```

### 6.2 Pre-aviso (10-30 segundos antes)

```
⚡ BitBread · Pre-señal BTCUSDT

Una señal de 🟢 COMPRA se está formando.
Cierre de vela en ~25 segundos.

Score en formación: 6.5/8
Precio: $98,450
```

### 6.3 Mensaje de bienvenida `/sp` (sin argumentos)

El comando `/sp` sin parámetros muestra un menú interactivo profesional:

```
📡 SmartSignals Pro
————————————————————

Señales de trading en tiempo real con análisis predictivo.
Recibirás alertas antes de que la señal se confirme.

🔹 Ciclo: cada 45 segundos
🔹 Pre-aviso: 10–30s antes del suceso
🔹 Incluye gráfico predictivo
🔹 Soporta BTC + 20 altcoins

Selecciona moneda y temporalidad:
[Botones de monedas]  [Botones de TF]
```

### 6.4 Uso con argumentos: `/sp BTC 5m`

Cuando se usa con argumentos, muestra directamente el snapshot de señal actual + botones para suscribirse a alertas automáticas.

---

## 7. 🎛️ Interface de Usuario — Handlers (`sp_handlers.py`)

### 7.1 Flujo del Comando `/sp`

```
Usuario escribe /sp
│
├── Sin args → Menú principal (lista de monedas con estado)
│   └── Tap moneda → Submenú de temporalidades
│       └── Tap TF → Vista de señal actual
│           ├── [🔔 Activar Alertas TF]
│           ├── [🔄 Refrescar]
│           ├── [📊 Ver Gráfico Predictivo]
│           └── [🤖 Análisis IA]
│
└── Con args /sp BTC 5m → Vista directa de señal
    ├── [🔔 Activar Alertas]
    └── [📊 Ver Gráfico]
```

### 7.2 Lista de Monedas Soportadas

Monedas disponibles en el módulo SP (ordenadas por relevancia):

```python
SP_SUPPORTED_COINS = [
    # Tier 1 — Core
    ("BTC",  "₿ Bitcoin",    "BTCUSDT"),
    ("ETH",  "⟠ Ethereum",   "ETHUSDT"),
    ("BNB",  "⬡ BNB",        "BNBUSDT"),
    ("SOL",  "◎ Solana",     "SOLUSDT"),
    ("XRP",  "✕ XRP",        "XRPUSDT"),
    # Tier 2 — Popular
    ("ADA",  "₳ Cardano",    "ADAUSDT"),
    ("AVAX", "▲ Avalanche",  "AVAXUSDT"),
    ("DOT",  "● Polkadot",   "DOTUSDT"),
    ("LINK", "⬡ Chainlink",  "LINKUSDT"),
    ("MATIC","⬡ Polygon",    "MATICUSDT"),
    # Tier 3 — Especulativo
    ("DOGE", "Ð Dogecoin",   "DOGEUSDT"),
    ("SHIB", "🐕 Shiba",     "SHIBUSDT"),
    ("PEPE", "🐸 Pepe",      "PEPEUSDT"),
]
```

### 7.3 Temporalidades Disponibles

```python
SP_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"]
# Default recomendado: 5m (mejor balance señal/ruido)
# BTC especial: también disponible 3m para scalping
```

---

## 8. 🗄️ Gestor de Datos — `utils/sp_manager.py`

### 8.1 Estructura de Archivos

```python
# Paths de datos
SP_SUBS_PATH  = os.path.join(DATA_DIR, "sp_subs.json")    # Suscripciones
SP_STATE_PATH = os.path.join(DATA_DIR, "sp_state.json")   # Estado de señales
SP_HIST_PATH  = os.path.join(DATA_DIR, "sp_history.json") # Historial de señales
```

### 8.2 Schema de `sp_subs.json`

```json
{
    "user_id_123": {
        "BTCUSDT": ["5m", "15m"],
        "ETHUSDT": ["1h"]
    }
}
```

### 8.3 Schema de `sp_state.json`

```json
{
    "BTCUSDT_5m": {
        "last_signal": "BUY",
        "last_signal_time": 1704000000,
        "last_signal_score": 6.5,
        "last_price": 98450.0,
        "cooldown_until": 1704000300,
        "daily_count": 3
    }
}
```

### 8.4 Funciones Principales

```python
def is_sp_subscribed(user_id, symbol, timeframe) -> bool
def toggle_sp_subscription(user_id, symbol, timeframe) -> bool
def get_sp_subscribers(symbol, timeframe) -> list[str]
def get_active_sp_symbols() -> list[str]
def get_sp_state(symbol, timeframe) -> dict
def update_sp_state(symbol, timeframe, signal_data) -> None
def can_send_signal(symbol, timeframe) -> bool   # Verifica cooldown
def record_signal(symbol, timeframe, signal) -> None
def get_user_sp_summary(user_id) -> dict          # Para /sp sin args
```

---

## 9. 🔑 Control de Acceso

### 9.1 Niveles de Acceso

| Usuario | Acceso |
|---|---|
| Admin (`ADMIN_CHAT_IDS`) | Acceso completo sin pago |
| Suscriptor SP (`sp_signals` activo) | Acceso completo |
| Usuario regular | Puede ver el comando, pero no activar alertas automáticas |
| Usuario sin registro | Redirigir a `/shop` |

### 9.2 Lógica de verificación en handlers

```python
async def sp_command(update, context):
    user_id = update.effective_user.id
    
    # Admins pasan directo
    if user_id not in ADMIN_CHAT_IDS:
        has_access, msg = check_feature_access(user_id, 'sp_signals')
        if not has_access:
            # Mostrar preview del módulo + botón de compra
            await show_sp_preview(update, context)
            return
    
    # Continuar con el comando...
```

---

## 10. 🔄 Bucle de Monitoreo — `core/sp_loop.py`

### 10.1 Arquitectura del Bucle

```python
async def sp_monitor_loop(bot):
    """
    Loop principal del módulo SmartSignals.
    Ciclo: 45 segundos.
    """
    add_log_line("📡 Iniciando SmartSignals Monitor...")
    
    engine = SPSignalEngine()
    
    while True:
        try:
            active_symbols = get_active_sp_symbols()
            if not active_symbols:
                await asyncio.sleep(30)
                continue
            
            for symbol_tf in active_symbols:
                symbol, tf = symbol_tf.rsplit('_', 1)
                
                # 1. Obtener datos frescos (reusar get_binance_klines de ta.py)
                df = get_binance_klines(symbol, tf, limit=100)
                if df is None or len(df) < 50:
                    continue
                
                # 2. Analizar señal
                result = engine.analyze_pre_signal(df, symbol)
                
                # 3. ¿Hay señal válida?
                if result['score_abs'] < 5:
                    continue
                    
                # 4. ¿Está en cooldown?
                if not can_send_signal(symbol, tf):
                    
                    # Pero si viene pre-aviso urgente (<30s) y hay señal fuerte,
                    # mandamos el pre-aviso aunque haya cooldown reciente
                    if result['is_urgent'] and result['score_abs'] >= 7:
                        await _send_pre_alert(bot, symbol, tf, result)
                    continue
                
                # 5. Generar y enviar señal
                subscribers = get_sp_subscribers(symbol, tf)
                if not subscribers:
                    continue
                
                # 6. Construir mensaje + gráfico
                msg = build_signal_message(symbol, tf, result, df)
                chart_buf = generate_sp_chart(df, symbol, tf, result)
                
                # 7. Enviar a todos los suscriptores
                for uid in subscribers:
                    try:
                        await bot.send_photo(
                            chat_id=int(uid),
                            photo=chart_buf,
                            caption=msg,
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=_get_sp_signal_keyboard(symbol, tf)
                        )
                        chart_buf.seek(0)  # Reset buffer para siguiente usuario
                    except Exception as e:
                        add_log_line(f"⚠️ SP send error to {uid}: {e}")
                
                # 8. Registrar señal enviada
                record_signal(symbol, tf, result)
                
        except Exception as e:
            add_log_line(f"❌ Error en sp_loop: {e}")
        
        await asyncio.sleep(45)
```

### 10.2 Sistema de Pre-aviso

```python
async def _send_pre_alert(bot, symbol, tf, result):
    """
    Pre-aviso liviano (texto, sin gráfico) cuando la señal está a <30s de confirmarse.
    """
    direction_emoji = "🟢" if result['direction'] == 'BUY' else "🔴"
    direction_text = "COMPRA" if result['direction'] == 'BUY' else "VENTA"
    
    msg = (
        f"⚡ *BitBread · Pre-señal {symbol.replace('USDT', '')}*\n"
        f"————————————————————\n\n"
        f"Una señal de {direction_emoji} *{direction_text}* se está formando.\n"
        f"Cierre de vela en aprox. *{result['time_to_close']}s*.\n\n"
        f"Score en formación: `{result['score']:.1f}/8`\n"
        f"Precio actual: `${result['price']:,.4f}`\n\n"
        f"_Espera confirmación en el cierre de vela._"
    )
    
    subscribers = get_sp_subscribers(symbol, tf)
    for uid in subscribers:
        try:
            await bot.send_message(int(uid), msg, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
```

---

## 11. 📊 Gráfico Predictivo — `utils/sp_chart.py`

### 11.1 Función Principal

```python
def generate_sp_chart(df: pd.DataFrame, symbol: str, tf: str, signal: dict) -> BytesIO:
    """
    Genera el gráfico predictivo del módulo SmartSignals.
    Basado en el motor de chart_generator.py pero especializado para señales.
    """
    fig = plt.figure(figsize=(12, 8), facecolor=TV_THEME['bg'])
    gs = GridSpec(3, 1, figure=fig, height_ratios=[3, 1, 1], hspace=0.05)
    
    ax_candles = fig.add_subplot(gs[0])  # Panel principal de velas
    ax_rsi = fig.add_subplot(gs[1])      # Panel RSI
    ax_macd = fig.add_subplot(gs[2])     # Panel MACD
    
    # === Panel de Velas ===
    _draw_candles(ax_candles, df)
    _draw_emas(ax_candles, df)
    _draw_bollinger(ax_candles, df)
    _draw_signal_zone(ax_candles, signal)     # ← EXCLUSIVO SP
    _draw_signal_arrow(ax_candles, signal)    # ← EXCLUSIVO SP
    _draw_targets(ax_candles, signal)         # ← EXCLUSIVO SP
    _draw_price_line(ax_candles, signal)
    
    # === Panel RSI ===
    _draw_rsi(ax_rsi, df)
    
    # === Panel MACD ===
    _draw_macd(ax_macd, df, signal)
    
    # === Header del gráfico ===
    direction = signal['direction']
    emoji = "🟢 COMPRA" if direction == "BUY" else "🔴 VENTA"
    fig.suptitle(
        f"📡 SmartSignals — {symbol} ({tf}) | {emoji}",
        color=TV_THEME['text'], fontsize=12, fontweight='bold'
    )
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf
```

---

## 12. 🔌 Integración en `bbalert.py`

### 12.1 Imports a agregar

```python
from handlers.sp_handlers import (
    sp_command, 
    sp_coin_callback, 
    sp_tf_callback,
    sp_toggle_callback,
    sp_refresh_callback
)
from core.sp_loop import sp_monitor_loop, set_sp_sender
```

### 12.2 Registrar handlers

```python
# En el bloque de registro de CommandHandlers:
app.add_handler(CommandHandler("sp", sp_command))

# Callbacks del módulo SP
app.add_handler(CallbackQueryHandler(sp_coin_callback,    pattern="^sp_coin\\|"))
app.add_handler(CallbackQueryHandler(sp_tf_callback,      pattern="^sp_tf\\|"))
app.add_handler(CallbackQueryHandler(sp_toggle_callback,  pattern="^sp_toggle\\|"))
app.add_handler(CallbackQueryHandler(sp_refresh_callback, pattern="^sp_refresh\\|"))
```

### 12.3 Iniciar bucle en `post_init()`

```python
# Agregar al bloque de bucles en post_init():
set_sp_sender(enviar_mensaje_telegram_async)
asyncio.create_task(sp_monitor_loop(app.bot))
logger.info("✅ Bucle SmartSignals (/sp) iniciado.")
```

---

## 13. 📋 Plan de Implementación por Fases

### FASE 1 — Fundación (Prioridad: Alta) 
**Estimado: 1 sesión**

- [ ] Crear `utils/sp_manager.py` con todas las funciones de datos
- [ ] Modificar `utils/file_manager.py` — añadir `sp_signals` a subscriptions
- [ ] Modificar `handlers/pay.py` — agregar producto SP (200 ⭐)
- [ ] Verificar que `add_subscription_days()` funciona con nuevo tipo

**Criterio de éxito:** `/shop` muestra SmartSignals, pago activa la suscripción correctamente.

---

### FASE 2 — Motor de Señales (Prioridad: Alta)
**Estimado: 1-2 sesiones**

- [ ] Crear `core/sp_loop.py` con `SPSignalEngine`
- [ ] Implementar scoring multi-indicador (grupos 1-4)
- [ ] Implementar detección de pre-señal (tiempo restante vela)
- [ ] Sistema de cooldown y anti-spam
- [ ] Tests unitarios básicos con datos históricos de BTC

**Criterio de éxito:** El engine detecta señales históricas conocidas correctamente.

---

### FASE 3 — Gráfico Predictivo (Prioridad: Media)
**Estimado: 1 sesión**

- [ ] Crear `utils/sp_chart.py` basado en `chart_generator.py`
- [ ] Implementar zona de entrada coloreada
- [ ] Agregar flechas de señal + líneas de target/SL
- [ ] Agregar badge de fuerza y countdown visual
- [ ] Tests visuales con BTC

**Criterio de éxito:** Gráfico se genera en <2s y es visualmente claro.

---

### FASE 4 — Handlers e Interface (Prioridad: Alta)
**Estimado: 1 sesión**

- [ ] Crear `handlers/sp_handlers.py` completo
- [ ] Implementar menú `/sp` interactivo con botones
- [ ] Soporte para `/sp BTC 5m` (acceso directo)
- [ ] Callbacks de suscripción/desuscripción
- [ ] Preview del módulo para usuarios sin suscripción
- [ ] Mensaje multilingüe (ES/EN)

**Criterio de éxito:** UX fluida, todos los flows funcionan sin errores.

---

### FASE 5 — Integración y Bucle (Prioridad: Alta)
**Estimado: 1 sesión**

- [ ] Registrar todo en `bbalert.py`
- [ ] Prueba del loop en vivo con 1 suscriptor
- [ ] Ajuste fino de umbrales de señal
- [ ] Prueba de pre-avisos
- [ ] Prueba de gráfico enviado como foto

**Criterio de éxito:** Bot envía señales reales con gráfico sin errores en producción.

---

### FASE 6 — Pulido y Lanzamiento (Prioridad: Media)
**Estimado: 0.5 sesiones**

- [ ] Añadir `/sp` al mensaje de `/help`
- [ ] Añadir SmartSignals al README
- [ ] Comandos de admin para ver estadísticas del módulo SP
- [ ] Panel de admin: cuántos suscriptores, señales enviadas hoy
- [ ] Mensaje de onboarding cuando el usuario activa por primera vez

---

## 14. ⚠️ Consideraciones Técnicas

### 14.1 Rate Limiting de Binance
- Binance permite ~1200 requests/min en el endpoint público
- Con 13 monedas × 5 timeframes = 65 calls/ciclo de 45s → ~87 calls/min ✅ Seguro
- Implementar exponential backoff en caso de 429

### 14.2 Concurrencia
- El loop SP es `async` como los demás, no bloquea el bot
- Envío a múltiples usuarios usa `asyncio.gather()` para paralelismo

### 14.3 Calidad de Señales
- **Señal débil (<5/8)**: No enviar, solo loggear internamente
- **Señal moderada (5-6/8)**: Enviar con disclaimer de debilidad
- **Señal fuerte (7-8/8)**: Enviar con énfasis, activar pre-aviso urgente
- **No enviar nunca en**: mercado de muy bajo volumen, fin de semana (opcional configurable)

### 14.4 Gestión de Memoria
- El historial SP se limita a las últimas 500 señales por par en `sp_history.json`
- Purga automática de señales >30 días

### 14.5 Compatibilidad con Módulos Existentes
- SmartSignals **reutiliza** `get_binance_klines()` de `ta.py` (import directo)
- SmartSignals **reutiliza** `BTCAdvancedAnalyzer` de `btc_advanced_analysis.py`
- SmartSignals **reutiliza** el tema visual de `chart_generator.py`
- NO duplica código, solo extiende la arquitectura existente

---

## 15. 🚀 Mejoras Futuras (Post v1.0)

| Feature | Descripción | Prioridad |
|---|---|---|
| **Backtesting visual** | Mostrar las últimas 10 señales y si acertaron | Alta |
| **SP Score histórico** | Estadística de precisión por moneda/TF | Media |
| **Modo scalping** | Ciclo de 15s para traders activos (+100 ⭐ extra) | Media |
| **Confirmación de señal** | Segunda alerta cuando la vela cierra confirmando | Alta |
| **Modo silencioso** | Solo resumen diario, sin alertas individuales | Baja |
| **Multi-exchange** | Señales de KuCoin, Bybit como alternativa a Binance | Baja |
| **IA integrada** | Análisis Groq automático en señales fuertes (7+/8) | Alta |

---

## 16. 📝 Resumen Ejecutivo

El módulo **SmartSignals `/sp`** se integra al ecosistema BBAlert como la capa de inteligencia proactiva de trading. Su valor diferencial respecto a los módulos existentes es el **factor tiempo**: no solo detecta señales, sino que las **anticipa** entre 10 y 30 segundos antes, dando al usuario una ventana real para actuar.

La implementación es modular (4 archivos nuevos, 3 modificados), reutiliza los componentes más maduros del proyecto (BTCAdvancedAnalyzer, chart_generator, get_binance_klines), y sigue exactamente los patrones de arquitectura del bot (loop async, manager de JSON, handlers con callbacks).

El modelo de negocio a **200 ⭐** se justifica por ser el módulo de mayor valor técnico del bot, siendo accesible solo para administradores y suscriptores de pago, lo que lo convierte en el producto premium por excelencia del ecosistema BitBread.

---

*Documento generado para el equipo de desarrollo de BitBread Alert.*
*Todos los fragmentos de código son pseudocódigo de diseño, no código de producción final.*

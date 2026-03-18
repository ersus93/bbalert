# 📋 Lista de Comandos BBAlert - Actualizado 2026

## 🎯 Comandos Principales

### 📊 Precios y Watchlist
- **`/prices`** - Gestión unificada de watchlist (ver precios, añadir, eliminar monedas)
  - `/prices` - Muestra precios actuales
  - `/prices add BTC,ETH,SOL` - Añade monedas
  - `/prices remove BTC` - Elimina monedas
  - `/prices list` - Ver lista de monedas
  - Botones interactivos inline disponibles

- **`/p <MONEDA>`** - Ver precio de una moneda específica
  - Ej: `/p BTC`, `/p ETH`
  - Incluye botones para análisis técnico y actualizar

- **`/precios`** - Alias de `/prices` (compatibilidad)

### 📈 Trading y Análisis Técnico
- **`/graf <MONEDA> [PAR] <TEMPORALIDAD>`** - Generar gráfico OHLCV profesional
  - Ej: `/graf BTC 4h`, `/graf ETH USDT 1d`
  - Temporalidades: `1m 5m 15m 30m 1h 2h 4h 6h 12h 1d 1w 1M`
  - Incluye EMAs, RSI, Bollinger Bands, niveles S/R

- **`/ta <MONEDA> [PAR] <TEMPORALIDAD>`** - Análisis técnico completo
  - Ej: `/ta BTC 4h`, `/ta SOL USDT 1d`
  - Muestra: RSI, MACD, Stoch, ADX, EMAs, Ichimoku, Fibonacci
  - Incluye señales de compra/venta con scoring

- **`/mk`** - Estado de mercados globales
  - Muestra horarios de apertura/cierre de principales bolsas
  - NY, Londres, Tokio, Hong Kong, etc.

### 🚨 Alertas de Precio
- **`/alertas`** - Gestión unificada de alertas de precio
  - `/alertas` - Ver tus alertas activas
  - `/alertas add BTC 50000` - Crear alerta
  - `/alertas remove 1` - Eliminar alerta por número
  - `/alertas clear` - Eliminar todas las alertas

- **`/misalertas`** - Alias para ver alertas

### ₿ Alertas Bitcoin (BTC)
- **`/btcalerts`** - Monitor avanzado de Bitcoin
  - Análisis pro con datos de Binance o TradingView
  - Suscripciones por temporalidad (1h, 2h, 4h, 8h, 12h, 1d, 1w)
  - Niveles dinámicos de soporte/resistencia
  - Botones para toggle de alertas y cambio de fuente

### 📡 SmartSignals (/sp) - Señales Predictivas
*Requiere suscripción Pro (200 ⭐)*

- **`/sp`** - Menú principal de SmartSignals
  - `/sp` - Abre menú interactivo
  - `/sp BTC` - Ver señal de BTC en 5m
  - `/sp ETH 1h` - Ver señal de ETH en 1h

- **`/sp_ops`** - Gestión de operaciones abiertas
  - Ver operaciones activas
  - Cerrar operaciones manualmente
  - Seguimiento de PnL

- **`/sp_alertas`** - Ver tus suscripciones de señales
- **`/sp_cleanup`** - Limpieza de operaciones (solo admin)

**Temporalidades disponibles:** `1m 5m 15m 1h 4h 1d`

### 🌤️ Clima y Alertas Meteorológicas
- **`/w <CIUDAD>`** - Consultar clima detallado
  - Ej: `/w Madrid`, `/w Buenos Aires`
  - Incluye: temperatura, humedad, viento, UV, calidad aire
  - Pronóstico de próximas horas
  - Consejos generados por IA

- **`/weather_settings`** - Configurar alertas de clima
  - Activar/desactivar alertas de lluvia, tormenta, UV, etc.
  - Configurar hora del resumen diario

- **`/wsub`** - Suscribirse a alertas climáticas
  - Recibe alertas automáticas de lluvia, tormentas, UV alto
  - Resumen diario configurable

### 💰 Monedas y Alertas HBD
- **`/hbdalerts`** - Gestión de alertas HBD
  - Ver lista de precios configurados por admin
  - Activar/desactivar suscripción personal
  - Solo admins pueden añadir/editar precios

### ⚙️ Ajustes y Configuración
- **`/ajustes`** - Menú unificado de ajustes
  - `/ajustes` - Ver configuración actual
  - `/ajustes lang es/en` - Cambiar idioma
  - `/ajustes temp 2.5` - Intervalo de alertas
  - `/ajustes monedas BTC,ETH` - Gestionar lista

- **`/lang`** - Cambiar idioma (es/en)
- **`/temp <HORAS>`** - Configurar intervalo de alertas
  - Rango: 0.5 - 24 horas
  - Límites según plan de usuario
- **`/monedas BTC,ETH,SOL`** - Gestionar lista de monedas

### 🔔 Recordatorios
- **`/rec`** - Gestión de recordatorios
  - Menú principal con lista de recordatorios
  - Crear recordatorios con fecha/hora
  - Soporta recurrencia: diaria, semanal, mensual, anual
  - Formatos de tiempo: `10m`, `2h`, `20:00`, `25/12 10:00`

### 📅 Progreso Anual
- **`/y`** - Progreso del año y frases motivacionales
  - Muestra porcentaje de avance del año
  - Frase del día
  - `/y add <frase>` - Añadir frase personalizada
  - Configurar alerta diaria con botones de hora

### 🛒 Tienda y Suscripciones
- **`/shop`** - Menú de la tienda
  - Comprar suscripciones con Telegram Stars ⭐
  - Productos disponibles:
    - 📡 SmartSignals Pro - 200 ⭐
    - 📦 Pack Control Total - 20 ⭐
    - 📈 TA Pro - 10 ⭐
    - 🪙 +1 Moneda - 5 ⭐
    - 🔔 +1 Alerta - 4 ⭐

### 👮 Comandos de Administrador
*Solo para IDs configurados en ADMIN_CHAT_IDS*

- **`/users`** - Lista de usuarios registrados
- **`/logs`** - Ver logs del sistema
- **`/set_admin`** - Configurar utilidades de admin
- **`/set_logs`** - Configurar logs
- **`/ms`** - Enviar mensaje masivo a usuarios
- **`/ad`** - Gestionar anuncios del bot
- **`/free`** - Otorgar acceso gratuito

### 🔧 Utilidades
- **`/start`** - Iniciar bot (welcome message)
- **`/myid`** - Ver tu ID de chat y datos de usuario
- **`/help`** - Menú de ayuda interactivo
  - `/help completo` - Ver todos los comandos
  - Navegación por categorías: Alertas, Trading, Clima, Ajustes

## 🎯 Comandos Deprecados/Obsoletos
*Estos comandos aún funcionan pero se recomienda usar los nuevos:*

- `/ver` → Usa `/prices`
- `/monedas` → Usa `/prices add` o `/ajustes monedas`
- `/mismonedas` → Usa `/prices list`
- `/valerts` → Usa `/sp` para señales o `/btcalerts` para BTC

## 📱 Características Destacadas

### ✅ Sistema de Suscripciones
- Plan gratuito con límites
- Planes premium con Telegram Stars
- Rate limiting por usuario
- Guardias de capacidad (monedas, alertas)

### 🌐 Internacionalización
- Soporte completo en Español (es) e Inglés (en)
- Traducciones dinámicas con gettext
- Cambio de idioma con `/lang`

### 🎨 Interfaz de Usuario
- Botones inline interactivos
- Menús contextuales
- Callbacks optimizados
- Mensajes con Markdown
- Emojis para mejor UX

### 🔄 Sistemas de Monitoreo (Background)
- Loop de precios HBD cada 2.5h (configurable)
- Loop de alertas BTC en tiempo real
- Loop SmartSignals cada 45s
- Loop de clima con resúmenes diarios
- Loop de desastres globales
- Loop de recordatorios

### 💾 Datos y Persistencia
- JSON files en `data/` y `data-example/`
- Gestión de usuarios, suscripciones, alertas
- Cache de precios para rate limiting
- Logs de actividad

## 🔧 Configuración Técnica

### Archivos de Configuración
- `core/config.py` - Variables de entorno, tokens, admins
- `requirements.txt` - Dependencias Python
- `mbot.sh` - Script de inicio
- `systemd/*.service` - Servicios systemd

### Estructura de Handlers
```
handlers/
├── general.py         - /start, /myid, /help
├── prices.py          - /prices (unificado)
├── precios.py         - /precios (alias)
├── alertas.py         - /alertas (unificado)
├── ajustes.py         - /ajustes (unificado)
├── trading.py         - /graf, /p, /mk, /ta
├── btc_handlers.py    - /btcalerts
├── sp_handlers.py     - /sp, /sp_ops, etc.
├── weather.py         - /w, /weather_settings, /wsub
├── pay.py             - /shop
├── reminders.py       - /rec
├── year_handlers.py   - /y
├── user_settings.py   - /lang, /temp, /monedas, /hbdalerts
└── valerts_handlers.py - /valerts
```

### Loops de Monitoreo (core/)
```
core/
├── loops.py              - Alertas HBD, custom alerts
├── btc_loop.py           - Monitoreo BTC
├── sp_loop.py            - SmartSignals
├── sp_trading_loop.py    - SP Trading operations
├── valerts_loop.py       - Volatility alerts
├── weather_loop_v2.py    - Alertas climáticas
├── global_disasters_loop.py - Desastres globales
├── reminders_loop.py     - Recordatorios
└── year_loop.py          - Progreso anual
```

## 📊 APIs Externas Utilizadas

- **CoinMarketCap** - Precios de criptomonedas
- **TradingView** - Análisis técnico y gráficos
- **Binance** - Datos OHLCV (velas)
- **KuCoin** - Fallback para datos
- **Bybit** - Fallback para datos
- **OpenWeatherMap** - Clima y pronóstico
- **USGS** - Desastres naturales (terremotos)
- **Groq** - Análisis con IA (clima, trading)

## 🔒 Seguridad y Rate Limiting

- Rate limiter por usuario en comandos críticos
- Validación de argumentos
- Sanitización de inputs
- Callback data validation
- Flood control anti-DoS
- Admin-only commands

## 📝 Notas de Actualización

**Última actualización:** 2026-03-18

**Cambios recientes:**
- Unificación de comandos de precios (`/prices` reemplaza `/ver`, `/monedas`)
- Unificación de alertas (`/alertas` reemplaza `/alerta`, `/valerts`, `/btcalerts` como separado)
- Introducción de SmartSignals Pro (/sp) con suscripción
- Sistema de tienda con Telegram Stars
- Mejora de handlers de clima con IA
- Sistema de recordatorios con recurrencia
- Soporte multi-idioma completo

**Próximas mejoras:**
- [ ] Comando `/trading` unificado
- [ ] Mejor integración de gráficos
- [ ] Más opciones de análisis técnico
- [ ] Alertas de noticias

---

*Para reportar errores o sugerencias, contacta al administrador.*
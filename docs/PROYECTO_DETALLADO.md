# 📚 Documentación Profesional del Proyecto BBAlert

## 📋 Índice

1. [📖 Introducción](#1-introducción)
2. [⚡ Tecnologías y Requisitos](#2-tecnologías-y-requisitos)
3. [🏗️ Arquitectura y Estructura](#3-arquitectura-y-estructura)
4. [🎯 Funcionalidades Core](#4-funcionalidades-core)
5. [🔧 Instalación y Configuración](#5-instalación-y-configuración)
6. [📁 Estructura de Archivos](#6-estructura-de-archivos)
7. [🚀 Manejo y Operaciones](#7-manejo-y-operaciones)
8. [🧩 Comandos y Handlers](#8-comandos-y-handlers)
9. [🔄 Sistemas de Alertas](#9-sistemas-de-alertas)
10. [🌐 Internacionalización (i18n)](#10-internacionalización-i18n)
11. [🛡️ Seguridad y Mejores Prácticas](#11-seguridad-y-mejores-prácticas)
12. [🔍 Depuración y Mantenimiento](#12-depuración-y-mantenimiento)
13. [❌ Solución de Problemas](#13-solución-de-problemas)
14. [📊 Monitoreo y Estadísticas](#14-monitoreo-y-estadísticas)
15. [🤝 Contribución](#15-contribución)
16. [📄 Licencia y Derechos](#16-licencia-y-derechos)
17. [🔮 Roadmap](#17-roadmap)
18. [📞 Soporte](#18-soporte)
19. [📚 Referencias Técnicas](#19-referencias-técnicas)

## 1. Introducción

### 1.1 Descripción General

**BBAlert** es un bot de Telegram multifuncional y escalable diseñado para monitoreo de criptomonedas, alertas meteorológicas y herramientas de trading. Con una arquitectura asíncrona robusta, el bot ofrece notificaciones en tiempo real, análisis técnico avanzado y gestión automatizada de múltiples servicios.

### 1.2 Objetivos Principales

- Proporcionar alertas instantáneas de precios de criptomonedas (BTC, HBD, etc.)
- Monitorizar condiciones climáticas y enviar alertas de emergencia
- Ofrecer herramientas de análisis técnico para traders
- Gestionar feeds RSS/Atom con notificaciones personalizadas
- Proporcionar un sistema de pagos integrado con Telegram Stars
- Mantenerse escalable y fácilmente extensible

## 2. Tecnologías y Requisitos

### 2.1 Stack Tecnológico

#### Lenguajes y Frameworks
- **Python 3.12+**: Lenguaje principal con características de async/await
- **python-telegram-bot v20.x**: Librería para interactuar con la API de Telegram
- **python-dotenv**: Gestión de variables de entorno
- **requests**: Consultas HTTP para APIs externas
- **Pandas**: Análisis de datos financieros
- **Pillow**: Generación de imágenes y gráficos
- **Babel**: Internacionalización (i18n)
- **pytz**: Manejo de zonas horarias
- **loguru**: Registro de eventos y depuración
- **tradingview-ta**: Análisis técnico de TradingView

#### APIs Externas
- **Telegram Bot API**: Comunicación con usuarios
- **CoinMarketCap API**: Datos de precios de criptomonedas
- **OpenWeather API**: Información meteorológica
- **Binance API**: Datos de velas BTC/USDT
- **GROQ API**: Análisis de clima con IA
- **Screenshot API**: Capturas de pantalla de TradingView

### 2.2 Requisitos de Sistema

#### Hardware
- Servidor VPS con Ubuntu/Debian (recomendado)
- Mínimo 1 GB RAM
- 20 GB de almacenamiento SSD
- Conexión a internet estable

#### Software
- Python 3.12 o superior
- Sistema de gestión de procesos systemd
- Git para control de versiones
- curl para instalación

## 3. Arquitectura y Estructura

### 3.1 Arquitectura General

El bot sigue una arquitectura modular y event-driven con los siguientes componentes principales:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Telegram Bot API                               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
            ┌──────────────▼──────────────────────┐
            │        bbalert.py (Entry Point)     │
            └──────────────┬──────────────────────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    │                      │                      │
┌───▼──────┐        ┌──────▼──────┐        ┌──────▼──────┐
│ Handlers │        │  Core Loop  │        │  Utils      │
│          │        │  Management │        │  Libraries  │
└───┬──────┘        └──────┬──────┘        └──────┬──────┘
    │                      │                      │
    │                      │                      │
┌───▼──────┐        ┌──────▼──────┐        ┌──────▼──────┐
│ Commands │        │ Async Tasks │        │ Data Access │
│ & Queries│        │ & Schedulers│        │ & Storage   │
└───┬──────┘        └──────┬──────┘        └──────┬──────┘
    │                      │                      │
    └──────────────┬───────┴──────────────────────┘
                   │
            ┌──────▼──────────┐
            │ Data Management │
            │  (JSON Files)   │
            └─────────────────┘
```

### 3.2 Patrones de Diseño Implementados

- **Dependency Injection**: Inyección de dependencias para handlers y servicios
- **Observer Pattern**: Para manejo de alertas y notificaciones
- **Singleton Pattern**: Para managers y utils
- **Command Pattern**: Para handlers de comandos Telegram
- **Async/Await**: Para operaciones concurrentes y loops de fondo


### 3.3 Arquitectura de Alertas

El sistema de alertas se basa en un diseño modular con múltiples loops concurrentes:

```
┌──────────────────────────────────────────────────────┐
│   Loop Principal (bbalert.py)                        │
├──────────────────────────────────────────────────────┤
│ ┌──────────────────────┐  ┌──────────────────────┐   │
│ │ Weather Alerts Loop  │  │ BTC Monitor Loop     │   │
│ │ (15 min interval)    │  │ (Variable interval)  │   │
│ └──────────┬───────────┘  └──────────┬───────────┘   │
│            │                         │                │
│ ┌──────────▼───────────┐  ┌──────────▼───────────┐   │
│ │ Weather API Client   │  │ Binance API Client   │   │
│ └──────────┬───────────┘  └──────────┬───────────┘   │
│            │                         │                │
│ ┌──────────▼───────────┐  ┌──────────▼───────────┐   │
│ │ Weather Manager      │  │ BTC Manager         │   │
│ └──────────┬───────────┘  └──────────┬───────────┘   │
│            │                         │                │
│ ┌──────────▼───────────┐  ┌──────────▼───────────┐   │
│ │ Alert Determination  │  │ Advanced Analysis   │   │
│ └──────────┬───────────┘  └──────────┬───────────┘   │
│            │                         │                │
│ └──────────┴─────────────────────────┘                │
│            │                                           │
│ ┌──────────▼───────────┐                              │
│ │ Message Sender       │                              │
│ └──────────┬───────────┘                              │
│            │                                           │
│ ┌──────────▼───────────┐                              │
│ │ Error Handling & Retries                              │
│ └──────────────────────┘                              │
└──────────────────────────────────────────────────────┘
```

## 4. Funcionalidades Core

### 4.1 Alertas de Criptomonedas

#### Alertas BTC
- Monitorización de niveles clave (pivot, soportes, resistencias)
- Alertas de ruptura de niveles y cambios de tendencia
- Análisis técnico avanzado (EMA, Bollinger Bands, RSI)
- Intervalos personalizables (1h, 4h, 12h, 1d)

#### Alertas HBD
- Umbrales dinámicos de precio
- Alertas de cruce de niveles configurados
- Historial completo de precios
- Suscripción por usuario

#### Alertas Personalizadas
- Configuración de alertas para cualquier criptomoneda
- Notificaciones al alcanzar precio objetivo
- Gestión de alertas activas
- Historial de alertas enviadas

### 4.2 Sistema de Clima

#### Alertas Meteorológicas
- Alertas de lluvia, tormenta, nieve, niebla
- Advertencia de calor extremo o frío intenso
- Índice UV alto
- Análisis de calidad del aire

#### Pronóstico Diario
- Envío automático de resumen diario
- Configuración de horario personalizado
- Datos detallados (temperatura, humedad, viento)
- Recomendaciones inteligentes con IA

#### Suscripciones
- Suscripción a alertas por ciudad
- Configuración de tipos de alertas
- Intervalos de notificación personalizables

### 4.3 Herramientas de Trading

#### Análisis Técnico (/ta)
- Indicadores múltiples (RSI, MACD, Bollinger Bands)
- Gráficos de TradingView
- Análisis de velas japonesas
- Recomendaciones de trading

#### Monitoreo de Mercados (/mk)
- Estado general de criptomercados
- Top 10 monedas por capitalización
- Datos en tiempo real de CoinMarketCap

#### Tasas de Cambio (/tasa)
- Tasas informales para Cuba
- Actualización automática
- Gráficos de evolución

### 4.4 Gestión de Feeds RSS/Atom

#### Configuración de Fuentes
- Añadir/eliminar fuentes RSS
- Configuración de plantillas HTML
- Filtros por palabra clave
- Monitoreo en tiempo real

#### Notificaciones Personalizadas
- Envío de noticias a usuarios suscritos
- Plantillas customizable
- Filtros de contenido

### 4.5 Sistema de Pago

#### Telegram Stars
- Integración con pagos por Telegram Stars
- Productos digitales y suscripciones
- Historial de transacciones
- Reembolsos y devoluciones

#### Gestión de Productos
- Creación de productos
- Configuración de precios
- Stock management
- Reportes de ventas

### 4.6 Administración del Sistema

#### Comandos de Admin
- Estadísticas de usuarios
- Gestión de anuncios rotativos
- Envío de mensajes masivos
- Monitoreo de logs del sistema

#### Configuración del Bot
- Ajustes de sistema
- Configuración de APIs
- Gestión de dependencias
- Backup y restauración

## 5. Instalación y Configuración

### 5.1 Instalación Rápida (Script)

```bash
# Clonar el repositorio
git clone https://github.com/ersus93/bbalert.git
cd bbalert

# Dar permisos al script
chmod +x mbot.sh

# Ejecutar instalador
./mbot.sh

# Seleccionar opción 1 para instalación completa
```

### 5.2 Configuración Manual

#### Variables de Entorno

Archivo `apit.env`:
```env
# Token del bot de Telegram
TOKEN_TELEGRAM="TU_TOKEN_DE_TELEGRAM"

# IDs de administradores (separados por comas)
ADMIN_CHAT_IDS=123456789,987654321

# APIs externas
CMC_API_KEY_ALERTA="TU_CMC_API_KEY"
CMC_API_KEY_CONTROL="TU_CMC_API_KEY_CONTROL"
SCREENSHOT_API_KEY="TU_SCREENSHOT_API_KEY"
ELTOQUE_API_KEY="TU_ELTOQUE_API_KEY"
OPENWEATHER_API_KEY="TU_OPENWEATHER_API_KEY"
GROQ_API_KEY="TU_GROQ_API_KEY"

# Opciones avanzadas
DIR_BASE="/ruta/a/tu/proyecto"
```

#### Instalación de Dependencias

```bash
# Crear entorno virtual
python3.12 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

#### Configuración del Servicio systemd

```bash
# Crear archivo de servicio
sudo nano /etc/systemd/system/bbalert.service

# Contenido del servicio:
[Unit]
Description=BBAlert Telegram Bot
After=network.target

[Service]
Type=simple
User=tu_usuario
WorkingDirectory=/ruta/a/bbalert
ExecStart=/ruta/a/bbalert/venv/bin/python3.12 /ruta/a/bbalert/bbalert.py
Restart=always
RestartSec=5
Environment=PYTHONPATH=/ruta/a/bbalert

[Install]
WantedBy=multi-user.target

# Habilitar y arrancar el servicio
sudo systemctl daemon-reload
sudo systemctl enable bbalert
sudo systemctl start bbalert
```


## 6. Estructura de Archivos

```
bbalert/
├── bbalert.py                          # Punto de entrada principal
├── mbot.sh                             # Script de gestión (v4)
├── apit.env                            # Variables de entorno
├── apit.env.example                    # Ejemplo de configuración
├── requirements.txt                    # Dependencias Python
├── babel.cfg                           # Configuración de i18n
├── version.txt                         # Versión del bot
│
├── core/                               # Núcleo del sistema
│   ├── btc_loop.py                     # Monitor BTC
│   ├── btc_advanced_analysis.py        # Análisis técnico BTC
│   ├── valerts_loop.py                 # Monitor multi-moneda PRO
│   ├── weather_loop_v2.py              # Alertas meteorológicas
│   ├── global_disasters_loop.py        # Alertas de desastres
│   ├── loops.py                        # Bucles generales (HBD, alertas)
│   ├── rss_loop_v2.py                  # Monitor RSS/Atom
│   ├── year_loop.py                    # Progreso anual
│   ├── reminders_loop.py               # Recordatorios
│   ├── i18n.py                         # Internacionalización
│   ├── config.py                       # Configuración global
│   ├── api_client.py                   # Cliente CMC API
│   ├── ai_logic.py                     # Lógica de IA
│
├── handlers/                           # Manejadores de comandos
│   ├── btc_handlers.py                 # Comandos BTC
│   ├── valerts_handlers.py             # Comandos Valerts
│   ├── weather.py                      # Comandos clima
│   ├── alerts.py                       # Alertas personalizadas
│   ├── general.py                      # Comandos generales
│   ├── admin.py                        # Comandos de administración
│   ├── user_settings.py                # Configuración usuario
│   ├── trading.py                      # Herramientas trading
│   ├── ta.py                           # Análisis técnico (/ta)
│   ├── tasa.py                         # Tasas de cambio
│   ├── pay.py                          # Sistema de pago
│   ├── reminders.py                    # Recordatorios
│   ├── year_handlers.py                # Progreso anual
│
├── utils/                              # Utilidades y managers
│   ├── btc_manager.py                  # Gestión BTC
│   ├── weather_manager.py              # Gestión clima
│   ├── valerts_manager.py              # Gestión Valerts
│   ├── file_manager.py                 # Gestión de archivos
│   ├── logger.py                       # Registro de eventos
│   ├── ads_manager.py                  # Anuncios rotativos
│   ├── image_generator.py              # Generación de imágenes
│   ├── weather_api.py                  # Cliente OpenWeather
│   ├── tv_helper.py                    # Helper TradingView
│   ├── telemetry.py                    # Monitoreo del sistema
│   ├── year_manager.py                 # Progreso anual
│   ├── reminders_manager.py            # Recordatorios
│   ├── rss_manager_v2.py               # Gestión RSS/Atom
│   ├── feed_parser_v4.py               # Parser de feeds
│   ├── global_disasters_api.py         # API desastres naturales
│
├── data/                               # Datos persistentes (JSON)
│   ├── users.json                      # Usuarios registrados
│   ├── price_alerts.json               # Alertas personalizadas
│   ├── btc_subs.json                   # Suscriptores BTC
│   ├── btc_alert_state.json            # Estado alertas BTC
│   ├── valerts_subs.json               # Suscriptores Valerts
│   ├── valerts_state.json              # Estado Valerts
│   ├── weather_subs.json               # Suscriptores clima
│   ├── weather_last_alerts.json        # Últimas alertas clima
│   ├── weather_alerts_history.json     # Historial alertas clima
│   ├── hbd_price_history.json          # Historial HBD
│   ├── hbd_thresholds.json             # Umbrales HBD
│   ├── custom_alert_history.json       # Historial alertas personalizadas
│   ├── eltoque_history.json            # Historial tasas
│   ├── last_prices.json                # Últimos precios
│   ├── ads.json                        # Anuncios
│   ├── rss_data.json                   # Datos RSS
│   ├── rss_data_v2.json                # Datos RSS v2
│   ├── events_log.json                 # Log de eventos
│   ├── img.jpg                         # Plantilla gráfica
│
├── locales/                            # Archivos de traducción
│   ├── bbalert.pot                     # Plantilla POT
│   ├── es/
│   │   └── LC_MESSAGES/
│   │       ├── bbalert.po              # Traducción ES
│   │       └── bbalert.mo              # Archivo compilado
│   └── en/
│       └── LC_MESSAGES/
│           ├── bbalert.po              # Traducción EN
│           └── bbalert.mo              # Archivo compilado
│
├── logs/                               # Registro de eventos
│   └── bbalert.log                     # Log principal
│
├── docs/                               # Documentación
│   ├── sk_ejecution.md                 # Protocolo de ejecución
│   ├── sk_translator.md                # Protocolo i18n
│   ├── sk_debug.md                     # Guía de depuración
│   ├── sk_telegram_announce.md         # Anuncios Telegram
│   └── PROYECTO_DETALLADO.md           # Este documento
│
├── systemd/                            # Configuraciones systemd
│   └── bbalert.service                 # Servicio systemd
│
├── tests/                              # Tests unitarios
│
└── scripts/                            # Scripts auxiliares
```

## 7. Manejo y Operaciones

### 7.1 Script de Gestión (mbot.sh)

El script `mbot.sh` v4 es la interfaz principal para la gestión del bot:

```bash
# Ejecutar script
./mbot.sh

# Menú principal:
┌───────────────────────────────────────────┐
│ GESTOR MULTI-BOT DE TELEGRAM (BBAlert v4) │
├───────────────────────────────────────────┤
│ 1. 🛠️ Instalación completa                │
│ 2. ▶️ Iniciar bot                        │
│ 3. ⏹️ Detener bot                        │
│ 4. 🔄 Reiniciar bot                      │
│ 5. 📊 Ver estado                        │
│ 6. 📜 Ver logs                          │
│ 7. 📥 Instalar dependencias              │
│ 8. 🗑️ Eliminar dependencias              │
│ 9. 💾 Backup completo                    │
│10. 🔧 Configurar bot                     │
│11. ❌ Salir                              │
└───────────────────────────────────────────┘
```

### 7.2 Comandos Systemd

```bash
# Ver estado del servicio
sudo systemctl status bbalert

# Ver logs en tiempo real
sudo journalctl -u bbalert -f

# Reiniciar servicio
sudo systemctl restart bbalert

# Detener servicio
sudo systemctl stop bbalert

# Habilitar servicio al inicio
sudo systemctl enable bbalert
```

### 7.3 Backup y Restauración

#### Crear Backup
```bash
# Mediante script
./mbot.sh  # Opción 9

# Manualmente
cd /home/$USER
tar -czf bbalert_backup_$(date +%Y%m%d).tar.gz bbalert/data bbalert/logs bbalert/apit.env
```

#### Restaurar Backup
```bash
# Descomprimir
tar -xzf bbalert_backup_20251210.tar.gz

# Restaurar datos
cp -r bbalert/data /ruta/a/bbalert/
cp -r bbalert/logs /ruta/a/bbalert/
cp bbalert/apit.env /ruta/a/bbalert/

# Reiniciar bot
sudo systemctl restart bbalert
```

## 8. Comandos y Handlers

### 8.1 Comandos Generales

| Comando | Descripción | Ámbito |
|---------|-------------|--------|
| `/start` | Iniciar bot, detectar idioma | Usuario |
| `/myid` | Obtener ID de Telegram | Usuario |
| `/help` | Ayuda general | Usuario |
| `/lang` | Cambiar idioma (ES/EN) | Usuario |
| `/ver` | Ver versión del bot | Usuario |

### 8.2 Comandos Criptomonedas

| Comando | Descripción | Ámbito |
|---------|-------------|--------|
| `/btcalerts` | Suscripción a alertas BTC | Usuario |
| `/hbdalerts` | Suscripción a alertas HBD | Usuario |
| `/alerta` | Crear alerta personalizada | Usuario |
| `/misalertas` | Ver alertas activas | Usuario |
| `/monedas` | Configurar monedas a monitorear | Usuario |
| `/mismonedas` | Ver monedas configuradas | Usuario |
| `/parar` | Detener alertas | Usuario |
| `/temp` | Intervalo de alertas (horas) | Usuario |

### 8.3 

## 9. Sistemas de Alertas

### 9.1 Alertas BTC

#### Funcionamiento
```
1. Obtener velas BTC/USDT desde Binance
2. Calcular niveles clave (pivot, S1-S3, R1-R3)
3. Analizar tendencia y patrones de velas
4. Detectar ruptura de niveles
5. Enviar notificacion a suscriptores
```

#### Niveles Calculados
- **Pivot Point**: Punto de equilibrio (PP = (H + L + C)/3)
- **Resistencias**: R1 = (2*PP) - L, R2 = PP + (H - L), R3 = H + 2*(PP - L)
- **Soportes**: S1 = (2*PP) - H, S2 = PP - (H - L), S3 = L - 2*(H - PP)

#### Indicadores Utilizados
- RSI (14 periodos)
- EMA (20 y 50 periodos)
- Bollinger Bands
- MACD (12, 26, 9)
- Volume Profile

### 9.2 Alertas Clima

#### Tipos de Alertas
```python
ALERT_TYPES = {
    "rain": {"emoji": "🌧️", "threshold": 0.3, "cooldown": 4},
    "storm": {"emoji": "⛈️", "threshold": 0.2, "cooldown": 3},
    "uv_high": {"emoji": "☀️", "threshold": 6, "cooldown": 12},
    "temp_high": {"emoji": "🔥", "threshold": 35, "cooldown": 8},
    "temp_low": {"emoji": "❄️", "threshold": 5, "cooldown": 8},
}
```

#### Logic Flow
```
1. Verificar suscriptores activos
2. Obtener datos meteorologicos para cada ciudad
3. Analizar condiciones actuales y pronostico
4. Determinar si se cumplen condiciones de alerta
5. Verificar cooldown y duplicados
6. Enviar notificacion
7. Marcar alerta como enviada
```

### 9.3 Alertas Personalizadas

#### Método de Funcionamiento
```
1. Usuario configura alerta: /alerta BTC 50000
2. Datos almacenados en price_alerts.json
3. Loop periodico verifica precios
4. Cuando precio alcanza objetivo
5. Enviar notificacion y marcar como completada
6. Registrar en custom_alert_history.json
```

## 10. Internacionalización (i18n)

### 10.1 Sistema de Traducción

El bot implementa i18n con gettext y soporta dos idiomas:

- **Español (es)**: Idioma principal (texto fuente)
- **Inglés (en)**: Traducción completa

### 10.2 Funcionamiento de la Traducción

```python
from core.i18n import _

# Uso básico
mensaje = _("Hola mundo", chat_id=123456789)

# Para texto fijo (no dependiente de usuario)
texto_fijo = _("Texto en español", chat_id=None)
```

### 10.3 Actualización de Traducciones

```bash
# Extraer strings
pybabel extract -F babel.cfg -o locales/bbalert.pot .

# Actualizar archivos .po (es)
pybabel update -i locales/bbalert.pot -d locales -l es

# Compilar a .mo
pybabel compile -d locales

# Para inglés:
pybabel init -i locales/bbalert.pot -d locales -l en
```

## 11. Seguridad y Mejores Prácticas

### 11.1 Protección de Datos Sensibles

#### Variables de Entorno
- **Nunca hardcodear credenciales**
- Usar `apit.env` para todas las credenciales
- Incluir `apit.env` en `.gitignore`
- Variables sensibles: `TOKEN_TELEGRAM`, `ADMIN_CHAT_IDS`, `API_KEYS`

#### Validación de Entrada
```python
from telegram import Update
from telegram.ext import ContextTypes

async def procesar_datos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    datos = context.args
    
    # Validar entrada
    if not datos or len(datos) < 2:
        await update.message.reply_text("Formato incorrecto")
        return
    
    # Sanitizar entrada
    coin = datos[0].upper()
    try:
        price = float(datos[1])
    except ValueError:
        await update.message.reply_text("Precio inválido")
        return
    
    # Procesar
    await procesar_alerta(user_id, coin, price)
```

### 11.2 Mejores Prácticas

#### Configuración del Servidor
- Usar SSH con clave pública
- Desactivar acceso root directo
- Configurar firewall con ufw
- Actualizar sistema regularmente

#### Código Seguro
- Validar todas las entradas
- Manejar errores adecuadamente
- No exponer datos internos al usuario
- Usar HTTPS para todas las conexiones


## 12. Depuración y Mantenimiento

### 12.1 Logs del Sistema

#### Ubicación
```
/var/log/journal/  # systemd journal
/home/USER/bbalert/logs/bbalert.log  # Log interno
```

#### Comandos Útiles
```bash
# Ver logs en tiempo real
journalctl -u bbalert -f

# Ver últimos 100 líneas
journalctl -u bbalert -n 100

# Filtrar por nivel
journalctl -u bbalert -p err

# Guardar logs en archivo
journalctl -u bbalert -o short -n 500 > bbalert_errors.txt
```

### 12.2 Monitoreo de Recursos

```bash
# Uso de CPU/RAM
top -p $(pgrep -f python)

# Uso de disco
df -h

# Estado de red
netstat -tuln

# Ver proceso del bot
ps aux | grep bbalert.py
```

### 12.3 Mantenimiento Regular

#### Actualización del Bot
```bash
# Método 1: Git Pull
cd /home/USER/bbalert
git pull
./mbot.sh  # Reiniciar bot

# Método 2: Reinstalación Limpia
cd /home/USER
rm -rf bbalert
git clone https://github.com/ersus93/bbalert.git
cd bbalert
chmod +x mbot.sh
./mbot.sh
```

## 13. Solución de Problemas

### 13.1 Problemas Comunes

#### Error 1: "ModuleNotFoundError"
**Causa**: Dependencias no instaladas o venv no activado
**Solución**:
```bash
# Mediante script
./mbot.sh  # Opción 7

# Manualmente
cd /home/USER/bbalert
source venv/bin/activate
pip install -r requirements.txt
```

#### Error 2: "Token inválido"
**Causa**: Token incorrecto o bot no activo
**Solución**:
1. Verificar `apit.env`: TOKEN_TELEGRAM="tu_token"
2. Confirmar bot está activo en @BotFather
3. Reiniciar servicio

#### Error 3: "API rate limit exceeded"
**Causa**: Demasiadas consultas en corto tiempo
**Solución**:
1. Aumentar intervalo de consultas
2. Usar API keys alternativas
3. Implementar caché local
4. Verificar límite de API del proveedor

#### Error 4: "Connection timed out"
**Causa**: Problemas de red o API no disponible
**Solución**:
1. Verificar conectividad
2. Comprobar status de APIs externas
3. Aumentar tiempo de timeout
4. Configurar proxies si es necesario

### 13.2 Diagnóstico de Fallos

#### Comprobar Estado del Bot
```bash
# Ver status del servicio
sudo systemctl status bbalert

# Ver logs del sistema
journalctl -u bbalert -n 20

# Ver proceso
ps aux | grep python
```

#### Testear Conexión API
```bash
# CoinMarketCap
curl -H "X-CMC_PRO_API_KEY: TU_KEY" \
  "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest" | head -20

# OpenWeather
curl "https://api.openweathermap.org/data/2.5/weather?q=Havana&appid=TU_KEY"
```

## 14. Monitoreo y Estadísticas

### 14.1 Métricas Clave

#### Usuarios
- Total de usuarios
- Usuarios activos (últimos 30 días)
- Suscripciones por servicio
- Tasa de retención

#### Alertas
- Alertas enviadas diarias
- Tasa de entrega
- Tiempo de respuesta medio
- Errores en envío

#### Rendimiento
- Uptime del servicio
- Tiempo de respuesta
- Uso de CPU/RAM
- Consumo de APIs

## 15. Contribución

### 15.1 Proceso de Contribución

```
1. Fork del repositorio
2. Crear una rama feature/[nombre]
3. Realizar cambios
4. Escribir tests correspondientes
5. Enviar Pull Request
6. Esperar review
7. Ajustar según comentarios
8. Merge a main
```

### 15.2 Estándares de Código

#### Nomenclatura
- **Variables**: snake_case
- **Funciones**: snake_case
- **Clases**: CamelCase
- **Módulos**: snake_case


#### Comentarios
```python
def calcular_niveles_btc(precios):
    """
    Calcula niveles de pivot, soporte y resistencia para BTC
    
    Args:
        precios: Lista de precios [high, low, close]
        
    Returns:
        Diccionario con niveles calculados
    """
    pp = (precios[0] + precios[1] + precios[2]) / 3
    r1 = 2 * pp - precios[1]
    r2 = pp + (precios[0] - precios[1])
    r3 = precios[0] + 2 * (pp - precios[1])
    s1 = 2 * pp - precios[0]
    s2 = pp - (precios[0] - precios[1])
    s3 = precios[1] - 2 * (precios[0] - pp)
    
    return {
        "pp": pp, "r1": r1, "r2": r2, "r3": r3,
        "s1": s1, "s2": s2, "s3": s3
    }
```

## 16. Licencia y Derechos

### 16.1 Licencia MIT

El proyecto está bajo la **licencia MIT**, que permite:

- Uso comercial
- Modificación
- Distribución
- Uso privado

### 16.2 Restricciones

- No renunciar a la autoría original
- No responsabilizar al autor por daños
- Incluir la licencia en todas las distribuciones

## 17. Roadmap

### Versión Actual (v1.1.7) - Completado
- ✅ Alertas BTC avanzadas
- ✅ Alertas HBD con umbrales dinámicos
- ✅ Sistema de clima inteligente
- ✅ Feeds RSS/Atom personalizados
- ✅ Pago con Telegram Stars
- ✅ Análisis técnico (/ta)
- ✅ Recordatorios y progreso anual
- ✅ Alertas de desastres naturales

### Versión Siguiente (v2.x) - En Desarrollo
- ⏳ Integración con más exchanges
- ⏳ Sistema de pago con HIVE Blockchain
- ⏳ Panel web de administración
- ⏳ API REST para integraciones
- ⏳ Soporte para más idiomas

### Futuro (v3.x)
- ⏳ Microservicios independientes
- ⏳ Dockerización completa
- ⏳ Base de datos PostgreSQL
- ⏳ Caché distribuido Redis
- ⏳ Integración con AI avanzada

## 18. Soporte

### 18.1 Canal Oficial
- **Telegram Channel**: @bbalertchannel
- **Grupo de Soporte**: @bbalertsupport
- **GitHub Issues**: github.com/ersus93/bbalert/issues
- **Email**: soporte@bbalert.com

### 18.2 Reportar Problemas

#### Información Requerida
- Versión del bot: /start
- Sistema operativo: lsb_release -a
- Python version: python3 --version
- Log del error: journalctl -u bbalert -n 50
- Paso a reproducir

#### Plantilla de Issue
```
## Descripción del Problema
Breve descripción del problema

## Paso a Reproducir
1. Abrir bot
2. Escribir comando /alerta BTC 50000
3. Recibir error: "Precio inválido"

## Versión
- Bot: v1.1.7
- OS: Ubuntu 22.04 LTS
- Python: 3.13.0
- Telegram: Bot API 7.5

## Logs
Pegar los logs relevantes (sin datos sensibles)
```

## 19. Referencias Técnicas

### 19.1 APIs y Servicios

#### CoinMarketCap
- **Endpoint**: https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest
- **Documentación**: coinmarketcap.com/api/documentation/v1/
- **Límite**: 333 requests/min

#### OpenWeather
- **Endpoint**: https://api.openweathermap.org/data/2.5/weather
- **Documentación**: openweathermap.org/api
- **Límite**: 60 requests/min (free tier)

#### Binance
- **Endpoint**: https://api.binance.com/api/v3/klines
- **Documentación**: binance-docs.github.io/apidocs/spot/en/
- **Límite**: 1200 requests/min

### 19.2 Librerías Importantes

#### python-telegram-bot
- **Documentación**: python-telegram-bot.readthedocs.io
- **Versión**: v20.x
- **Características**: Async, ConversationHandlers, JobQueue

#### Pandas
- **Documentación**: pandas.pydata.org
- **Uso**: Análisis de series temporales
- **Métodos**: DataFrame, rolling, resample

#### Babel
- **Documentación**: babel.pocoo.org
- **Uso**: Internacionalización y localización
- **Comandos**: pybabel extract, update, compile

---


## 📚 Anexos Técnicos

### A. Estructura de Datos JSON

#### users.json
```json
{
  "123456789": {
    "nombre": "Nombre Usuario",
    "username": "@username",
    "idioma": "es",
    "fecha_registro": "2025-12-10T12:00:00",
    "intervalo_alerta_h": 2.5,
    "hbd_alerts_enabled": true,
    "monedas": ["BTC", "ETH", "HIVE"]
  }
}
```

#### price_alerts.json
```json
{
  "123456789": {
    "BTC": {
      "price": 50000,
      "target": "above",
      "active": true,
      "created": "2025-12-10T12:00:00"
    }
  }
}
```

#### weather_subs.json
```json
{
  "123456789": {
    "ciudad": "Havana",
    "country_code": "CU",
    "alertas": ["rain", "storm", "uv_high"],
    "summary_time": "07:00",
    "timezone": "America/Havana"
  }
}
```

### B. Diagramas de Flujo

#### Flujo de Alerta BTC
```
[Inicio]
    │
    ▼
[Obtener Velas] → [Calcular Niveles]
    │                    │
    ▼                    ▼
[Detectar Ruptura] ← [Comparar con Anterior]
    │
    ▼
[Enviar Notificación]
    │
    ▼
[Actualizar Estado]
    │
    ▼
  [Fin]
```

#### Flujo de Alerta Clima
```
[Inicio Loop]
    │
    ▼
[Verificar Suscriptores]
    │
    ▼
[Obtener Datos Clima]
    │
    ▼
[Analizar Condiciones]
    │
    ├─────► [Lluvia Detectada] ───────┐
    │                                    ▼
    ├─────► [Tormenta Detectada] ──────┼────► [Enviar Alerta]
    │                                    │            │
    ├─────► [UV Alto Detectado] ───────┘            ▼
    │                                            [Actualizar Estado]
    │                                                   │
    ▼                                                   ▼
[Esperar Intervalo] ◄──────────────────────────────────┘
```

### C. Referencias Rápidas

#### Intervalos de Loop
| Loop | Intervalo | Descripción |
|------|-----------|-------------|
| BTC Monitor | Variable | Según temporalidad (1h, 4h, 12h, 1d) |
| Weather Alerts | 15 min | Verificación de alertas meteorológicas |
| HBD Alert | 5 min | Alertas de precio HBD |
| RSS Check | 10 min | Monitoreo de feeds RSS |
| Reminders | 1 min | Verificación de recordatorios |

#### Límites de APIs
| API | Límite | Plan |
|-----|--------|------|
| CoinMarketCap | 333 req/min | Free |
| OpenWeather | 60 req/min | Free |
| Binance | 1200 req/min | Public |
| Telegram Bot | 30 msg/sec | Default |

### D. Glosario de Términos

| Término | Descripción |
|---------|-------------|
| **Handler** | Función que procesa comandos o callbacks |
| **Loop** | Bucle asíncrono de monitoreo continuo |
| **Manager** | Clase que gestiona datos y lógica de negocio |
| **Callback** | Función ejecutada al presionar un botón |
| **Webhook** | Método de recepción de actualizaciones |
| **Polling** | Consulta periódica a la API de Telegram |
| **Cooldown** | Período de espera entre alertas similares |

---

## 🎯 Guía Rápida de Uso

### Para Usuarios Finales

1. **Iniciar Bot**: Enviar `/start` al bot
2. **Ver Precio**: `/p BTC` - Ver precio actual de Bitcoin
3. **Clima**: `/w Habana` - Consultar clima de una ciudad
4. **Alerta Personalizada**: `/alerta BTC 50000` - Crear alerta
5. **Ayuda**: `/help` - Ver todos los comandos disponibles

### Para Administradores

1. **Ver Usuarios**: `/users` - Estadísticas de usuarios
2. **Ver Logs**: `/logs` - Logs del sistema
3. **Mensaje Masivo**: `/ms` - Enviar mensaje a todos los usuarios
4. **Gestionar Anuncios**: `/ad add [texto]` - Añadir anuncio rotativo

---

## 📊 Flujo de Trabajo de Desarrollo

### Fase 1: Investigación
- Identificar requisitos del feature
- Mapear archivos afectados
- Verificar dependencias

### Fase 2: Planificación
- Crear Issue en GitHub
- Definir estructura de datos
- Planificar tests

### Fase 3: Implementación
- Crear rama feature/[nombre]
- Implementar código
- Escribir tests unitarios

### Fase 4: Internacionalización
- Extraer strings con pybabel
- Traducir a idiomas soportados
- Compilar archivos .mo

### Fase 5: Pruebas
- Ejecutar tests
- Verificar integración
- Realizar QA manual

### Fase 6: Despliegue
- Merge a rama principal
- Actualizar versión
- Reiniciar servicio en VPS

---

## 🔐 Checklist de Seguridad

### Antes de Commit
- [ ] No incluir credenciales en el código
- [ ] Verificar .gitignore actualizado
- [ ] Revisar logs por datos sensibles
- [ ] Validar entrada de usuarios
- [ ] Manejar errores adecuadamente

### Antes de Despliegue
- [ ] Variables de entorno configuradas
- [ ] Dependencias instaladas
- [ ] Tests pasan exitosamente
- [ ] Archivos i18n compilados
- [ ] Backup de datos realizado

### Operaciones Diarias
- [ ] Verificar logs de errores
- [ ] Monitorizar uso de recursos
- [ ] Verificar estado de APIs externas
- [ ] Revisar alertas pendientes

---

**📚 Documentación Generada con ❤️ para BBAlert**  
**Autor**: Ersus  
**Versión**: v1.1.7  
**Última Actualización**: 2025-03-03  
**Licencia**: MIT

---

**Enlaces Rápidos**:
- [Repositorio GitHub](https://github.com/ersus93/bbalert)
- [Canal Telegram](https://t.me/bbalertchannel)
- [Documentación Completa](./PROYECTO_DETALLADO.md)


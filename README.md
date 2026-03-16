# 🤖 BitBread Alert (BBAlert)

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.2.0-orange.svg)](version.txt)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4.svg)](https://t.me/bbalertchannel)

**Bot de Telegram Multifuncional para Criptomonedas, Clima y Trading**

[📖 Documentación Completa](./docs/PROYECTO_DETALLADO.md) • [🚀 Instalación Rápida](#-instalación-rápida) • [📋 Comandos](#-comandos-principales) • [🔧 Configuración](#-configuración)

</div>

---

## 📋 Tabla de Contenidos

- [✨ Características](#-características)
- [🚀 Instalación Rápida](#-instalación-rápida)
- [🔧 Configuración](#-configuración)
- [📋 Comandos Principales](#-comandos-principales)
- [🏗️ Arquitectura](#️-arquitectura)
- [📁 Estructura del Proyecto](#-estructura-del-proyecto)
- [🛡️ Seguridad](#️-seguridad)
- [🤝 Contribución](#-contribución)
- [📄 Licencia](#-licencia)
- [📞 Soporte](#-soporte)

---

## ✨ Características

### 🔔 Sistema de Alertas Multiplataforma
- **Alertas BTC**: Monitoreo de niveles clave (pivot, soportes/resistencias) con análisis técnico avanzado
- **Alertas HBD**: Umbrales dinámicos de precio para HIVE Dollar
- **Alertas Personalizadas**: Configuración de límites de precio para cualquier criptomoneda
- **Alertas Clima**: Notificaciones de lluvia, tormenta, UV alto, calor/frío extremo

### 📊 Herramientas de Trading
- Análisis técnico avanzado (`/ta`) con indicadores múltiples (RSI, MACD, Bollinger Bands)
- Gráficos automáticos desde TradingView (`/graf`)
- Monitoreo de mercados globales (`/mk`)
- Tasas de cambio informal para Cuba (`/tasa`)
- SmartSignals (`/sp`): Señales predictivas de trading con análisis técnico avanzado

### 🌐 Características Adicionales
- **Multi-idioma**: Español e Inglés (i18n con gettext/Babel)
- **Sistema de Pagos**: Integración con Telegram Stars
- **Feeds RSS/Atom**: Monitoreo de noticias personalizado
- **Recordatorios**: Sistema de recordatorios programados
- **Progreso Anual**: Seguimiento del avance del año

---

## 🚀 Instalación Rápida

### Prerrequisitos
- Servidor VPS con Ubuntu/Debian (recomendado)
- Python 3.12 o superior
- Git

### Instalación Automatizada (Recomendada)

```bash
# 1. Clonar repositorio
git clone https://github.com/ersus93/bbalert.git
cd bbalert

# 2. Configurar permisos
chmod +x mbot.sh

# 3. Ejecutar instalador
./mbot.sh

# 4. Seleccionar opción 1 (Instalación Completa)
```

### Instalación Manual

```bash
# 1. Clonar y entrar al directorio
git clone https://github.com/ersus93/bbalert.git
cd bbalert

# 2. Crear entorno virtual
python3.12 -m venv venv
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp apit.env.example apit.env
nano apit.env  # Editar con tus credenciales

# 5. Iniciar bot
python bbalert.py
```

---

## 🔧 Configuración

### Variables de Entorno

Crear archivo `apit.env`:

```env
# Credenciales Telegram (obligatorio)
TOKEN_TELEGRAM="TU_TOKEN_DE_BOTFATHER"
ADMIN_CHAT_IDS="123456789,987654321"

# APIs Externas
CMC_API_KEY_ALERTA="TU_CMC_API_KEY"
CMC_API_KEY_CONTROL="TU_CMC_API_KEY"
OPENWEATHER_API_KEY="TU_OPENWEATHER_KEY"
GROQ_API_KEY="TU_GROQ_KEY"
ELTOQUE_API_KEY="TU_ELTOQUE_KEY"
SCREENSHOT_API_KEY="TU_SCREENSHOT_KEY"
```

### Configuración del Bot en Telegram

1. Buscar **@BotFather** en Telegram
2. Enviar `/newbot`
3. Seguir instrucciones para nombre y username
4. Guardar el token proporcionado
5. Configurar comandos del bot:
   ```
   start - Iniciar bot
   help - Ayuda general
   btcalerts - Alertas BTC
   hbdalerts - Alertas HBD
   alerta - Crear alerta personalizada
   w - Consultar clima
   ta - Análisis técnico
   p - Precio de cripto
   mk - Mercados globales
   shop - Tienda
   sp - SmartSignals
   ```

---

## 📋 Comandos Principales

### 👤 Usuario

| Comando | Descripción |
|---------|-------------|
| `/start` | Iniciar bot y detectar idioma |
| `/help` | Mostrar ayuda general |
| `/myid` | Obtener tu ID de Telegram |
| `/lang` | Cambiar idioma (ES/EN) |
| `/ver` | Ver versión del bot |

### 💰 Criptomonedas

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `/p [moneda]` | Precio actual | `/p BTC` |
| `/ta [par]` | Análisis técnico | `/ta BTCUSDT` |
| `/graf [par] [tf]` | Gráfico TradingView | `/graf BTCUSDT 1h` |
| `/mk` | Estado de mercados | - |
| `/tasa` | Tasas de cambio Cuba | - |
| `/sp [moneda] [tf]` | SmartSignals | `/sp BTC 4h` |
| `/btcalerts` | Gestionar alertas BTC | - |
| `/hbdalerts` | Gestionar alertas HBD | - |
| `/alerta [moneda] [precio]` | Crear alerta | `/alerta BTC 50000` |
| `/misalertas` | Ver alertas activas | - |
| `/monedas [lista]` | Configurar monedas | `/monedas BTC,ETH,HIVE` |
| `/parar` | Detener alertas | - |
| `/temp [horas]` | Intervalo alertas | `/temp 2.5` |

### 🌤️ Clima

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `/w [ciudad]` | Clima actual | `/w Havana` |
| `/weather_sub` | Suscribirse a alertas | - |
| `/weather_settings` | Configurar alertas | - |

### 🛠️ Administración (Solo Admins)

| Comando | Descripción |
|---------|-------------|
| `/users` | Estadísticas de usuarios |
| `/logs` | Ver logs del sistema |
| `/ad [add/del/list]` | Gestionar anuncios |
| `/ms` | Envío masivo de mensajes |

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    Telegram Bot API                     │
└───────────────────────────┬─────────────────────────────┘
                            │
              ┌─────────────▼────────────────┐
              │      bbalert.py (Entry)      │
              └─────────────┬────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼─────┐      ┌──────▼──────┐      ┌────▼─────┐
   │ Handlers │      │ Core Loops  │      │  Utils   │
   └────┬─────┘      └──────┬──────┘      └────┬─────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                   ┌────────▼─────────┐
                   │  JSON Storage    │
                   └──────────────────┘
```

### Tecnologías Principales

- **Python 3.12+** con Async/Await
- **python-telegram-bot v20.x** para API de Telegram
- **Pandas** para análisis de datos
- **Babel** para internacionalización
- **Systemd** para gestión de servicios

---

## 📁 Estructura del Proyecto

```
bbalert/
├── bbalert.py                    # Punto de entrada principal
├── mbot.sh                       # Script de gestión (TUI)
├── apit.env.example              # Plantilla de variables de entorno
├── babel.cfg                     # Configuración i18n/gettext
├── requirements.txt              # Dependencias Python
├── update_version.py             # Utilidad de versión
│
├── core/                         # Lógica central y loops
│   ├── btc_loop.py               # Monitor BTC
│   ├── weather_loop_v2.py        # Alertas clima
│   ├── sp_loop.py                # Motor SmartSignals
│   ├── valerts_loop.py           # Multi-moneda PRO
│   ├── loops.py                  # Bucles generales
│   ├── reminders_loop.py         # Recordatorios
│   ├── year_loop.py              # Progreso anual
│   ├── global_disasters_loop.py  # Desastres globales
│   ├── ai_logic.py               # Lógica IA
│   ├── api_client.py             # Clientes API
│   ├── btc_advanced_analysis.py  # Análisis avanzado BTC
│   ├── config.py                 # Configuración
│   └── i18n.py                   # Internacionalización
│
├── handlers/                     # Comandos Telegram
│   ├── btc_handlers.py           # Alertas BTC
│   ├── weather.py                # Clima
│   ├── trading.py                # Trading (/ta, /graf)
│   ├── sp_handlers.py            # SmartSignals (/sp)
│   ├── alerts.py                 # Alertas personalizadas
│   ├── valerts_handlers.py       # Multi-moneda
│   ├── admin.py                  # Administración
│   ├── general.py                # Comandos generales
│   ├── pay.py                    # Pagos (Telegram Stars)
│   ├── feed_parser_v4.py         # Feeds RSS/Atom
│   ├── reminders.py              # Recordatorios
│   ├── user_settings.py          # Configuración usuario
│   ├── ta.py                     # Análisis técnico
│   ├── tasa.py                   # Tasas Cuba
│   └── year_handlers.py          # Progreso anual
│
├── utils/                        # Utilidades
│   ├── btc_manager.py            # Gestión BTC
│   ├── weather_manager.py        # Gestión clima
│   ├── weather_api.py            # API OpenWeatherMap
│   ├── sp_manager.py             # Gestor SmartSignals
│   ├── sp_chart.py               # Gráficos predictivos
│   ├── valerts_manager.py        # Gestión multi-moneda
│   ├── tasa_manager.py           # Tasas de cambio
│   ├── cadeca_scraper.py         # Scraping CADECA
│   ├── bcc_scraper.py            # Scraping BCC
│   ├── file_manager.py           # Operaciones JSON
│   ├── logger.py                 # Logging (loguru)
│   ├── ads_manager.py            # Gestión de anuncios
│   ├── reminders_manager.py      # Gestión recordatorios
│   ├── chart_generator.py        # Generador de gráficos
│   ├── image_generator.py        # Generador de imágenes
│   ├── tv_helper.py              # Helper TradingView
│   ├── global_disasters_api.py   # API desastres
│   ├── year_manager.py           # Gestión año
│   └── telemetry.py              # Telemetría
│
├── data-example/                 # Plantillas de datos
│   ├── users.json.example
│   ├── price_alerts.json.example
│   ├── btc_alert_state.json.example
│   ├── hbd_thresholds.json.example
│   ├── weather_subs.json.example
│   └── ... (más ejemplos)
│
├── data/                         # Datos persistentes (runtime)
│   ├── users.json
│   ├── price_alerts.json
│   ├── weather_subs.json
│   └── ... (archivos de datos)
│
├── locales/                      # Traducciones (i18n)
│   ├── bbalert.pot               # Plantilla
│   ├── texts.py                  # Textos comunes
│   ├── es/LC_MESSAGES/           # Español
│   │   ├── bbalert.po
│   │   └── bbalert.mo
│   └── en/LC_MESSAGES/           # Inglés
│       ├── bbalert.po
│       └── bbalert.mo
│
├── docs/                         # Documentación
│   ├── PROYECTO_DETALLADO.md     # Documentación completa
│   ├── MANUAL_SETUP.md           # Instalación manual
│   ├── WORKFLOW.md               # Flujo de trabajo
│   └── WebApp/                   # Planificación WebApp
│       └── PLAN_WEBAPP_BBALERT.md
│
├── plans/                        # Planes de desarrollo
│   ├── PLAN_SMARTSIGNALS_SP.md
│   ├── code-improvement-plan.md
│   ├── i18n-translation-implementation-plan.md
│   └── ... (más planes)
│
├── scripts/                      # Scripts de despliegue
│   ├── deploy-prod.sh
│   └── deploy-staging.sh
│
├── systemd/                      # Unidades systemd
│   ├── README.md
│   ├── bbalert-prod.service
│   └── bbalert-staging.service
│
└── tests/                        # Tests automatizados
    ├── test_command_tracking_integration.py
    ├── test_reminders_recurring.py
    ├── test_users_dashboard.py
    └── ... (más tests)
```

**Archivos ignorados** (`.gitignore`):
- `apit.env` — credenciales reales
- `data/` — datos de runtime
- `logs/` — logs de ejecución
- `version.txt` — versión local
- `__pycache__/`, `*.pyc` — caché Python

---

## 🛡️ Seguridad

### Checklist de Seguridad

- ✅ **Nunca** hardcodear credenciales
- ✅ Usar `apit.env` para variables sensibles
- ✅ Incluir `apit.env` en `.gitignore`
- ✅ Validar todas las entradas de usuario
- ✅ Manejar errores adecuadamente
- ✅ Usar HTTPS para todas las conexiones

### Buenas Prácticas

```bash
# Configurar firewall
sudo ufw allow OpenSSH
sudo ufw enable

# Desactivar acceso root
sudo nano /etc/ssh/sshd_config
# PermitRootLogin no

# Actualizar sistema regularmente
sudo apt update && sudo apt upgrade -y
```

---

## 🤝 Contr

## 🤝 Contribución

### Flujo de Trabajo (6 Fases)

1. **Investigación**: Analizar requisitos y archivos afectados
2. **Planificación**: Crear Issue en GitHub con plan detallado
3. **Implementación**: Desarrollar en rama `feature/nombre`
4. **i18n**: Actualizar traducciones si hay texto visible
5. **Pruebas**: Tests unitarios y QA manual
6. **Despliegue**: Merge, versión y reinicio en VPS

### Estándares de Código

- **Variables/Funciones**: `snake_case`
- **Clases**: `CamelCase`
- **Comentarios**: Docstrings obligatorios
- **Tests**: Obligatorios para nuevas funcionalidades

```bash
# Crear rama feature
git checkout -b feature/nueva-funcionalidad dev

# Commits convencionales
# tipo(ámbito): descripción (#IssueID)
git commit -m "feat(btc): agregar indicador MACD (#23)"
```

---

## 📄 Licencia

Este proyecto está bajo la licencia **MIT**.

```
MIT License

Copyright (c) 2025 Ersus

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## 📞 Soporte

### Canales Oficiales

- 📱 **Canal Telegram**: [@bbalertchannel](https://t.me/bbalertchannel)
- 💬 **Grupo Soporte**: [@bbalertsupport](https://t.me/bbalertsupport)
- 🐙 **GitHub Issues**: [github.com/ersus93/bbalert/issues](https://github.com/ersus93/bbalert/issues)
- 📧 **Email**: soporte@bbalert.com

### Reportar Problemas

Al reportar un issue, incluir:
- Versión del bot (`/ver`)
- Sistema operativo (`lsb_release -a`)
- Versión Python (`python3 --version`)
- Logs relevantes (`journalctl -u bbalert -n 50`)
- Pasos para reproducir el problema

---

## 🔮 Roadmap

### ✅ Completado (v1.2.0)
- Alertas BTC avanzadas
- Sistema de clima inteligente
- Alertas HBD dinámicas
- Pagos con Telegram Stars
- Feeds RSS/Atom
- Análisis técnico (/ta)
- SmartSignals (/sp) - Señales predictivas de trading

### ⏳ En Desarrollo (v2.x)
- Integración con más exchanges
- Panel web de administración
- API REST
- Soporte para más idiomas

### 🔮 Futuro (v3.x)
- Microservicios
- Docker completo
- PostgreSQL
- Redis caché

---

<div align="center">

**⭐ Si te gusta este proyecto, dale una estrella en GitHub!**

[📖 Documentación Completa](./docs/PROYECTO_DETALLADO.md) • [🐛 Reportar Issue](https://github.com/ersus93/bbalert/issues) • [💡 Sugerencias](https://github.com/ersus93/bbalert/discussions)

---

**Desarrollado con ❤️ por [Ersus](https://github.com/ersus93)**

</div>

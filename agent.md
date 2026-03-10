# BBAlert - Agentes de Desarrollo

## Visión General
6 agentes especializados que asisten en el desarrollo, mantenimiento y evolución del proyecto BBAlert.

---

## Agentes

### 1. crypto-analyst
**Propósito:** Análisis y gestión de funcionalidades relacionadas con criptomonedas
- Alertas BTC (pivotes, soportes, resistencias)
- Alertas HBD dinámicas  
- Precios de criptomonedas
- Tasas de cambio informales (Cuba)
- Estados y subscripciones

**Archivos principales:**
- `handlers/btc_handlers.py`
- `handlers/alerts.py`
- `utils/btc_manager.py`
- `utils/tasa_manager.py`
- `data/valerts_*.json`

**Herramientas:** python-telegram-bot, CoinMarketCap API, TradingView

---

### 2. trading-expert
**Propósito:** Análisis técnico y señales de trading
- Comandos `/ta`, `/sp`, `/graf`
- Indicadores técnicos (RSI, MACD, Bollinger Bands)
- SmartSignals - señales predictivas
- Gráficos automáticos desde TradingView
- Mercados globales

**Archivos principales:**
- `handlers/trading.py`
- `handlers/sp_handlers.py`
- `core/sp_loop.py`
- `utils/sp_manager.py`
- `utils/sp_chart.py`
- `utils/tv_helper.py`

**Herramientas:** pandas, TradingView API, análisis técnico

---

### 3. weather-specialist
**Propósito:** Sistema de alertas climáticas
- Clima actual y pronósticos
- Alertas de lluvia, tormentas, UV, temperatura extrema
- Suscripciones por ciudad
- Historial de alertas

**Archivos principales:**
- `handlers/weather.py`
- `core/weather_loop_v2.py`
- `utils/weather_manager.py`
- `utils/weather_api.py`
- `data/weather_*.json`

**Herramientas:** OpenWeatherMap API

---

### 4. devops-agent
**Propósito:** Infraestructura y operaciones
- Testing (pytest, coverage)
- Linting y type checking
- Scripts de despliegue (`mbot.sh`, deploy-*.sh)
- Servicios systemd
- Gestión de dependencias
- Configuración (requirements.txt, apit.env)

**Archivos principales:**
- `requirements.txt`
- `mbot.sh`
- `scripts/deploy-*.sh`
- `systemd/*.service`

**Herramientas:** pytest, mypy, flake8, systemd, Git

---

### 5. docs-agent
**Propósito:** Documentación y localización
- Documentación del proyecto (README, docs/)
- Internacionalización (i18n)
- Traducciones (locales/es/, locales/en/)
- Archivos POT
- Mensajes del bot

**Archivos principales:**
- `README.md`
- `docs/`
- `locales/`
- `locales/texts.py`
- `babel.cfg`

**Herramientas:** Babel, gettext, Sphinx (opcional)

---

### 6. feature-builder (Coordinador)
**Propósito:** Gestión del ciclo de vida de nuevas funcionalidades
- Recibir ideas del usuario
- Analizar y expandir la idea
- Consultar con otros agentes relevantes
- Proponer mejoras y alternativas
- Crear plan de implementación
- Coordinar con agentes para implementación

**Flujo de trabajo:**
```
1. Usuario presenta idea
2. feature-builder analiza alcance
3. Consulta agentes domain (crypto, trading, weather)
4. Propone mejoras y alternativas
5. Usuario selecciona enfoque
6. Crea plan de implementación (plans/)
7. Coordina implementación con agentes correspondientes
```

**Habilidades requeridas:**
- context-driven-development
- brainstorming
- writing-plans

---

## Cómo Usar los Agentes

### Agregar nueva funcionalidad
1. Contactar a `feature-builder` con la idea
2. El agente analizará y consultará a otros
3. Recibirás propuestas mejoradas
4. Approbar diseño
5. Plan de implementación creado

### Mantenimiento específico
- ¿Problema con precios BTC? → `crypto-analyst`
- ¿Mejora en análisis técnico? → `trading-expert`
- ¿Nueva alerta climática? → `weather-specialist`
- ¿Testing o despliegue? → `devops-agent`
- ¿Traducciones o docs? → `docs-agent`

---

## Configuración de Contexto

Cada agente debe tener acceso a:
- Estructura del proyecto (tree.md)
- README.md y docs/WORKFLOW.md
- Requirements.txt
- Versión actual (version.txt)

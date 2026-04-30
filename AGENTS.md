# AGENTS.md — Guía para agentes de BBAlert

## Comandos de desarrollo

```bash
# Ejecutar CLI interactivo
python bbalert.py

# Forzar skill inicial
python bbalert.py --skill <nombre>

# Estado del asistente
python bbalert.py --status

# Tests
pytest -v
```

## Entorno y dependencias

- **Python**: 3.12
- **Dependencias**: `python-telegram-bot`, `python-dotenv`, `httpx`, `requests`, `unidecode`
- **Instalar**: `pip install -r requirements.txt`

## Estructura del proyecto

```
bbalert/
├── bbalert.py          # CLI principal
├── bot.py              # Bot de Telegram
├── config.yaml         # Configuración general
├── skills/             # Skills en markdown
├── memory/             # Memoria persistente (facts.md, pinned.md)
├── core/               # Lógica del asistente
├── handlers/           # Handlers de comandos
├── utils/              # Utilidades (skill_loader, memory_writer)
└── tests/              # Tests pytest
```

## Configuración obligatoria

**Variables de entorno requeridas** (`.env`):
- `TELEGRAM_TOKEN` — Token del bot de Telegram
- `CMC_API_KEY_CONTROL` — API key de CoinMarketCap para control
- `CMC_API_KEY_ALERTA` — API key de CoinMarketCap para alertas
- `GROQ_API_KEYS` — API keys de Groq (separadas por comas)
- `ADMIN_IDS` — IDs de administradores (separados por comas)

```bash
# Setup rápido
cp .env.example .env
# Editar .env con las credenciales
```

## Arquitectura

- **Stack**: Flask + SQLAlchemy + PostgreSQL + Jinja2 + TailwindCSS
- **Patrón**: Hexagonal (dominio / aplicación / infraestructura)
- **Separación estricta**: NUNCA poner lógica en las rutas

## Convenciones de código

- **Python**: `snake_case` funciones/variables, `PascalCase` clases
- **Docstrings**: en español para módulos propios
- **Type hints**: en funciones públicas
- **Línea**: máximo 120 caracteres
- **Commits**: formato `tipo(scope): descripción` (feat, fix, refactor, docs, test, chore)

## Skills

Los skills son playbooks en `skills/*.md`. Se activan:
- **Automático**: por keywords en `config.yaml`
- **Manual**: `/skill <nombre>`

**Skills disponibles**: `github-workflow`, `code-review`, `debug-session`, `daily-standup`, `project-planning`

## Testing

- Framework: pytest
- Comandos: `pytest -v` o `pytest tests/`
- Fixtures en `tests/conftest.py`

## Notas importantes

- **Entorno de desarrollo/local**: Windows 10/11, Python 3.12, bot NO desplegado localmente
- **Producción**: El bot está desplegado en un VPS (ver `deployment/` para scripts)
- **DataLab** es el proyecto principal (ver `CONTEXT.md`)
- La migración activa es Bootstrap 5 → Liquid Glass Design System
- El archivo `memory/pinned.md` es permanente y se inyecta en cada sesión

## Agentes (bot de Telegram)

El bot tiene un sistema de agentes especializados definidos en `handlers/agents.py`:
- `general` — IA General (sin documentos locales)
- `bitbread` — Soporte del sistema y configuraciones
- `iso17025` — Normativas ONARC/ONIE y laboratorios

Usar `/agents` en el bot para cambiar de agente.

## Monedas y Precios

### Comandos disponibles
- `/prices` - Muestra precios de tu lista de monedas
- `/prices add BTC,ETH` - Añade monedas a tu lista
- `/prices remove BTC` - Elimina monedas de tu lista
- `/prices lista` - Muestra tu lista guardada

### Indicadores de movimiento
Los mensajes de precios muestran indicadores visuales de cambio:
- 📈 Subida (precio actual > precio anterior)
- 📉 Bajada (precio actual < precio anterior)
- ➖ Sin cambio o primera consulta

### Almacenamiento
- Las listas de monedas se guardan en Redis
- Los precios se obtienen de CoinMarketCap API
- Cache de precios para optimizar llamadas a la API
# BBAlert - Project Context

## Project Overview

**BBAlert** is a multi-functional Telegram bot for cryptocurrency monitoring, weather alerts, and trading tools. Built with Python 3.12+ and python-telegram-bot v20.x, it provides real-time notifications, advanced technical analysis, and automated multi-service management.

### Core Features
- **Cryptocurrency Alerts**: BTC pivot/support/resistance monitoring, HBD dynamic thresholds, custom price alerts
- **Trading Tools**: Technical analysis (`/ta`), TradingView charts (`/graf`), SmartSignals (`/sp`), market overview (`/mk`), Cuba exchange rates (`/tasa`)
- **Weather Alerts**: Rain, storms, high UV, extreme temperature notifications via OpenWeatherMap API
- **Additional**: RSS/Atom feeds, reminders, annual progress tracking, Telegram Stars payments

### Tech Stack
- **Language**: Python 3.12+ (async/await)
- **Framework**: python-telegram-bot v20.x
- **Data**: Pandas, pandas_ta for financial analysis
- **i18n**: Babel/gettext (Spanish & English)
- **Logging**: loguru
- **APIs**: CoinMarketCap, OpenWeatherMap, Binance, GROQ, TradingView

---

## Building and Running

### Prerequisites
- Python 3.12 or higher
- Linux VPS (Ubuntu/Debian recommended) or Windows for development
- Telegram Bot Token (from @BotFather)

### Installation

#### Automated (Recommended for Linux)
```bash
git clone https://github.com/ersus93/bbalert.git
cd bbalert
chmod +x mbot.sh
./mbot.sh  # Select option 1 for full installation
```

#### Manual
```bash
# Clone repository
git clone https://github.com/ersus93/bbalert.git
cd bbalert

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp apit.env.example apit.env
# Edit apit.env with your credentials

# Run bot
python bbalert.py
```

### Configuration (apit.env)
```env
TOKEN_TELEGRAM="your_bot_token"
ADMIN_CHAT_IDS="123456789,987654321"
CMC_API_KEY_ALERTA="your_cmc_key"
OPENWEATHER_API_KEY="your_openweather_key"
GROQ_API_KEY="your_groq_key"
ELTOQUE_API_KEY="your_eltoque_key"
SCREENSHOT_API_KEY="your_screenshot_key"
```

### Development Commands
```bash
# Run tests (if available)
pytest

# Check code style
flake8 .
mypy .

# View logs
journalctl -u bbalert -f  # Production (systemd)
tail -f logs/bbalert.log  # Development

# Restart bot (systemd)
sudo systemctl restart bbalert
```

---

## Development Conventions

### Code Style
- **Naming**: `snake_case` for variables/functions, `CamelCase` for classes
- **Docstrings**: Required for all public functions/classes
- **Type Hints**: Encouraged for function signatures
- **Error Handling**: Use try/except with proper logging via `logger`

### Architecture Patterns
- **Modular Design**: Handlers (`handlers/`), Core Logic (`core/`), Utilities (`utils/`)
- **Async-First**: All I/O operations use async/await
- **Dependency Injection**: Bot/app instances passed to handlers
- **Singleton Pattern**: For managers (e.g., `btc_manager`, `weather_manager`)
- **Observer Pattern**: For alert notifications

### File Organization
```
bbalert/
├── bbalert.py              # Entry point, bot initialization
├── mbot.sh                 # Bash TUI for bot management
├── apit.env                # Environment variables (gitignored)
├── requirements.txt        # Python dependencies
│
├── core/                   # Core business logic
│   ├── btc_loop.py         # BTC price monitoring loop
│   ├── weather_loop_v2.py  # Weather alerts loop
│   ├── sp_loop.py          # SmartSignals engine
│   ├── valerts_loop.py     # Multi-currency alerts
│   ├── config.py           # Configuration loader
│   └── i18n.py             # Internationalization
│
├── handlers/               # Telegram command handlers
│   ├── btc_handlers.py     # BTC alert commands
│   ├── weather.py          # Weather commands
│   ├── trading.py          # /ta, /graf, /mk commands
│   ├── sp_handlers.py      # SmartSignals commands
│   ├── alerts.py           # Custom price alerts
│   └── admin.py            # Admin-only commands
│
├── utils/                  # Utility modules
│   ├── btc_manager.py      # BTC data processing
│   ├── weather_manager.py  # Weather data handling
│   ├── sp_manager.py       # SmartSignals logic
│   ├── logger.py           # Logging configuration
│   └── file_manager.py     # JSON file operations
│
├── data/                   # Persistent JSON storage (gitignored)
│   ├── users.json
│   ├── price_alerts.json
│   └── weather_subs.json
│
├── locales/                # i18n translations
│   ├── es/                 # Spanish
│   └── en/                 # English
│
└── docs/                   # Documentation
    └── PROYECTO_DETALLADO.md
```

### Testing Practices
- Tests located in `tests/` directory (gitignored)
- Use `pytest` for unit tests
- Mock external APIs using `unittest.mock`
- Run tests before committing: `pytest tests/`

### Git Workflow
```bash
# Create feature branch
git checkout -b feature/new-feature dev

# Conventional commits
# format: type(scope): description (#IssueID)
git commit -m "feat(btc): add MACD indicator (#23)"
git commit -m "fix(weather): resolve UV alert bug (#45)"
git commit -m "docs(readme): update installation steps"

# Types: feat, fix, docs, style, refactor, test, chore
```

### i18n (Internationalization)
- All user-facing text must use `_()` from `core.i18n`
- Update translations in `locales/es/LC_MESSAGES/messages.po`
- Generate POT file: `pybabel extract -F babel.cfg -o locales/messages.pot .`
- Update translations: `pybabel update -i locales/messages.pot -d locales`
- Compile: `pybabel compile -d locales`

### Key Design Principles
1. **Async-First**: Use `async def` for all handlers and loops
2. **Error Resilience**: Wrap API calls in try/except, log errors, continue execution
3. **Data Persistence**: Store user data in JSON files under `data/`
4. **Modular Loops**: Each alert type runs in independent async loop
5. **Admin Separation**: Admin commands restricted via `ADMIN_CHAT_IDS` check

---

## Agent System

This project uses a **6-agent development system** (see `agent.md`):

| Agent | Purpose |
|-------|---------|
| **crypto-analyst** | BTC/HBD alerts, price monitoring, exchange rates |
| **trading-expert** | Technical analysis, SmartSignals, TradingView charts |
| **weather-specialist** | Weather alerts, forecasts, subscriptions |
| **devops-agent** | Testing, deployment, systemd, scripts |
| **docs-agent** | Documentation, i18n, translations |
| **feature-builder** | Coordinates new feature lifecycle |

### Using Agents
- **New feature**: Start with `feature-builder` → coordinates with domain agents
- **Bug fix**: Contact relevant domain agent (crypto, trading, weather)
- **Deployment**: `devops-agent` for scripts, systemd, CI/CD
- **Translations**: `docs-agent` for i18n updates

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `bbalert.py` | Bot entry point, handler registration, loop initialization |
| `core/config.py` | Environment variable loader, path configuration |
| `core/i18n.py` | Translation system (`_()` function) |
| `utils/logger.py` | Loguru-based logging system |
| `utils/file_manager.py` | JSON file read/write utilities |
| `mbot.sh` | Interactive bash TUI for bot management |
| `requirements.txt` | Python dependencies |
| `apit.env.example` | Environment variable template |

---

## Common Tasks

### Add New Command
1. Create handler in `handlers/your_command.py`
2. Register in `bbalert.py` with `CommandHandler`
3. Add i18n strings to `locales/texts.py`
4. Update translations in `locales/*/LC_MESSAGES/messages.po`

### Add New Alert Type
1. Create manager in `utils/` for data handling
2. Create loop in `core/` for monitoring
3. Create handler in `handlers/` for user commands
4. Register loop in `bbalert.py post_init()`

### Debug Issues
```bash
# Check bot status
systemctl status bbalert

# View recent logs
journalctl -u bbalert -n 50

# Test configuration
python -c "from core.config import *; print(TOKEN_TELEGRAM)"

# Run in foreground for debugging
python bbalert.py
```

---

## Version Management
- Version stored in `version.txt` (gitignored)
- Use `update_version.py` script to bump versions
- Version displayed via `/ver` command
- Format: `MAJOR.MINOR.PATCH` (e.g., `1.2.0`)

---

## Security Notes
- **Never** commit `apit.env` or `data/` files
- All API keys loaded from environment variables
- Admin commands restricted to `ADMIN_CHAT_IDS`
- Input validation on all user commands
- HTTPS enforced for all external API calls

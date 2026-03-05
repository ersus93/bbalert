# BBAlert - Estructura del Proyecto

Actualizado: 2026-03-05

```
.
├── .github/
│   └── PULL_REQUEST_TEMPLATE.md
├── .gitignore
├── apit.env.example              # Plantilla de variables de entorno
├── babel.cfg                     # Configuración para i18n/gettext
├── bbalert.py                    # Punto de entrada principal del bot
├── LICENSE
├── mbot.sh                       # Script de gestión del bot (v4)
├── README.md
├── requirements.txt
├── update_version.py             # Utilidad para bump de versión
├── version.txt.example           # Plantilla de version.txt local
│
├── core/                         # Lógica central y loops
│   ├── __init__.py
│   ├── ai_logic.py
│   ├── api_client.py
│   ├── btc_advanced_analysis.py
│   ├── btc_loop.py
│   ├── config.py
│   ├── global_disasters_loop.py
│   ├── i18n.py
│   ├── loops.py
│   ├── reminders_loop.py
│   ├── valerts_loop.py
│   ├── weather_loop_v2.py
│   └── year_loop.py
│
├── data-example/                 # Plantillas de datos (sin datos reales)
│   ├── ads.json.example
│   ├── btc_alert_state.json.example
│   ├── btc_subs.json.example
│   ├── custom_alert_history.json.example
│   ├── eltoque_history.json.example
│   ├── hbd_price_history.json.example
│   ├── hbd_thresholds.json.example
│   ├── last_prices.json.example
│   ├── price_alerts.json.example
│   ├── users.json.example
│   ├── weather_last_alerts.json.example
│   └── weather_subs.json.example
│
├── docs/                         # Documentación y notas de planificación
│   ├── MANUAL_SETUP.md
│   ├── PROYECTO_DETALLADO.md
│   ├── WORKFLOW.md
│   ├── sk_debug.md
│   ├── sk_ejecution.md
│   ├── sk_telegram_announce.md
│   ├── sk_translator.md
│   ├── WebApp/                   # Planificación de la WebApp
│   │   ├── ISSUES_006_014.md
│   │   ├── ISSUE_001_setup_fastapi.md
│   │   ├── ISSUE_002_auth_jwt.md
│   │   ├── ISSUE_003_endpoints_lectura.md
│   │   ├── ISSUE_004_endpoints_escritura.md
│   │   ├── ISSUE_005_dashboard_frontend.md
│   │   └── PLAN_WEBAPP_BBALERT.md
│   └── mutil/                    # Notas de trabajo / brainstorming
│       ├── planwather.md
│       ├── weather_api.md
│       ├── weather_daily_summary_loop_notes.md
│       └── weather_loop_v2.md
│
├── handlers/                     # Manejadores de comandos Telegram
│   ├── __init__.py
│   ├── admin.py
│   ├── alerts.py
│   ├── btc_handlers.py
│   ├── feed_parser_v4.py
│   ├── general.py
│   ├── pay.py
│   ├── reminders.py
│   ├── ta.py
│   ├── tasa.py
│   ├── trading.py
│   ├── user_settings.py
│   ├── valerts_handlers.py
│   ├── weather.py
│   └── year_handlers.py
│
├── locales/                      # Internacionalización (i18n)
│   ├── bbalert.pot               # Plantilla de traducciones
│   ├── texts.py
│   ├── en/LC_MESSAGES/
│   │   ├── bbalert.mo            # Binario compilado (msgfmt)
│   │   └── bbalert.po            # Fuente de traducciones EN
│   └── es/LC_MESSAGES/
│       ├── bbalert.mo            # Binario compilado (msgfmt)
│       └── bbalert.po            # Fuente de traducciones ES
│
├── plans/                        # Planes de desarrollo
│   ├── code-improvement-plan.md
│   ├── fix-users-dashboard-v2.md
│   ├── git-workflow-plan.md
│   ├── i18n-translation-implementation-plan.md
│   ├── merge-dev-to-main-plan.md
│   ├── tasa-image-optimization-plan.md
│   └── update-version-fix-plan.md
│
├── scripts/                      # Scripts de despliegue
│   ├── deploy-prod.sh
│   └── deploy-staging.sh
│
├── systemd/                      # Unidades systemd para producción
│   ├── README.md
│   ├── bbalert-prod.service
│   └── bbalert-staging.service
│
├── tests/                        # Tests automatizados
│   ├── test_command_tracking_integration.py
│   ├── test_reminders_recurring.py
│   ├── test_reminders_sorting.py
│   ├── test_telemetry.py
│   ├── test_users_dashboard.py
│   └── test_valerts_antispam.py
│
└── utils/                        # Utilidades y módulos de apoyo
    ├── __init__.py
    ├── ads_manager.py
    ├── bcc_scraper.py
    ├── btc_manager.py
    ├── cadeca_scraper.py
    ├── chart_generator.py
    ├── file_manager.py
    ├── global_disasters_api.py
    ├── image_generator.py
    ├── logger.py
    ├── reminders_manager.py
    ├── tasa_manager.py
    ├── telemetry.py
    ├── tv_helper.py
    ├── valerts_manager.py
    ├── weather_api.py
    ├── weather_manager.py
    └── year_manager.py
```

## Archivos ignorados por .gitignore (no en repo)
- `apit.env` — credenciales reales
- `data/` — datos de runtime (usuarios, alertas, historiales)
- `logs/` — logs de ejecución
- `version.txt` — versión local de cada entorno
- `__pycache__/`, `*.pyc` — caché de Python
- `.pytest_cache/` — caché de pytest

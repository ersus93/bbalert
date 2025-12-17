.
├── apit.env
├── babel.cfg
├── bbalert.py
├── bbalertv3.sh
├── bba.sh
├── core
│   ├── api_client.py
│   ├── btc_advanced_analysis.py
│   ├── btc_loop.py
│   ├── config.py
│   ├── global_disasters_loop.py
│   ├── i18n.py
│   ├── __init__.py
│   ├── loops.py
│   ├── rss_loop_v2.py
│   ├── valerts_loop.py
│   └── weather_loop_v2.py
├── data
│   ├── ads.json
│   ├── btc_alert_state.json
│   ├── btc_subs.json
│   ├── custom_alert_history.json
│   ├── eltoque_history.json
│   ├── hbd_price_history.json
│   ├── hbd_thresholds.json
│   ├── hive_accounts.json
│   ├── hive_invoices.json
│   ├── hive_payments.json
│   ├── img.png
│   ├── last_prices.json
│   ├── price_alerts.json
│   ├── rss_data.json
│   ├── rss_data_v2.json
│   ├── rss_data_v2.json.backup
│   ├── users.json
│   ├── valerts_state.json
│   ├── valerts_subs.json
│   ├── weather_alerts_history.json
│   ├── weather_alerts_log.json
│   ├── weather_last_alerts.json
│   └── weather_subs.json
├── handlers
│   ├── admin.py
│   ├── alerts.py
│   ├── btc_handlers.py
│   ├── general.py
│   ├── __init__.py
│   ├── pay.py
│   ├── trading.py
│   ├── user_settings.py
│   ├── valerts_handlers.py
│   └── weather.py
├── LICENSE
├── locales
│   ├── bbalert.pot
│   ├── en
│   │   └── LC_MESSAGES
│   │       ├── bbalert.mo
│   │       └── bbalert.po
│   ├── es
│   │   └── LC_MESSAGES
│   │       ├── bbalert.mo
│   │       └── bbalert.po
│   └── texts.py
├── logs
│   └── bbalert.log
├── README.md
├── requirements.txt
├── utils
   ├── ads_manager.py
   ├── btc_manager.py
   ├── content_filter.py
   ├── feed_parser_v4.py
   ├── file_manager.py
   ├── global_disasters_api.py
   ├── image_generator.py
   ├── __init__.py
   ├── instagram_scraper.py
   ├── logger.py
   ├── rss_generator.py
   ├── rss_manager_v2.py
   ├── tv_helper.py
   ├── valerts_manager.py
   ├── weather_api.py
   ├── weather_manager.py
   └── web_scraper.py
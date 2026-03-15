# locales/texts.py

HELP_MSG = {
    "es": (
        "📚 *Ayuda Rápida*\n\n"
        "Selecciona una categoría:\n\n"
        "_Usa /help completo para ver todos los comandos_"
    ),
    "en": (
        "📚 *Quick Help*\n\n"
        "Select a category:\n\n"
        "_Use /help full to see all commands_"
    )
}

HELP_CATEGORIES = {
    "es": {
        "help_alerts": (
            "🚨 *Alertas*\n\n"
            "/alerta MONEDA PRECIO - Crear\\nalerta\n"
            "/misalertas - Ver tus alertas\n"
            "/monedas BTC,ETH - Configurar lista\n"
            "/temp 2.5 - Intervalo de alertas\n"
            "/parar - Detener alertas\n\n"
            "[← Volver]"
        ),
        "help_trading": (
            "📊 *Trading*\n\n"
            "/p BTC - Ver precio\n"
            "/ta BTCUSDT - Análisis técnico\n"
            "/graf BTC 1h - Gráfico\n"
            "/mk - Mercados globales\n"
            "/sp BTC 4h - SmartSignals\n\n"
            "[← Volver]"
        ),
        "help_weather": (
            "🌤️ *Clima*\n\n"
            "/w Madrid - Clima actual\n"
            "/weather_settings - Configurar alertas\n\n"
            "[← Volver]"
        ),
        "help_settings": (
            "⚙️ *Ajustes*\n\n"
            "/lang - Cambiar idioma\n"
            "/shop - Tienda\n"
            "/myid - Tu ID de Telegram\n\n"
            "[← Volver]"
        ),
        "help_all": (
            "📋 *Todos los Comandos*\n\n"
            "Usa /help para ver ayuda por categorías.\n\n"
            "[← Volver a categorías]"
        )
    },
    "en": {
        "help_alerts": (
            "🚨 *Alerts*\n\n"
            "/alerta SYMBOL PRICE - Create\\nalert\n"
            "/misalertas - View your alerts\n"
            "/monedas BTC,ETH - Set watchlist\n"
            "/temp 2.5 - Alert interval\n"
            "/parar - Stop alerts\n\n"
            "[← Back]"
        ),
        "help_trading": (
            "📊 *Trading*\n\n"
            "/p BTC - Check price\n"
            "/ta BTCUSDT - Technical analysis\n"
            "/graf BTC 1h - Chart\n"
            "/mk - Global markets\n"
            "/sp BTC 4h - SmartSignals\n\n"
            "[← Back]"
        ),
        "help_weather": (
            "🌤️ *Weather*\n\n"
            "/w Madrid - Current weather\n"
            "/weather_settings - Configure alerts\n\n"
            "[← Back]"
        ),
        "help_settings": (
            "⚙️ *Settings*\n\n"
            "/lang - Change language\n"
            "/shop - Store\n"
            "/myid - Your Telegram ID\n\n"
            "[← Back]"
        ),
        "help_all": (
            "📋 *All Commands*\n\n"
            "Use /help for category-based help.\n\n"
            "[← Back to categories]"
        )
    }
}

HELP_FULL = {
    "es": (
        "📚 *Menú de Ayuda*\n"
        "—————————————————\n"
        "🚀 *Alertas Periódicas (Monitor)*\n"
        "  • `/shop`: Muestra la tienda para adquirir suscripciones y extras. ⭐\n"
        "  • `/monedas <SÍMBOLO1, ...>`: Configura tu lista de monedas (ej. `/monedas BTC, ETH`).\n"
        "  • `/temp <HORAS>`: Ajusta la frecuencia de la alerta periódica (ej. `/temp 2.5`).\n"
        "  • `/parar`: Detiene la alerta periódica, pero mantiene tu lista.\n"
        "  • `/mismonedas`: Muestra tu lista de monedas configuradas.\n\n"
        "🚨 *Alertas por Cruce de Precio*\n"
        "  • `/alerta <SÍMBOLO> <PRECIO>`: Crea una alerta de precio (ej. `/alerta HIVE 0.35`).\n"
        "  • `/misalertas`: Muestra y borra tus alertas activas.\n\n"
        "📈 *Comandos de Consulta*\n"
        "  • `/p <MONEDA>`: Precio detallado de una moneda (ej. `/p HIVE`).\n"
        "  • `/graf <MONEDA> [PAR] <TIEMPO>`: Gráfico (ej. `/graf BTC 1h`).\n"
        "  • `/tasa`: Tasas de cambio de ElToque (CUP).\n"
        "  • `/mk`: Estado de mercados globales.\n"
        "  • `/ta <MONEDA> [PAR] [TIEMPO]`: Análisis técnico (RSI, MACD, S/R).\n"
        "  • `/ver`: Consulta rápida de precios de tu lista.\n"
        "  • `/w`: Gestión de alertas de clima\n\n"
        "⚙️ *Configuración y Varios*\n"
        "  • `/hbdalerts [add/del/run/stop]`: Administra umbrales HBD.\n"
        "  • `/btcalerts`: Alertas y análisis de volatilidad BTC.\n"
        "  • `/valerts`: Alertas y análisis multi-moneda.\n"
        "  • `/lang`: Cambia idioma.\n"
        "  • `/myid`: Tu ID de Telegram.\n"
        "  • `/start`: Bienvenida.\n"
        "  • `/help`: Este menú.\n\n—————————————————\n\n"
        "🔑 *Comandos de Administrador*\n"
        "  • `/users`: Muestra estadísticas y lista de usuarios.\n"
        "  • `/logs [N]`: Muestra las últimas líneas del log.\n"
        "  • `/ms`: Enviar mensaje masivo a todos los usuarios.\n"
        "  • `/ad`: Gestionar anuncios (listar, añadir, borrar).\n"
    ),
    "en": (
        "📚 *Help Menu*\n"
        "—————————————————\n"
        "🚀 *Periodic Alerts (Monitor)*\n"
        "  • `/shop`: Shows the store to acquire subscriptions and extras. ⭐\n"
        "  • `/monedas <SYMBOL1, ...>`: Set up your watchlist (e.g. `/monedas BTC, ETH`).\n"
        "  • `/temp <HOURS>`: Adjust the periodic alert frequency (e.g. `/temp 2.5`).\n"
        "  • `/parar`: Stops the periodic alert, but keeps your list.\n"
        "  • `/mismonedas`: Shows your configured coin list.\n\n"
        "🚨 *Price Crossing Alerts*\n"
        "  • `/alerta <SYMBOL> <PRICE>`: Create a price alert (e.g. `/alerta HIVE 0.35`).\n"
        "  • `/misalertas`: Shows and clears your active cross alerts.\n\n"
        "📈 *Query Commands*\n"
        "  • `/p <COIN>`: Detailed price of a coin (e.g. `/p HIVE`).\n"
        "  • `/graf <COIN> [PAIR] <TIME>`: Chart (e.g. `/graf BTC 1h`).\n"
        "  • `/tasa`: Exchange rates from ElToque (CUP).\n"
        "  • `/mk`: Check the status (open/closed) of the major global markets.\n"
        "  • `/ta <COIN> [PAIR] [TIME]`: Detailed technical analysis (RSI, MACD, S/R).\n"
        "  • `/ver`: Quick check of your watchlist prices.\n"
        "  • `/w`: Manage weather alerts.\n\n"
        "⚙️ *Settings & Misc*\n"
        "  • `/hbdalerts [add/del/run/stop]`: Manage HBD thresholds. (Ex: `/hbdalerts add 0.9950`).\n"
        "  • `/btcalerts`: BTC volatility alerts and analysis. (Ex: `/btcalerts`).\n"
        "  • `/valerts`: Multi-coin volatility alerts and analysis. (Ex: `/valerts`).\n"
        "  • `/lang`: Change the bot language.\n"
        "  • `/myid`: Shows your Telegram ID.\n"
        "  • `/start`: Welcome message.\n"
        "  • `/help`: Shows this menu.\n\n—————————————————\n\n"
        "🔑 *Admin Commands*\n"
        "  • `/users`: Shows statistics and user list.\n"
        "  • `/logs [N]`: Shows the last lines of the log.\n"
        "  • `/ms`: Send mass message to all users.\n"
        "  • `/ad`: Manage ads (list, add, delete).\n"
    )
}

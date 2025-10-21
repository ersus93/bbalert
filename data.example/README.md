# Archivos de datos de ejemplo

Este directorio contiene ejemplos de los archivos JSON que usa el bot. Úsalos como referencia para entender la estructura de datos.

## Estructura de archivos

### users.json
Almacena la configuración de cada usuario:
```json
{
    "CHAT_ID": {
        "monedas": ["BTC", "HIVE", "HBD", "TON"],  // Monedas a mostrar
        "hbd_alerts": true,                         // Recibir alertas de HBD
        "intervalo_alerta_h": 1.0                   // Intervalo entre alertas (horas)
    }
}
```

### price_alerts.json
Guarda las alertas de precio configuradas:
```json
{
    "CHAT_ID": [
        {
            "alert_id": "id_único",     // ID generado automáticamente
            "coin": "SYMBOL",           // Símbolo de la moneda
            "target_price": 1.05,       // Precio objetivo
            "condition": "ABOVE/BELOW",  // Dirección del cruce
            "status": "ACTIVE"          // ACTIVE o TRIGGERED
        }
    ]
}
```

### custom_alert_history.json
Último precio conocido para cada moneda:
```json
{
    "SYMBOL": precio_float  // Ejemplo: "HBD": 1.0123
}
```

### hbd_price_history.json
Historial de precios HBD y otras monedas:
```json
[
    {
        "timestamp": "YYYY-MM-DD HH:MM:SS",
        "btc": precio_float,
        "hive": precio_float,
        "hbd": precio_float,
        "ton": precio_float
    }
]
```

## Notas
- Los archivos reales se crean en `/data/` (no en este directorio).
- Estos son solo ejemplos; los archivos reales pueden tener más o menos datos.
- Los IDs de chat son strings aunque representan números.
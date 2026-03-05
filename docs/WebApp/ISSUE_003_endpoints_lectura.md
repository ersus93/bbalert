# 📖 Issue #003 — Endpoints de Lectura de Datos JSON

**Fase**: 1 — Backend API  
**Prioridad**: 🔴 Alta  
**Etiquetas**: `backend`, `api`, `datos`  
**Rama**: `feature/webapp-fase-1-read-endpoints`  
**Depende de**: #001, #002

---

## 📋 Descripción

Crear el servicio `data_reader.py` y los endpoints de lectura que exponen de forma segura el contenido de los archivos JSON del bot (`data/`). Todos los endpoints son de solo lectura (GET) y requieren autenticación JWT.

---

## 🎯 Objetivos

- Servicio centralizado `DataReader` para leer los archivos JSON del bot
- Endpoints para: usuarios, alertas BTC, alertas clima, alertas personalizadas, ads, eventos
- Modelos Pydantic para serializar y validar los datos leídos
- Manejo de errores si un archivo no existe o está malformado
- Soporte para paginación y filtros básicos en listas largas

---

## 📁 Archivos JSON a Exponer

| Archivo | Endpoint |
|---------|----------|
| `data/users.json` | `GET /api/users/` |
| `data/btc_subs.json` | `GET /api/alerts/btc` |
| `data/weather_subs.json` | `GET /api/alerts/weather` |
| `data/price_alerts.json` | `GET /api/alerts/custom` |
| `data/hbd_thresholds.json` | `GET /api/alerts/hbd` |
| `data/ads.json` | `GET /api/config/ads` |
| `data/events_log.json` | `GET /api/stats/events` |
| `data/last_prices.json` | `GET /api/stats/prices` |
| `data/rss_data_v2.json` | `GET /api/config/rss` |

---

## 💻 Implementación

### `services/data_reader.py`
```python
import json
import os
from pathlib import Path
from core.config import DIR_BASE  # reutilizar config del bot

DATA_DIR = Path(DIR_BASE) / "data"

class DataReader:
    @staticmethod
    def _read(filename: str) -> dict | list:
        path = DATA_DIR / filename
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_users(self) -> dict:
        return self._read("users.json")

    def get_btc_subs(self) -> dict:
        return self._read("btc_subs.json")

    def get_weather_subs(self) -> dict:
        return self._read("weather_subs.json")

    def get_price_alerts(self) -> dict:
        return self._read("price_alerts.json")

    def get_hbd_thresholds(self) -> dict:
        return self._read("hbd_thresholds.json")

    def get_ads(self) -> list:
        return self._read("ads.json")

    def get_events_log(self) -> list:
        return self._read("events_log.json")

    def get_last_prices(self) -> dict:
        return self._read("last_prices.json")

    def get_rss_data(self) -> dict:
        return self._read("rss_data_v2.json")

data_reader = DataReader()
```

### Endpoint ejemplo — `routers/stats.py`
```python
from fastapi import APIRouter, Depends
from services.data_reader import data_reader
from routers.auth import get_current_admin

router = APIRouter()

@router.get("/summary")
async def get_summary(admin=Depends(get_current_admin)):
    users = data_reader.get_users()
    btc = data_reader.get_btc_subs()
    weather = data_reader.get_weather_subs()
    alerts = data_reader.get_price_alerts()
    return {
        "total_users": len(users),
        "btc_subscribers": len(btc),
        "weather_subscribers": len(weather),
        "active_price_alerts": sum(len(v) for v in alerts.values()),
    }

@router.get("/prices")
async def get_prices(admin=Depends(get_current_admin)):
    return data_reader.get_last_prices()

@router.get("/events")
async def get_events(limit: int = 50, admin=Depends(get_current_admin)):
    events = data_reader.get_events_log()
    return events[-limit:] if isinstance(events, list) else events
```

---

## ✅ Criterios de Aceptación

- [ ] Todos los endpoints devuelven 200 con datos correctos cuando los archivos existen
- [ ] Si un archivo JSON no existe, el endpoint devuelve `{}` o `[]` (no 500)
- [ ] Si un archivo está malformado, el endpoint devuelve 500 con mensaje claro
- [ ] `GET /api/stats/summary` devuelve conteos correctos comparando con archivos reales
- [ ] Los endpoints soportan parámetro `limit` en listas (máx. 500)
- [ ] Todos los endpoints requieren JWT válido (401 sin token)

---

## 🔗 Dependencias

- Issue #001, #002

---

## 📝 Notas

- `DIR_BASE` se toma de `apit.env` igual que en el bot, garantizando que ambos lean los mismos archivos
- No modificar ningún archivo en esta issue, solo lectura
- Los archivos JSON se leen en cada petición (no cachear en esta fase, el bot los modifica continuamente)

# ✏️ Issue #004 — Endpoints de Escritura y Acciones

**Fase**: 1 — Backend API  
**Prioridad**: 🟠 Media-Alta  
**Etiquetas**: `backend`, `api`, `escritura`  
**Rama**: `feature/webapp-fase-1-write-endpoints`  
**Depende de**: #003

---

## 📋 Descripción

Crear el servicio `data_writer.py` y los endpoints de escritura que permiten al administrador modificar datos del bot (usuarios, alertas, ads, config) desde el panel web. También incluye el servicio `bot_sender.py` para enviar mensajes de Telegram desde la API.

> ⚠️ Estos endpoints modifican los mismos archivos JSON que usa el bot en tiempo real. Se debe implementar un mecanismo de escritura atómica (write-then-rename) para evitar corrupción de datos.

---

## 🎯 Objetivos

- Servicio `DataWriter` con escritura atómica de archivos JSON
- Servicio `BotSender` para enviar mensajes vía Telegram Bot API
- Endpoints para: eliminar usuario, activar/desactivar alertas, añadir/borrar ads, enviar mensaje a usuario
- Validación estricta de inputs con Pydantic antes de escribir
- Log de cada operación de escritura en `events_log.json`

---

## 🔧 Endpoints de Escritura

| Método | Endpoint | Acción |
|--------|----------|--------|
| `DELETE` | `/api/users/{user_id}` | Eliminar usuario del bot |
| `PATCH` | `/api/alerts/btc/{user_id}` | Activar/desactivar alerta BTC |
| `PATCH` | `/api/alerts/weather/{user_id}` | Activar/desactivar alerta clima |
| `DELETE` | `/api/alerts/custom/{user_id}/{coin}` | Eliminar alerta personalizada |
| `POST` | `/api/config/ads` | Añadir anuncio rotativo |
| `DELETE` | `/api/config/ads/{index}` | Eliminar anuncio |
| `POST` | `/api/users/{user_id}/message` | Enviar mensaje a usuario |
| `POST` | `/api/users/broadcast` | Mensaje masivo a todos |

---

## 💻 Implementación

### `services/data_writer.py`
```python
import json
import os
import tempfile
from pathlib import Path
from core.config import DIR_BASE

DATA_DIR = Path(DIR_BASE) / "data"

class DataWriter:
    @staticmethod
    def _write_atomic(filename: str, data: dict | list):
        """Escritura atómica: escribe a temp y luego renombra."""
        path = DATA_DIR / filename
        with tempfile.NamedTemporaryFile(
            mode="w", dir=DATA_DIR, suffix=".tmp",
            delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name
        os.replace(tmp_path, path)

    def remove_user(self, user_id: str):
        for filename in ["users.json", "btc_subs.json", "weather_subs.json",
                         "price_alerts.json", "valerts_subs.json"]:
            data = DataReader._read(filename)
            if user_id in data:
                del data[user_id]
                self._write_atomic(filename, data)

    def toggle_btc_alert(self, user_id: str, enabled: bool):
        data = DataReader._read("btc_subs.json")
        if user_id in data:
            data[user_id]["enabled"] = enabled
            self._write_atomic("btc_subs.json", data)

    def add_ad(self, text: str):
        ads = DataReader._read("ads.json") or []
        ads.append({"text": text, "active": True})
        self._write_atomic("ads.json", ads)

    def remove_ad(self, index: int):
        ads = DataReader._read("ads.json") or []
        if 0 <= index < len(ads):
            ads.pop(index)
            self._write_atomic("ads.json", ads)
```

### `services/bot_sender.py`
```python
import httpx
import os

class BotSender:
    def __init__(self):
        self.token = os.getenv("TOKEN_TELEGRAM")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML"):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
            )
            return resp.json()

bot_sender = BotSender()
```

---

## ✅ Criterios de Aceptación

- [ ] La escritura atómica no corrompe archivos JSON aunque el bot los esté usando
- [ ] `DELETE /api/users/{id}` elimina al usuario de todos los archivos JSON relevantes
- [ ] `POST /api/users/{id}/message` envía el mensaje correctamente vía Telegram API
- [ ] `POST /api/users/broadcast` envía a todos los usuarios con delay de 50ms entre mensajes (respeta rate limit de Telegram: 30 msg/s)
- [ ] Cada operación de escritura queda registrada en `events_log.json` con timestamp y admin
- [ ] Inputs vacíos o malformados devuelven 422 Unprocessable Entity

---

## 🔗 Dependencias

- Issue #001, #002, #003

---

## 📝 Notas

- El bot y la web app acceden a los mismos archivos. La escritura atómica es **no negociable**
- El broadcast masivo debe respetar los rate limits de Telegram (Issue #008 profundiza en esto)
- Considerar añadir un flag `--dry-run` en desarrollo para simular escrituras sin aplicarlas

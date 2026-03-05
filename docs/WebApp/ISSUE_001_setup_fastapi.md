# 🛠️ Issue #001 — Setup Proyecto FastAPI para BBAlert Web App

**Fase**: 1 — Backend API  
**Prioridad**: 🔴 Alta  
**Etiquetas**: `backend`, `setup`, `fastapi`  
**Rama**: `feature/webapp-fase-1-setup`

---

## 📋 Descripción

Crear la estructura base del proyecto web dentro del repositorio de BBAlert. Esta issue cubre el scaffolding inicial, instalación de dependencias y configuración del servidor FastAPI para que sirva como API REST y también sirva el frontend estático.

---

## 🎯 Objetivos

- Crear la carpeta `webapp/` con la estructura de archivos definida en el plan
- Instalar y configurar FastAPI + uvicorn
- Crear el archivo `main.py` con la app base y los routers vacíos
- Servir archivos estáticos (`static/`) desde FastAPI
- Documentar el arranque del servidor en `README_WEBAPP.md`
- Añadir `requirements_web.txt` con las dependencias necesarias

---

## 📁 Archivos a Crear

```
bbalert/
└── webapp/
    ├── main.py
    ├── requirements_web.txt
    ├── README_WEBAPP.md
    ├── routers/
    │   ├── __init__.py
    │   ├── auth.py          (stub vacío)
    │   ├── users.py         (stub vacío)
    │   ├── alerts.py        (stub vacío)
    │   ├── stats.py         (stub vacío)
    │   └── config.py        (stub vacío)
    ├── services/
    │   ├── __init__.py
    │   ├── data_reader.py   (stub vacío)
    │   └── data_writer.py   (stub vacío)
    ├── models/
    │   ├── __init__.py
    │   └── base.py
    └── static/
        └── index.html       (placeholder)
```

---

## 💻 Implementación

### `requirements_web.txt`
```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.9
aiofiles>=23.2.1
```

### `main.py` (estructura base)
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, users, alerts, stats, config

app = FastAPI(
    title="BBAlert Web App",
    description="Panel de administración para el bot de Telegram BBAlert",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restringir en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Usuarios"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alertas"])
app.include_router(stats.router, prefix="/api/stats", tags=["Estadísticas"])
app.include_router(config.router, prefix="/api/config", tags=["Configuración"])

app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

### Arranque del servidor
```bash
cd bbalert/webapp
pip install -r requirements_web.txt
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

---

## ✅ Criterios de Aceptación

- [ ] El servidor arranca sin errores con `uvicorn main:app`
- [ ] `/api/docs` muestra la documentación interactiva de Swagger
- [ ] `/` sirve el `index.html` placeholder
- [ ] Todos los routers están registrados aunque devuelvan 501 Not Implemented
- [ ] `requirements_web.txt` instalable con un único `pip install -r`
- [ ] El `DIR_BASE` del bot se lee desde `apit.env` para encontrar los archivos JSON

---

## 🔗 Dependencias

- Ninguna (issue inicial)

---

## 📝 Notas

- Usar el mismo entorno virtual del bot si es posible, o crear uno separado `venv_web/`
- El puerto por defecto será `8080` para no interferir con otros servicios
- En producción nginx actuará como proxy inverso (ver Issue #013)

# 🌐 Plan de Implementación — BBAlert Web App

**Proyecto**: Mini Web App de administración y monitoreo para BBAlert  
**Versión Bot**: v1.1.7  
**Autor**: Ersus  
**Fecha**: 2025-03-03  

---

## 🎯 Objetivo

Crear una mini aplicación web que sirva como **panel de control y monitoreo** del bot de Telegram BBAlert, permitiendo al administrador gestionar usuarios, alertas, estadísticas y configuración desde el navegador, sin necesidad de acceder directamente al servidor.

---

## 🗺️ Visión General

```
┌─────────────────────────────────────────────────────────┐
│                  BBAlert Web App                        │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │Dashboard │  │ Usuarios │  │ Alertas  │  │Config  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘  │
│       └─────────────┴─────────────┴─────────────┘       │
│                          │                               │
│                    ┌─────▼──────┐                        │
│                    │  REST API  │  (FastAPI)              │
│                    └─────┬──────┘                        │
│                          │                               │
│           ┌──────────────┼──────────────┐               │
│           │              │              │               │
│    ┌──────▼─────┐  ┌─────▼──────┐  ┌───▼──────┐        │
│    │ JSON Files │  │ Bot Python │  │ APIs Ext.│        │
│    └────────────┘  └────────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────┘
```

---

## 🏗️ Stack Tecnológico

### Backend (API)
- **FastAPI** — API REST ligera y rápida
- **uvicorn** — Servidor ASGI
- **python-jose** — Autenticación JWT
- **passlib** — Hashing de contraseñas

### Frontend
- **HTML5 + CSS3 + Vanilla JS** (o React si se prefiere)
- **Chart.js** — Gráficos y estadísticas
- **TailwindCSS** — Estilos

### Integración con Bot
- Lectura directa de archivos JSON del bot (`data/`)
- Endpoint de Telegram para envío de mensajes desde el panel
- Webhooks opcionales para eventos en tiempo real

---

## 📦 Fases de Implementación

### Fase 1 — Backend API (Semana 1–2)
**Issues**: #001, #002, #003, #004

Crear la capa API que expone los datos del bot de forma segura.

- Setup del proyecto FastAPI
- Sistema de autenticación JWT para admins
- Endpoints de lectura de archivos JSON
- Endpoints de escritura/modificación de datos

### Fase 2 — Dashboard Principal (Semana 2–3)
**Issues**: #005, #006

Página de inicio con las métricas más relevantes del bot.

- Contador de usuarios activos
- Alertas enviadas en las últimas 24h
- Estado del bot (online/offline)
- Gráfica de actividad reciente

### Fase 3 — Gestión de Usuarios (Semana 3–4)
**Issues**: #007, #008

Panel para ver y administrar los usuarios del bot.

- Listado de usuarios con filtros
- Detalle de usuario (alertas, suscripciones, idioma)
- Envío de mensajes individuales desde la web
- Exportar lista de usuarios

### Fase 4 — Gestión de Alertas (Semana 4–5)
**Issues**: #009, #010

Panel para visualizar y gestionar todas las alertas activas.

- Ver alertas BTC, HBD, clima y personalizadas
- Activar/desactivar alertas por usuario
- Historial de alertas enviadas
- Filtros por tipo y fecha

### Fase 5 — Panel de Configuración (Semana 5–6)
**Issues**: #011, #012

Configuración del bot desde la interfaz web.

- Ajuste de umbrales de alertas
- Gestión de anuncios rotativos (ads)
- Configuración de intervalos de loops
- Vista de logs del sistema en tiempo real

### Fase 6 — Despliegue y Seguridad (Semana 6)
**Issues**: #013, #014

Poner en producción de forma segura en el mismo VPS.

- Configurar nginx como reverse proxy
- Certificado SSL con Let's Encrypt
- Configurar systemd para el servicio web
- Hardening de seguridad

---

## 📁 Estructura de Archivos Propuesta

```
bbalert/
└── webapp/
    ├── main.py                  # Punto de entrada FastAPI
    ├── requirements_web.txt     # Dependencias web
    ├── routers/
    │   ├── auth.py              # Autenticación JWT
    │   ├── users.py             # Endpoints usuarios
    │   ├── alerts.py            # Endpoints alertas
    │   ├── stats.py             # Endpoints estadísticas
    │   └── config.py            # Endpoints configuración
    ├── services/
    │   ├── data_reader.py       # Lectura de JSON del bot
    │   ├── data_writer.py       # Escritura de JSON del bot
    │   └── bot_sender.py        # Envío de mensajes via Telegram API
    ├── models/
    │   ├── user.py              # Modelos Pydantic
    │   ├── alert.py
    │   └── stats.py
    ├── static/
    │   ├── index.html           # SPA principal
    │   ├── css/
    │   │   └── styles.css
    │   └── js/
    │       ├── app.js
    │       ├── dashboard.js
    │       ├── users.js
    │       └── alerts.js
    └── systemd/
        └── bbalert-web.service  # Servicio systemd para la web
```

---

## 🔐 Seguridad

- Autenticación basada en JWT con expiración configurable
- Panel accesible **solo para admins** (IDs definidos en `apit.env`)
- HTTPS obligatorio en producción (nginx + certbot)
- Rate limiting en endpoints de escritura
- Validación estricta de inputs con Pydantic
- Logs de acceso separados

---

## 📊 Métricas del Dashboard (MVP)

| Métrica | Fuente |
|--------|--------|
| Total usuarios | `data/users.json` |
| Alertas BTC activas | `data/btc_subs.json` |
| Alertas clima activas | `data/weather_subs.json` |
| Alertas personalizadas | `data/price_alerts.json` |
| Suscriptores HBD | `data/loops.py` state |
| Anuncios activos | `data/ads.json` |
| Última actividad | `data/events_log.json` |

---

## 🚀 Comandos de Integración con mbot.sh

Se añadirán opciones al script `mbot.sh` existente:

```
│12. 🌐 Iniciar Web App          │
│13. ⏹️ Detener Web App          │
│14. 🔄 Reiniciar Web App        │
│15. 📊 Estado Web App           │
```

---

## 📋 Issues Creadas

| Issue | Título | Fase |
|-------|--------|------|
| [#001](./issues/ISSUE_001_setup_fastapi.md) | Setup proyecto FastAPI | 1 |
| [#002](./issues/ISSUE_002_auth_jwt.md) | Sistema autenticación JWT | 1 |
| [#003](./issues/ISSUE_003_endpoints_lectura.md) | Endpoints lectura JSON | 1 |
| [#004](./issues/ISSUE_004_endpoints_escritura.md) | Endpoints escritura/acciones | 1 |
| [#005](./issues/ISSUE_005_dashboard_frontend.md) | Dashboard principal (frontend) | 2 |
| [#006](./issues/ISSUE_006_graficas_actividad.md) | Gráficas y métricas en tiempo real | 2 |
| [#007](./issues/ISSUE_007_gestion_usuarios.md) | Panel gestión de usuarios | 3 |
| [#008](./issues/ISSUE_008_mensajes_individuales.md) | Envío de mensajes desde el panel | 3 |
| [#009](./issues/ISSUE_009_gestion_alertas.md) | Panel gestión de alertas | 4 |
| [#010](./issues/ISSUE_010_historial_alertas.md) | Historial y filtros de alertas | 4 |
| [#011](./issues/ISSUE_011_panel_config.md) | Panel de configuración del bot | 5 |
| [#012](./issues/ISSUE_012_logs_realtime.md) | Vista de logs en tiempo real | 5 |
| [#013](./issues/ISSUE_013_deploy_nginx.md) | Despliegue nginx + SSL | 6 |
| [#014](./issues/ISSUE_014_systemd_web.md) | Servicio systemd para la web app | 6 |

---

## ✅ Definition of Done

Una fase se considera completa cuando:

- [ ] El código está en una rama `feature/webapp-fase-N`
- [ ] Los endpoints están documentados con OpenAPI (FastAPI auto-docs)
- [ ] El frontend funciona en móvil y escritorio
- [ ] No se exponen credenciales ni datos sensibles
- [ ] El servicio se reinicia automáticamente con systemd
- [ ] El acceso está protegido por HTTPS y JWT

---

**📚 BBAlert Web App Plan — Ersus — v0.1**

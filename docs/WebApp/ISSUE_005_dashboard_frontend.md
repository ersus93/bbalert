# 🖥️ Issue #005 — Dashboard Principal (Frontend)

**Fase**: 2 — Dashboard  
**Prioridad**: 🔴 Alta  
**Etiquetas**: `frontend`, `dashboard`, `ui`  
**Rama**: `feature/webapp-fase-2-dashboard`  
**Depende de**: #001, #002, #003

---

## 📋 Descripción

Crear el frontend de la web app: una Single Page Application (SPA) ligera en HTML/CSS/JS que consuma la API REST creada en la Fase 1. La primera pantalla será el **Dashboard** con un resumen del estado del bot y métricas clave.

El diseño debe ser limpio, responsive y funcional en móvil (el admin puede necesitar revisar el panel desde el teléfono).

---

## 🎯 Objetivos

- Pantalla de **login** con formulario y manejo del JWT en `localStorage`
- **Sidebar/navbar** de navegación entre secciones (Dashboard, Usuarios, Alertas, Config, Logs)
- **Dashboard** con tarjetas de métricas y estado del bot
- Manejo de sesión: logout, expiración del token con redirección al login
- Diseño dark mode por defecto (coherente con el estilo de un bot de trading)

---

## 🎨 Diseño del Dashboard

```
┌─────────────────────────────────────────────────────────┐
│ 🤖 BBAlert Admin Panel                    [Logout]      │
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│ Dashboard│  📊 Resumen General                          │
│ Usuarios │                                              │
│ Alertas  │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│ Config   │  │👥 Usuarios│ │📈 BTC Sub│ │🌦️ Clima  │    │
│ Logs     │  │   1,234  │ │    89   │ │   156   │    │
│          │  └──────────┘ └──────────┘ └──────────┘    │
│          │                                              │
│          │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│          │  │🔔 Alertas│ │📰 RSS    │ │💬 Ads    │    │
│          │  │   342   │ │   12    │ │    5    │    │
│          │  └──────────┘ └──────────┘ └──────────┘    │
│          │                                              │
│          │  📉 Actividad últimas 24h                   │
│          │  [Gráfica de líneas — events_log]           │
│          │                                              │
│          │  🕐 Últimos eventos                         │
│          │  [Tabla con últimas 10 entradas del log]    │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

---

## 💻 Estructura de Archivos Frontend

```
static/
├── index.html          # SPA única
├── css/
│   └── styles.css      # Estilos dark mode + responsive
└── js/
    ├── app.js          # Router SPA, manejo JWT, fetch helper
    ├── dashboard.js    # Lógica del dashboard
    ├── users.js        # (fase 3)
    ├── alerts.js       # (fase 4)
    ├── config.js       # (fase 5)
    └── logs.js         # (fase 5)
```

---

## 💻 Implementación Clave

### `js/app.js` — Fetch helper con JWT
```javascript
const API = {
  token: localStorage.getItem("bbalert_token"),

  async get(path) {
    const res = await fetch(`/api${path}`, {
      headers: { Authorization: `Bearer ${this.token}` }
    });
    if (res.status === 401) { logout(); return; }
    return res.json();
  },

  async post(path, body) {
    const res = await fetch(`/api${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.token}`
      },
      body: JSON.stringify(body)
    });
    if (res.status === 401) { logout(); return; }
    return res.json();
  }
};

function logout() {
  localStorage.removeItem("bbalert_token");
  showLogin();
}
```

### `js/dashboard.js` — Cargar métricas
```javascript
async function loadDashboard() {
  const summary = await API.get("/stats/summary");
  document.getElementById("total-users").textContent = summary.total_users;
  document.getElementById("btc-subs").textContent = summary.btc_subscribers;
  document.getElementById("weather-subs").textContent = summary.weather_subscribers;
  document.getElementById("price-alerts").textContent = summary.active_price_alerts;

  const events = await API.get("/stats/events?limit=10");
  renderEventsTable(events);
}
```

---

## ✅ Criterios de Aceptación

- [ ] La pantalla de login funciona y almacena el JWT correctamente
- [ ] Con token inválido/expirado, el usuario es redirigido al login automáticamente
- [ ] El dashboard muestra las 6 métricas clave correctamente
- [ ] La tabla de últimos eventos muestra las 10 entradas más recientes
- [ ] El diseño es responsive y usable en pantalla de móvil (375px+)
- [ ] El dark mode está activo por defecto
- [ ] El botón de logout elimina el token y redirige al login

---

## 🔗 Dependencias

- Issue #001, #002, #003 (API base y endpoints de stats)

---

## 📝 Notas

- No usar frameworks JS pesados (React, Vue) en esta fase para mantener el bundle mínimo
- Usar `Chart.js` desde CDN para las gráficas (Issue #006)
- El sidebar puede colapsarse en móvil con un botón hamburguesa

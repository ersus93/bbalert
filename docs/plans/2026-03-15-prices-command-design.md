# 📊 Diseño: Comando Unificado `/prices`

**Fecha:** 2026-03-15  
**Issue:** #AUDIT-20  
**Estado:** En revisión

---

## 🎯 **Objetivo**

Fusionar `/ver`, `/monedas` y `/mismonedas` en un único comando `/prices` con interfaz interactiva moderna, haciendo el bot más intuitivo para usuarios menos expertos.

---

## 📋 **Requisitos**

### **Funcionales**
1. Un solo comando `/prices` para toda la gestión de watchlist
2. Interfaz con botones inline para acciones principales
3. Mostrar precios con indicadores visuales (🔺🔻▫️)
4. Permitir añadir/eliminar monedas sin escribir comandos
5. Rate limiting unificado pero configurable
6. Soporte i18n completo (es/en)

### **No Funcionales**
1. UX moderna y limpia
2. Mínimo número de clicks para acciones comunes
3. Mensajes claros y descriptivos
4. Backward compatibility (opcional: aliases para comandos antiguos)

---

## 🎨 **Diseño de Interfaz**

### **Vista Principal: `/prices`**

```
📊 Precios Actuales
—————————————————

🟠 BTC/USD: $52,340.50 🔺
🔷 ETH/USD: $2,890.25 🔻
🐝 HIVE/USD: $0.4520 ▫️

—————————————————
📅 15/03/2026 14:30:45

[ ➕ Añadir ]  [ 🗑️ Eliminar ]
[ 📋 Ver Lista ]  [ ⚙️ Configurar ]
```

**Botones:**
- `➕ Añadir` → Abre diálogo para añadir monedas
- `🗑️ Eliminar` → Muestra lista con checkboxes para eliminar
- `📋 Ver Lista` → Muestra solo la lista (sin precios)
- `⚙️ Configurar` → Muestra opciones avanzadas (temporalidad, etc.)

---

### **Vista: Añadir Monedas**

```
➕ Añadir Monedas
—————————————————

Escribe los símbolos separados por comas:
Ejemplo: BTC, ETH, HIVE

Tu lista actual: BTC, ETH

[ ← Volver ]
```

**Flujo:**
1. Usuario hace click en "➕ Añadir"
2. Bot solicita input de texto
3. Usuario escribe: "SOL, ADA"
4. Bot confirma: "✅ Añadidas: SOL, ADA"
5. Vuelve a vista principal actualizada

---

### **Vista: Eliminar Monedas**

```
🗑️ Eliminar Monedas
—————————————————

Selecciona las monedas a eliminar:

[✓] BTC
[✓] ETH
[✓] HIVE

[ ✅ Eliminar Seleccionadas ]
[ ← Volver ]
```

**Flujo:**
1. Usuario hace click en "🗑️ Eliminar"
2. Bot muestra lista con botones toggle
3. Usuario selecciona monedas
4. Click en "Eliminar Seleccionadas"
5. Bot confirma y vuelve a vista principal

---

### **Vista: Ver Lista**

```
📋 Tu Lista de Monedas
—————————————————

• BTC
• ETH
• HIVE

Total: 3 monedas

[ ← Volver ]
```

---

### **Vista: Configurar**

```
⚙️ Configuración de Alertas
—————————————————

Intervalo actual: 2.5 horas
Mínimo de tu plan: 0.25 horas

[ 🕐 Cambiar Intervalo ]
[ 🔔 Alertas HBD ]
[ 🌐 Idioma ]

[ ← Volver ]
```

---

## 🏗️ **Arquitectura**

### **Estructura de Archivos**

```
handlers/
├── prices.py          # NUEVO: Comando unificado /prices
├── general.py         # Eliminar: ver()
├── user_settings.py   # Eliminar: monedas(), mismonedas()
└── ...

locales/
├── es/LC_MESSAGES/messages.po
└── en/LC_MESSAGES/messages.po
```

### **Componentes**

```python
# handlers/prices.py

class PricesView:
    """Vista principal de precios con botones."""
    async def show(update: Update, context: ContextTypes.DEFAULT_TYPE)
    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE)

class PricesAddHandler:
    """Manejo de añadir monedas."""
    async def add_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE)
    async def add_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE)

class PricesRemoveHandler:
    """Manejo de eliminar monedas."""
    async def remove_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE)
    async def remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE)

class PricesListHandler:
    """Vista de solo lista."""
    async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE)

class PricesSettingsHandler:
    """Sub-menú de configuración."""
    async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE)
```

---

## 🔄 **Flujo de Datos**

```
Usuario: /prices
    ↓
PricesView.show()
    ↓
1. Obtener monedas del usuario
2. Consultar precios (API)
3. Calcular indicadores
4. Construir mensaje
5. Añadir botones inline
    ↓
Enviar mensaje con InlineKeyboardMarkup
    ↓
Usuario: Click en [➕ Añadir]
    ↓
PricesAddHandler.add_dialog()
    ↓
Esperar input de texto
    ↓
Usuario: "SOL, ADA"
    ↓
Actualizar lista en DB
Enviar confirmación
Volver a PricesView.show()
```

---

## 🎯 **Rate Limiting**

Unificar el rate limit de los 3 comandos antiguos en uno solo:

```python
# Antes:
/ver → 8 consultas/día (gratuito)
/monedas → Sin límite
/mismonedas → Sin límite

# Después:
/prices → 8 consultas/día (gratuito)
        → 48 consultas/día (watchlist_bundle)

# Acciones sin límite:
- Añadir monedas
- Eliminar monedas
- Ver lista (sin precios)
- Configurar
```

---

## 🌐 **i18n Strings**

### **Español**
```python
PRICES_TITLE = "📊 Precios Actuales"
PRICES_EMPTY = "📝 Tu lista está vacía"
PRICES_ADD_BUTTON = "➕ Añadir"
PRICES_REMOVE_BUTTON = "🗑️ Eliminar"
PRICES_LIST_BUTTON = "📋 Ver Lista"
PRICES_SETTINGS_BUTTON = "⚙️ Configurar"
PRICES_ADD_PROMPT = "Escribe los símbolos separados por comas"
PRICES_REMOVE_PROMPT = "Selecciona las monedas a eliminar"
PRICES_BACK_BUTTON = "← Volver"
```

### **Inglés**
```python
PRICES_TITLE = "📊 Current Prices"
PRICES_EMPTY = "📝 Your list is empty"
PRICES_ADD_BUTTON = "➕ Add"
PRICES_REMOVE_BUTTON = "🗑️ Remove"
PRICES_LIST_BUTTON = "📋 View List"
PRICES_SETTINGS_BUTTON = "⚙️ Settings"
PRICES_ADD_PROMPT = "Enter symbols separated by commas"
PRICES_REMOVE_PROMPT = "Select coins to remove"
PRICES_BACK_BUTTON = "← Back"
```

---

## ✅ **Criterios de Aceptación**

- [ ] `/prices` muestra precios con indicadores
- [ ] Botones inline funcionales
- [ ] Añadir monedas funciona (con validación)
- [ ] Eliminar monedas funciona (con confirmación)
- [ ] Ver lista muestra solo símbolos
- [ ] Rate limiting aplicado correctamente
- [ ] i18n completo (es/en)
- [ ] Comandos antiguos eliminados (`/ver`, `/monedas`, `/mismonedas`)
- [ ] `/help` actualizado
- [ ] Tests pasan (si existen)

---

## 🚀 **Plan de Implementación**

### **Fase 1: Crear `/prices`**
1. Crear `handlers/prices.py` con vista principal
2. Implementar botones inline
3. Implementar callbacks de botones
4. Añadir i18n strings

### **Fase 2: Sub-diálogos**
1. Implementar diálogo de añadir
2. Implementar diálogo de eliminar
3. Implementar vista de lista
4. Implementar sub-menú de configuración

### **Fase 3: Limpieza**
1. Eliminar `/ver` de `handlers/general.py`
2. Eliminar `/monedas` y `/mismonedas` de `handlers/user_settings.py`
3. Eliminar registros de handlers en `bbalert.py`
4. Actualizar `/help` en `locales/texts.py`

### **Fase 4: Testing**
1. Probar flujo completo
2. Validar rate limiting
3. Verificar i18n
4. Testear edge cases

---

## 📊 **Métricas de Éxito**

- **Reducción de comandos:** 4 → 1 (75% menos)
- **Clicks para añadir moneda:** 2 (antes: escribir comando + argumentos)
- **Clicks para eliminar moneda:** 3 (antes: escribir comando + símbolo)
- **Satisfacción UX:** Medir con feedback de usuarios

---

## ⚠️ **Riesgos y Mitigación**

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Usuarios confundidos por cambio | Medio | Mantener aliases temporales (`/ver` → `/prices`) |
| Rate limiting muy restrictivo | Alto | Aumentar límite a 12 consultas/día |
| Botones no renderizan en móviles | Medio | Diseñar botones compactos |
| Diálogo de añadir muy complejo | Bajo | Usar ConversationHandler simple |

---

## 🔗 **Referencias**

- [Telegram InlineKeyboardMarkup Docs](https://core.telegram.org/bots/api#inlinekeyboardmarkup)
- [python-telegram-bot ConversationHandler](https://docs.python-telegram-bot.org/en/stable/telegram.ext.conversationhandler.html)
- Issue: #AUDIT-19 (Eliminar código muerto)

---

*Documento de diseño aprobado: [PENDIENTE]*  
*Implementación: [PENDIENTE]*

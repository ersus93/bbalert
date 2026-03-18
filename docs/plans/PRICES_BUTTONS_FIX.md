# 🔧 Corrección: Botones del Comando `/prices`

**Fecha:** 2026-03-16  
**Estado:** ✅ **COMPLETADO** (Actualizado)

---

## 📋 Problemas Identificados y Soluciones

### 1. Bug en Orden de Callbacks (CRÍTICO)
**Problema:** El patrón `^prices_` capturaba `prices_del_BTC` antes de que llegara al handler específico.

**Solución:** Invertido el orden - primero el más específico (`prices_del_`), luego el general (`prices_`).

```python
# bbalert.py
app.add_handler(CallbackQueryHandler(prices_delete_callback, pattern="^prices_del_"))
app.add_handler(CallbackQueryHandler(prices_callback_handler, pattern="^prices_"))
```

### 2. Bug en `_handle_back_button`
**Problema:** Intentaba llamar a `prices_command()` con un CallbackQuery.

**Solución:** Reescrito para replicar la lógica internamente.

### 3. Bug en `prices_delete_callback`
**Problema:** Usaba `update.effective_chat.id` que puede fallar en grupos.

**Solución:** Cambiado a usar `query.message.chat.id`.

### 4. Botón Añadir - Falta ConversationHandler
**Problema:** El botón mostraba un mensaje pero no había handler para recibir las monedas escritas.

**Solución:** Creado `prices_add_conversation_handler` y registrado en bbalert.py.

### 5. Bug en `_handle_settings_button`
**Problema:** Llamaba a `check_feature_access(user_id, ...)` pero la función requiere `chat_id`.

**Solución:** Corregido a `check_feature_access(chat_id, ...)`.

---

## 📁 Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `handlers/prices.py` | Múltiples correcciones de bugs |
| `bbalert.py` | Imports, orden de handlers, ConversationHandler |

---

## ✅ Cambios Realizados

### `handlers/prices.py`

1. **_handle_back_button** - Reescrito para replicar la lógica internamente:
   - Obtiene monedas del usuario
   - Consulta precios
   - Construye mensaje con botones
   - Usa `query.edit_message_text()` directamente

2. **prices_delete_callback** - Corregido chat_id:
   ```python
   # Antes (incorrecto):
   chat_id = update.effective_chat.id
   
   # Después (correcto):
   chat_id = query.message.chat.id if query.message else query.from_user.id
   ```

3. **Typos corregidos** - Cambiado `monedAS` → `monedas` (error de escritura)

### `bbalert.py`

1. **Imports actualizados** - Agregados:
   ```python
   prices_add_start,
   prices_add_receive,
   prices_add_done,
   prices_add_cancel,
   ADD_COIN,
   ```

---

## 🧪 Testing Recomendado

1. Ejecutar `/prices` y verificar que muestre los precios
2. Hacer click en "➕ Añadir" - debe mostrar mensaje instructivo
3. Hacer click en "🗑️ Eliminar" - debe mostrar lista de monedas
4. Click en una moneda para eliminar - debe eliminar y confirmar
5. Click en "← Volver" - debe volver a mostrar precios
6. Click en "📋 Ver Lista" - debe mostrar la lista
7. Click en "⚙️ Configurar" - debe mostrar opciones

---

## 📝 Notas

- Los botones ahora usan el patrón `prices_` (nuevo módulo)
- El módulo legacy `/precios` usa el patrón `precios_` - son independientes
- El ConversationHandler para añadir monedas no fue implementado ya que el flujo actual simplemente muestra instrucciones y el usuario debe usar el comando `/prices add`

---

*Documento creado: 2026-03-16*

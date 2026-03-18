# Plan de Corrección para Errores en Comando Prices

## Problemas Identificados

Después de analizar el código del comando `/prices` en el bot BBAlert, he identificado dos problemas principales:

1. **Botón "Añadir" no inicia correctamente la conversación**
   - Cuando se presiona el botón "Añadir" para agregar monedas, muestra un mensaje de error "⚠️ Datos incorrectos" en lugar de iniciar la conversación correctamente.

2. **Botón "Configurar" da error al cambiar el intervalo**
   - Al intentar cambiar el intervalo de alertas, muestra un mensaje de error similar debido a un problema con la función `actualizar_intervalo_alerta`.

## Análisis de Causas Raíz

### Problema 1: Botón "Añadir"
- La función `_handle_add_button` no está conectada correctamente con el `ConversationHandler`.
- No se está retornando el estado correcto (`ADD_COIN`) para iniciar el flujo de conversación.
- El ConversationHandler está configurado con `per_message=True`, lo que puede causar problemas con los callbacks.

### Problema 2: Botón "Configurar"
- La función `actualizar_intervalo_alerta` existe en `utils/user_data.py` pero no está siendo importada en `handlers/prices.py`.
- Cuando se intenta usar la función en `_handle_temp_callback`, ocurre un error al no estar definida.

## Soluciones Propuestas

### 1. Importar correctamente la función actualizar_intervalo_alerta

En el archivo `handlers/prices.py`, añadir la importación faltante:

```python
from utils.user_data import (
    obtener_monedas_usuario, actualizar_monedas, cargar_usuarios, 
    actualizar_intervalo_alerta  # Añadir esta importación
)
```

### 2. Corregir la función _handle_add_button

Modificar la función para que inicie correctamente el flujo de conversación:

```python
async def _handle_add_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja click en botón 'Añadir' - inicia conversación."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    chat_id = query.message.chat.id if query.message else query.from_user.id
    
    # Obtener lista actual
    actuales = obtener_monedas_usuario(chat_id)
    
    mensaje = _(
        "➕ *Añadir monedas*\n"
        "────────────────────────────────\n\n"
        "Tu lista actual: {lista}\n\n"
        "Escribe los símbolos separados por comas.\n\n"
        "*Ejemplo:*\n"
        "`BTC, ETH, HIVE, SOL`\n\n"
        "O usa directamente: /prices add BTC,ETH\n\n"
        "Envía `/cancel` para cancelar.",
        user_id
    ).format(lista=', '.join(actuales) if actuales else "(vacía)")
    
    try:
        await query.edit_message_text(
            mensaje,
            parse_mode=ParseMode.MARKDOWN
        )
        # Retornar el estado ADD_COIN para iniciar el flujo de conversación
        return ADD_COIN
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=mensaje,
            parse_mode=ParseMode.MARKDOWN
        )
        return ADD_COIN  # También retornar el estado aquí
```

### 3. Ajustar el ConversationHandler

Modificar la configuración del ConversationHandler para que funcione correctamente con callbacks:

```python
# ConversationHandler para añadir monedas
prices_add_conversation_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(_handle_add_button, pattern="^prices_add$")
    ],
    states={
        ADD_COIN: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, prices_add_receive)
        ]
    },
    fallbacks=[
        CommandHandler("cancel", prices_add_cancel),
        CommandHandler("done", prices_add_done),
    ],
    per_message=False,  # Cambiar a False para permitir que funcione con callbacks
    allow_reentry=True,
    name="prices_add"
)
```

## Implementación

La implementación de estas correcciones debe realizarse en el archivo `handlers/prices.py`. Es recomendable seguir el siguiente orden:

1. Añadir la importación faltante.
2. Modificar la función `_handle_add_button` para que retorne el estado correcto.
3. Ajustar la configuración del ConversationHandler.

## Consideraciones Adicionales

1. **Logging para diagnóstico**: Recomiendo añadir más logs en puntos críticos para facilitar el diagnóstico de problemas similares en el futuro:

```python
from utils.logger import logger

# En los puntos críticos:
logger.info(f"[PRICES_ADD] Iniciando diálogo para usuario {user_id}")
```

2. **Manejo de errores mejorado**: Capturar específicamente los tipos de excepciones que pueden ocurrir para proporcionar mensajes de error más descriptivos.

3. **Pruebas después de la implementación**: Probar exhaustivamente ambos botones después de aplicar los cambios para asegurar que funcionan correctamente.

## Conclusión

Estos cambios deberían resolver los problemas con los botones "Añadir" y "Configurar" en el comando `/prices`. La solución aborda tanto los problemas de integración con el ConversationHandler como la falta de importación de la función necesaria.

Implementar estas correcciones mejorará la experiencia del usuario al usar el comando `/prices`, permitiendo añadir monedas y configurar el intervalo de alertas sin errores.
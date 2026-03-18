# Plan de Implementación: Corrección de Botones en Comando Prices

## Resumen
Este plan detalla los pasos específicos para implementar las correcciones a los errores en los botones "añadir" y "configurar" del comando `/prices` en BBAlert.

## Cambios a Realizar

### 1. Añadir la importación faltante
Modificar la línea de importación en `handlers/prices.py` para incluir `actualizar_intervalo_alerta`:

```python
from utils.user_data import (
    obtener_monedas_usuario, actualizar_monedas, cargar_usuarios,
    actualizar_intervalo_alerta  # Añadir esta importación
)
```

### 2. Modificar la función _handle_add_button
Actualizar la función para que retorne correctamente el estado `ADD_COIN`:

```python
async def _handle_add_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja click en botón 'Añadir' - inicia conversación."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    chat_id = query.message.chat.id if query.message else query.from_user.id
    
    # Obtener lista actual
    actuales = obtener_monedas_usuario(chat_id)
    
    # Añadir logs para diagnóstico
    from utils.logger import logger
    logger.info(f"[PRICES_ADD] Iniciando diálogo para usuario {user_id} en chat {chat_id}")
    
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
    except Exception as e:
        logger.error(f"[PRICES_ADD_ERROR] Error al iniciar diálogo: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=mensaje,
            parse_mode=ParseMode.MARKDOWN
        )
        return ADD_COIN  # También retornar el estado aquí
```

### 3. Modificar el ConversationHandler
Actualizar la configuración del ConversationHandler para que funcione correctamente con callbacks:

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

### 4. Actualizar la lista __all__
Asegurar que todos los handlers necesarios estén correctamente exportados:

```python
__all__ = [
    # ... mantener los elementos existentes ...
    'prices_add_conversation_handler',  # Añadir si no está presente
]
```

## Pasos de Implementación

1. Modificar la importación al principio del archivo
2. Actualizar la función `_handle_add_button`
3. Modificar el `ConversationHandler`
4. Actualizar la lista `__all__`
5. Verificar que no haya errores de sintaxis
6. Probar los cambios

## Pruebas Recomendadas

1. Probar el botón "añadir" para verificar que inicia correctamente la conversación
2. Probar el botón "configurar" para verificar que permite cambiar el intervalo
3. Verificar que se pueden añadir monedas correctamente
4. Verificar que se pueden configurar intervalos correctamente

## Consideraciones Adicionales

- Añadir logs adicionales para facilitar el diagnóstico futuro
- Mejorar los mensajes de error para que sean más descriptivos
- Considerar capturar excepciones específicas en lugar de usar bloques genéricos
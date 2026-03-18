# Ejemplo de Implementación para Corregir Errores en Prices.py

A continuación se muestra un ejemplo de cómo implementar los cambios necesarios para corregir los errores en los botones "añadir" y "configurar" del comando prices.

## 1. Añadir la importación faltante

```python
# Al principio del archivo, en la sección de importaciones
from utils.user_data import obtener_monedas_usuario, actualizar_monedas, cargar_usuarios, actualizar_intervalo_alerta
```

## 2. Modificar la función _handle_add_button

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
    
    # Añadir logs para diagnóstico
    from utils.logger import logger
    logger.info(f"[PRICES_ADD] Iniciando diálogo para usuario {user_id} en chat {chat_id}")
    
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

## 3. Modificar el ConversationHandler

```python
# ConversationHandler para añadir monedas
prices_add_conversation_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(prices_add_start, pattern="^prices_add$")
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

## 4. Asegurar que la función prices_add_start está correctamente definida

Si hay discrepancia entre el entry_point del ConversationHandler y la función `_handle_add_button`, asegúrate de que estén alineados:

```python
async def prices_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el diálogo de añadir monedas."""
    # Si el update viene de un callback query (botón)
    if update.callback_query:
        return await _handle_add_button(update, context)
    
    # Si viene de un comando directo
    user_id = update.effective_user.id
    
    mensaje = _(
        "➕ *Añadir monedas*\n—————————————————\n\n"
        "Escribe los símbolos separados por comas.\n\n"
        "*Ejemplo:*\n"
        "`BTC, ETH, HIVE, SOL`\n\n"
        "Envía `/cancel` para cancelar.",
        user_id
    )
    
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
    return ADD_COIN
```

## 5. Para cerrar el círculo, asegúrate de que los handlers estén correctamente exportados

Añade o confirma que los siguientes elementos estén en el `__all__` al final del archivo:

```python
__all__ = [
    # ... otros elementos...
    'prices_callback_handler',
    'prices_add_start',
    'prices_add_receive',
    'prices_add_done',
    'prices_add_cancel',
    'prices_delete_callback',
    'prices_add_conversation_handler',  # ¡Importante añadir esto!
]
```

## Consideraciones adicionales

1. **Mejorar los mensajes de error**: Actualiza cualquier mensaje genérico "⚠️ Datos incorrectos" por mensajes más específicos que indiquen exactamente qué ocurrió.

2. **Logging**: Añadir más logs como se muestra en el ejemplo para facilitar el diagnóstico futuro.

3. **Manejo de excepciones**: Si es posible, captura tipos específicos de excepciones en lugar de usar bloques `except Exception:` genéricos.

Estos cambios deberían solucionar los problemas identificados con los botones "añadir" y "configurar" del comando prices.
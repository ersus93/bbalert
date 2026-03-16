# handlers/prices.py
"""
Comando unificado /prices para gestión de watchlist.
Reemplaza a: /ver, /monedas, /mismonedas
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, CommandHandler
from utils.user_data import obtener_monedas_usuario, actualizar_monedas, cargar_usuarios
from core.api_client import obtener_precios_control
from utils.subscription_manager import check_feature_access, registrar_uso_comando
from utils.ads_manager import get_random_ad_text
from core.i18n import _
from datetime import datetime

# Estados para ConversationHandler
ADD_COIN, REMOVE_COIN = range(2)


async def prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comando principal /prices.
    Muestra precios actuales con botones interactivos.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # === GUARDIA DE RATE LIMITING ===
    acceso, mensaje = check_feature_access(chat_id, 'prices_limit')
    if not acceso:
        # Manejar caso donde update.message es None (viene de callback)
        if update.message:
            await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    # Registrar uso
    registrar_uso_comando(chat_id, 'prices')
    # ================================

    # Obtener monedas del usuario
    monedas = obtener_monedas_usuario(chat_id)

    if not monedas:
        # Vista: lista vacía
        await _show_empty_list(update, context)
        return

    # Notificar que estamos cargando
    # Manejar caso donde update.message es None
    if update.message:
        msg = await update.message.reply_text(
            _("⏳ Consultando precios...", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Si viene de callback, no mostramos loading
        msg = None

    # Obtener precios
    precios = obtener_precios_control(monedas)

    if not precios:
        if msg:
            await msg.edit_text(
                _("❌ No se pudieron obtener los precios. Intenta luego.", user_id),
                parse_mode=ParseMode.MARKDOWN
            )
        return

    # Construir mensaje con precios
    mensaje = await _build_prices_message(monedas, precios, chat_id, user_id)

    # Crear botones inline
    keyboard = [
        [
            InlineKeyboardButton(_("➕ Añadir", user_id), callback_data="prices_add"),
            InlineKeyboardButton(_("🗑️ Eliminar", user_id), callback_data="prices_remove"),
        ],
        [
            InlineKeyboardButton(_("📋 Ver Lista", user_id), callback_data="prices_list"),
            InlineKeyboardButton(_("⚙️ Configurar", user_id), callback_data="prices_settings"),
        ],
        [
            InlineKeyboardButton(_("← Volver", user_id), callback_data="prices_back"),
        ],
    ]

    await msg.edit_text(
        mensaje,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def _show_empty_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra vista cuando la lista está vacía."""
    user_id = update.effective_user.id

    mensaje = _(
        "📝 *Tu lista está vacía*\n\n"
        "Comienza añadiendo monedas:\n"
        "• Haz click en '➕ Añadir'\n"
        "• O escribe: `/prices add BTC,ETH,HIVE`",
        user_id
    )

    keyboard = [
        [InlineKeyboardButton(_("➕ Añadir Primera Moneda", user_id), callback_data="prices_add")],
    ]

    await update.message.reply_text(
        mensaje,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def _build_prices_message(monedas: list, precios: dict, chat_id: int, user_id: int) -> str:
    """Construye el mensaje de precios con indicadores."""
    from utils.file_manager import load_last_prices_status

    todos_precios_anteriores = load_last_prices_status()
    chat_id_str = str(chat_id)
    precios_anteriores = todos_precios_anteriores.get(chat_id_str, {})

    mensaje = _("📊 *Precios Actuales*\n—————————————————\n\n", user_id)

    TOLERANCIA = 0.0000001

    for moneda in monedas:
        p_actual = precios.get(moneda)
        p_anterior = precios_anteriores.get(moneda)

        if p_actual is not None:
            # Calcular indicador
            indicador = ""
            if p_anterior:
                if p_actual > p_anterior + TOLERANCIA:
                    indicador = " 🔺"
                elif p_actual < p_anterior - TOLERANCIA:
                    indicador = " 🔻"
                else:
                    indicador = " ▫️"

            mensaje += f"*{moneda}/USD*: ${p_actual:,.4f}{indicador}\n"
        else:
            mensaje += f"*{moneda}/USD*: N/A\n"

    # Footer con fecha y anuncio
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    mensaje += f"\n—————————————————\n"
    mensaje += f"_📅 {fecha}_\n"
    mensaje += get_random_ad_text()

    return mensaje


async def prices_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja los callbacks de los botones inline."""
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat.id if query.message else query.from_user.id
    user_id = query.from_user.id

    if data == "prices_add":
        await _handle_add_button(update, context)
    elif data == "prices_remove":
        await _handle_remove_button(update, context)
    elif data == "prices_list":
        await _handle_list_button(update, context)
    elif data == "prices_settings":
        await _handle_settings_button(update, context)
    elif data == "prices_back":
        await _handle_back_button(update, context)


async def _handle_add_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=mensaje,
            parse_mode=ParseMode.MARKDOWN
        )


async def _handle_remove_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja click en botón 'Eliminar'."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    monedas = obtener_monedas_usuario(chat_id)
    
    if not monedas:
        try:
            await update.callback_query.edit_message_text(
                _("📝 Tu lista está vacía.", user_id)
            )
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id,
                text=_("📝 Tu lista está vacía.", user_id)
            )
        return
    
    # Crear botones para cada moneda
    keyboard = []
    for moneda in monedas:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ {moneda}",
                callback_data=f"prices_del_{moneda}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver", user_id), callback_data="prices_back")])

    mensaje = _(
        "🗑️ *Eliminar monedas*\n—————————————————\n\n"
        "Haz click en una moneda para eliminarla:\n\n",
        user_id
    )
    
    try:
        await update.callback_query.edit_message_text(
            mensaje,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=mensaje,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )


async def _handle_list_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja click en botón 'Ver Lista' - muestra lista con botones para eliminar."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    monedas = obtener_monedas_usuario(chat_id)
    
    if not monedas:
        try:
            await update.callback_query.edit_message_text(
                _("📝 Tu lista está vacía.", user_id)
            )
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id,
                text=_("📝 Tu lista está vacía.", user_id)
            )
        return
    
    # Crear botones para cada moneda (para eliminar)
    keyboard = []
    for moneda in monedas:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ {moneda}",
                callback_data=f"prices_del_{moneda}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver", user_id), callback_data="prices_back")])

    mensaje = _(
        "📋 *Tu Lista de monedas*\n—————————————————\n\n"
        "monedas en tu lista (haz click para eliminar):\n\n",
        user_id
    )
    mensaje += "\n".join([f"• {m}" for m in monedas])
    mensaje += f"\n\n_Total: {len(monedas)} monedas_\n"
    
    try:
        await update.callback_query.edit_message_text(
            mensaje,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=mensaje,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )


async def _handle_settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja click en botón 'Configurar'."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    chat_id = query.message.chat.id if query.message else query.from_user.id
    
    usuarios = cargar_usuarios()
    intervalo = usuarios.get(str(chat_id), {}).get('intervalo_alerta_h', 2.5)
    min_val, _ = check_feature_access(chat_id, 'temp_min_val')
    
    mensaje = _(
        "⚙️ *Configuración de Alertas*\n—————————————————\n\n"
        "🕐 *Intervalo actual:* {intervalo} horas\n"
        "📊 *Mínimo de tu plan:* {min_val} horas\n\n"
        "Para cambiar el intervalo usa:\n"
        "`/temp <horas>` (ej: `/temp 0.25`)\n\n"
        "[ ← Volver ](/prices)",
        user_id
    ).format(intervalo=intervalo, min_val=min_val)
    
    keyboard = [[InlineKeyboardButton(_("← Volver", user_id), callback_data="prices_back")]]
    
    try:
        await update.callback_query.edit_message_text(
            mensaje,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=mensaje,
            parse_mode=ParseMode.MARKDOWN
        )


async def _handle_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja click en botón 'Volver' - muestra precios nuevamente."""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat.id if query.message else query.from_user.id

    # Replicar la lógica de prices_command aquí para evitar problemas con CallbackQuery
    try:
        monedas = obtener_monedas_usuario(chat_id)
        
        if not monedas:
            await query.edit_message_text(
                _("📝 Tu lista está vacía. Usa /prices para añadir monedas.", user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Obtener precios
        precios = obtener_precios_control(monedas)
        
        if not precios:
            await query.edit_message_text(
                _("❌ No se pudieron obtener los precios. Intenta luego.", user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Construir mensaje con precios
        mensaje = await _build_prices_message(monedas, precios, chat_id, user_id)
        
        # Crear botones inline
        keyboard = [
            [
                InlineKeyboardButton(_("➕ Añadir", user_id), callback_data="prices_add"),
                InlineKeyboardButton(_("🗑️ Eliminar", user_id), callback_data="prices_remove"),
            ],
            [
                InlineKeyboardButton(_("📋 Ver Lista", user_id), callback_data="prices_list"),
                InlineKeyboardButton(_("⚙️ Configurar", user_id), callback_data="prices_settings"),
            ],
            [
                InlineKeyboardButton(_("← Volver", user_id), callback_data="prices_back"),
            ],
        ]
        
        await query.edit_message_text(
            mensaje,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        # Fallback: enviar mensaje nuevo si falla
        await context.bot.send_message(
            chat_id=chat_id,
            text=_("⚠️ Error al cargar precios. Usa /prices para intentar de nuevo.", user_id),
            parse_mode=ParseMode.MARKDOWN
        )


async def prices_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja eliminación de moneda específica."""
    query = update.callback_query
    await query.answer()
    
    # Usar query.message.chat.id para evitar problemas en grupos
    chat_id = query.message.chat.id if query.message else query.from_user.id
    user_id = query.from_user.id
    
    # Extraer moneda del callback data
    data = query.data  # prices_del_BTC
    moneda = data.replace("prices_del_", "")
    
    # Eliminar moneda
    monedas = obtener_monedas_usuario(chat_id)
    if moneda in monedas:
        monedas.remove(moneda)
        actualizar_monedas(chat_id, monedas)
        
        mensaje = _("✅ *{moneda} eliminada*\n\nTu lista: {lista}", user_id).format(
            moneda=moneda,
            lista=', '.join(monedas) if monedas else _("(vacía)", user_id)
        )
        
        await query.edit_message_text(
            mensaje,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.edit_message_text(
            _("⚠️ {moneda} no está en tu lista.", user_id).format(moneda=moneda),
            parse_mode=ParseMode.MARKDOWN
        )


# === SUBCOMANDOS: /prices add y /prices remove ===

async def prices_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Subcomando: /prices add BTC,ETH,HIVE
    Añade monedas a la lista del usuario.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        await update.message.reply_text(
            _("⚠️ *Uso:*\n`/prices add BTC,ETH,HIVE`\n\n"
              "Escribe los símbolos separados por comas.", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Procesar argumentos
    nuevas = []
    for arg in args:
        nuevas.extend([m.strip().upper() for m in arg.split(",") if m.strip()])

    actuales = obtener_monedas_usuario(chat_id)
    añadidas = []

    for m in nuevas:
        if m not in actuales:
            actuales.append(m)
            añadidas.append(m)

    actualizar_monedas(chat_id, actuales)

    if añadidas:
        mensaje = _("✅ *Añadidas:* {lista}\n\n"
                    "📋 *Tu lista:* {total}", user_id).format(
            lista=', '.join(añadidas),
            total=', '.join(actuales)
        )
    else:
        mensaje = _("ℹ️ Estas monedas ya están en tu lista.", user_id)

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


async def show_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Muestra solo la lista de monedas SIN precios.
    Alias: /mismonemonas
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    monedas = obtener_monedas_usuario(chat_id)
    
    if not monedas:
        if update.message:
            await update.message.reply_text(
                _("📝 Tu lista está vacía.\n\n"
                  "Usa `/prices add BTC,ETH` para añadir monedas.", user_id),
                parse_mode=ParseMode.MARKDOWN
            )
        return
    
    mensaje = _("📋 *Tu Lista de monedas*\n—————————————————\n\n", user_id)
    mensaje += "\n".join([f"• {m}" for m in monedas])
    mensaje += f"\n\n_Total: {len(monedas)} monedas_\n"
    
    if update.message:
        await update.message.reply_text(
            mensaje,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.callback_query.edit_message_text(
            mensaje,
            parse_mode=ParseMode.MARKDOWN
        )


async def prices_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Subcomando: /prices list
    Muestra solo la lista de monedas (alias de show_list_command).
    """
    await show_list_command(update, context)


async def prices_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Subcomando: /prices remove BTC,ETH
    Elimina monedas de la lista del usuario.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        await update.message.reply_text(
            _("⚠️ *Uso:*\n`/prices remove BTC,ETH`\n\n"
              "Escribe los símbolos separados por comas.", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Procesar argumentos
    quitar = []
    for arg in args:
        quitar.extend([m.strip().upper() for m in arg.split(",") if m.strip()])

    actuales = obtener_monedas_usuario(chat_id)
    eliminadas = []

    for m in quitar:
        if m in actuales:
            actuales.remove(m)
            eliminadas.append(m)

    actualizar_monedas(chat_id, actuales)

    if eliminadas:
        mensaje = _("✅ *Eliminadas:* {lista}\n\n"
                    "📋 *Tu lista:* {total}", user_id).format(
            lista=', '.join(eliminadas),
            total=', '.join(actuales) if actuales else _("(vacía)", user_id)
        )
    else:
        mensaje = _("ℹ️ Esas monedas no están en tu lista.", user_id)

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


# === COMANDO MAESTRO /prices (detecta subcomandos) ===

async def prices_master_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler maestro para /prices.
    Detecta subcomandos y bifurca accordingly.
    
    Formatos soportados:
    - /prices → muestra precios
    - /prices add BTC,ETH → añade monedas
    - /prices remove BTC → elimina monedas
    - /prices list → muestra lista sin precios
    """
    if not update.message:
        return
    
    args = context.args
    
    if not args:
        # /prices → mostrar precios
        await prices_command(update, context)
        return
    
    # Primer argumento es el subcomando
    subcommand = args[0].lower()
    remaining_args = args[1:]
    
    if subcommand == "add":
        # /prices add BTC,ETH,HIVE
        context.args = remaining_args
        await prices_add_command(update, context)
    elif subcommand == "remove" or subcommand == "del":
        # /prices remove BTC
        context.args = remaining_args
        await prices_remove_command(update, context)
    elif subcommand == "list" or subcommand == "ls":
        # /prices list
        await show_list_command(update, context)
    else:
        # Subcomando desconocido - treating as coin to add
        # Re-construct args as coins
        context.args = args  # Restore all args as coins
        await prices_add_command(update, context)


# === CONVERSATION HANDLERS ===

async def prices_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el diálogo de añadir monedas."""
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


async def prices_add_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y procesa las monedas a añadir."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    texto = update.message.text.strip()
    
    # Procesar
    nuevas = []
    for arg in texto.split(","):
        if arg.strip():
            nuevas.append(arg.strip().upper())
    
    actuales = obtener_monedas_usuario(chat_id)
    añadidas = []
    
    for m in nuevas:
        if m not in actuales:
            actuales.append(m)
            añadidas.append(m)
    
    actualizar_monedas(chat_id, actuales)
    
    if añadidas:
        mensaje = _("✅ *Añadidas:* {lista}\n\n"
                    "📋 *Tu lista:* {total}\n\n"
                    "¿Quieres añadir más monedas?\n"
                    "Envía otra lista o `/done` para terminar.", user_id).format(
            lista=', '.join(añadidas),
            total=', '.join(actuales)
        )
        return ADD_COIN  # Permitir añadir más
    else:
        mensaje = _("ℹ️ Estas monedas ya están en tu lista.\n\n"
                    "¿Quieres añadir otras?\n"
                    "Envía otra lista o `/done` para terminar.", user_id)
        return ADD_COIN


async def prices_add_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finaliza el diálogo de añadir."""
    user_id = update.effective_user.id
    
    mensaje = _("✅ ¡Listo! Usa /prices para ver tus precios.", user_id)
    await update.message.reply_text(mensaje)
    return ConversationHandler.END


async def prices_add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela el diálogo de añadir."""
    user_id = update.effective_user.id
    
    mensaje = _("❌ Operación cancelada.", user_id)
    await update.message.reply_text(mensaje)
    return ConversationHandler.END


async def prices_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el diálogo de eliminar monedas."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    monedas = obtener_monedas_usuario(chat_id)
    
    if not monedas:
        await update.message.reply_text(
            _("📝 Tu lista está vacía.", user_id)
        )
        return ConversationHandler.END
    
    mensaje = _(
        "🗑️ *Eliminar monedas*\n—————————————————\n\n"
        "Tu lista actual: {lista}\n\n"
        "Escribe los símbolos a eliminar separados por comas.\n\n"
        "*Ejemplo:*\n"
        "`BTC, ETH`\n\n"
        "Envía `/cancel` para cancelar.",
        user_id
    ).format(lista=', '.join(monedas))
    
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
    return REMOVE_COIN


async def prices_remove_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y procesa las monedas a eliminar."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    texto = update.message.text.strip()
    
    # Procesar
    quitar = []
    for arg in texto.split(","):
        if arg.strip():
            quitar.append(arg.strip().upper())
    
    actuales = obtener_monedas_usuario(chat_id)
    eliminadas = []
    
    for m in quitar:
        if m in actuales:
            actuales.remove(m)
            eliminadas.append(m)
    
    actualizar_monedas(chat_id, actuales)
    
    if eliminadas:
        mensaje = _("✅ *Eliminadas:* {lista}\n\n"
                    "📋 *Tu lista:* {total}\n\n"
                    "¿Quieres eliminar más monedas?\n"
                    "Envía otra lista o `/done` para terminar.", user_id).format(
            lista=', '.join(eliminadas),
            total=', '.join(actuales) if actuales else _("(vacía)", user_id)
        )
        return REMOVE_COIN
    else:
        mensaje = _("ℹ️ Esas monedas no están en tu lista.\n\n"
                    "¿Quieres eliminar otras?\n"
                    "Envía otra lista o `/done` para terminar.", user_id)
        return REMOVE_COIN


async def prices_remove_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finaliza el diálogo de eliminar."""
    user_id = update.effective_user.id
    
    mensaje = _("✅ ¡Listo! Usa /prices para ver tus precios.", user_id)
    await update.message.reply_text(mensaje)
    return ConversationHandler.END


# === EXPORTS ===

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
    per_message=False,
    allow_reentry=True,
    name="prices_add"
)

__all__ = [
    'prices_command',
    'prices_master_command',
    'prices_callback_handler',
    'prices_add_command',
    'prices_remove_command',
    'prices_list_command',
    'show_list_command',
    'prices_delete_callback',
    'prices_add_start',
    'prices_add_receive',
    'prices_add_done',
    'prices_add_cancel',
    'prices_remove_start',
    'prices_remove_receive',
    'prices_remove_done',
    'ADD_COIN',
    'REMOVE_COIN',
]

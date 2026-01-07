from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.error import BadRequest
from datetime import datetime, timedelta
import re
from utils.reminders_manager import get_user_reminders, add_reminder, delete_reminder, postpone_reminder_by_id, add_reminder
from utils.logger import logger

# Estados de la conversación
WAITING_TEXT, WAITING_TIME = range(2)

async def rec_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la lista de recordatorios y el menú principal."""
    user_id = update.effective_user.id
    reminders = get_user_reminders(user_id)
    
    if not reminders:
        msg = "📭 *No tienes recordatorios pendientes.*"
    else:
        msg = "📋 *Tus Recordatorios:*\n\n"
        for r in reminders:
            dt = datetime.fromisoformat(r['time'])
            msg += f"▫️ `{dt.strftime('%d/%m %H:%M')}` - {r['text']}\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Nuevo Recordatorio", callback_data="rem_new")],
        [InlineKeyboardButton("🗑 Eliminar", callback_data="rem_delete_menu")] if reminders else [],
        [InlineKeyboardButton("🔄 Actualizar", callback_data="rem_refresh")]
    ]
    # Limpiamos listas vacías
    keyboard = [row for row in keyboard if row]
    
    # Si viene de callback o mensaje
    if update.callback_query:
        await update.callback_query.answer()
        try:
            # 👇 MODIFICACIÓN: Envolvemos esto en try-except
            await update.callback_query.edit_message_text(
                msg, 
                parse_mode="Markdown", 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except BadRequest as e:
            # Si el mensaje no ha cambiado, Telegram lanza este error.
            # Lo ignoramos porque significa que ya está actualizado.
            if "Message is not modified" in str(e):
                pass
            else:
                # Si es otro error, lo relanzamos para que salga en los logs
                raise e
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# --- FLUJO DE CREACIÓN (CONVERSATION) ---

async def start_add_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia la creación: Pide el texto."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📝 *¿Qué quieres recordar?*\n\nEscribe el mensaje del recordatorio (o /cancel para salir).",
        parse_mode="Markdown"
    )
    return WAITING_TEXT

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guarda el texto y pide la hora."""
    context.user_data['rem_text'] = update.message.text
    await update.message.reply_text(
        "⏰ *¿Cuándo?*\n\n"
        "Formatos aceptados:\n"
        "• `10m`, `30m` (minutos)\n"
        "• `1h`, `2h` (horas)\n"
        "• `20:00` (hora hoy/mañana)\n"
        "• `mañana 09:00`\n"
        "• `04/02 10:00` (fecha y hora)\n"
        "• `25-12-2026 10:00` (fecha completa)",
        parse_mode="Markdown"
    )
    return WAITING_TIME

async def receive_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la hora (soporta fechas completas) y guarda todo."""
    time_str = update.message.text.lower().strip()
    user_id = update.effective_user.id
    text = context.user_data.get('rem_text')
    
    now = datetime.now()
    trigger_dt = None
    
    try:
        # 1. Intentamos buscar formatos de FECHA COMPLETA primero
        # Formatos: DD/MM/YYYY HH:MM o DD-MM-YYYY HH:MM
        date_formats = [
            "%d/%m/%Y %H:%M", 
            "%d-%m-%Y %H:%M",
            "%d/%m/%y %H:%M", # Soporte para año corto (25)
            "%d-%m-%y %H:%M"
        ]
        
        for fmt in date_formats:
            try:
                trigger_dt = datetime.strptime(time_str, fmt)
                break # Si funciona, salimos del bucle
            except ValueError:
                continue

        # 2. Intentamos FECHA CORTA (sin año) -> DD/MM HH:MM
        if not trigger_dt:
            short_date_formats = ["%d/%m %H:%M", "%d-%m %H:%M"]
            for fmt in short_date_formats:
                try:
                    # strptime pone año 1900 por defecto
                    parsed_dt = datetime.strptime(time_str, fmt)
                    # Asignamos el año actual
                    trigger_dt = parsed_dt.replace(year=now.year)
                    
                    # Si la fecha resultante ya pasó (ej: puse 01/01 y estamos en Febrero),
                    # asumimos que es para el año que viene.
                    if trigger_dt < now:
                        trigger_dt = trigger_dt.replace(year=now.year + 1)
                    break
                except ValueError:
                    continue

        # 3. Si no es fecha, probamos lógica RELATIVA o HORA SIMPLE (Lógica original mejorada)
        if not trigger_dt:
            # Caso: Relativo (10m, 5h)
            if time_str.endswith('m') and time_str[:-1].isdigit():
                mins = int(time_str[:-1])
                trigger_dt = now + timedelta(minutes=mins)
            
            elif time_str.endswith('h') and time_str[:-1].isdigit():
                hours = int(time_str[:-1])
                trigger_dt = now + timedelta(hours=hours)
            
            # Caso: Absoluto simple (HH:MM)
            elif re.match(r'^\d{1,2}:\d{2}$', time_str):
                h, m = map(int, time_str.split(':'))
                trigger_dt = now.replace(hour=h, minute=m, second=0)
                if trigger_dt < now: # Si ya pasó hoy, es mañana
                    trigger_dt += timedelta(days=1)

            # Caso: "mañana HH:MM"
            elif "mañana" in time_str:
                parts = time_str.split()
                for p in parts:
                    if ':' in p:
                        h, m = map(int, p.split(':'))
                        trigger_dt = now.replace(hour=h, minute=m, second=0) + timedelta(days=1)
                        break
        
        # --- BLOQUE FINAL DE GUARDADO (Igual que antes) ---
        if trigger_dt:
            # Una validación extra: no permitir fechas en el pasado
            if trigger_dt < now:
                 await update.message.reply_text("⚠️ La fecha indicada ya pasó. Por favor, indica una fecha futura.")
                 return WAITING_TIME

            add_reminder(user_id, text, trigger_dt)
            
            # Formateo bonito para la confirmación
            msg_dt = trigger_dt.strftime('%d/%m/%Y a las %H:%M')
            
            await update.message.reply_text(
                f"✅ *Recordatorio guardado.*\n\n📅 {msg_dt}\n📝 {text}",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text("⚠️ No entendí la hora/fecha. Prueba formato: `DD/MM HH:MM` o `10m`.")
            return WAITING_TIME

    except Exception as e:
        logger.error(f"Error parseando hora: {e}")
        await update.message.reply_text("⚠️ Error procesando la fecha. Intenta de nuevo.")
        return WAITING_TIME

async def cancel_op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

# --- MANEJO DE BOTONES (CALLBACKS) ---

async def reminders_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    if data == "rem_refresh":
        await rec_command(update, context)
        
    elif data == "rem_delete_menu":
        reminders = get_user_reminders(user_id)
        keyboard = []
        for r in reminders:
            # Botón para borrar cada uno
            btn_text = f"❌ {r['text'][:15]}... ({datetime.fromisoformat(r['time']).strftime('%H:%M')})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"rem_del_{r['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="rem_refresh")])
        await query.edit_message_text("🗑 *Selecciona para eliminar:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data.startswith("rem_del_"):
        rem_id = data.split("_")[2]
        if delete_reminder(user_id, rem_id):
            await query.answer("Eliminado")
            
            # --- CORRECCIÓN: Reconstruimos el menú directamente ---
            # En lugar de modificar query.data, regeneramos la lista aquí mismo
            reminders = get_user_reminders(user_id)
            keyboard = []
            
            if not reminders:
                # Si ya no quedan, mostramos mensaje y botón de volver
                msg_text = "🗑 *No quedan recordatorios para eliminar.*"
            else:
                msg_text = "🗑 *Selecciona para eliminar:*"
                for r in reminders:
                    # Reconstruimos los botones de borrar
                    dt_obj = datetime.fromisoformat(r['time'])
                    btn_text = f"❌ {r['text'][:15]}... ({dt_obj.strftime('%H:%M')})"
                    keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"rem_del_{r['id']}")])
            
            keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="rem_refresh")])
            
            # Editamos el mensaje con la lista actualizada
            # Usamos try/except por si el usuario hace click muy rápido (prevención de errores)
            try:
                await query.edit_message_text(
                    msg_text, 
                    parse_mode="Markdown", 
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception:
                pass # Si falla la edición (raro), no rompemos el flujo
                
        else:
            await query.answer("Error o ya no existe", show_alert=True)
            # Opcional: Si falló al borrar, refrescamos la lista general
            await rec_command(update, context)

    # --- ACCIONES AL DISPARARSE LA ALERTA (POSTPONE / ACK) ---
    elif data.startswith("rem_postpone_"):
        # data format: rem_postpone_{id}_{minutes}
        _, _, rem_id, mins = data.split("_")
        
        # OJO: Como el loop borró el recordatorio al enviarlo, aquí tenemos que "re-crearlo"
        # O, si modificaste el loop para no borrar, simplemente actualizas.
        # ASUMIRÉ que el mensaje original tiene el texto. Telegram no nos da fácil el texto original en callback sin leer el mensaje.
        
        # Estrategia robusta: El recordatorio YA se borró del JSON en el loop (linea dirty=True).
        # Así que creamos uno NUEVO basado en el mensaje actual.
        
        original_text = query.message.text
        # Intentamos extraer el texto limpio del mensaje
        # Formato esperado: "📝 Texto..."
        clean_text = "Recordatorio pospuesto"
        for line in original_text.split('\n'):
            if "📝" in line:
                clean_text = line.replace("📝", "").strip()
                break
        
        new_time = datetime.now() + timedelta(minutes=int(mins))
        add_reminder(user_id, clean_text, new_time)
        
        await query.edit_message_text(f"✅ Pospuesto {mins}m.\nNueva hora: {new_time.strftime('%H:%M')}")

    elif data.startswith("rem_ack_"):
        # Solo borrar el mensaje o editarlo para decir "Completado"
        await query.edit_message_text("✅ *Recordatorio completado.*", parse_mode="Markdown")

# Definición del ConversationHandler
reminders_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_reminder, pattern="^rem_new$")],
    states={
        WAITING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
        WAITING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time)],
    },
    fallbacks=[CommandHandler("cancel", cancel_op)],
)
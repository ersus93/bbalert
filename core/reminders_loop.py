import asyncio
import json
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.reminders_manager import load_reminders, save_reminders
from utils.logger import logger
from core.i18n import _

async def reminders_monitor_loop(bot):
    """Bucle infinito que revisa recordatorios cada 30 segundos."""
    logger.info("✅ Bucle de Recordatorios iniciado.")
    
    while True:
        try:
            now = datetime.now()
            data = load_reminders()
            dirty = False # Flag para saber si hay que guardar cambios
            
            for user_id_str, reminders in data.items():
                user_id = int(user_id_str)
                active_reminders = []
                for rem in reminders:
                    trigger_time = datetime.fromisoformat(rem["time"])
                    
                    if now >= trigger_time:
                        # ¡ES HORA! Enviar alerta
                        try:
                            # Botones para posponer o borrar (este último es visual, ya que se borra al enviarse)
                            keyboard = [
                                [
                                    InlineKeyboardButton(_("💤 15m", user_id), callback_data=f"rem_postpone_{rem['id']}_15"),
                                    InlineKeyboardButton(_("💤 1h", user_id), callback_data=f"rem_postpone_{rem['id']}_60"),
                                ],
                                [InlineKeyboardButton(_("✅ Entendido", user_id), callback_data=f"rem_ack_{rem['id']}")]
                            ]
                            
                            msg_template = _(
                                "🔔 *RECORDATORIO*\n\n"
                                "📝 {text}\n"
                                "⏰ {time}",
                                user_id
                            )
                            msg_text = msg_template.format(text=rem['text'], time=trigger_time.strftime('%H:%M'))
                            
                            await bot.send_message(
                                chat_id=user_id,
                                text=msg_text,
                                parse_mode="Markdown",
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            )
                            logger.info(f"🔔 Recordatorio enviado a {user_id_str}: {rem['text']}")
                            
                            # NO lo agregamos a active_reminders, efectivamente borrándolo de la lista pendiente
                            # A MENOS que quieras que persista hasta que le den "Entendido".
                            # En este diseño: Se envía y se borra del JSON (si el usuario quiere posponer, el botón re-creará la entrada).
                            dirty = True
                            
                        except Exception as e:
                            logger.error(f"Error enviando recordatorio a {user_id_str}: {e}")
                            # Si falla el envío, lo mantenemos para reintentar (o podrías decidir borrarlo)
                            active_reminders.append(rem)
                    else:
                        # Aún no es la hora, se queda
                        active_reminders.append(rem)
                
                # Actualizamos la lista del usuario
                if len(active_reminders) != len(reminders):
                    data[user_id_str] = active_reminders
                    dirty = True
            
            if dirty:
                save_reminders(data)

        except Exception as e:
            logger.error(f"❌ Error crítico en reminders_monitor_loop: {e}")
        
        await asyncio.sleep(30) # Revisar cada 30 segundos

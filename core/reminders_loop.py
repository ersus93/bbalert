import asyncio
import json
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.reminders_manager import load_reminders, save_reminders, is_recurring, calculate_next_occurrence, update_reminder_time
from utils.logger import logger
from core.i18n import _


def get_recurrence_description(reminder, user_id):
    """Obtiene la descripción de recurrencia del recordatorio."""
    if not reminder.get("recurrence") or not reminder["recurrence"].get("enabled"):
        return ""
    
    r = reminder["recurrence"]
    type_map = {
        "daily": _("cada día", user_id),
        "weekly": _("cada semana", user_id),
        "monthly": _("cada mes", user_id),
        "yearly": _("cada año", user_id)
    }
    
    interval = r.get("interval", 1)
    if interval == 1:
        return type_map.get(r["type"], "")
    else:
        return f"{interval} {type_map.get(r['type'], r['type'])}s"


async def reminders_monitor_loop(bot):
    """Bucle infinito que revisa recordatorios cada 30 segundos."""
    logger.info("✅ Bucle de Recordatorios iniciado.")
    
    while True:
        try:
            now = datetime.now()
            data = load_reminders()
            dirty = False
            
            for user_id_str, reminders in data.items():
                user_id = int(user_id_str)
                active_reminders = []
                for rem in reminders:
                    trigger_time = datetime.fromisoformat(rem["time"])
                    
                    if now >= trigger_time:
                        try:
                            keyboard = [
                                [
                                    InlineKeyboardButton(_("💤 15m", user_id), callback_data=f"rem_postpone_{rem['id']}_15"),
                                    InlineKeyboardButton(_("💤 1h", user_id), callback_data=f"rem_postpone_{rem['id']}_60"),
                                ],
                                [
                                    InlineKeyboardButton(_("🔁 Repetir", user_id), callback_data=f"rem_repeat_{rem['id']}"),
                                    InlineKeyboardButton(_("✅ Entendido", user_id), callback_data=f"rem_ack_{rem['id']}")
                                ]
                            ]
                            
                            msg_template = _(
                                "🔔 *RECORDATORIO*\n\n"
                                "📝 {text}\n"
                                "⏰ {time}",
                                user_id
                            )
                            msg_text = msg_template.format(text=rem['text'], time=trigger_time.strftime('%H:%M'))
                            
                            recurrence_desc = get_recurrence_description(rem, user_id)
                            if recurrence_desc:
                                msg_text += f"\n🔄 {_('Se repetirá', user_id)}: {recurrence_desc}"
                            
                            await bot.send_message(
                                chat_id=user_id,
                                text=msg_text,
                                parse_mode="Markdown",
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            )
                            logger.info(f"🔔 Recordatorio enviado a {user_id_str}: {rem['text']}")
                            
                            if is_recurring(rem):
                                next_time = calculate_next_occurrence(rem)
                                if next_time:
                                    rem["time"] = next_time.isoformat()
                                    active_reminders.append(rem)
                                    dirty = True
                                    logger.info(f"🔄 Recordatorio recurrente recalculado para {user_id_str}: {rem['text']} → {next_time.isoformat()}")
                                else:
                                    dirty = True
                                    logger.info(f"⏹️ Recordatorio recurrente finalizado para {user_id_str}: {rem['text']}")
                            else:
                                dirty = True
                                
                        except Exception as e:
                            logger.error(f"Error enviando recordatorio a {user_id_str}: {e}")
                            active_reminders.append(rem)
                    else:
                        active_reminders.append(rem)
                
                if len(active_reminders) != len(reminders):
                    data[user_id_str] = active_reminders
                    dirty = True
            
            if dirty:
                save_reminders(data)

        except Exception as e:
            logger.error(f"❌ Error crítico en reminders_monitor_loop: {e}")
        
        await asyncio.sleep(30)

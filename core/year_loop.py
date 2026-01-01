# core/year_loop.py

import asyncio
from datetime import datetime
from utils.year_manager import load_subs, save_subs, get_detailed_year_message
from utils.file_manager import add_log_line

async def year_progress_loop(bot):
    """
    Bucle infinito que chequea si hay que enviar el reporte anual a los usuarios.
    """
    add_log_line("⏳ Loop de Progreso Anual iniciado.")
    
    while True:
        try:
            now = datetime.now()
            current_hour = now.hour
            today_str = now.strftime("%Y-%m-%d")
            
            subs = load_subs()
            dirty = False # Para saber si hay que guardar cambios en el json
            
            for user_id, data in subs.items():
                user_hour = data.get("hour")
                last_sent = data.get("last_sent")
                
                # Si la hora coincide Y no se ha enviado hoy
                if user_hour == current_hour and last_sent != today_str:
                    try:
                        msg = get_detailed_year_message()
                        await bot.send_message(chat_id=int(user_id), text=msg, parse_mode="Markdown")
                        
                        # Actualizar registro de enviado
                        subs[user_id]["last_sent"] = today_str
                        dirty = True
                        
                        # Pequeña pausa para no saturar si hay muchos usuarios
                        await asyncio.sleep(0.1) 
                        
                    except Exception as e:
                        add_log_line(f"❌ Error enviando Year Progress a {user_id}: {e}")
                        # Si el usuario bloqueó el bot, podrías borrarlo aquí
            
            if dirty:
                save_subs(subs)
                
            # Esperar 60 segundos antes de volver a chequear
            # Importante para no enviar múltiples veces en la misma hora y minuto
            # (Aunque la lógica de 'last_sent' ya protege eso)
            await asyncio.sleep(60)

        except Exception as e:
            add_log_line(f"⚠️ Error en year_progress_loop: {e}")
            await asyncio.sleep(60) # Esperar antes de reintentar tras error
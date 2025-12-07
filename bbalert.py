# bbalert.py - Punto de Entrada Principal del Bot de Telegram para BitBread.

import asyncio
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from utils.file_manager import add_log_line, cargar_usuarios
from utils.file_manager import guardar_usuarios
from core.config import TOKEN_TELEGRAM, ADMIN_CHAT_IDS, VERSION, PID, PYTHON_VERSION, STATE
from core.loops import (
    alerta_loop, 
    check_custom_price_alerts,
    programar_alerta_usuario, 
    get_logs_data, 
    set_enviar_mensaje_telegram_async
)
from core.i18n import _ # <-- Importar _

# --- Importación de Handlers y Utilidades ---
from handlers.general import start, myid, ver, help_command
from handlers.admin import users, logs_command, set_admin_util, set_logs_util, ms_conversation_handler, tasaimg_command, ad_command
from handlers.user_settings import (
    mismonedas, parar, cmd_temp, set_monedas_command, # <-- CAMBIADO
    set_reprogramar_alerta_util, toggle_hbd_alerts_callback, hbd_alerts_command, lang_command, set_language_callback
)
from handlers.alerts import (
    alerta_command,
    misalertas, 
    borrar_alerta_callback, 
    borrar_todas_alertas_callback,
    
)
from handlers.trading import graf_command, p_command, eltoque_command, refresh_command_callback, mk_command, ta_command


async def post_init(app: Application):
    """
    (NUEVO) Se ejecuta después de que el bot se inicializa.
    Inicia los bucles de fondo y programa las alertas para todos los usuarios existentes.
    """
    add_log_line("🤖 Bot inicializado. Iniciando tareas de fondo...")
    
    # 1. Iniciar los bucles de fondo globales
    asyncio.create_task(alerta_loop(app.bot))
    asyncio.create_task(check_custom_price_alerts(app.bot))
    add_log_line("✅ Bucles de fondo (HBD y Alertas de Cruce) iniciados.")

    # 2. Programar las alertas periódicas para cada usuario registrado
    usuarios = cargar_usuarios()
    if usuarios:
        add_log_line(f"👥 Encontrados {len(usuarios)} usuarios. Programando sus alertas periódicas...")
        for user_id, data in usuarios.items():
            intervalo_h = data.get('intervalo_alerta_h', 2.5) # Valor por defecto si no está establecido
            programar_alerta_usuario(int(user_id), intervalo_h)
    else:
        add_log_line("👥 No hay usuarios registrados. Esperando a que se unan.")
    
    add_log_line("✅ Todas las tareas de fondo han sido iniciadas.")

    try:
        # --- PLANTILLA ENVUELTA ---
        # (Se usa _() sin chat_id para que envíe en el idioma por defecto, español)
        startup_message_template = _(
            "🚀 *¡Bot en línea!* 🚀\n\n"
            "🤖 `BitBread Alert v{version}`\n"
            "🪪 `PID: {pid}`\n"
            "🐍 `Python: v{python_version}`\n\n"
            "✅ Ejecutado y funcionando perfectamente.",
            user_id 
        )
        startup_message = startup_message_template.format(
            version=VERSION,
            pid=PID,
            python_version=PYTHON_VERSION
        )

        # Enviamos el mensaje a cada admin
        for admin_id in ADMIN_CHAT_IDS:
            await app.bot.send_message(chat_id=admin_id, text=startup_message, parse_mode=ParseMode.MARKDOWN)

        add_log_line("📬 Notificación de inicio enviada a los administradores.")
    except Exception as e:
        add_log_line(f"⚠️ Fallo al enviar notificación de inicio a los admins: {e}")
    


def main():
    """Inicia el bot y configura todos los handlers."""
    
    builder = ApplicationBuilder().token(TOKEN_TELEGRAM)
    app = builder.build()
    
    # 1. FUNCIÓN DE ENVÍO DE MENSAJES
    async def enviar_mensajes(mensaje, chat_ids, parse_mode=ParseMode.MARKDOWN, reply_markup=None, photo=None):
        """
        Envía un mensaje a una lista de chat_ids y reporta errores detallados.
        Automáticamente elimina a los usuarios que han bloqueado el bot.
        """
        fallidos = {}
        usuarios_actualizados = None

        for chat_id in chat_ids:
            try:
                if photo:
                    caption = mensaje.strip() if mensaje and mensaje.strip() else None
                    await app.bot.send_photo(
                        chat_id=int(chat_id),
                        photo=photo,
                        caption=caption,
                        parse_mode=parse_mode if caption else None,
                        reply_markup=reply_markup
                    )
                elif mensaje:
                    await app.bot.send_message(
                        chat_id=int(chat_id),
                        text=mensaje,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup
                    )
                await asyncio.sleep(0.1)

            except Exception as e:
                error_str = str(e)
                fallidos[chat_id] = error_str
                add_log_line(f"❌ Fallo al enviar a {chat_id}: {error_str}")

                if "Chat not found" in error_str or "bot was blocked" in error_str:
                    if usuarios_actualizados is None:
                        usuarios_actualizados = cargar_usuarios()
                    if chat_id in usuarios_actualizados:
                        del usuarios_actualizados[chat_id]
                        add_log_line(f"🗑️ Usuario {chat_id} ha bloqueado el bot. Eliminado de la lista.")

        if usuarios_actualizados is not None:
            guardar_usuarios(usuarios_actualizados)

        return fallidos

    # 2. INYECCIÓN DE DEPENDENCIAS (Crucial)
    set_admin_util(enviar_mensajes)
    set_logs_util(get_logs_data)
    set_reprogramar_alerta_util(programar_alerta_usuario)
    set_enviar_mensaje_telegram_async(enviar_mensajes, app) # Se pasa también la app
    
    # 3. REGISTRO DE HANDLERS
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("ver", ver))
    app.add_handler(CommandHandler("mk", mk_command))
    app.add_handler(CommandHandler("ta", ta_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("logs", logs_command))    
    app.add_handler(CommandHandler("ad", ad_command))
    app.add_handler(ms_conversation_handler)  
    app.add_handler(CommandHandler("mismonedas", mismonedas))
    app.add_handler(CommandHandler("parar", parar))
    app.add_handler(CommandHandler("temp", cmd_temp))
    app.add_handler(CommandHandler("hbdalerts", hbd_alerts_command))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(CommandHandler("alerta", alerta_command))
    app.add_handler(CommandHandler("misalertas", misalertas))
    app.add_handler(CommandHandler("graf", graf_command)) 
    app.add_handler(CommandHandler("p", p_command))       
    app.add_handler(CommandHandler("tasa", eltoque_command))
    app.add_handler(CallbackQueryHandler(refresh_command_callback, pattern=r"^refresh_"))
    app.add_handler(CommandHandler("monedas", set_monedas_command))
    app.add_handler(CallbackQueryHandler(borrar_alerta_callback, pattern='^delete_alert_'))
    app.add_handler(CallbackQueryHandler(toggle_hbd_alerts_callback, pattern="^toggle_hbd_alerts$"))
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^set_lang_"))
    app.add_handler(CallbackQueryHandler(borrar_todas_alertas_callback, pattern="^delete_all_alerts$"))
    # app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, actualizar_monedas_texto))
    
    # 4. Asignar la función post_init
    app.post_init = post_init
    
    # 5. Iniciar el polling
    print("✅ Bot iniciado. Esperando mensajes...")
    add_log_line("----------- BOT INICIADO -----------")
    app.run_polling()

if __name__ == "__main__":
    main()
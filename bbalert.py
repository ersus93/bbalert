# bbalert.py - Punto de Entrada Principal del Bot de Telegram para BitBread.

import asyncio
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, PreCheckoutQueryHandler
from telegram.constants import ParseMode
from utils.file_manager import add_log_line, cargar_usuarios
from utils.file_manager import guardar_usuarios
from core.btc_loop import btc_monitor_loop, set_btc_sender
from handlers.btc_handlers import btc_handlers_list
from core.config import TOKEN_TELEGRAM, ADMIN_CHAT_IDS, VERSION, PID, PYTHON_VERSION, STATE
from core.loops import (
    alerta_loop, 
    check_custom_price_alerts,
    programar_alerta_usuario, 
    get_logs_data, 
    set_enviar_mensaje_telegram_async,
    weather_alerts_loop
)
from core.i18n import _ 
from handlers.general import start, myid, ver, help_command
from handlers.admin import users, logs_command, set_admin_util, set_logs_util, ms_conversation_handler, ad_command
from core.rss_loop import rss_monitor_loop # Importar Loop
from handlers.rss import rss_dashboard, rss_conv_handler, rss_action_handler # Importar Handlers
from handlers.user_settings import (
    mismonedas, parar, cmd_temp, set_monedas_command,
    set_reprogramar_alerta_util, toggle_hbd_alerts_callback, hbd_alerts_command, lang_command, set_language_callback
)
from handlers.alerts import (
    alerta_command,
    misalertas, 
    borrar_alerta_callback, 
    borrar_todas_alertas_callback,
    
)
from handlers.trading import graf_command, p_command, eltoque_command, refresh_command_callback, mk_command, ta_command
from handlers.pay import shop_command, shop_callback, precheckout_callback, successful_payment_callback
# === INICIO DE INTEGRACIÓN VALERTS (CORRECCIÓN IMPORTACIÓN) ===
from handlers.valerts_handlers import valerts_handlers_list
# Importación corregida: 'enviar_mensaje_seguro' no está definida aquí, la función a inyectar es local ('enviar_mensajes')
from core.valerts_loop import valerts_monitor_loop, set_valerts_sender 
# === FIN DE INTEGRACIÓN VALERTS ===

# --- CORRECCIÓN IMPORTANTE: Solo importamos lo que realmente existe en weather.py ---
from handlers.weather import (
    weather_command, 
    weather_subscribe_command, 
    weather_settings_command, 
    weather_conversation_handler, 
    weather_callback_handlers
)

async def post_init(app: Application):
    """
    (NUEVO) Se ejecuta después de que el bot se inicializa.
    Inicia los bucles de fondo y programa las alertas para todos los usuarios existentes.
    """
    add_log_line("🤖 Bot inicializado. Iniciando tareas de fondo...")

    # Iniciar bucle de clima
    asyncio.create_task(weather_alerts_loop(app.bot))
    add_log_line("✅ Bucle de alertas de clima iniciado.")

    asyncio.create_task(rss_monitor_loop(app.bot))
    add_log_line("✅ Bucle RSS iniciado.")
    
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
        # Mensaje de inicio para administradores usando idioma por defecto (español)
        startup_message_template = _(
            "🚀 *¡Bot en línea!* 🚀\n\n"
            "🤖 `BitBread Alert v{version}`\n"
            "🪪 `PID: {pid}`\n"
            "🐍 `Python: v{python_version}`\n\n"
            "✅ Ejecutado y funcionando perfectamente.",
            None  # Sin chat_id específico, usa español por defecto
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
        
    # Inicio de Loops de Monitoreo (BTC y VALERTS)
    asyncio.create_task(btc_monitor_loop(app.bot))
    # === INICIO DE INTEGRACIÓN VALERTS (AÑADIR LOOP) ===
    asyncio.create_task(valerts_monitor_loop(app.bot))
    # === FIN DE INTEGRACIÓN VALERTS ===
    

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
    set_enviar_mensaje_telegram_async(enviar_mensajes, app)
    set_btc_sender(enviar_mensajes)
    # === INICIO DE INTEGRACIÓN VALERTS (CORRECCIÓN SENDER) ===
    # Usamos la función local 'enviar_mensajes' que es la que maneja los errores y las bajas
    set_valerts_sender(enviar_mensajes) 
    # === FIN DE INTEGRACIÓN VALERTS ===
    
    # 3. REGISTRO DE HANDLERS
    app.add_handler(CommandHandler("shop", shop_command))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern="^buy_"))
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
    # === INICIO DE INTEGRACIÓN VALERTS (REGISTRO) ===
    # El registro de la lista de handlers ya estaba aquí y es correcto
    app.add_handlers(valerts_handlers_list)
    # === FIN DE INTEGRACIÓN VALERTS ===
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
    app.add_handler(CommandHandler("monedas", set_monedas_command))
    for handler in btc_handlers_list:
        app.add_handler(handler)
    
    # --- REGISTRO DE HANDLERS DE CLIMA (Corregido) ---
    app.add_handler(CommandHandler("w", weather_command))
    app.add_handler(CommandHandler("weather_sub", weather_subscribe_command))
    app.add_handler(CommandHandler("weather_settings", weather_settings_command))
    
    # La conversación debe tener prioridad alta en ciertos casos, pero aquí está bien
    app.add_handler(weather_conversation_handler)
    
    # Registramos TODOS los callbacks de clima usando la lista que viene de weather.py
    if weather_callback_handlers:
        if isinstance(weather_callback_handlers, list):
            for handler in weather_callback_handlers:
                app.add_handler(handler)
        else:
            app.add_handler(weather_callback_handlers)
            
    # NOTA: Eliminamos los registros manuales de callbacks (weather_alerttime_callback, etc.)
    # porque ya están incluidos dentro de 'weather_callback_handlers'.
    app.add_handler(CommandHandler("rss", rss_dashboard))
    app.add_handler(rss_conv_handler)
    # Otros handlers
    app.add_handler(CallbackQueryHandler(rss_action_handler, pattern="^rss_"))
    app.add_handler(CallbackQueryHandler(refresh_command_callback, pattern=r"^refresh_"))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(CallbackQueryHandler(borrar_alerta_callback, pattern='^delete_alert_'))
    app.add_handler(CallbackQueryHandler(toggle_hbd_alerts_callback, pattern="^toggle_hbd_alerts$"))
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^set_lang_"))
    app.add_handler(CallbackQueryHandler(borrar_todas_alertas_callback, pattern="^delete_all_alerts$"))
    
    # 4. Asignar la función post_init
    app.post_init = post_init
    
    # 5. Iniciar el polling
    print("✅ Bot iniciado. Esperando mensajes...")
    add_log_line("----------- BOT INICIADO -----------")
    app.run_polling()

if __name__ == "__main__":
    main()
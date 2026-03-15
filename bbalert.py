# bbalert.py - Punto de Entrada Principal del Bot de Telegram para BitBread.

import asyncio
import time
import threading
import warnings
from telegram.warnings import PTBUserWarning
from telegram import Update
from telegram.error import BadRequest, NetworkError, TimedOut, RetryAfter
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, PreCheckoutQueryHandler
from telegram.constants import ParseMode
from utils.logger import logger
from utils.file_manager import cargar_usuarios, guardar_usuarios, add_log_line
from core.btc_loop import btc_monitor_loop, set_btc_sender
from handlers.btc_handlers import btc_handlers_list, graf_from_btc_callback
from core.config import TOKEN_TELEGRAM, ADMIN_CHAT_IDS, VERSION, PID, PYTHON_VERSION, STATE
from core.loops import (
    alerta_loop, 
    check_custom_price_alerts,
    programar_alerta_usuario,   
    get_logs_data, 
    set_enviar_mensaje_telegram_async,
)
from core.weather_loop_v2 import weather_alerts_loop, weather_daily_summary_loop
from core.global_disasters_loop import global_disasters_loop
from core.i18n import _ 
from handlers.general import start, myid, ver, help_command
from handlers.admin import users, logs_command, set_admin_util, set_logs_util, ms_conversation_handler, ad_command, free_command
from handlers.year_handlers import year_command, year_sub_callback
from core.year_loop import year_progress_loop

from handlers.reminders import rec_command, reminders_conv_handler, reminders_callback_handler
from core.reminders_loop import reminders_monitor_loop


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
from handlers.trading import graf_command, graf_timeframe_callback, p_command, refresh_command_callback, mk_command, ta_quick_callback
from handlers.trading_unified import trading_command
from handlers.ta import ta_command, ta_switch_callback, ai_analysis_callback, graf_from_ta_callback
from handlers.tasa import eltoque_command, eltoque_provincias_callback, eltoque_refresh_callback
from handlers.pay import shop_command, shop_callback, precheckout_callback, successful_payment_callback
from handlers.general import start, myid, ver, help_command, start_button_callback, help_category_callback, help_back_callback

from handlers.valerts_handlers import valerts_handlers_list
from core.valerts_loop import valerts_monitor_loop, set_valerts_sender
from handlers.health import health_command
from core.rate_limiter import check_rate_limit, get_user_stats, cleanup_rate_limits

# ── SmartSignals (/sp) ────────────────────────────────────────────────────────
from handlers.sp_handlers import sp_handlers_list
from core.sp_loop import sp_monitor_loop, set_sp_sender
from core.sp_trading_loop import sp_trading_monitor_loop

from handlers.weather import (
    weather_command, 
    weather_subscribe_command, 
   weather_settings_command, 
   weather_conversation_handler, 
    weather_callback_handlers
)

from handlers.precios import show_prices as precios_command, precios_callback
from handlers.alertas import alertas_command
from handlers.ajustes import ajustes_command

# Ignorar advertencias específicas de PTB sobre CallbackQueryHandler en ConversationHandler
warnings.filterwarnings("ignore", category=PTBUserWarning, message=".*CallbackQueryHandler.*")

async def post_init(app: Application):
    """
    Se ejecuta después de que el bot se inicializa.
    Inicia los bucles de fondo y programa las alertas para todos los usuarios existentes.
    """
    
    logger.info("🤖 Bot inicializado: Iniciando tareas de fondo...")

    # Progreso Anual 
    asyncio.create_task(year_progress_loop(app.bot))
    logger.info("✅ Bucle de Progreso Anual iniciado.")

    # Iniciando recordatorios
    asyncio.create_task(reminders_monitor_loop(app.bot))
    logger.info("✅ Bucle de recordatorios iniciado.")

    # Iniciar bucles de clima separados
    asyncio.create_task(weather_alerts_loop(app.bot))
    logger.info("✅ Bucle de alertas de emergencia (clima) iniciado.")

    asyncio.create_task(weather_daily_summary_loop(app.bot))
    logger.info("✅ Bucle de resumen diario (clima) iniciado.")

    asyncio.create_task(global_disasters_loop(app.bot))
    logger.info("✅ Bucle de alertas de desastres globales iniciado.")
   
    # 1. Iniciar los bucles de fondo globales
    asyncio.create_task(alerta_loop(app.bot))
    asyncio.create_task(check_custom_price_alerts(app.bot))
    logger.info("✅ Bucles de fondo (HBD y Alertas de Cruce) iniciados.")

    # 2. Programar las alertas periódicas para cada usuario registrado
    usuarios = cargar_usuarios()
    if usuarios:
        add_log_line(f"👥 Encontrados {len(usuarios)} usuarios. Programando sus alertas periódicas...")
        for user_id, data in usuarios.items():
            intervalo_h = data.get('intervalo_alerta_h', 2.5)
            programar_alerta_usuario(int(user_id), intervalo_h)
    else:
        logger.info("👥 No hay usuarios registrados. Esperando a que se unan.")
    
    logger.info("✅ Todas las tareas de fondo han sido iniciadas.")

    # Rate limiting cleanup (cada hora)
    def cleanup_loop():
        while True:
            time.sleep(3600)  # 1 hour
            cleanup_rate_limits()
    
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()
    logger.info("✅ Hilo de cleanup de rate limits iniciado.")

    try:
        startup_message_template = _(
            "🍞 *¡Llego el pan a la bodega!* 🍞\n————————————————————\n\n"
            "🤖 `BitBread Alert v{version}`\n"
            "🪪 `PID: {pid}`\n"
            "🐍 `Python: v{python_version}`\n\n————————————————————\n"
            "✅ Ácido y aplastado, pero comible. 👍.\n"
            "🫣 ¡Vamos por mas!",
            None
        )
        startup_message = startup_message_template.format(
            version=VERSION,
            pid=PID,
            python_version=PYTHON_VERSION
        )

        for admin_id in ADMIN_CHAT_IDS:
            await app.bot.send_message(chat_id=admin_id, text=startup_message, parse_mode=ParseMode.MARKDOWN)

        logger.info("📬 Notificación de inicio enviada a los administradores.")
    except Exception as e:
        logger.error(f"⚠️ Fallo al enviar notificación de inicio a los admins: {e}")
        
    # Inicio de Loops de Monitoreo (BTC, VALERTS y SMARTSIGNALS)
    asyncio.create_task(btc_monitor_loop(app.bot))
    asyncio.create_task(valerts_monitor_loop(app.bot))
    asyncio.create_task(sp_monitor_loop(app.bot))
    asyncio.create_task(sp_trading_monitor_loop(app.bot, add_log_line))
    logger.info("✅ Bucle SmartSignals (/sp) iniciado.")
    logger.info("✅ Bucle Trading Monitor (/sp) iniciado.")


def main():
    """Inicia el bot y configura todos los handlers."""
    
    builder = ApplicationBuilder().token(TOKEN_TELEGRAM)
    app = builder.build()
    
    # 1. FUNCIÓN DE ENVÍO DE MENSAJES
    async def enviar_mensajes(mensaje, chat_ids, parse_mode=ParseMode.MARKDOWN, reply_markup=None, photo=None):
        """
        Envía mensaje a lista de chat_ids. Si falla el Markdown, reintenta en texto plano.
        """
        fallidos = {}
        usuarios_actualizados = None

        for chat_id in chat_ids:
            try:
                # Intentamos enviar con el formato original (Markdown)
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
                await asyncio.sleep(0.05) # Pequeña pausa para evitar flood limits

            except BadRequest as e:
                # SI FALLA EL FORMATO (Markdown roto), REINTENTAMOS EN TEXTO PLANO
                error_str = str(e)
                if "parse entities" in error_str or "can't find end" in error_str:
                    try:
                        logger.warning(f"⚠️ Formato Markdown fallido para {chat_id}. Reenviando como texto plano.")
                        if photo:
                            await app.bot.send_photo(
                                chat_id=int(chat_id),
                                photo=photo,
                                caption=mensaje, # Sin parse_mode
                                reply_markup=reply_markup
                            )
                        else:
                            await app.bot.send_message(
                                chat_id=int(chat_id),
                                text=mensaje, 
                                parse_mode=None, # <--- Sin formato
                                reply_markup=reply_markup
                            )
                    except Exception as e2:
                        # Si falla incluso en texto plano, entonces sí es un error real
                        fallidos[chat_id] = str(e2)
                        logger.error(f"❌ Fallo definitivo al enviar a {chat_id}: {e2}")
                else:
                    # Otros errores BadRequest (ej: chat not found)
                    fallidos[chat_id] = error_str
                    logger.error(f"❌ Error BadRequest en {chat_id}: {error_str}")

            except Exception as e:
                # Errores generales (Bloqueos, red, etc)
                error_str = str(e)
                fallidos[chat_id] = error_str
                logger.error(f"❌ Fallo al enviar a {chat_id}: {error_str}")

                if "Chat not found" in error_str or "bot was blocked" in error_str:
                    if usuarios_actualizados is None:
                        usuarios_actualizados = cargar_usuarios()
                    # chat_id is int, but dictionary keys are strings
                    if str(chat_id) in usuarios_actualizados:
                        del usuarios_actualizados[str(chat_id)]
                        logger.info(f"🗑️ Usuario {chat_id} ha bloqueado el bot. Eliminado de la lista.")

        if usuarios_actualizados is not None:
            guardar_usuarios(usuarios_actualizados)

        return fallidos

    # 2. INYECCIÓN DE DEPENDENCIAS
    set_admin_util(enviar_mensajes)
    set_logs_util(get_logs_data)
    set_reprogramar_alerta_util(programar_alerta_usuario)
    set_enviar_mensaje_telegram_async(enviar_mensajes, app)
    set_btc_sender(enviar_mensajes)
    set_valerts_sender(enviar_mensajes)
    set_sp_sender(enviar_mensajes)    # ← SmartSignals
    
        # 3. REGISTRO DE HANDLERS
    
    # ============================================
    # IMPORTANTE: Handlers de conversación PRIMERO
    # ============================================
    
    # 1️⃣ ConversationHandler de CLIMA (DEBE IR PRIMERO)
    app.add_handler(weather_conversation_handler)
    
    # 2️⃣ ConversationHandler de Mensajes Admin
    app.add_handler(ms_conversation_handler)

    app.add_handler(reminders_conv_handler)

    # ============================================
    # Comandos generales
    # ============================================
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("ver", ver))
    app.add_handler(CommandHandler("help", help_command))
    
    # ============================================
    # Comandos de Admin
    # ============================================
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CommandHandler("ad", ad_command))
    app.add_handler(CommandHandler("free", free_command))
    app.add_handler(CommandHandler("health", health_command))
    
    # ============================================
    # Comandos de Trading/Cripto
    # ============================================
    app.add_handler(CommandHandler("mk", mk_command))
    app.add_handler(CommandHandler("trading", trading_command))
    app.add_handler(CommandHandler("graf", graf_command))
    app.add_handler(CommandHandler("p", p_command))
    app.add_handler(CommandHandler("tasa", eltoque_command))
    app.add_handler(CommandHandler("ta", ta_command))
    app.add_handler(CommandHandler("precios", precios_command))
    
    # ============================================
    # Comandos de Usuario
    # ============================================
    app.add_handler(CommandHandler("mismonedas", mismonedas))
    app.add_handler(CommandHandler("monedas", set_monedas_command))
    app.add_handler(CommandHandler("parar", parar))
    app.add_handler(CommandHandler("temp", cmd_temp))
    app.add_handler(CommandHandler("ajustes", ajustes_command))
    app.add_handler(CommandHandler("hbdalerts", hbd_alerts_command))
    app.add_handler(CommandHandler("lang", lang_command))
    
    # ============================================
    # Comandos de Alertas
    # ============================================
    app.add_handler(CommandHandler("alerta", alerta_command))
    app.add_handler(CommandHandler("misalertas", misalertas))
    app.add_handler(CommandHandler("alertas", alertas_command))
    
    # ============================================
    # Comandos de CLIMA (comandos directos, NO conversación)
    # ============================================
    app.add_handler(CommandHandler("w", weather_command))
    app.add_handler(CommandHandler("weather_settings", weather_settings_command))
    app.add_handler(CommandHandler("wsub", weather_subscribe_command))
    
    # ============================================
    # Comandos de PAGO
    # ============================================
    app.add_handler(CommandHandler("shop", shop_command))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    
    app.add_handler(CommandHandler("rec", rec_command))
    
    # ============================================
    # Handlers de BTC y VALERTS (listas)
    # ============================================
    for handler in btc_handlers_list:
        app.add_handler(handler)
    
    app.add_handlers(valerts_handlers_list)

    # ── SmartSignals (/sp) ────────────────────────────────────────────────────
    for handler in sp_handlers_list:
        app.add_handler(handler)
    
    # ============================================
    # CallbackQueryHandlers (DEBEN IR AL FINAL)
    # ============================================

    # Callbacks de /start buttons
    app.add_handler(CallbackQueryHandler(start_button_callback, pattern="^start_"))

    # Callbacks de /help categories - help_back DEBE ir primero porque ^help_ también captura help_back
    app.add_handler(CallbackQueryHandler(help_back_callback, pattern="^help_back$"))
    app.add_handler(CallbackQueryHandler(help_category_callback, pattern="^help_"))

    # Callbacks de Clima
    if weather_callback_handlers:
        if isinstance(weather_callback_handlers, list):
            for handler in weather_callback_handlers:
                app.add_handler(handler)
        else:
            app.add_handler(weather_callback_handlers)

    app.add_handler(CommandHandler("y", year_command))
    
    # Callbacks de Trading
    app.add_handler(CallbackQueryHandler(reminders_callback_handler, pattern="^rem_"))
    app.add_handler(CallbackQueryHandler(year_sub_callback, pattern="^year_sub_"))
    app.add_handler(CallbackQueryHandler(ta_switch_callback, pattern="^ta_switch\\|"))
    app.add_handler(CallbackQueryHandler(ai_analysis_callback, pattern="^ai_analyze\\|"))
    app.add_handler(CallbackQueryHandler(graf_from_ta_callback, pattern="^graf_from_ta\\|"))
    app.add_handler(CallbackQueryHandler(graf_from_btc_callback, pattern="^graf_from_btc\\|"))
    app.add_handler(CallbackQueryHandler(graf_timeframe_callback, pattern="^graf_tf\\|"))
    app.add_handler(CallbackQueryHandler(refresh_command_callback, pattern=r"^refresh_"))
    app.add_handler(CallbackQueryHandler(ta_quick_callback, pattern=r"^ta_quick\|"))
    app.add_handler(CallbackQueryHandler(eltoque_refresh_callback, pattern="^eltoque_refresh$"))
    app.add_handler(CallbackQueryHandler(eltoque_provincias_callback, pattern="^eltoque_provincias$"))
    
    # Callbacks de Alertas
    app.add_handler(CallbackQueryHandler(borrar_alerta_callback, pattern='^delete_alert_'))
    app.add_handler(CallbackQueryHandler(borrar_todas_alertas_callback, pattern="^delete_all_alerts$"))
    
    # Callbacks de Configuración
    app.add_handler(CallbackQueryHandler(toggle_hbd_alerts_callback, pattern="^toggle_hbd_alerts$"))
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^set_lang_"))
    
    # Callbacks de Pago
    app.add_handler(CallbackQueryHandler(shop_callback, pattern="^buy_"))
    
    # Callbacks de Precios
    app.add_handler(CallbackQueryHandler(precios_callback, pattern="^precios_"))
    
    # 4. Asignar la función post_init
    app.post_init = post_init

    # ── Error handler global ──────────────────────────────────────────────────
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Captura excepciones no manejadas y las loguea limpiamente.
        - Categoriza errores para mejor debugging
        - Envía feedback friendly al usuario
        - Maneja errores transitorios automáticamente
        """
        from core.errors import (
            categorize_error, 
            ErrorCategory, 
            get_user_message,
            log_error_with_context,
            send_error_message
        )
        from utils.user_data import obtener_datos_usuario
        
        err = context.error
        category = categorize_error(err)
        
        # Obtener idioma del usuario si está disponible
        user_lang = "es"
        if update and hasattr(update, 'effective_user') and update.effective_user:
            try:
                user_data = obtener_datos_usuario(update.effective_user.id)
                user_lang = user_data.get('language', 'es')
            except Exception:
                pass
        
        # Manejar errores transitorios
        from telegram.error import RetryAfter, NetworkError, TimedOut
        
        if isinstance(err, (NetworkError, TimedOut)):
            # Errores de red esperados - solo log
            logger.debug(f"🌐 Error de red transitorio: {err}")
            return
            
        if isinstance(err, RetryAfter):
            # Flood control - esperar y reintentar
            logger.warning(f"⏳ Flood control: esperando {err.retry_after}s")
            await asyncio.sleep(err.retry_after)
            return
        
        # Loguear error categorizado
        log_error_with_context(category, err, update, context=context.bot)
        
        # Enviar mensaje friendly al usuario
        await send_error_message(update, category, user_lang)

    app.add_error_handler(error_handler)
    # ─────────────────────────────────────────────────────────────────────────
    
    # 5. Iniciar el polling
    print("✅ BitBread iniciado. Esperando mensajes...")
    add_log_line("----------- 🤖 BitBread INICIADO -----------")
    app.run_polling()

if __name__ == "__main__":
    main()
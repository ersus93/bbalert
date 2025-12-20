# handlers/tasa.py

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.file_manager import add_log_line, check_feature_access, registrar_uso_comando
# Importamos las nuevas funciones de historial BCC
from utils.tasa_manager import (
    load_eltoque_history, save_eltoque_history, obtener_tasas_eltoque,
    load_bcc_history, save_bcc_history,
    load_cadeca_history, save_cadeca_history
)
from utils.image_generator import generar_imagen_tasas_eltoque
from utils.ads_manager import get_random_ad_text
from utils.bcc_scraper import obtener_tasas_bcc
from utils.cadeca_scraper import obtener_tasas_cadeca
from core.i18n import _

async def eltoque_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id 

    # === GUARDIA DE PAGO ===
#    acceso, mensaje = check_feature_access(chat_id, 'tasa_limit')
#    if not acceso:
#        if update.callback_query:
#           await update.callback_query.answer(mensaje, show_alert=True)
#        else:
#            await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
#        return
    
#    registrar_uso_comando(chat_id, 'tasa')
    
    # Manejo del mensaje de estado (botón vs comando)
    msg_estado = None
    if update.callback_query:
        await update.callback_query.answer()
        # Intentamos borrar el mensaje anterior para que se vea fresco
        try: await update.callback_query.message.delete()
        except: pass
        msg_estado = await context.bot.send_message(user_id, _("⏳ Conectando con fuentes (ElToque, CADECA & BCC)...", user_id))
    else:
        msg_estado = await update.message.reply_text(_("⏳ Conectando con fuentes (ElToque, CADECA & BCC)...", user_id))

    loop = asyncio.get_running_loop()
    
    # --- FUNCIÓN HELPER PARA EJECUCIÓN SEGURA ---
    async def fetch_safe(func, timeout_secs, name):
        """Ejecuta una función síncrona en un hilo con timeout individual."""
        try:
            return await asyncio.wait_for(loop.run_in_executor(None, func), timeout=timeout_secs)
        except asyncio.TimeoutError:
            add_log_line(f"⚠️ Timeout individual en {name}")
            return None
        except Exception as e:
            add_log_line(f"❌ Error en {name}: {e}")
            return None

    # Ejecutar peticiones en paralelo, pero con timeouts INDIVIDUALES
    # Si CADECA falla, BCC y ElToque siguen vivos.
    tasas_data, tasas_bcc, tasas_cadeca = await asyncio.gather(
        fetch_safe(obtener_tasas_eltoque, 12, "ElToque"),
        fetch_safe(obtener_tasas_bcc, 10, "BCC"),
        fetch_safe(obtener_tasas_cadeca, 8, "CADECA") # Timeout menor para CADECA pq suele fallar
    )
    # Reintento rápido solo para ElToque si falló
    if not tasas_data:
        try:
            tasas_data = await loop.run_in_executor(None, obtener_tasas_eltoque)
        except: pass
    
    # Si ElToque falla definitivamente, error
    if not tasas_data:
        try:
            await msg_estado.edit_text(_("⚠️ *Error de Conexión*.\nNo se pudieron obtener datos de El Toque.", user_id), parse_mode=ParseMode.MARKDOWN)
        except: 
            # Fallback por si el mensaje fue borrado
            await context.bot.send_message(user_id, _("⚠️ *Error de Conexión*.", user_id))
        return 

    try:
        # --- PROCESAMIENTO EL TOQUE ---
        tasas_actuales = tasas_data.get('tasas')
        tasas_anteriores = load_eltoque_history() 
        save_eltoque_history(tasas_actuales) 

        fecha = tasas_data.get('date', '')
        hora = tasas_data.get('hour', 0)
        minutos = tasas_data.get('minutes', 0)
        timestamp_str = f"{fecha} {hora:02d}:{minutos:02d}"
        TOLERANCIA = 0.0001

        # 1. BLOQUE EL TOQUE (Informal)
        mensaje_texto_final = _("📊 *MERCADO INFORMAL (El Toque)*\n—————————————————\n", user_id)
        mensaje_lineas = []
        monedas_ordenadas = [  'ECU',   'USD',   'MLC',   'ZELLE',   'BTC',   'TRX', 'USDT_TRC20']
            
        for moneda_key in monedas_ordenadas:
            if moneda_key in tasas_actuales:
                tasa_actual = tasas_actuales[moneda_key]
                tasa_anterior = tasas_anteriores.get(moneda_key)
                
                moneda_display = 'USDT' if moneda_key == 'USDT_TRC20' else ('EUR' if moneda_key == 'ECU' else moneda_key)
                
                indicador = ""
                cambio_str = ""
                if tasa_anterior is not None:
                    diferencia = tasa_actual - tasa_anterior
                    if diferencia > TOLERANCIA:
                        indicador = "🔺"
                        cambio_str = f" +{diferencia:,.2f}"
                    elif diferencia < -TOLERANCIA:
                        indicador = "🔻"
                        cambio_str = f" {diferencia:,.2f}"
                    
                linea = f" *{moneda_display}:*   {tasa_actual:,.2f}  *CUP* {indicador}{cambio_str}"
                mensaje_lineas.append(linea)

        mensaje_texto_final += "\n".join(mensaje_lineas)


        # 2. BLOQUE CADECA (CON FALLBACK A HISTORIAL)
        tasas_anteriores_cadeca = load_cadeca_history()
        es_dato_viejo = False

        if not tasas_cadeca:
            # Si falló la conexión, usamos lo que tenemos guardado
            tasas_cadeca = tasas_anteriores_cadeca
            es_dato_viejo = True
            
        if tasas_cadeca:
            if not es_dato_viejo:
                save_cadeca_history(tasas_cadeca)
            
            titulo_cadeca = "🏢 *CADECA (Casas de Cambio)*\n└── _Aeropuertos, Puertos y Hoteles_\n"
            if es_dato_viejo:
                titulo_cadeca += " ⚠️ _(Caché) WEB OUT_"
                
            mensaje_texto_final += f"\n\n•••\n\n{titulo_cadeca}\n—————————————————\n"
            orden_cadeca = ['EUR', 'USD', 'MLC', 'CAD', 'MXN', 'GBP', 'CHF', 'RUB', 'AUD', 'JPY']
            
            mensaje_texto_final += "_Moneda_     _Compra_      _Venta_\n"

            for m in orden_cadeca:
                if m in tasas_cadeca:
                    compra = tasas_cadeca[m]['compra']
                    venta = tasas_cadeca[m]['venta']
                    
                    indicador = ""
                    # Solo comparamos si el dato actual es fresco
                    if not es_dato_viejo:
                        anterior = tasas_anteriores_cadeca.get(m, {})
                        venta_anterior = anterior.get('venta')
                        if venta_anterior:
                            dif = venta - venta_anterior
                            if dif > TOLERANCIA: indicador = "🔺"
                            elif dif < -TOLERANCIA: indicador = "🔻"

                    # Formato en columnas simuladas con espacios
                    # Ajusta los espacios según necesites. 
                    # Ejem: USD    120.00   125.00
                    linea = f" *{m}*          {compra:6.2f}       {venta:6.2f}  {indicador}"
                    mensaje_texto_final += linea + "\n"
        else:
             mensaje_texto_final += "\n•••\n\n🏢 *CADECA (Casas de Cambio)*\n└── _Aeropuertos, Puertos y Hoteles_\n—————————————————\n ⚠️ No disponible\n_Probablemente esten sin corriente 🫣_"

        # 3. BLOQUE BCC (Oficial) - CON HISTORIAL
        if tasas_bcc:
            # Cargar y guardar historial BCC
            tasas_anteriores_bcc = load_bcc_history()
            save_bcc_history(tasas_bcc)

            mensaje_texto_final += "\n•••\n\n🏛 *TASA OFICIAL (BCC)*\n—————————————————\n"
            orden_bcc = [  'EUR',  'USD',  'MLC',  'CAD',  'MXN',  'GBP',  'CHF',    'RUB',  'AUD',    'JPY']
            
            for m in orden_bcc:
                if m in tasas_bcc:
                    val_actual = tasas_bcc[m]
                    val_anterior = tasas_anteriores_bcc.get(m)
                    
                    indicador_bcc = ""
                    cambiobcc_str = ""
                    
                    # CORRECCIÓN AQUÍ: Usamos val_anterior y val_actual
                    if val_anterior is not None:
                        diferencia = val_actual - val_anterior
                        
                        if diferencia > TOLERANCIA:
                            indicador_bcc = "🔺"  # CORREGIDO: antes decía 'indicador'
                            cambiobcc_str = f" +{diferencia:,.2f}"
                        elif diferencia < -TOLERANCIA:
                            indicador_bcc = "🔻"  # CORREGIDO: antes decía 'indicador'
                            cambiobcc_str = f" {diferencia:,.2f}"

                    mensaje_texto_final += f"*{m}:*   {val_actual:,.2f}   *CUP*  {indicador_bcc}{cambiobcc_str}\n"
            
            # Otras monedas
            for m, val in tasas_bcc.items():
                if m not in orden_bcc:
                    mensaje_texto_final += f"*{m}:* {val:,.2f}  *CUP*\n"
        else:
             mensaje_texto_final += "\n\n•••\n\n🏛 *TASA OFICIAL (BCC)\n—————————————————\n ⚠️ No disponible"

        # Footer
        actualizado_label = _("📆", user_id)
        fuente_label = _("*Fuentes de consulta:*\n🔗 _elToque.com\n🔗 www.cadeca.cu\n🔗 www.bc.gob.cu_", user_id)
        mensaje_texto_final += f"\n—————————————————\n_{actualizado_label} {timestamp_str}_\n{fuente_label}"
        mensaje_texto_final += get_random_ad_text()

        # Generar Imagen
        image_bio = await asyncio.to_thread(generar_imagen_tasas_eltoque)
        
        keyboard = [
            [InlineKeyboardButton("🗺 Ver Tasas por Provincia", callback_data="eltoque_provincias")],
            [InlineKeyboardButton("🔄 Actualizar", callback_data="eltoque_refresh")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # ENVIO FINAL ROBUSTO
        try:
            if image_bio:
                # Intentamos borrar el mensaje de "Conectando..." antes de enviar la foto
                try: await msg_estado.delete()
                except: pass
                
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=image_bio, 
                    caption=mensaje_texto_final, 
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup 
                )
            else:
                await msg_estado.edit_text(
                    mensaje_texto_final, 
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
        except Exception as e_send:
            add_log_line(f"⚠️ Error enviando foto en /tasa: {e_send}. Reintentando solo texto.")
            # Si falla enviar la foto (timeout de subida), enviamos solo el texto
            await context.bot.send_message(
                chat_id=chat_id,
                text=mensaje_texto_final,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )

    except Exception as e:
        add_log_line(f"Error fatal en /tasa: {e}.")
        try:
            await msg_estado.edit_text(_("❌ Ocurrió un error inesperado.", user_id), parse_mode=ParseMode.MARKDOWN)
        except: pass

async def eltoque_provincias_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # 1. Avisar a Telegram que recibimos el clic
    await query.answer("🗺 Cargando datos provinciales...")
    
    add_log_line("🔍 Iniciando solicitud de provincias...")

    try:
        # Obtener datos (reusamos la función existente)
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, obtener_tasas_eltoque)

        # DEBUG: Ver qué claves llegan realmente
        if data:
            print(f"🔍 CLAVES JSON ELTOQUE: {list(data.keys())}")
        else:
            print("❌ DATA es None")

        # 2. Verificar si existen datos de provincias
        # La API pública 'v1/trmi' a veces NO trae 'provincias'.
        if not data or 'provincias' not in data:
            add_log_line("⚠️ La clave 'provincias' no está en el JSON de la API.")
            
            # FALLBACK: Editamos el mensaje para que el usuario sepa que falló
            msj_error = "⚠️ *Datos provinciales no disponibles.*\nLa API actual solo devolvió tasas nacionales."
            keyboard_back = [[InlineKeyboardButton("🔙 Volver a Nacional", callback_data="eltoque_refresh")]]
            
            if query.message.photo:
                await query.edit_message_caption(
                    caption=msj_error, 
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(keyboard_back)
                )
            else:
                await query.edit_message_text(
                    text=msj_error, 
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(keyboard_back)
                )
            return

        # 3. Si hay datos, construimos el mensaje
        provincias_data = data['provincias']
        mensaje = "🗺 *TASAS POR PROVINCIAS*\n—————————————————\n"
        
        hay_datos = False
        for nombre, info in provincias_data.items():
            # Ajusta 'tasa' según la estructura real del JSON (puede ser 'compra', 'venta' o un promedio)
            # A veces llega como objeto, a veces como número directo.
            valor = 0
            if isinstance(info, dict):
                valor = info.get('tasa', info.get('promedio', 0))
            elif isinstance(info, (int, float)):
                valor = info
            
            if valor > 0:
                mensaje += f"📍 *{nombre}:* {valor} CUP\n"
                hay_datos = True

        if not hay_datos:
            mensaje += "⚠️ Datos vacíos o estructura desconocida.\n"

        mensaje += get_random_ad_text()
        
        # 4. Editar el mensaje final
        keyboard = [[InlineKeyboardButton("🔙 Volver a Nacional", callback_data="eltoque_refresh")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query.message.photo:
            await query.edit_message_caption(
                caption=mensaje, 
                parse_mode=ParseMode.MARKDOWN, 
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                text=mensaje, 
                parse_mode=ParseMode.MARKDOWN, 
                reply_markup=reply_markup
            )

    except Exception as e:
        add_log_line(f"❌ Error CRÍTICO en provincias: {e}")
        # Intentamos enviar un mensaje nuevo si la edición falla
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Error al procesar provincias. Revisa los logs.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="eltoque_refresh")]])
            )
        except:
            pass


async def eltoque_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve a mostrar las tasas nacionales desde el botón de Provincias."""
    query = update.callback_query
    await query.answer("🔄 Recargando tasas nacionales...")
    
    # Simulamos que el usuario escribió /tasa de nuevo
    # Creamos un objeto simulado para reutilizar la lógica
    context.args = []  # Sin argumentos (comportamiento por defecto)
    
    # Llamamos al comando original
    await eltoque_command(update, context)
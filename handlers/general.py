# handlers/general.py 

import asyncio
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from utils.file_manager import (
    registrar_usuario, 
    obtener_monedas_usuario, 
    load_last_prices_status
)
from core.api_client import obtener_precios_control
from core.config import ADMIN_CHAT_IDS
from core.i18n import _

#  Telegram comando /start 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start. Registra al usuario."""

    user = update.effective_user
    user_id = user.id
    user_lang = user.language_code
    
    registrar_usuario(user_id, user_lang)
    
    nombre_usuario = update.effective_user.first_name

    mensaje = _(
    "*Hola👋 {nombre_usuario}!* Bienvenido a BitBreadAlert.\n\n"
    "Para recibir alertas periódicas con los precios de tu lista de monedas, "
    "usa el comando `/monedas` seguido de los símbolos separados por comas. "
    "Puedes usar *cualquier* símbolo de criptomoneda listado en CoinMarketCap. Ejemplo:\n\n"
    "`/monedas BTC, ETH, TRX, HIVE, ADA`\n\n"
    "Puedes modificar la temporalidad de esta alerta en cualquier momento con el comando /temp seguido de las horas (entre 0.5 y 24.0).\n"
    "Ejemplo: /temp 2.5 (para 2 horas y 30 minutos)\n\n"
    "Usa /help para ver todos los comandos disponibles.",
    user_id
    ).format(nombre_usuario=nombre_usuario) 

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)

# COMANDO /ver REFACTORIZADO
async def ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra los precios actuales de la lista de monedas del usuario.
    No afecta al cronómetro de la alerta periódica.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # 1. Obtener las monedas configuradas por el usuario
    monedas = obtener_monedas_usuario(chat_id)
    
    if not monedas:
        await update.message.reply_text(
            _("⚠️ No tienes monedas configuradas. Usa /monedas para añadir algunas.", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # 2. Notificar que estamos cargando (ya que la API puede tardar un segundo)
    mensaje_espera = await update.message.reply_text(_("⏳ Consultando precios actuales...", user_id))

    # 3. Obtener precios en tiempo real
    precios_actuales = obtener_precios_control(monedas)
    
    if not precios_actuales:
        await mensaje_espera.edit_text(
            _("❌ No se pudieron obtener los precios en este momento. Intenta luego.", user_id)
        )
        return

    # 4. Cargar precios anteriores (SOLO LECTURA) para mostrar tendencias
    # No guardamos nada aquí para no romper la lógica de "cambio desde la última alerta".
    todos_precios_anteriores = load_last_prices_status()
    precios_anteriores_usuario = todos_precios_anteriores.get(str(chat_id), {})

    # 5. Construir el mensaje
    mensaje = _("📊 *Precios Actuales (Tu Lista):*\n\n", user_id)
    
    TOLERANCIA = 0.0000001
    
    for moneda in monedas:
        p_actual = precios_actuales.get(moneda)
        p_anterior = precios_anteriores_usuario.get(moneda)
        
        if p_actual is not None:
            # Calcular indicador visual
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

    # Añadir fecha
    fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    mensaje += f"\n_📅 Consulta: {fecha_actual}_"

    # 6. Editar el mensaje de espera con el resultado final
    await mensaje_espera.edit_text(mensaje, parse_mode=ParseMode.MARKDOWN)

# ============================================================

# COMANDO /myid para ver datos del usuario
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /myid. Muestra el ID de chat del usuario."""
    user_id = update.effective_user.id
    user = update.effective_user

    nombre_completo = user.first_name or 'N/A'
    username_str = f"@{user.username}" if user.username else 'N/A'


    mensaje_template = _(
        "Estos son tus datos de Telegram:\n\n"
        "Nombre: {nombre}\n"
        "Usuario: {usuario}\n"
        "ID: `{id_chat}`",
        user_id 
    )


    mensaje = mensaje_template.format(
        nombre=nombre_completo,
        usuario=username_str,
        id_chat=user_id
    )

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)



# === COMANDO /help ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de ayuda con todos los comandos."""
    user_id = update.effective_user.id
    chat_id_str = str(user_id)


    help_text_template = _(
        "👋 ¡Hola! Aquí tienes la lista de comandos disponibles:\n\n"
        "📊 *Alertas Periódicas (Tu Lista)*\n"
        "  • `/monedas <LISTA>`: Define tu lista de monedas (ej. `/monedas BTC, ETH, HIVE`).\n"
        "  • `/mismonedas`: Muestra tu lista de monedas actual.\n"
        "  • `/temp <HORAS>`: Cambia cada cuántas horas recibes tu alerta (ej. `/temp 2.5`).\n"
        "  • `/parar`: Detiene tus alertas periódicas (borra tu lista).\n\n"
        "🔔 *Alertas de Cruce (Precio Fijo)*\n"
        "  • `/alerta <MONEDA> <PRECIO>`: Crea una alerta cuando una moneda cruza un precio (ej. `/alerta BTC 60000`).\n"
        "  • `/misalertas`: Muestra y te permite borrar tus alertas de cruce activas.\n\n"
        "📈 *Comandos de Consulta*\n"
        "  • `/p <MONEDA>`: Muestra el precio detallado de una moneda (ej. `/p HIVE`).\n"
        "  • `/graf <MONEDA> [PAR] <TIEMPO>`: Genera un gráfico (ej. `/graf BTC 1h` o `/graf HIVE USDT 15m`).\n"
        "  • `/tasa`: Muestra las tasas de cambio de ElToque (para CUP).\n"
        "  • `/ver`: Consulta al instante los precios de tu lista de monedas sin afectar tu alerta periódica.\n\n"
        "⚙️ *Configuración y Varios*\n"
        "  • `/hbdalerts`: Activa o desactiva las alertas predefinidas de HBD.\n"
        "  • `/lang`: Cambia el idioma del bot.\n"
        "  • `/myid`: Muestra tu información de usuario de Telegram.\n"
        "  • `/start`: Muestra el mensaje de bienvenida.\n"
        "  • `/help`: Muestra este menú de ayuda.\n"
        , user_id
    )


    admin_help_text_template = _(
        "\n\n"
        "🔑 *Comandos de Administrador*\n"
        "  • `/users`: Muestra la lista de todos los usuarios registrados.\n"
        "  • `/logs [N]`: Muestra las últimas N líneas del log del bot.\n"
        "  • `/ms`: Inicia el asistente para enviar un mensaje masivo a todos los usuarios.\n"
        , user_id
    )


    message = help_text_template
    if chat_id_str in ADMIN_CHAT_IDS:
        message += admin_help_text_template

    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

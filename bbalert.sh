#!/bin/bash

# ¿Cómo usar este script?
# Sube el script a tu VPS, dentro de la carpeta donde tienes el bbalert.py y el requirements.txt (ej: /home/ersus/bbalert/).
# Dale permisos de ejecución con (solo necesitas hacer esto una vez): chmod +x bbalert.sh
# Asegurate de tener el directorio "bbalert" con los archivos del bot (bbalert.py, requirements.txt, etc).
# Los puedes obtener clonando con "git clone https://github.com/ersus93/bbalert/" o subiendo los archivos manualmente.
# Luego, simplemente ejecuta este script de esta forma "./bbalert.sh" para instalar y gestionar el bot.

# ==========================================
# GESTOR DE BOT DE TELEGRAM (BBAlert)
# ==========================================

# --- CONFIGURACIÓN DE VERSIÓN ---
# Definimos la versión exacta de Python que queremos usar.
# La 3.12 es actualmente la más equilibrada entre novedad y estabilidad.
TARGET_PYTHON="python3.12"

# Definimos variables automáticas
SERVICE_NAME="bbalert"
PROJECT_DIR=$(pwd)   # Detecta la carpeta actual
CURRENT_USER=$(whoami) # Detecta tu usuario actual
VENV_DIR="$PROJECT_DIR/venv"
# Dentro del venv, el binario siempre se llama 'python' (es un link a la versión real)
PYTHON_BIN="$VENV_DIR/bin/python" 
PIP_BIN="$VENV_DIR/bin/pip"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

# Colores para el menú
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Función para comprobar si es root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        SUDO="sudo"
    else
        SUDO=""
    fi
}

install_bot() {
    echo -e "${YELLOW}--- INICIANDO INSTALACIÓN PROFESIONAL ---${NC}"
    echo -e "${CYAN}Objetivo: Instalar $TARGET_PYTHON y configurar servicio.${NC}"
    
    # 1. Preparar PPA para Python actualizado
    echo -e "${GREEN}1. Agregando repositorio 'deadsnakes' (para tener el último Python)...${NC}"
    $SUDO apt update
    $SUDO apt install -y software-properties-common
    $SUDO add-apt-repository ppa:deadsnakes/ppa -y
    $SUDO apt update

    # 2. Instalar la versión específica de Python y dependencias
    echo -e "${GREEN}2. Instalando $TARGET_PYTHON y herramientas...${NC}"
    # Instalamos la versión base, el módulo venv específico y dev tools
    $SUDO apt install -y $TARGET_PYTHON ${TARGET_PYTHON}-venv ${TARGET_PYTHON}-dev python3-pip

    # 3. Crear entorno virtual con la versión específica
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${GREEN}3. Creando entorno virtual con $TARGET_PYTHON...${NC}"
        # IMPORTANTE: Usamos el binario específico (ej: python3.12 -m venv ...)
        $TARGET_PYTHON -m venv venv
        
        # Actualizamos pip dentro del entorno para evitar errores
        echo "Actualizando pip interno..."
        "$PIP_BIN" install --upgrade pip
    else
        echo -e "${YELLOW}El entorno virtual ya existe. Saltando creación.${NC}"
    fi

    # 4. Instalar requirements.txt
    if [ -f "requirements.txt" ]; then
        echo -e "${GREEN}4. Instalando librerías desde requirements.txt...${NC}"
        "$PIP_BIN" install -r requirements.txt
    else
        echo -e "${RED}ERROR: No se encontró requirements.txt en $PROJECT_DIR${NC}"
        return
    fi

    # 5. Crear archivo de servicio Systemd
    echo -e "${GREEN}5. Configurando servicio Systemd...${NC}"
    
    SERVICE_CONTENT="[Unit]
Description=Bot de Telegram BBAlert
After=network.target

[Service]
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON_BIN $PROJECT_DIR/bbalert.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target"

    echo "$SERVICE_CONTENT" | $SUDO tee $SERVICE_FILE > /dev/null

    # 6. Activar servicio
    echo -e "${GREEN}6. Activando el bot...${NC}"
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable $SERVICE_NAME
    $SUDO systemctl start $SERVICE_NAME

    echo -e "${GREEN}✅ ¡INSTALACIÓN COMPLETADA!${NC}"
    echo -e "Python usado: $($PYTHON_BIN --version)"
    echo -e "El bot se iniciará automáticamente al reiniciar el VPS."
    read -p "Presiona Enter para volver al menú..."
}

manage_service() {
    ACTION=$1
    echo -e "${YELLOW}Ejecutando: $ACTION bbalert...${NC}"
    $SUDO systemctl $ACTION $SERVICE_NAME
    
    if [ "$ACTION" == "status" ]; then
        read -p "Presiona Enter para volver..."
    else
        echo -e "${GREEN}Comando enviado.${NC}"
        sleep 1
    fi
}

view_logs() {
    echo -e "${YELLOW}Mostrando logs en tiempo real (Presiona Ctrl+C para salir)...${NC}"
    $SUDO journalctl -u $SERVICE_NAME -f
}

# --- MENÚ PRINCIPAL ---
check_root

while true; do
    clear
    echo -e "${GREEN}=====================================${NC}"
    echo -e "   🤖 GESTOR BBALERT ($CURRENT_USER)   "
    echo -e "${GREEN}=====================================${NC}"
    echo "1. 🛠  INSTALAR TODO DESDE 0 (Con $TARGET_PYTHON)"
    echo "2. ▶️  Iniciar Bot"
    echo "3. ⏹️  Detener Bot"
    echo "4. 🔄 Reiniciar Bot"
    echo "5. 📊 Ver Estado (Status)"
    echo "6. 📜 Ver Logs (Tiempo Real)"
    echo "7. ❌ Salir"
    echo -e "${GREEN}=====================================${NC}"
    read -p "Selecciona una opción: " option

    case $option in
        1) install_bot ;;
        2) manage_service "start" ;;
        3) manage_service "stop" ;;
        4) manage_service "restart" ;;
        5) manage_service "status" ;;
        6) view_logs ;;
        7) echo "Adiós 👋"; exit ;;
        *) echo -e "${RED}Opción no válida${NC}"; sleep 1 ;;
    esac
done
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
TARGET_PYTHON="python3.12"

# 1. DETECCIÓN DE USUARIO Y RUTAS ABSOLUTAS
CURRENT_USER=$(whoami)
PROJECT_DIR="/home/$CURRENT_USER/bbalert"

# Definimos el resto de rutas
VENV_DIR="$PROJECT_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python" 
PIP_BIN="$VENV_DIR/bin/pip"
SERVICE_NAME="bbalert"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
REQUIREMENTS_FILE="$PROJECT_DIR/requirements.txt"

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# --- VALIDACIÓN INICIAL ---
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}ERROR CRÍTICO:${NC} No se encuentra el directorio del bot."
    echo -e "Ruta esperada: ${YELLOW}$PROJECT_DIR${NC}"
    exit 1
fi

check_root() {
    if [ "$EUID" -ne 0 ]; then SUDO="sudo"; else SUDO=""; fi
}

install_bot() {
    echo -e "${YELLOW}--- INSTALACIÓN ---${NC}"
    
    echo -e "${GREEN}1. Repositorios...${NC}"
    $SUDO apt update && $SUDO apt install -y software-properties-common
    $SUDO add-apt-repository ppa:deadsnakes/ppa -y && $SUDO apt update

    echo -e "${GREEN}2. Instalando Python...${NC}"
    $SUDO apt install -y $TARGET_PYTHON ${TARGET_PYTHON}-venv ${TARGET_PYTHON}-dev python3-pip

    echo -e "${GREEN}3. Entorno virtual...${NC}"
    if [ ! -d "$VENV_DIR" ]; then
        cd "$PROJECT_DIR" || exit
        $TARGET_PYTHON -m venv venv
        "$PIP_BIN" install --upgrade pip
    fi

    check_dependencies "install_mode"

    echo -e "${GREEN}5. Configurando servicio...${NC}"
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

    $SUDO systemctl daemon-reload
    $SUDO systemctl enable $SERVICE_NAME
    $SUDO systemctl start $SERVICE_NAME

    echo -e "${GREEN}✅ INSTALACIÓN COMPLETADA${NC}"
    read -p "Enter para volver..."
}

manage_service() {
    ACTION=$1
    echo -e "${YELLOW}Ejecutando: $ACTION...${NC}"
    $SUDO systemctl $ACTION $SERVICE_NAME
    if [ "$ACTION" == "status" ]; then read -p "Enter para volver..."; else sleep 1; fi
}

view_logs() {
    echo -e "${YELLOW}Logs en tiempo real (Ctrl+C para salir)...${NC}"
    $SUDO journalctl -u $SERVICE_NAME -f
}

check_dependencies() {
    MODE=$1 
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        echo -e "${RED}Falta requirements.txt${NC}"; read -p "Enter..."; return
    fi

    "$PIP_BIN" install -r "$REQUIREMENTS_FILE"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Dependencias OK.${NC}"
    else
        echo -e "${RED}❌ Error en dependencias.${NC}"
    fi

    if [ "$MODE" != "install_mode" ]; then
        read -p "¿Reiniciar el bot ahora? (s/n): " restart_opt
        if [[ "$restart_opt" =~ ^[sS]$ ]]; then manage_service "restart"; fi
    fi
}

remove_dependency() {
    if [ ! -f "$REQUIREMENTS_FILE" ]; then echo -e "${RED}Falta requirements.txt${NC}"; sleep 2; return; fi

    mapfile -t lines < <(grep -v '^\s*$' "$REQUIREMENTS_FILE" | grep -v '^\s*#')
    
    if [ ${#lines[@]} -eq 0 ]; then echo -e "${YELLOW}Lista vacía.${NC}"; read -p "Enter..."; return; fi

    echo -e "${CYAN}--- LISTA DE DEPENDENCIAS ---${NC}"
    i=1
    for line in "${lines[@]}"; do echo -e "$i) ${YELLOW}$line${NC}"; ((i++)); done
    echo -e "${GREEN}0) Cancelar${NC}"
    
    read -p "Número a eliminar: " selection

    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -gt 0 ] && [ "$selection" -le "${#lines[@]}" ]; then
        SELECTED_LINE="${lines[$((selection-1))]}"
        PACKAGE_NAME=$(echo "$SELECTED_LINE" | sed -E 's/([a-zA-Z0-9_\-]+).*/\1/')

        echo -e "${RED}Eliminando $PACKAGE_NAME...${NC}"
        "$PIP_BIN" uninstall -y "$PACKAGE_NAME"
        grep -vF "$SELECTED_LINE" "$REQUIREMENTS_FILE" > "${REQUIREMENTS_FILE}.tmp" && mv "${REQUIREMENTS_FILE}.tmp" "$REQUIREMENTS_FILE"
        
        read -p "¿Reiniciar bot? (s/n): " restart_opt
        if [[ "$restart_opt" =~ ^[sS]$ ]]; then manage_service "restart"; fi
    fi
}

# --- MENÚ PRINCIPAL ---
check_root

while true; do
    clear
    echo -e "${GREEN}=====================================${NC}"
    echo -e "   🤖 GESTOR BBALERT ($CURRENT_USER)   "
    echo -e "${GREEN}=====================================${NC}"
    echo -e "${CYAN}Ruta: $PROJECT_DIR${NC}"
    echo "-------------------------------------"
    echo "1. 🛠  Instalar Todo (Desde 0)"
    echo "2. ▶️ Iniciar Bot"
    echo "3. ⏹️ Detener Bot"
    echo "4. 🔄 Reiniciar Bot"
    echo "5. 📊 Ver Estado"
    echo "6. 📜 Ver Logs en tiempo real"
    echo "7. 📥 Verificar/Instalar Dependencias"
    echo "8. 🗑️ Eliminar Dependencias"
    echo "9. ❌ Salir"
    echo -e "${GREEN}=====================================${NC}"
    read -p "Selecciona: " option

    case $option in
        1) install_bot ;;
        2) manage_service "start" ;;
        3) manage_service "stop" ;;
        4) manage_service "restart" ;;
        5) manage_service "status" ;;
        6) view_logs ;;
        7) check_dependencies ;;
        8) remove_dependency ;;
        9) echo "Adiós 👋"; exit ;;
        *) echo -e "${RED}Opción no válida${NC}"; sleep 1 ;;
    esac
done
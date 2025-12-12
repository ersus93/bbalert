#!/bin/bash

# ==========================================
# GESTOR MULTI-BOT DE TELEGRAM (BBAlert v2)
# ==========================================
# Autor: Modificado para robustez y dinamismo
# Uso: ./manager.sh

# --- CONFIGURACIÓN GLOBAL ---
TARGET_PYTHON="python3.12"
CURRENT_USER=$(whoami)

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# --- FUNCIONES DE UTILIDAD ---

check_root() {
    if [ "$EUID" -ne 0 ]; then SUDO="sudo"; else SUDO=""; fi
}

get_absolute_path() {
    # Convierte rutas relativas a absolutas
    echo "$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
}

select_target_directory() {
    clear
    echo -e "${CYAN}--- SELECCIÓN DE DIRECTORIO DEL BOT ---${NC}"
    
    # 1. Intenta detectar si estamos DENTRO de la carpeta del bot
    if [ -f "bbalert.py" ] && [ -f "requirements.txt" ]; then
        DETECTED_DIR=$(pwd)
        echo -e "Detectado bot en directorio actual: ${GREEN}$DETECTED_DIR${NC}"
        read -p "¿Usar este directorio? (S/n): " confirm
        if [[ "$confirm" =~ ^[sS]$ ]] || [[ -z "$confirm" ]]; then
            PROJECT_DIR="$DETECTED_DIR"
        fi
    fi

    # 2. Si no se detectó o el usuario dijo NO, pedir ruta manual
    while [ -z "$PROJECT_DIR" ]; do
        echo -e "${YELLOW}Ingresa la ruta de la carpeta del bot (ej: /home/ersus/bbalert_v2):${NC}"
        read -e -p "> " INPUT_DIR
        
        # Expandir tilde (~) si el usuario la usa
        INPUT_DIR="${INPUT_DIR/#\~/$HOME}"
        
        if [ -d "$INPUT_DIR" ]; then
            # Verificar si parece un bot válido
            if [ -f "$INPUT_DIR/bbalert.py" ]; then
                PROJECT_DIR=$(cd "$INPUT_DIR" && pwd) # Obtener ruta absoluta real
            else
                echo -e "${RED}Error: No veo 'bbalert.py' en esa carpeta.${NC}"
            fi
        else
            echo -e "${RED}Error: El directorio no existe.${NC}"
        fi
    done

    # --- CONFIGURACIÓN DE VARIABLES DEPENDIENTES DEL DIRECTORIO ---
    FOLDER_NAME=$(basename "$PROJECT_DIR")
    SERVICE_NAME="${FOLDER_NAME}" # El servicio se llama como la carpeta
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
    
    VENV_DIR="$PROJECT_DIR/venv"
    PYTHON_BIN="$VENV_DIR/bin/python" 
    PIP_BIN="$VENV_DIR/bin/pip"
    REQUIREMENTS_FILE="$PROJECT_DIR/requirements.txt"
}

install_bot() {
    echo -e "${YELLOW}--- INSTALACIÓN PARA: $FOLDER_NAME ---${NC}"
    
    echo -e "${GREEN}1. Actualizando Repositorios del Sistema...${NC}"
    $SUDO apt update -qq
    $SUDO apt install -y software-properties-common -qq
    $SUDO add-apt-repository ppa:deadsnakes/ppa -y > /dev/null 2>&1
    $SUDO apt update -qq

    echo -e "${GREEN}2. Verificando Python $TARGET_PYTHON...${NC}"
    $SUDO apt install -y $TARGET_PYTHON ${TARGET_PYTHON}-venv ${TARGET_PYTHON}-dev python3-pip -qq

    echo -e "${GREEN}3. Configurando Entorno Virtual (venv)...${NC}"
    if [ ! -d "$VENV_DIR" ]; then
        echo "   Creando venv nuevo en $VENV_DIR..."
        $TARGET_PYTHON -m venv "$VENV_DIR"
        "$PIP_BIN" install --upgrade pip -q
    else
        echo "   ✅ Venv ya existe. Verificando integridad..."
        if [ ! -f "$PYTHON_BIN" ]; then
            echo -e "${RED}   Venv corrupto. Recreando...${NC}"
            rm -rf "$VENV_DIR"
            $TARGET_PYTHON -m venv "$VENV_DIR"
        fi
    fi

    echo -e "${GREEN}4. Instalando Dependencias...${NC}"
    check_dependencies "silent"

    echo -e "${GREEN}5. Creando Servicio Systemd ($SERVICE_NAME)...${NC}"
    # Creamos el servicio dinámicamente apuntando a ESTA carpeta y ESTE venv
    SERVICE_CONTENT="[Unit]
Description=Bot Telegram ($FOLDER_NAME)
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

    echo "$SERVICE_CONTENT" | $SUDO tee "$SERVICE_FILE" > /dev/null

    $SUDO systemctl daemon-reload
    $SUDO systemctl enable "$SERVICE_NAME"
    $SUDO systemctl restart "$SERVICE_NAME"

    echo -e "${GREEN}✅ INSTALACIÓN COMPLETADA. Servicio: $SERVICE_NAME${NC}"
    read -p "Presiona Enter para volver..."
}

manage_service() {
    ACTION=$1
    echo -e "${YELLOW}Ejecutando $ACTION en $SERVICE_NAME...${NC}"
    $SUDO systemctl "$ACTION" "$SERVICE_NAME"
    
    # Si es status, mostramos y esperamos. Si no, solo pausa breve.
    if [ "$ACTION" == "status" ]; then 
        read -p "Presiona Enter para volver..."
    else 
        sleep 1
    fi
}

view_logs() {
    echo -e "${YELLOW}Viendo logs de $SERVICE_NAME (Ctrl+C para salir)...${NC}"
    $SUDO journalctl -u "$SERVICE_NAME" -f
}

check_dependencies() {
    MODE=$1
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        if [ "$MODE" != "silent" ]; then echo -e "${RED}Falta requirements.txt${NC}"; read -p "Enter..."; fi
        return
    fi

    echo "   Instalando desde requirements.txt..."
    "$PIP_BIN" install -r "$REQUIREMENTS_FILE"

    if [ "$MODE" != "silent" ]; then
        echo -e "${GREEN}✅ Dependencias actualizadas.${NC}"
        read -p "¿Reiniciar el bot para aplicar cambios? (s/n): " restart_opt
        if [[ "$restart_opt" =~ ^[sS]$ ]]; then manage_service "restart"; fi
    fi
}

remove_dependency() {
    if [ ! -f "$REQUIREMENTS_FILE" ]; then echo -e "${RED}Falta requirements.txt${NC}"; sleep 2; return; fi

    mapfile -t lines < <(grep -v '^\s*$' "$REQUIREMENTS_FILE" | grep -v '^\s*#')
    
    if [ ${#lines[@]} -eq 0 ]; then echo -e "${YELLOW}Lista vacía.${NC}"; read -p "Enter..."; return; fi

    echo -e "${CYAN}--- LISTA DE DEPENDENCIAS INSTALADAS ---${NC}"
    i=1
    for line in "${lines[@]}"; do echo -e "$i) ${YELLOW}$line${NC}"; ((i++)); done
    echo -e "${GREEN}0) Cancelar${NC}"
    
    read -p "Número a eliminar: " selection

    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -gt 0 ] && [ "$selection" -le "${#lines[@]}" ]; then
        SELECTED_LINE="${lines[$((selection-1))]}"
        PACKAGE_NAME=$(echo "$SELECTED_LINE" | sed -E 's/([a-zA-Z0-9_\-]+).*/\1/')

        echo -e "${RED}Eliminando $PACKAGE_NAME...${NC}"
        "$PIP_BIN" uninstall -y "$PACKAGE_NAME"
        # Eliminar del archivo requirements
        grep -vF "$SELECTED_LINE" "$REQUIREMENTS_FILE" > "${REQUIREMENTS_FILE}.tmp" && mv "${REQUIREMENTS_FILE}.tmp" "$REQUIREMENTS_FILE"
        
        echo -e "${GREEN}Eliminado.${NC}"
        read -p "¿Reiniciar bot? (s/n): " restart_opt
        if [[ "$restart_opt" =~ ^[sS]$ ]]; then manage_service "restart"; fi
    fi
}

change_directory() {
    PROJECT_DIR=""
    select_target_directory
}

# --- INICIO DEL SCRIPT ---
check_root
select_target_directory

while true; do
    clear
    echo -e "${GREEN}=====================================${NC}"
    echo -e "   🤖 GESTOR MULTI-BOT (${CYAN}$FOLDER_NAME${NC})   "
    echo -e "${GREEN}=====================================${NC}"
    echo -e "Directorio: ${YELLOW}$PROJECT_DIR${NC}"
    echo -e "Servicio:   ${YELLOW}$SERVICE_NAME${NC}"
    echo "-------------------------------------"
    echo "1. 🛠  Instalar/Reparar (Crea Venv + Systemd)"
    echo "2. ▶️  Iniciar Bot"
    echo "3. ⏹️  Detener Bot"
    echo "4. 🔄 Reiniciar Bot"
    echo "5. 📊 Ver Estado"
    echo "6. 📜 Ver Logs en vivo"
    echo "7. 📥 Instalar Librerías (requirements.txt)"
    echo "8. 🗑️  Eliminar Librería"
    echo "-------------------------------------"
    echo "9. 📂 Cambiar Directorio de Bot Objetivo"
    echo "0. ❌ Salir"
    echo -e "${GREEN}=====================================${NC}"
    read -p "Selecciona: " option

    case $option in
        1) install_bot ;;
        2) manage_service "start" ;;
        3) manage_service "stop" ;;
        4) manage_service "restart" ;;
        5) manage_service "status" ;;
        6) view_logs ;;
        7) check_dependencies "interactive" ;;
        8) remove_dependency ;;
        9) change_directory ;;
        0) echo "Adiós 👋"; exit ;;
        *) echo -e "${RED}Opción no válida${NC}"; sleep 1 ;;
    esac
done
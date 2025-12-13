#!/bin/bash

# ============================================
# BitBread Bot - Script de Instalación y Gestión
# Gestor Multi-Bot (nombre del servicio = nombre del directorio)
# ============================================

# === CONFIGURACIÓN ===
TARGET_PYTHON="python3.13"  # Versión de Python a usar
VENV_DIR="venv"
BOT_SCRIPT="bbalert.py"

# Obtener el nombre del directorio actual (nombre del bot)
BOT_NAME=$(basename "$PWD")
SERVICE_NAME="${BOT_NAME}.service"

# Colores para mensajes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # Sin color

# === FUNCIONES AUXILIARES ===

print_header() {
    echo -e "${BLUE}"
    echo "============================================"
    echo "$1"
    echo "============================================"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Verificar si el script se ejecuta como root
check_root() {
    if [ "$EUID" -eq 0 ]; then
        print_warning "No ejecutes este script como root directamente."
        print_info "Usa: sudo -u tu_usuario ./setup.sh"
        exit 1
    fi
}

# Verificar si Python está instalado
check_python() {
    print_info "Verificando instalación de Python..."
    
    if ! command -v $TARGET_PYTHON &> /dev/null; then
        print_error "$TARGET_PYTHON no está instalado."
        print_info "Instálalo con: sudo apt install ${TARGET_PYTHON} ${TARGET_PYTHON}-venv ${TARGET_PYTHON}-dev -y"
        exit 1
    fi
    
    local python_version=$($TARGET_PYTHON --version 2>&1)
    print_success "Encontrado: $python_version"
}

# Crear entorno virtual si no existe
create_venv() {
    print_header "CONFIGURACIÓN DEL ENTORNO VIRTUAL"
    
    if [ -d "$VENV_DIR" ]; then
        print_warning "El entorno virtual ya existe en: $VENV_DIR"
        read -p "¿Deseas recrearlo? (s/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            print_info "Eliminando entorno virtual existente..."
            rm -rf "$VENV_DIR"
        else
            print_info "Usando entorno virtual existente."
            return 0
        fi
    fi
    
    print_info "Creando entorno virtual con $TARGET_PYTHON..."
    
    # Crear el venv con la versión específica de Python
    $TARGET_PYTHON -m venv "$VENV_DIR"
    
    if [ $? -ne 0 ]; then
        print_error "Falló la creación del entorno virtual."
        print_info "Asegúrate de tener instalado: sudo apt install ${TARGET_PYTHON}-venv -y"
        exit 1
    fi
    
    print_success "Entorno virtual creado exitosamente en: $VENV_DIR"
    
    # Verificar que el directorio de activación existe
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        print_error "No se encontró el script de activación en $VENV_DIR/bin/activate"
        exit 1
    fi
}

# Activar entorno virtual
activate_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        print_error "El entorno virtual no existe. Créalo primero con la opción 1."
        exit 1
    fi
    
    print_info "Activando entorno virtual..."
    source "$VENV_DIR/bin/activate"
    
    if [ $? -eq 0 ]; then
        print_success "Entorno virtual activado: $(which python)"
        python --version
    else
        print_error "Falló la activación del entorno virtual."
        exit 1
    fi
}

# Instalar dependencias
install_dependencies() {
    print_header "INSTALACIÓN DE DEPENDENCIAS PARA: $BOT_NAME"
    
    # Asegurar que el venv existe
    if [ ! -d "$VENV_DIR" ]; then
        print_info "Creando entorno virtual primero..."
        create_venv
    fi
    
    # Activar el entorno virtual
    activate_venv
    
    # Actualizar pip
    print_info "Actualizando pip..."
    pip install --upgrade pip
    
    # Instalar dependencias
    if [ -f "requirements.txt" ]; then
        print_info "Instalando dependencias desde requirements.txt..."
        pip install -r requirements.txt
        
        if [ $? -eq 0 ]; then
            print_success "Todas las dependencias instaladas correctamente."
        else
            print_error "Hubo errores al instalar algunas dependencias."
            exit 1
        fi
    else
        print_error "No se encontró el archivo requirements.txt"
        exit 1
    fi
    
    # Mostrar paquetes instalados
    print_info "Paquetes instalados:"
    pip list
}

# Configurar variables de entorno
configure_env() {
    print_header "CONFIGURACIÓN DE VARIABLES DE ENTORNO - $BOT_NAME"
    
    if [ -f ".env" ]; then
        print_warning "Ya existe un archivo .env"
        read -p "¿Deseas reconfigurarlo? (s/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Ss]$ ]]; then
            print_info "Conservando configuración existente."
            return 0
        fi
    fi
    
    print_info "Creando archivo .env..."
    
    # Solicitar datos al usuario
    read -p "🔑 TOKEN de Telegram Bot: " TELEGRAM_TOKEN
    read -p "👤 ADMIN_CHAT_IDS (separados por coma): " ADMIN_IDS
    read -p "🌦️  OpenWeatherMap API Key (opcional, Enter para omitir): " WEATHER_KEY
    
    # Crear archivo .env
    cat > .env << EOF
# ============================================
# $BOT_NAME - Variables de Entorno
# ============================================

# Token del Bot de Telegram (Requerido)
TOKEN_TELEGRAM=$TELEGRAM_TOKEN

# IDs de administradores separados por comas (Requerido)
ADMIN_CHAT_IDS=$ADMIN_IDS

# API Key de OpenWeatherMap (Opcional)
OPENWEATHER_API_KEY=$WEATHER_KEY

# Otras configuraciones opcionales
# DEBUG=False
EOF
    
    chmod 600 .env  # Permisos restrictivos para seguridad
    print_success "Archivo .env creado exitosamente."
}

# Crear servicio systemd
create_service() {
    print_header "CREACIÓN DE SERVICIO SYSTEMD: $SERVICE_NAME"
    
    local current_dir=$(pwd)
    local current_user=$(whoami)
    local python_path="$current_dir/$VENV_DIR/bin/python"
    local script_path="$current_dir/$BOT_SCRIPT"
    
    # Verificar que los archivos existan
    if [ ! -f "$python_path" ]; then
        print_error "No se encontró Python en: $python_path"
        print_info "Asegúrate de haber creado el entorno virtual primero."
        exit 1
    fi
    
    if [ ! -f "$script_path" ]; then
        print_error "No se encontró el script del bot en: $script_path"
        exit 1
    fi
    
    # Crear archivo de servicio temporal
    local service_file="/tmp/$SERVICE_NAME"
    
    print_info "Generando configuración del servicio..."
    cat > "$service_file" << EOF
[Unit]
Description=$BOT_NAME - BitBread Alert Bot (Telegram)
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$current_user
WorkingDirectory=$current_dir
Environment="PATH=$current_dir/$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$python_path $script_path
Restart=always
RestartSec=10

# Seguridad adicional
NoNewPrivileges=true
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$BOT_NAME

[Install]
WantedBy=multi-user.target
EOF
    
    # Copiar el servicio a systemd (requiere sudo)
    print_info "Instalando servicio systemd (se requiere sudo)..."
    sudo cp "$service_file" "/etc/systemd/system/$SERVICE_NAME"
    
    if [ $? -ne 0 ]; then
        print_error "Falló la instalación del servicio."
        exit 1
    fi
    
    # Recargar systemd
    sudo systemctl daemon-reload
    
    # Habilitar el servicio
    sudo systemctl enable "$SERVICE_NAME"
    
    print_success "Servicio $SERVICE_NAME creado y habilitado."
    print_info "Comandos útiles:"
    echo "  • Iniciar:  sudo systemctl start $SERVICE_NAME"
    echo "  • Detener:  sudo systemctl stop $SERVICE_NAME"
    echo "  • Estado:   sudo systemctl status $SERVICE_NAME"
    echo "  • Logs:     sudo journalctl -u $SERVICE_NAME -f"
}

# Iniciar el bot
start_bot() {
    print_header "INICIANDO EL BOT: $BOT_NAME"
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_warning "El servicio ya está corriendo."
        read -p "¿Deseas reiniciarlo? (s/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            sudo systemctl restart "$SERVICE_NAME"
            print_success "Servicio reiniciado."
        fi
    else
        sudo systemctl start "$SERVICE_NAME"
        sleep 2
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            print_success "Bot $BOT_NAME iniciado exitosamente."
        else
            print_error "El bot no pudo iniciarse. Revisa los logs:"
            echo "  sudo journalctl -u $SERVICE_NAME -n 50"
        fi
    fi
}

# Detener el bot
stop_bot() {
    print_header "DETENIENDO EL BOT: $BOT_NAME"
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        sudo systemctl stop "$SERVICE_NAME"
        print_success "Bot $BOT_NAME detenido."
    else
        print_warning "El bot no está corriendo."
    fi
}

# Ver estado del bot
status_bot() {
    print_header "ESTADO DEL BOT: $BOT_NAME"
    sudo systemctl status "$SERVICE_NAME" --no-pager
}

# Ver logs en tiempo real
view_logs() {
    print_header "LOGS DEL BOT: $BOT_NAME (Ctrl+C para salir)"
    sudo journalctl -u "$SERVICE_NAME" -f
}

# Desinstalar servicio
uninstall_service() {
    print_header "DESINSTALACIÓN DEL SERVICIO: $SERVICE_NAME"
    
    print_warning "Esto eliminará el servicio systemd de $BOT_NAME"
    read -p "¿Estás seguro? (s/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        print_info "Operación cancelada."
        return 0
    fi
    
    # Detener el servicio si está corriendo
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_info "Deteniendo servicio..."
        sudo systemctl stop "$SERVICE_NAME"
    fi
    
    # Deshabilitar el servicio
    sudo systemctl disable "$SERVICE_NAME" 2>/dev/null
    
    # Eliminar el archivo del servicio
    if [ -f "/etc/systemd/system/$SERVICE_NAME" ]; then
        sudo rm "/etc/systemd/system/$SERVICE_NAME"
        print_success "Servicio eliminado."
    fi
    
    # Recargar systemd
    sudo systemctl daemon-reload
    sudo systemctl reset-failed
    
    print_success "Servicio $SERVICE_NAME desinstalado completamente."
}

# Instalación completa automática
full_install() {
    print_header "INSTALACIÓN COMPLETA AUTOMÁTICA - $BOT_NAME"
    
    # 1. Verificar Python
    check_python
    
    # 2. Crear entorno virtual
    create_venv
    
    # 3. Instalar dependencias
    install_dependencies
    
    # 4. Configurar variables de entorno
    configure_env
    
    # 5. Crear servicio
    create_service
    
    # 6. Iniciar bot
    start_bot
    
    print_header "✅ INSTALACIÓN COMPLETADA - $BOT_NAME"
    print_success "El bot está ahora corriendo como servicio systemd."
    print_info "Servicio: $SERVICE_NAME"
    print_info "Usa './setup.sh' para ver el menú de gestión."
}

# Menú principal
show_menu() {
    clear
    print_header "BITBREAD BOT - MENÚ DE GESTIÓN"
    echo -e "${CYAN}Bot:${NC} $BOT_NAME"
    echo -e "${CYAN}Servicio:${NC} $SERVICE_NAME"
    echo -e "${CYAN}Directorio:${NC} $(pwd)"
    echo ""
    echo "1)  📦 Instalar/Actualizar Dependencias"
    echo "2)  ⚙️  Configurar Variables de Entorno (.env)"
    echo "3)  🔧 Crear/Actualizar Servicio Systemd"
    echo "4)  ▶️  Iniciar Bot"
    echo "5)  ⏹️  Detener Bot"
    echo "6)  🔄 Reiniciar Bot"
    echo "7)  📊 Ver Estado"
    echo "8)  📜 Ver Logs (tiempo real)"
    echo "9)  🚀 Instalación Completa (Todo automático)"
    echo "10) 🗑️  Desinstalar Servicio"
    echo "0)  ❌ Salir"
    echo ""
    echo -e "${BLUE}Estado actual:${NC}"
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo -e "  ${GREEN}● Bot en ejecución${NC}"
    else
        echo -e "  ${RED}○ Bot detenido${NC}"
    fi
    echo ""
}

# === PROGRAMA PRINCIPAL ===

# Verificar que no se ejecuta como root
check_root

# Si se pasa argumento "--install", hacer instalación completa
if [ "$1" == "--install" ]; then
    full_install
    exit 0
fi

# Menú interactivo
while true; do
    show_menu
    read -p "Selecciona una opción: " choice
    
    case $choice in
        1)
            install_dependencies
            read -p "Presiona Enter para continuar..."
            ;;
        2)
            configure_env
            read -p "Presiona Enter para continuar..."
            ;;
        3)
            create_service
            read -p "Presiona Enter para continuar..."
            ;;
        4)
            start_bot
            read -p "Presiona Enter para continuar..."
            ;;
        5)
            stop_bot
            read -p "Presiona Enter para continuar..."
            ;;
        6)
            sudo systemctl restart "$SERVICE_NAME"
            print_success "Bot $BOT_NAME reiniciado."
            read -p "Presiona Enter para continuar..."
            ;;
        7)
            status_bot
            read -p "Presiona Enter para continuar..."
            ;;
        8)
            view_logs
            ;;
        9)
            full_install
            read -p "Presiona Enter para continuar..."
            ;;
        10)
            uninstall_service
            read -p "Presiona Enter para continuar..."
            ;;
        0)
            print_info "¡Hasta luego!"
            exit 0
            ;;
        *)
            print_error "Opción inválida."
            read -p "Presiona Enter para continuar..."
            ;;
    esac
done

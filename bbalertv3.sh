#!/bin/bash

# ============================================
# GESTOR MULTI-BOT DE TELEGRAM (BBAlert v3)
# Versión Mejorada con Detección Automática
# ============================================
# Características:
# - Detección inteligente de bots
# - Gestión multi-directorio
# - Creación robusta de venv
# - Soporte Python 3.12 y 3.13
# ============================================

# --- CONFIGURACIÓN GLOBAL ---
DEFAULT_PYTHON="python3.13"  # Versión preferida
FALLBACK_PYTHON="python3.12" # Versión alternativa
CURRENT_USER=$(whoami)
BOT_MAIN_FILE="bbalert.py"   # Archivo principal del bot
REQUIREMENTS_FILE="requirements.txt"

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# --- FUNCIONES DE UTILIDAD ---

print_header() {
    clear
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  $1"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""
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

print_step() {
    echo -e "${MAGENTA}▶ $1${NC}"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then 
        SUDO="sudo"
    else 
        SUDO=""
        print_warning "Ejecutando como root. Se recomienda usar un usuario normal."
    fi
}

# Detectar versión de Python disponible
detect_python() {
    print_step "Detectando versión de Python disponible..."
    
    if command -v $DEFAULT_PYTHON &> /dev/null; then
        TARGET_PYTHON=$DEFAULT_PYTHON
        print_success "Usando $DEFAULT_PYTHON"
        return 0
    elif command -v $FALLBACK_PYTHON &> /dev/null; then
        TARGET_PYTHON=$FALLBACK_PYTHON
        print_warning "Python 3.13 no disponible, usando $FALLBACK_PYTHON"
        return 0
    else
        print_error "No se encontró Python 3.12 ni 3.13"
        print_info "Instala Python con: sudo apt install python3.13 python3.13-venv python3.13-dev -y"
        return 1
    fi
}

# Validar si un directorio contiene un bot válido
validate_bot_directory() {
    local dir=$1
    
    if [ ! -d "$dir" ]; then
        return 1
    fi
    
    if [ ! -f "$dir/$BOT_MAIN_FILE" ]; then
        return 1
    fi
    
    if [ ! -f "$dir/$REQUIREMENTS_FILE" ]; then
        return 1
    fi
    
    return 0
}

# Seleccionar directorio del bot
select_target_directory() {
    print_header "🔍 SELECCIÓN DE DIRECTORIO DEL BOT"
    
    # 1. Verificar si estamos dentro de un directorio de bot
    if validate_bot_directory "$(pwd)"; then
        DETECTED_DIR=$(pwd)
        print_success "Detectado bot en directorio actual:"
        echo -e "   ${CYAN}$DETECTED_DIR${NC}"
        echo ""
        read -p "¿Usar este directorio? (S/n): " confirm
        
        if [[ "$confirm" =~ ^[nN]$ ]]; then
            DETECTED_DIR=""
        else
            PROJECT_DIR="$DETECTED_DIR"
        fi
    fi

    # 2. Si no se detectó o el usuario rechazó, buscar en subdirectorios comunes
    if [ -z "$PROJECT_DIR" ]; then
        print_info "Buscando bots en subdirectorios..."
        
        local found_bots=()
        local search_paths=(
            "$HOME"
            "$HOME/bots"
            "$HOME/telegram"
            "/opt"
            "$(pwd)"
        )
        
        for base_path in "${search_paths[@]}"; do
            if [ -d "$base_path" ]; then
                while IFS= read -r -d '' bot_dir; do
                    if validate_bot_directory "$bot_dir"; then
                        found_bots+=("$bot_dir")
                    fi
                done < <(find "$base_path" -maxdepth 2 -name "$BOT_MAIN_FILE" -type f -print0 2>/dev/null | xargs -0 dirname -z 2>/dev/null)
            fi
        done
        
        # Eliminar duplicados
        found_bots=($(printf '%s\n' "${found_bots[@]}" | sort -u))
        
        if [ ${#found_bots[@]} -gt 0 ]; then
            echo ""
            print_success "Se encontraron ${#found_bots[@]} bot(s):"
            echo ""
            for i in "${!found_bots[@]}"; do
                local bot_name=$(basename "${found_bots[$i]}")
                echo -e "  ${GREEN}$((i+1)))${NC} ${CYAN}$bot_name${NC}"
                echo -e "      ${found_bots[$i]}"
            done
            echo -e "  ${YELLOW}0)${NC} Ingresar ruta manualmente"
            echo ""
            
            read -p "Selecciona un bot (0-${#found_bots[@]}): " selection
            
            if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -gt 0 ] && [ "$selection" -le "${#found_bots[@]}" ]; then
                PROJECT_DIR="${found_bots[$((selection-1))]}"
            fi
        fi
    fi

    # 3. Solicitar ruta manual si es necesario
    while [ -z "$PROJECT_DIR" ]; do
        echo ""
        print_info "Ingresa la ruta completa del bot:"
        echo -e "${YELLOW}Ejemplos:${NC}"
        echo "  • /home/$CURRENT_USER/bbalert_v2"
        echo "  • ~/bots/mi_bot"
        echo "  • ./bot_folder"
        echo ""
        read -e -p "Ruta: " INPUT_DIR
        
        # Expandir tilde y rutas relativas
        INPUT_DIR="${INPUT_DIR/#\~/$HOME}"
        INPUT_DIR=$(realpath "$INPUT_DIR" 2>/dev/null || echo "$INPUT_DIR")
        
        if validate_bot_directory "$INPUT_DIR"; then
            PROJECT_DIR="$INPUT_DIR"
            print_success "Directorio válido confirmado."
        else
            print_error "No se encontró un bot válido en ese directorio."
            print_info "Asegúrate que contenga: $BOT_MAIN_FILE y $REQUIREMENTS_FILE"
            echo ""
            read -p "¿Intentar con otro directorio? (S/n): " retry
            if [[ "$retry" =~ ^[nN]$ ]]; then
                print_error "Operación cancelada."
                exit 1
            fi
        fi
    done

    # --- CONFIGURACIÓN DE VARIABLES DEPENDIENTES ---
    PROJECT_DIR=$(realpath "$PROJECT_DIR")
    FOLDER_NAME=$(basename "$PROJECT_DIR")
    SERVICE_NAME="${FOLDER_NAME}"
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
    
    VENV_DIR="$PROJECT_DIR/venv"
    PYTHON_BIN="$VENV_DIR/bin/python"
    PIP_BIN="$VENV_DIR/bin/pip"
    ACTIVATE_SCRIPT="$VENV_DIR/bin/activate"
    REQUIREMENTS_PATH="$PROJECT_DIR/$REQUIREMENTS_FILE"
    BOT_SCRIPT_PATH="$PROJECT_DIR/$BOT_MAIN_FILE"
    
    echo ""
    print_success "Configuración cargada:"
    echo -e "  ${CYAN}Nombre:${NC}     $FOLDER_NAME"
    echo -e "  ${CYAN}Ruta:${NC}       $PROJECT_DIR"
    echo -e "  ${CYAN}Servicio:${NC}   $SERVICE_NAME"
    echo ""
    sleep 1
}

# Crear entorno virtual robusto
create_venv() {
    print_header "🔧 CONFIGURACIÓN DEL ENTORNO VIRTUAL"
    
    # Verificar que estamos en el directorio correcto
    cd "$PROJECT_DIR" || {
        print_error "No se pudo acceder al directorio del bot."
        return 1
    }
    
    print_info "Directorio de trabajo: $(pwd)"
    
    # Eliminar venv existente si está corrupto
    if [ -d "$VENV_DIR" ]; then
        print_warning "Ya existe un entorno virtual en: $VENV_DIR"
        
        # Verificar integridad
        if [ ! -f "$ACTIVATE_SCRIPT" ] || [ ! -f "$PYTHON_BIN" ]; then
            print_warning "El entorno virtual está corrupto."
            read -p "¿Eliminar y recrear? (S/n): " recreate
            
            if [[ ! "$recreate" =~ ^[nN]$ ]]; then
                print_step "Eliminando entorno virtual corrupto..."
                rm -rf "$VENV_DIR"
            else
                print_error "No se puede continuar con un venv corrupto."
                return 1
            fi
        else
            print_success "El entorno virtual existente parece estar bien."
            read -p "¿Recrearlo de todos modos? (s/N): " force_recreate
            
            if [[ "$force_recreate" =~ ^[sS]$ ]]; then
                print_step "Eliminando entorno virtual existente..."
                rm -rf "$VENV_DIR"
            else
                print_info "Usando entorno virtual existente."
                return 0
            fi
        fi
    fi
    
    # Detectar Python disponible
    if ! detect_python; then
        return 1
    fi
    
    # Verificar que python -m venv está disponible
    print_step "Verificando módulo venv..."
    if ! $TARGET_PYTHON -m venv --help &>/dev/null; then
        print_error "El módulo venv no está disponible para $TARGET_PYTHON"
        print_info "Instálalo con:"
        echo "  sudo apt update"
        echo "  sudo apt install ${TARGET_PYTHON}-venv ${TARGET_PYTHON}-dev -y"
        return 1
    fi
    
    # Crear el entorno virtual
    print_step "Creando entorno virtual con $TARGET_PYTHON..."
    echo -e "${CYAN}Ejecutando: $TARGET_PYTHON -m venv venv${NC}"
    
    $TARGET_PYTHON -m venv "$VENV_DIR"
    
    if [ $? -ne 0 ]; then
        print_error "Falló la creación del entorno virtual."
        print_info "Verifica los permisos del directorio y que tengas espacio en disco."
        return 1
    fi
    
    # Verificar que se creó correctamente
    if [ ! -f "$ACTIVATE_SCRIPT" ]; then
        print_error "No se encontró el script de activación."
        return 1
    fi
    
    if [ ! -f "$PYTHON_BIN" ]; then
        print_error "No se encontró el intérprete de Python en el venv."
        return 1
    fi
    
    print_success "Entorno virtual creado exitosamente."
    
    # Activar y actualizar pip
    print_step "Activando entorno virtual..."
    source "$ACTIVATE_SCRIPT"
    
    print_step "Actualizando pip..."
    "$PYTHON_BIN" -m pip install --upgrade pip --quiet
    
    print_success "pip actualizado a la última versión."
    
    # Mostrar información del entorno
    echo ""
    print_info "Información del entorno virtual:"
    echo -e "  ${CYAN}Python:${NC}  $("$PYTHON_BIN" --version)"
    echo -e "  ${CYAN}Pip:${NC}     $("$PIP_BIN" --version | cut -d' ' -f1-2)"
    echo -e "  ${CYAN}Ruta:${NC}    $VENV_DIR"
    echo ""
    
    return 0
}

# Instalar dependencias
install_dependencies() {
    print_step "Instalando dependencias desde requirements.txt..."
    
    if [ ! -f "$REQUIREMENTS_PATH" ]; then
        print_error "No se encontró $REQUIREMENTS_FILE en $PROJECT_DIR"
        return 1
    fi
    
    # Verificar que el venv existe
    if [ ! -f "$PIP_BIN" ]; then
        print_error "El entorno virtual no existe o está corrupto."
        print_info "Créalo primero con la opción de instalación."
        return 1
    fi
    
    # Activar venv
    source "$ACTIVATE_SCRIPT"
    
    # Mostrar dependencias a instalar
    print_info "Dependencias encontradas:"
    grep -v '^\s*#' "$REQUIREMENTS_PATH" | grep -v '^\s*$' | while read line; do
        echo -e "  • $line"
    done
    echo ""
    
    # Instalar
    print_step "Instalando paquetes..."
    "$PIP_BIN" install -r "$REQUIREMENTS_PATH"
    
    if [ $? -eq 0 ]; then
        print_success "Todas las dependencias instaladas correctamente."
        return 0
    else
        print_error "Hubo errores al instalar algunas dependencias."
        print_info "Revisa los mensajes de error anteriores."
        return 1
    fi
}

# Instalación completa desde cero
full_install() {
    print_header "🚀 INSTALACIÓN COMPLETA: $FOLDER_NAME"
    
    echo -e "${YELLOW}Este proceso realizará:${NC}"
    echo "  1. Instalación de paquetes del sistema necesarios"
    echo "  2. Creación del entorno virtual"
    echo "  3. Instalación de dependencias Python"
    echo "  4. Creación del servicio systemd"
    echo "  5. Inicio del bot"
    echo ""
    read -p "¿Continuar? (S/n): " confirm
    
    if [[ "$confirm" =~ ^[nN]$ ]]; then
        print_info "Instalación cancelada."
        return 1
    fi
    
    # Paso 1: Actualizar repositorios e instalar Python
    print_header "📦 PASO 1/5: Instalación de Paquetes del Sistema"
    
    print_step "Actualizando repositorios..."
    $SUDO apt update -qq
    
    print_step "Agregando repositorio deadsnakes (Python)..."
    $SUDO apt install -y software-properties-common -qq
    $SUDO add-apt-repository ppa:deadsnakes/ppa -y > /dev/null 2>&1
    $SUDO apt update -qq
    
    print_step "Instalando Python y herramientas..."
    $SUDO apt install -y python3.13 python3.13-venv python3.13-dev python3-pip -qq
    
    if [ $? -eq 0 ]; then
        print_success "Paquetes del sistema instalados."
    else
        print_warning "Hubo algunos problemas, pero continuando..."
    fi
    
    sleep 1
    
    # Paso 2: Crear entorno virtual
    print_header "🔧 PASO 2/5: Creación del Entorno Virtual"
    
    if ! create_venv; then
        print_error "Falló la creación del entorno virtual."
        read -p "Presiona Enter para volver al menú..."
        return 1
    fi
    
    sleep 1
    
    # Paso 3: Instalar dependencias
    print_header "📚 PASO 3/5: Instalación de Dependencias"
    
    if ! install_dependencies; then
        print_error "Falló la instalación de dependencias."
        print_info "Puedes intentar instalarlas manualmente con:"
        echo "  cd $PROJECT_DIR"
        echo "  source venv/bin/activate"
        echo "  pip install -r requirements.txt"
        read -p "Presiona Enter para volver al menú..."
        return 1
    fi
    
    sleep 1
    
    # Paso 4: Crear servicio
    print_header "⚙️ PASO 4/5: Creación del Servicio Systemd"
    
    if ! create_systemd_service; then
        print_warning "No se pudo crear el servicio automáticamente."
        print_info "Puedes crearlo manualmente desde el menú."
    fi
    
    sleep 1
    
    # Paso 5: Verificar .env
    print_header "🔑 PASO 5/5: Verificación de Configuración"
    
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        print_warning "No se encontró archivo .env"
        print_info "Necesitas configurar las variables de entorno."
        read -p "¿Configurar ahora? (S/n): " config_env
        
        if [[ ! "$config_env" =~ ^[nN]$ ]]; then
            configure_env
        else
            print_warning "Recuerda configurar .env antes de iniciar el bot."
        fi
    else
        print_success "Archivo .env encontrado."
    fi
    
    # Resumen final
    print_header "✅ INSTALACIÓN COMPLETADA"
    
    print_success "Bot instalado correctamente:"
    echo -e "  ${CYAN}Nombre:${NC}     $FOLDER_NAME"
    echo -e "  ${CYAN}Servicio:${NC}   $SERVICE_NAME"
    echo -e "  ${CYAN}Directorio:${NC} $PROJECT_DIR"
    echo ""
    
    read -p "¿Iniciar el bot ahora? (S/n): " start_now
    
    if [[ ! "$start_now" =~ ^[nN]$ ]]; then
        start_bot
    fi
    
    echo ""
    read -p "Presiona Enter para volver al menú..."
}

# Crear servicio systemd
create_systemd_service() {
    print_step "Generando configuración del servicio..."
    
    # Crear archivo de servicio temporal
    SERVICE_CONTENT="[Unit]
Description=Bot Telegram - $FOLDER_NAME
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
Environment=\"PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"
Environment=\"PYTHONUNBUFFERED=1\"
ExecStart=$PYTHON_BIN $BOT_SCRIPT_PATH
Restart=always
RestartSec=10

# Seguridad adicional
NoNewPrivileges=true
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$FOLDER_NAME

[Install]
WantedBy=multi-user.target"

    # Guardar en archivo temporal
    echo "$SERVICE_CONTENT" > "/tmp/$SERVICE_NAME.service"
    
    # Copiar a systemd
    print_step "Instalando servicio (requiere sudo)..."
    $SUDO cp "/tmp/$SERVICE_NAME.service" "$SERVICE_FILE"
    
    if [ $? -ne 0 ]; then
        print_error "Falló la instalación del servicio."
        return 1
    fi
    
    # Recargar y habilitar
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable "$SERVICE_NAME" &>/dev/null
    
    print_success "Servicio $SERVICE_NAME creado y habilitado."
    return 0
}

# Configurar variables de entorno
configure_env() {
    print_header "🔑 CONFIGURACIÓN DE VARIABLES DE ENTORNO"
    
    if [ -f "$PROJECT_DIR/.env" ]; then
        print_warning "Ya existe un archivo .env"
        read -p "¿Deseas reconfigurarlo? (s/N): " recreate
        
        if [[ ! "$recreate" =~ ^[sS]$ ]]; then
            print_info "Conservando configuración existente."
            return 0
        fi
    fi
    
    print_info "Configurando $FOLDER_NAME..."
    echo ""
    
    # Solicitar datos
    read -p "🔑 TOKEN de Telegram Bot: " TELEGRAM_TOKEN
    read -p "👤 ADMIN_CHAT_IDS (separados por coma): " ADMIN_IDS
    read -p "🌦️  OpenWeatherMap API Key (Enter para omitir): " WEATHER_KEY
    
    # Crear archivo .env
    cat > "$PROJECT_DIR/.env" << EOF
# ============================================
# $FOLDER_NAME - Variables de Entorno
# Generado: $(date)
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
    
    chmod 600 "$PROJECT_DIR/.env"
    print_success "Archivo .env creado exitosamente."
    
    return 0
}

# Gestión del servicio
manage_service() {
    ACTION=$1
    
    case $ACTION in
        "start")
            print_step "Iniciando $SERVICE_NAME..."
            $SUDO systemctl start "$SERVICE_NAME"
            sleep 2
            ;;
        "stop")
            print_step "Deteniendo $SERVICE_NAME..."
            $SUDO systemctl stop "$SERVICE_NAME"
            sleep 1
            ;;
        "restart")
            print_step "Reiniciando $SERVICE_NAME..."
            $SUDO systemctl restart "$SERVICE_NAME"
            sleep 2
            ;;
        "status")
            $SUDO systemctl status "$SERVICE_NAME" --no-pager -l
            return 0
            ;;
    esac
    
    # Verificar resultado
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_success "Bot corriendo correctamente."
    else
        print_error "El bot no está corriendo."
        print_info "Revisa los logs con: sudo journalctl -u $SERVICE_NAME -n 50"
    fi
}

start_bot() {
    print_header "▶️ INICIANDO BOT: $FOLDER_NAME"
    
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        print_warning "El servicio ya está corriendo."
        read -p "¿Deseas reiniciarlo? (s/N): " restart_opt
        
        if [[ "$restart_opt" =~ ^[sS]$ ]]; then
            manage_service "restart"
        fi
    else
        manage_service "start"
    fi
    
    echo ""
    read -p "¿Ver logs en tiempo real? (s/N): " view_logs_opt
    
    if [[ "$view_logs_opt" =~ ^[sS]$ ]]; then
        view_logs
    fi
}

stop_bot() {
    print_header "⏹️ DETENIENDO BOT: $FOLDER_NAME"
    manage_service "stop"
    echo ""
    read -p "Presiona Enter para continuar..."
}

restart_bot() {
    print_header "🔄 REINICIANDO BOT: $FOLDER_NAME"
    manage_service "restart"
    echo ""
    read -p "¿Ver logs en tiempo real? (s/N): " view_logs_opt
    
    if [[ "$view_logs_opt" =~ ^[sS]$ ]]; then
        view_logs
    else
        read -p "Presiona Enter para continuar..."
    fi
}

status_bot() {
    print_header "📊 ESTADO DEL BOT: $FOLDER_NAME"
    manage_service "status"
    echo ""
    read -p "Presiona Enter para continuar..."
}

view_logs() {
    print_header "📜 LOGS EN TIEMPO REAL: $FOLDER_NAME"
    print_info "Presiona Ctrl+C para salir"
    echo ""
    sleep 1
    $SUDO journalctl -u "$SERVICE_NAME" -f
}

# Actualizar dependencias
update_dependencies() {
    print_header "📥 ACTUALIZACIÓN DE DEPENDENCIAS"
    
    if [ ! -f "$REQUIREMENTS_PATH" ]; then
        print_error "No se encontró requirements.txt"
        read -p "Presiona Enter para continuar..."
        return 1
    fi
    
    print_info "Instalando/Actualizando dependencias..."
    
    if install_dependencies; then
        print_success "Dependencias actualizadas."
        echo ""
        read -p "¿Reiniciar el bot para aplicar cambios? (S/n): " restart_opt
        
        if [[ ! "$restart_opt" =~ ^[nN]$ ]]; then
            manage_service "restart"
        fi
    fi
    
    echo ""
    read -p "Presiona Enter para continuar..."
}

# Eliminar dependencia
remove_dependency() {
    print_header "🗑️ ELIMINAR DEPENDENCIA"
    
    if [ ! -f "$REQUIREMENTS_PATH" ]; then
        print_error "No se encontró requirements.txt"
        read -p "Presiona Enter para continuar..."
        return 1
    fi
    
    # Leer dependencias
    mapfile -t lines < <(grep -v '^\s*$' "$REQUIREMENTS_PATH" | grep -v '^\s*#')
    
    if [ ${#lines[@]} -eq 0 ]; then
        print_warning "No hay dependencias instaladas."
        read -p "Presiona Enter para continuar..."
        return 0
    fi
    
    print_info "Dependencias actuales:"
    echo ""
    i=1
    for line in "${lines[@]}"; do
        echo -e "  ${GREEN}$i)${NC} ${YELLOW}$line${NC}"
        ((i++))
    done
    echo -e "  ${RED}0)${NC} Cancelar"
    echo ""
    
    read -p "Número de dependencia a eliminar: " selection
    
    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -gt 0 ] && [ "$selection" -le "${#lines[@]}" ]; then
        SELECTED_LINE="${lines[$((selection-1))]}"
        PACKAGE_NAME=$(echo "$SELECTED_LINE" | sed -E 's/([a-zA-Z0-9_\-]+).*/\1/')
        
        print_step "Eliminando $PACKAGE_NAME del venv..."
        "$PIP_BIN" uninstall -y "$PACKAGE_NAME"
        
        print_step "Eliminando de requirements.txt..."
        grep -vF "$SELECTED_LINE" "$REQUIREMENTS_PATH" > "${REQUIREMENTS_PATH}.tmp"
        mv "${REQUIREMENTS_PATH}.tmp" "$REQUIREMENTS_PATH"
        
        print_success "Dependencia eliminada."
        
        read -p "¿Reiniciar bot? (s/N): " restart_opt
        if [[ "$restart_opt" =~ ^[sS]$ ]]; then
            manage_service "restart"
        fi
    elif [ "$selection" -eq 0 ]; then
        print_info "Operación cancelada."
    else
        print_error "Selección inválida."
    fi
    
    echo ""
    read -p "Presiona Enter para continuar..."
}

# Desinstalar servicio
uninstall_service() {
    print_header "🗑️ DESINSTALAR SERVICIO"
    
    print_warning "Esto eliminará el servicio systemd de $FOLDER_NAME"
    print_info "El directorio y archivos del bot NO serán eliminados."
    echo ""
    read -p "¿Estás seguro? (s/N): " confirm
    
    if [[ ! "$confirm" =~ ^[sS]$ ]]; then
        print_info "Operación cancelada."
        read -p "Presiona Enter para continuar..."
        return 0
    fi
    
    # Detener servicio
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        print_step "Deteniendo servicio..."
        $SUDO systemctl stop "$SERVICE_NAME"
    fi
    
    # Deshabilitar
    $SUDO systemctl disable "$SERVICE_NAME" 2>/dev/null
    
    # Eliminar archivo
    if [ -f "$SERVICE_FILE" ]; then
        $SUDO rm "$SERVICE_FILE"
        print_success "Archivo de servicio eliminado."
    fi
    
    # Recargar systemd
    $SUDO systemctl daemon-reload
    $SUDO systemctl reset-failed 2>/dev/null
    
    print_success "Servicio $SERVICE_NAME desinstalado completamente."
    echo ""
    read -p "Presiona Enter para continuar..."
}

# Cambiar directorio objetivo
change_directory() {
    PROJECT_DIR=""
    FOLDER_NAME=""
    SERVICE_NAME=""
    select_target_directory
}

# --- FUNCIONES DE GIT ---

# Obtener rama actual de Git
get_git_branch() {
    if [ -d "$PROJECT_DIR/.git" ]; then
        cd "$PROJECT_DIR"
        git branch --show-current 2>/dev/null || echo "N/A"
    else
        echo "N/A"
    fi
}

# Clonar repositorio
git_clone_repository() {
    print_header "📥 CLONAR REPOSITORIO"
    
    # URL por defecto
    DEFAULT_REPO="https://github.com/ersus93/bbalert.git"
    read -p "URL del repositorio [$DEFAULT_REPO]: " REPO_URL
    REPO_URL=${REPO_URL:-$DEFAULT_REPO}
    
    # Directorio destino
    read -p "Directorio destino [~/bbalert]: " DEST_DIR
    DEST_DIR=${DEST_DIR:-"$HOME/bbalert"}
    DEST_DIR="${DEST_DIR/#\~/$HOME}"
    
    # Verificar si ya existe
    if [ -d "$DEST_DIR" ]; then
        print_warning "El directorio $DEST_DIR ya existe."
        read -p "¿Eliminar y continuar? (s/N): " overwrite
        if [[ "$overwrite" =~ ^[sS]$ ]]; then
            rm -rf "$DEST_DIR"
        else
            print_info "Operación cancelada."
            return 1
        fi
    fi
    
    # Clonar
    print_step "Clonando $REPO_URL..."
    git clone "$REPO_URL" "$DEST_DIR"
    
    if [ $? -eq 0 ]; then
        print_success "Repositorio clonado en $DEST_DIR"
        
        # Ofrecer configurar
        read -p "¿Configurar este bot ahora? (S/n): " setup_now
        if [[ ! "$setup_now" =~ ^[nN]$ ]]; then
            PROJECT_DIR="$DEST_DIR"
            FOLDER_NAME=$(basename "$PROJECT_DIR")
            SERVICE_NAME="${FOLDER_NAME}"
            SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
            VENV_DIR="$PROJECT_DIR/venv"
            PYTHON_BIN="$VENV_DIR/bin/python"
            PIP_BIN="$VENV_DIR/bin/pip"
            ACTIVATE_SCRIPT="$VENV_DIR/bin/activate"
            REQUIREMENTS_PATH="$PROJECT_DIR/$REQUIREMENTS_FILE"
            BOT_SCRIPT_PATH="$PROJECT_DIR/$BOT_MAIN_FILE"
        fi
    else
        print_error "Error al clonar el repositorio."
        return 1
    fi
}

# Actualizar código del repositorio
git_pull_repository() {
    print_header "📥 ACTUALIZAR CÓDIGO DEL REPOSITORIO"
    
    cd "$PROJECT_DIR" || return 1
    
    # Verificar que es un repo git
    if [ ! -d ".git" ]; then
        print_error "Este directorio no es un repositorio Git."
        return 1
    fi
    
    # Mostrar rama actual
    CURRENT_BRANCH=$(git branch --show-current)
    print_info "Rama actual: $CURRENT_BRANCH"
    
    # Fetch
    print_step "Buscando actualizaciones..."
    git fetch origin
    
    # Verificar si hay cambios
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse @{u} 2>/dev/null)
    
    if [ "$LOCAL" = "$REMOTE" ]; then
        print_success "El código está actualizado."
        return 0
    fi
    
    # Mostrar cambios disponibles
    print_info "Nuevos commits disponibles:"
    git log HEAD..@{u} --oneline
    
    echo ""
    read -p "¿Actualizar ahora? (S/n): " confirm
    if [[ "$confirm" =~ ^[nN]$ ]]; then
        return 0
    fi
    
    # Pull
    print_step "Actualizando código..."
    git pull origin "$CURRENT_BRANCH"
    
    if [ $? -eq 0 ]; then
        print_success "Código actualizado correctamente."
        
        # Preguntar sobre dependencias
        read -p "¿Actualizar dependencias? (S/n): " update_deps
        if [[ ! "$update_deps" =~ ^[nN]$ ]]; then
            install_dependencies
        fi
        
        # Preguntar sobre reinicio
        if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
            read -p "¿Reiniciar el bot? (S/n): " restart_bot
            if [[ ! "$restart_bot" =~ ^[nN]$ ]]; then
                manage_service "restart"
            fi
        fi
    fi
}

# Cambiar de rama
git_switch_branch() {
    print_header "🔄 CAMBIAR DE RAMA"
    
    cd "$PROJECT_DIR" || return 1
    
    # Verificar que es un repo git
    if [ ! -d ".git" ]; then
        print_error "Este directorio no es un repositorio Git."
        return 1
    fi
    
    # Mostrar rama actual
    CURRENT_BRANCH=$(git branch --show-current)
    print_info "Rama actual: ${CYAN}$CURRENT_BRANCH${NC}"
    
    # Verificar cambios pendientes
    if ! git diff-index --quiet HEAD --; then
        print_warning "Tienes cambios sin committear:"
        git status --short
        echo ""
        read -p "¿Descartar cambios y continuar? (s/N): " discard
        if [[ ! "$discard" =~ ^[sS]$ ]]; then
            print_info "Operación cancelada."
            return 0
        fi
        git checkout -- .
    fi
    
    # Listar ramas
    echo ""
    print_info "Ramas disponibles:"
    echo ""
    
    BRANCHES=("main" "testing" "dev")
    local i=1
    for branch in "${BRANCHES[@]}"; do
        if [ "$branch" = "$CURRENT_BRANCH" ]; then
            echo -e "  ${GREEN}*) $branch ${YELLOW}(actual)${NC}"
        else
            echo -e "  ${GREEN}$i)${NC} $branch"
        fi
        ((i++))
    done
    echo -e "  ${YELLOW}0)${NC} Cancelar"
    echo ""
    
    read -p "Selecciona rama: " selection
    
    if [ "$selection" = "0" ]; then
        return 0
    fi
    
    # Determinar rama destino
    if [[ "$selection" =~ ^[0-9]+$ ]]; then
        TARGET_BRANCH="${BRANCHES[$((selection-1))]}"
    else
        TARGET_BRANCH="$selection"
    fi
    
    if [ -z "$TARGET_BRANCH" ]; then
        print_error "Selección inválida."
        return 1
    fi
    
    # Cambiar de rama
    print_step "Cambiando a rama $TARGET_BRANCH..."
    git checkout "$TARGET_BRANCH"
    git pull origin "$TARGET_BRANCH"
    
    if [ $? -eq 0 ]; then
        print_success "Ahora en rama: $TARGET_BRANCH"
        
        # Actualizar dependencias
        read -p "¿Actualizar dependencias? (S/n): " update_deps
        if [[ ! "$update_deps" =~ ^[nN]$ ]]; then
            install_dependencies
        fi
    fi
}

# Ver estado del repositorio
git_show_status() {
    print_header "📊 ESTADO DEL REPOSITORIO"
    
    cd "$PROJECT_DIR" || return 1
    
    if [ ! -d ".git" ]; then
        print_error "No es un repositorio Git."
        return 1
    fi
    
    echo ""
    # Rama actual
    CURRENT_BRANCH=$(git branch --show-current)
    echo -e "${CYAN}Rama actual:${NC}     $CURRENT_BRANCH"
    
    # Remote
    REMOTE_URL=$(git remote get-url origin 2>/dev/null)
    echo -e "${CYAN}Remote:${NC}          $REMOTE_URL"
    
    # Último commit
    LAST_COMMIT=$(git log -1 --format="%h - %s (%cr)")
    echo -e "${CYAN}Último commit:${NC}   $LAST_COMMIT"
    
    echo ""
    echo -e "${YELLOW}Estado de archivos:${NC}"
    git status --short
    
    echo ""
    echo -e "${YELLOW}Commits locales no enviados:${NC}"
    git log @{u}..HEAD --oneline 2>/dev/null || echo "  (ninguno)"
    
    echo ""
    echo -e "${YELLOW}Commits remotos no descargados:${NC}"
    git log HEAD..@{u} --oneline 2>/dev/null || echo "  (ninguno)"
    
    echo ""
    read -p "Presiona Enter para continuar..."
}

# Ver historial de commits
git_show_history() {
    print_header "📜 HISTORIAL DE COMMITS"
    
    cd "$PROJECT_DIR" || return 1
    
    if [ ! -d ".git" ]; then
        print_error "No es un repositorio Git."
        return 1
    fi
    
    echo ""
    print_info "Últimos 15 commits:"
    echo ""
    git log --oneline -15 --decorate --graph
    
    echo ""
    read -p "¿Ver detalles de un commit? (ingresa hash o Enter para continuar): " commit_hash
    
    if [ -n "$commit_hash" ]; then
        echo ""
        git show "$commit_hash"
        read -p "Presiona Enter para continuar..."
    fi
}

# Gestión de entornos staging/producción
manage_environments() {
    print_header "🌐 GESTIÓN DE ENTORNOS"
    
    echo ""
    print_info "Entornos disponibles:"
    echo ""
    echo -e "  ${GREEN}1)${NC} Staging    ${YELLOW}(rama: testing)${NC}"
    echo -e "  ${GREEN}2)${NC} Producción ${YELLOW}(rama: main)${NC}"
    echo -e "  ${YELLOW}0)${NC} Volver"
    echo ""
    
    read -p "Selecciona entorno: " env_choice
    
    case $env_choice in
        1)
            ENV_NAME="staging"
            ENV_DIR="$HOME/bbalert-staging"
            ENV_BRANCH="testing"
            ;;
        2)
            ENV_NAME="producción"
            ENV_DIR="$HOME/bbalert-prod"
            ENV_BRANCH="main"
            ;;
        *)
            return 0
            ;;
    esac
    
    print_header "🔧 ENTORNO: $ENV_NAME"
    
    # Verificar si existe
    if [ ! -d "$ENV_DIR" ]; then
        print_warning "El entorno no existe."
        read -p "¿Crear entorno $ENV_NAME? (S/n): " create_env
        
        if [[ ! "$create_env" =~ ^[nN]$ ]]; then
            create_environment "$ENV_DIR" "$ENV_BRANCH"
        fi
        return 0
    fi
    
    # Mostrar estado
    ENV_SERVICE=$(basename "$ENV_DIR")
    echo ""
    print_info "Directorio: $ENV_DIR"
    print_info "Rama: $ENV_BRANCH"
    
    if systemctl is-active --quiet "$ENV_SERVICE" 2>/dev/null; then
        echo -e "${GREEN}Estado: En ejecución${NC}"
    else
        echo -e "${RED}Estado: Detenido${NC}"
    fi
    
    echo ""
    echo -e "${YELLOW}Acciones:${NC}"
    echo "  1) Actualizar código (git pull)"
    echo "  2) Iniciar servicio"
    echo "  3) Detener servicio"
    echo "  4) Reiniciar servicio"
    echo "  5) Ver logs"
    echo "  0) Volver"
    echo ""
    
    read -p "Acción: " action
    
    case $action in
        1) 
            cd "$ENV_DIR"
            git checkout "$ENV_BRANCH"
            git pull origin "$ENV_BRANCH"
            print_success "Código actualizado."
            ;;
        2) sudo systemctl start "$ENV_SERVICE" ;;
        3) sudo systemctl stop "$ENV_SERVICE" ;;
        4) sudo systemctl restart "$ENV_SERVICE" ;;
        5) sudo journalctl -u "$ENV_SERVICE" -f ;;
    esac
}

# Crear entorno
create_environment() {
    local ENV_DIR=$1
    local ENV_BRANCH=$2
    
    print_step "Creando entorno en $ENV_DIR..."
    
    # Clonar
    git clone https://github.com/ersus93/bbalert.git "$ENV_DIR"
    cd "$ENV_DIR"
    git checkout "$ENV_BRANCH"
    
    # Crear venv
    detect_python
    $TARGET_PYTHON -m venv venv
    
    # Instalar dependencias
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    
    print_success "Entorno creado exitosamente."
    print_info "Recuerda configurar el archivo .env en $ENV_DIR"
}

# Menú principal
show_menu() {
    clear
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}   🤖 GESTOR MULTI-BOT TELEGRAM (v3)        ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Bot Actual:${NC}    $FOLDER_NAME"
    echo -e "${CYAN}Servicio:${NC}     $SERVICE_NAME"
    echo -e "${CYAN}Directorio:${NC}   $PROJECT_DIR"
    echo -e "${CYAN}Rama Git:${NC}     $(get_git_branch)"
    echo ""
    
    # Mostrar estado
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo -e "${GREEN}● Estado: Bot en ejecución${NC}"
    else
        echo -e "${RED}○ Estado: Bot detenido${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📦 INSTALACIÓN Y CONFIGURACIÓN${NC}"
    echo "  1)  🚀 Instalación Completa (desde cero)"
    echo "  2)  🔧 Crear/Recrear Entorno Virtual (venv)"
    echo "  3)  📥 Instalar/Actualizar Dependencias"
    echo "  4)  🔑 Configurar Variables de Entorno (.env)"
    echo "  5)  ⚙️  Crear/Actualizar Servicio Systemd"
    echo ""
    echo -e "${YELLOW}🎮 CONTROL DEL BOT${NC}"
    echo "  6)  ▶️  Iniciar Bot"
    echo "  7)  ⏹️  Detener Bot"
    echo "  8)  🔄 Reiniciar Bot"
    echo "  9)  📊 Ver Estado del Servicio"
    echo "  10) 📜 Ver Logs en Tiempo Real"
    echo ""
    echo -e "${YELLOW}🔀 CONTROL DE GIT${NC}"
    echo "  11) 📥 Clonar Repositorio"
    echo "  12) 🔄 Actualizar Código (git pull)"
    echo "  13) 🌿 Cambiar de Rama"
    echo "  14) 📊 Ver Estado del Repositorio"
    echo "  15) 📜 Ver Historial de Commits"
    echo ""
    echo -e "${YELLOW}🌐 ENTORNOS${NC}"
    echo "  16) 🗺️  Gestión de Entornos (Staging/Producción)"
    echo ""
    echo -e "${YELLOW}� MANTENIMIENTO${NC}"
    echo "  17) 🗑️  Eliminar Dependencia"
    echo "  18) 🗑️  Desinstalar Servicio"
    echo ""
    echo -e "${YELLOW}📂 OTROS${NC}"
    echo "  19) 📂 Cambiar Bot/Directorio Objetivo"
    echo "  0)  ❌ Salir"
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# === PROGRAMA PRINCIPAL ===

check_root

# Si se pasa --install, hacer instalación completa automática
if [ "$1" == "--install" ]; then
    select_target_directory
    full_install
    exit 0
fi

# Seleccionar directorio al inicio
select_target_directory

# Menú interactivo
while true; do
    show_menu
    read -p "Selecciona una opción: " choice
    
    case $choice in
        1)  full_install ;;
        2)  create_venv; read -p "Presiona Enter para continuar..." ;;
        3)  update_dependencies ;;
        4)  configure_env; read -p "Presiona Enter para continuar..." ;;
        5)  create_systemd_service; read -p "Presiona Enter para continuar..." ;;
        6)  start_bot ;;
        7)  stop_bot ;;
        8)  restart_bot ;;
        9)  status_bot ;;
        10) view_logs;;
        11) git_clone_repository; read -p "Presiona Enter para continuar..." ;;
        12) git_pull_repository ;;
        13) git_switch_branch ;;
        14) git_show_status ;;
        15) git_show_history ;;
        16) manage_environments ;;
        17) remove_dependency ;;
        18) uninstall_service ;;
        19) change_directory ;;
        0)  
            print_info "¡Hasta luego!"
            exit 0
            ;;
        *)  
            print_error "Opción inválida."
            sleep 1
            ;;
    esac
done

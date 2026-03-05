#!/bin/bash

# ============================================

# GESTOR MULTI-BOT DE TELEGRAM (BBAlert v4)

# Version Mejorada con Deteccion Automatica

# ============================================

# Mejoras v4:

# - Seguridad: tokens con read -s, validacion

# - Sistema de backup con rotacion automatica

# - Monitoreo: CPU, RAM, uptime, reinicios

# - Gestion avanzada de logs (filtrar, exportar)

# - Notificaciones por Telegram al admin

# - Dashboard multi-bot

# - Verificacion de dependencias del sistema

# - Manejo de errores mejorado (trap)

# ============================================

# — MANEJO GLOBAL DE ERRORES —

# Nota: set -e no se usa para no interrumpir flujos con || o 2>/dev/null

handle_error() {
local line=${1:-"?"}
echo -e "\033[0;31m[ERR] Error inesperado en linea $line. Volviendo al menu principal.\033[0m"
sleep 2
}

trap 'handle_error $LINENO' ERR

# — CONFIGURACION GLOBAL —

DEFAULT_PYTHON="python3.13"
FALLBACK_PYTHON="python3.12"
CURRENT_USER=$(whoami)
BOT_MAIN_FILE="bbalert.py"
REQUIREMENTS_FILE="requirements.txt"
BACKUP_DIR="$HOME/backups"
MAX_BACKUPS=5

# Colores

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
NC='\033[0m'

# — FUNCIONES DE UTILIDAD —

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

# ============================================

# NUEVO: Verificar dependencias del sistema

# ============================================

check_system_dependencies() {
print_step "Verificando dependencias del sistema…"
local missing=()

for cmd in curl git systemctl tar; do
    if ! command -v "$cmd" &>/dev/null; then
        missing+=("$cmd")
    fi
done

if [ ${#missing[@]} -gt 0 ]; then
    print_error "Faltan herramientas requeridas: ${missing[*]}"
    print_info "Instalalas con: sudo apt install ${missing[*]} -y"
    echo ""
    read -p "Intentar instalarlas ahora? (S/n): " install_now
    if [[ ! "$install_now" =~ ^[nN]$ ]]; then
        $SUDO apt update -qq && $SUDO apt install -y "${missing[@]}" -qq
        print_success "Dependencias instaladas."
    else
        print_error "No se puede continuar sin las dependencias."
        exit 1
    fi
else
    print_success "Todas las dependencias del sistema estan disponibles."
fi

}

detect_python() {
print_step "Detectando version de Python disponible…"
if command -v $DEFAULT_PYTHON &>/dev/null; then
TARGET_PYTHON=$DEFAULT_PYTHON
print_success "Usando $DEFAULT_PYTHON"
return 0
elif command -v $FALLBACK_PYTHON &>/dev/null; then
TARGET_PYTHON=$FALLBACK_PYTHON
print_warning "Python 3.13 no disponible, usando $FALLBACK_PYTHON"
return 0
else
print_error "No se encontro Python 3.12 ni 3.13"
print_info "Instala Python con: sudo apt install python3.13 python3.13-venv python3.13-dev -y"
return 1
fi
}

validate_bot_directory() {
local dir=$1
[ -d "$dir" ] || return 1
[ -f "$dir/$BOT_MAIN_FILE" ] || return 1
[ -f "$dir/$REQUIREMENTS_FILE" ] || return 1
return 0
}

select_target_directory() {
print_header "🔍 SELECCION DE DIRECTORIO DEL BOT"

if validate_bot_directory "$(pwd)"; then
    DETECTED_DIR=$(pwd)
    print_success "Detectado bot en directorio actual:"
    echo -e "   ${CYAN}$DETECTED_DIR${NC}"
    echo ""
    read -p "Usar este directorio? (S/n): " confirm
    if [[ ! "$confirm" =~ ^[nN]$ ]]; then
        PROJECT_DIR="$DETECTED_DIR"
    else
        PROJECT_DIR=""
    fi
fi

if [ -z "${PROJECT_DIR:-}" ]; then
    print_info "Buscando bots en subdirectorios..."
    local found_bots=()
    local search_paths=("$HOME" "$HOME/bots" "$HOME/telegram" "/opt" "$(pwd)")

    for base_path in "${search_paths[@]}"; do
        if [ -d "$base_path" ]; then
            while IFS= read -r -d '' bot_dir; do
                if validate_bot_directory "$bot_dir"; then
                    found_bots+=("$bot_dir")
                fi
            done < <(find "$base_path" -maxdepth 2 -name "$BOT_MAIN_FILE" -type f -print0 2>/dev/null | xargs -0 dirname -z 2>/dev/null)
        fi
    done

    found_bots=($(printf '%s\n' "${found_bots[@]}" | sort -u 2>/dev/null || true))

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

while [ -z "${PROJECT_DIR:-}" ]; do
    echo ""
    print_info "Ingresa la ruta completa del bot:"
    echo -e "${YELLOW}Ejemplos:${NC}"
    echo "  ? /home/$CURRENT_USER/bbalert_v2"
    echo "  ? ~/bots/mi_bot"
    read -e -p "Ruta: " INPUT_DIR
    INPUT_DIR="${INPUT_DIR/#\~/$HOME}"
    INPUT_DIR=$(realpath "$INPUT_DIR" 2>/dev/null || echo "$INPUT_DIR")

    if validate_bot_directory "$INPUT_DIR"; then
        PROJECT_DIR="$INPUT_DIR"
        print_success "Directorio valido confirmado."
    else
        print_error "No se encontro un bot valido en ese directorio."
        print_info "Asegurate que contenga: $BOT_MAIN_FILE y $REQUIREMENTS_FILE"
        read -p "Intentar con otro directorio? (S/n): " retry
        if [[ "$retry" =~ ^[nN]$ ]]; then
            print_error "Operacion cancelada."
            exit 1
        fi
    fi
done

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
print_success "Configuracion cargada:"
echo -e "  ${CYAN}Nombre:${NC}     $FOLDER_NAME"
echo -e "  ${CYAN}Ruta:${NC}       $PROJECT_DIR"
echo -e "  ${CYAN}Servicio:${NC}   $SERVICE_NAME"
echo ""
sleep 1

}

create_venv() {
print_header "🔧 CONFIGURACION DEL ENTORNO VIRTUAL"

cd "$PROJECT_DIR" || { print_error "No se pudo acceder al directorio del bot."; return 1; }
print_info "Directorio de trabajo: $(pwd)"

if [ -d "$VENV_DIR" ]; then
    print_warning "Ya existe un entorno virtual en: $VENV_DIR"
    if [ ! -f "$ACTIVATE_SCRIPT" ] || [ ! -f "$PYTHON_BIN" ]; then
        print_warning "El entorno virtual esta corrupto."
        read -p "Eliminar y recrear? (S/n): " recreate
        if [[ ! "$recreate" =~ ^[nN]$ ]]; then
            rm -rf "$VENV_DIR"
        else
            print_error "No se puede continuar con un venv corrupto."
            return 1
        fi
    else
        print_success "El entorno virtual existente parece estar bien."
        read -p "Recrearlo de todos modos? (s/N): " force_recreate
        if [[ "$force_recreate" =~ ^[sS]$ ]]; then
            rm -rf "$VENV_DIR"
        else
            print_info "Usando entorno virtual existente."
            return 0
        fi
    fi
fi

if ! detect_python; then return 1; fi

print_step "Verificando modulo venv..."
if ! $TARGET_PYTHON -m venv --help &>/dev/null; then
    print_error "El modulo venv no esta disponible para $TARGET_PYTHON"
    print_info "Instalalo con: sudo apt install ${TARGET_PYTHON}-venv ${TARGET_PYTHON}-dev -y"
    return 1
fi

print_step "Creando entorno virtual con $TARGET_PYTHON..."
$TARGET_PYTHON -m venv "$VENV_DIR"

if [ ! -f "$ACTIVATE_SCRIPT" ] || [ ! -f "$PYTHON_BIN" ]; then
    print_error "El entorno virtual no se creo correctamente."
    return 1
fi

print_success "Entorno virtual creado exitosamente."
source "$ACTIVATE_SCRIPT"
print_step "Actualizando pip..."
"$PYTHON_BIN" -m pip install --upgrade pip --quiet
print_success "pip actualizado."

echo ""
print_info "Informacion del entorno virtual:"
echo -e "  ${CYAN}Python:${NC}  $("$PYTHON_BIN" --version)"
echo -e "  ${CYAN}Pip:${NC}     $("$PIP_BIN" --version | cut -d' ' -f1-2)"
echo -e "  ${CYAN}Ruta:${NC}    $VENV_DIR"
echo ""
return 0

}

install_dependencies() {
print_step "Instalando dependencias desde requirements.txt…"

if [ ! -f "$REQUIREMENTS_PATH" ]; then
    print_error "No se encontro $REQUIREMENTS_FILE en $PROJECT_DIR"
    return 1
fi
if [ ! -f "$PIP_BIN" ]; then
    print_error "El entorno virtual no existe o esta corrupto."
    return 1
fi

source "$ACTIVATE_SCRIPT"
print_info "Dependencias encontradas:"
grep -v '^\s*#' "$REQUIREMENTS_PATH" | grep -v '^\s*$' | while read -r line; do
    echo -e "  ? $line"
done
echo ""

"$PIP_BIN" install -r "$REQUIREMENTS_PATH"

if [ $? -eq 0 ]; then
    print_success "Todas las dependencias instaladas correctamente."
    return 0
else
    print_error "Hubo errores al instalar algunas dependencias."
    return 1
fi

}

# ============================================

# NUEVO: Validar token de Telegram

# ============================================

validate_telegram_token() {
local token="$1"

# Validar formato: 8-10 digitos, ":", 35 caracteres alfanumericos
if [[ ! "$token" =~ ^[0-9]{8,10}:[A-Za-z0-9_-]{35}$ ]]; then
    print_error "Formato de token invalido."
    print_info "Formato esperado: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ12345678"
    return 1
fi

print_step "Verificando token con la API de Telegram..."
local response
response=$(curl -s --max-time 10 "https://api.telegram.org/bot${token}/getMe" 2>/dev/null || echo "")

if echo "$response" | grep -q '"ok":true'; then
    local bot_username
    bot_username=$(echo "$response" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
    local bot_name
    bot_name=$(echo "$response" | grep -o '"first_name":"[^"]*"' | cut -d'"' -f4)
    print_success "Token valido. Bot: $bot_name (@$bot_username)"
    return 0
else
    local desc
    desc=$(echo "$response" | grep -o '"description":"[^"]*"' | cut -d'"' -f4)
    print_error "Token rechazado por Telegram: ${desc:-Sin respuesta de la API}"
    return 1
fi

}

# ============================================

# NUEVO: Notificaciones por Telegram

# ============================================

notify_telegram() {
local message="$1"

if [ ! -f "$PROJECT_DIR/.env" ]; then return 0; fi

# Cargar variables sin hacer set -a global
local token="" admins=""
token=$(grep '^TOKEN_TELEGRAM=' "$PROJECT_DIR/.env" | cut -d'=' -f2- | tr -d '"')
admins=$(grep '^ADMIN_CHAT_IDS=' "$PROJECT_DIR/.env" | cut -d'=' -f2- | tr -d '"')

if [ -z "$token" ] || [ -z "$admins" ]; then return 0; fi

IFS=',' read -ra admin_list <<< "$admins"
for admin_id in "${admin_list[@]}"; do
    admin_id=$(echo "$admin_id" | tr -d ' ')
    curl -s --max-time 5 -X POST \
        "https://api.telegram.org/bot${token}/sendMessage" \
        -d "chat_id=${admin_id}&text=${message}&parse_mode=HTML" \
        > /dev/null 2>&1 || true
done

}

# ============================================

# NUEVO: Sistema de Backup

# ============================================

backup_bot() {
print_header "💾 BACKUP DEL BOT: $FOLDER_NAME"

local bot_backup_dir="$BACKUP_DIR/$FOLDER_NAME"
local timestamp
timestamp=$(date '+%Y%m%d_%H%M%S')
local backup_file="${bot_backup_dir}/${FOLDER_NAME}_${timestamp}.tar.gz"

mkdir -p "$bot_backup_dir"

print_step "Creando backup (excluyendo venv y cache)..."
tar -czf "$backup_file" \
    --exclude="$PROJECT_DIR/venv" \
    --exclude="$PROJECT_DIR/__pycache__" \
    --exclude="$PROJECT_DIR/*.pyc" \
    --exclude="$PROJECT_DIR/.git" \
    -C "$(dirname "$PROJECT_DIR")" "$(basename "$PROJECT_DIR")" 2>/dev/null

if [ $? -eq 0 ]; then
    local size
    size=$(du -sh "$backup_file" | cut -f1)
    print_success "Backup creado: $(basename "$backup_file") (${size})"

    # Rotar: conservar solo los ultimos MAX_BACKUPS
    local count
    count=$(ls "$bot_backup_dir"/*.tar.gz 2>/dev/null | wc -l)
    if [ "$count" -gt "$MAX_BACKUPS" ]; then
        local to_delete=$(( count - MAX_BACKUPS ))
        ls -t "$bot_backup_dir"/*.tar.gz | tail -n "$to_delete" | xargs rm -f
        print_info "Rotacion: eliminados $to_delete backup(s) antiguos (maximo $MAX_BACKUPS)."
    fi

    echo ""
    print_info "Backups disponibles:"
    ls -lh "$bot_backup_dir"/*.tar.gz 2>/dev/null | awk '{print "  ?", $NF, "("$5")"}'
else
    print_error "Fallo la creacion del backup."
    return 1
fi

echo ""
read -p "Presiona Enter para continuar..."

}

restore_backup() {
print_header "🔄 RESTAURAR BACKUP: $FOLDER_NAME"

local bot_backup_dir="$BACKUP_DIR/$FOLDER_NAME"

if [ ! -d "$bot_backup_dir" ] || [ -z "$(ls "$bot_backup_dir"/*.tar.gz 2>/dev/null)" ]; then
    print_error "No hay backups disponibles para $FOLDER_NAME"
    read -p "Presiona Enter para continuar..."
    return 1
fi

print_info "Backups disponibles:"
echo ""
mapfile -t backups < <(ls -t "$bot_backup_dir"/*.tar.gz 2>/dev/null)

for i in "${!backups[@]}"; do
    local fname
    fname=$(basename "${backups[$i]}")
    local fsize
    fsize=$(du -sh "${backups[$i]}" | cut -f1)
    echo -e "  ${GREEN}$((i+1)))${NC} $fname ${CYAN}($fsize)${NC}"
done
echo -e "  ${YELLOW}0)${NC} Cancelar"
echo ""

read -p "Selecciona backup a restaurar: " selection

if [[ ! "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -eq 0 ]; then
    print_info "Operacion cancelada."
    read -p "Presiona Enter para continuar..."
    return 0
fi

if [ "$selection" -gt "${#backups[@]}" ]; then
    print_error "Seleccion invalida."
    read -p "Presiona Enter para continuar..."
    return 1
fi

local selected_backup="${backups[$((selection-1))]}"

print_warning "Esto SOBREESCRIBIRA el directorio actual del bot."
read -p "Estas seguro? (s/N): " confirm
if [[ ! "$confirm" =~ ^[sS]$ ]]; then
    print_info "Restauracion cancelada."
    read -p "Presiona Enter para continuar..."
    return 0
fi

# Detener bot si esta corriendo
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    print_step "Deteniendo bot para restaurar..."
    $SUDO systemctl stop "$SERVICE_NAME"
fi

print_step "Restaurando desde $(basename "$selected_backup")..."
tar -xzf "$selected_backup" -C "$(dirname "$PROJECT_DIR")" 2>/dev/null

if [ $? -eq 0 ]; then
    print_success "Backup restaurado correctamente."
    read -p "Reiniciar el bot ahora? (S/n): " restart_opt
    if [[ ! "$restart_opt" =~ ^[nN]$ ]]; then
        manage_service "start"
    fi
else
    print_error "Fallo la restauracion."
fi

echo ""
read -p "Presiona Enter para continuar..."

}

# ============================================

# NUEVO: Monitoreo de recursos

# ============================================

show_bot_stats() {
print_header "📊 ESTADISTICAS DEL BOT: $FOLDER_NAME"

local pid
pid=$(systemctl show "$SERVICE_NAME" --property=MainPID --value 2>/dev/null || echo "0")

echo -e "${YELLOW}== Servicio ==================================${NC}"

if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo -e "  ${GREEN}* Estado:${NC}       En ejecucion"
else
    echo -e "  ${RED}o Estado:${NC}       Detenido"
fi

local since
since=$(systemctl show "$SERVICE_NAME" --property=ActiveEnterTimestamp --value 2>/dev/null || echo "N/A")
echo -e "  ${CYAN}Activo desde:${NC}  $since"

local restarts
restarts=$(systemctl show "$SERVICE_NAME" --property=NRestarts --value 2>/dev/null || echo "0")
if [ "$restarts" -gt 5 ] 2>/dev/null; then
    echo -e "  ${RED}Reinicios:${NC}     $restarts [WARN]  (muchos reinicios, revisa los logs)"
else
    echo -e "  ${CYAN}Reinicios:${NC}     $restarts"
fi

echo ""
echo -e "${YELLOW}== Proceso ===================================${NC}"

if [ -n "$pid" ] && [ "$pid" != "0" ] && kill -0 "$pid" 2>/dev/null; then
    local cpu ram mem_percent threads
    cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ' || echo "N/A")
    ram=$(ps -p "$pid" -o rss= 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo "N/A")
    mem_percent=$(ps -p "$pid" -o %mem= 2>/dev/null | tr -d ' ' || echo "N/A")
    threads=$(ps -p "$pid" -o nlwp= 2>/dev/null | tr -d ' ' || echo "N/A")

    echo -e "  ${CYAN}PID:${NC}           $pid"
    echo -e "  ${CYAN}CPU:${NC}           ${cpu}%"
    echo -e "  ${CYAN}RAM:${NC}           $ram (${mem_percent}%)"
    echo -e "  ${CYAN}Hilos:${NC}         $threads"
else
    echo -e "  ${RED}El proceso no esta corriendo.${NC}"
fi

echo ""
echo -e "${YELLOW}== Disco =====================================${NC}"
local project_size venv_size
project_size=$(du -sh "$PROJECT_DIR" --exclude="$VENV_DIR" 2>/dev/null | cut -f1 || echo "N/A")
venv_size=$(du -sh "$VENV_DIR" 2>/dev/null | cut -f1 || echo "N/A")
echo -e "  ${CYAN}Bot (sin venv):${NC} $project_size"
echo -e "  ${CYAN}Venv:${NC}          $venv_size"

# Backups
local backup_count backup_size
backup_count=$(ls "$BACKUP_DIR/$FOLDER_NAME/"*.tar.gz 2>/dev/null | wc -l || echo "0")
backup_size=$(du -sh "$BACKUP_DIR/$FOLDER_NAME" 2>/dev/null | cut -f1 || echo "0")
echo -e "  ${CYAN}Backups:${NC}       $backup_count archivo(s) ($backup_size)"

echo ""
echo -e "${YELLOW}== Errores recientes (24h) ===================${NC}"
local error_count
error_count=$(journalctl -u "$SERVICE_NAME" --since "24h ago" -p err --no-pager -q 2>/dev/null | wc -l || echo "0")

if [ "$error_count" -gt 0 ]; then
    echo -e "  ${RED}[WARN]  $error_count error(s) en las ultimas 24 horas:${NC}"
    echo ""
    journalctl -u "$SERVICE_NAME" --since "24h ago" -p err --no-pager -n 5 2>/dev/null || true
else
    echo -e "  ${GREEN}Sin errores en las ultimas 24 horas.${NC}"
fi

echo ""
read -p "Presiona Enter para continuar..."

}

# ============================================

# NUEVO: Dashboard multi-bot

# ============================================

show_all_bots_dashboard() {
print_header "📊 DASHBOARD MULTI-BOT"

# Buscar servicios de bots instalados
local services
services=$(systemctl list-units --type=service --state=loaded \
    --no-pager --no-legend 2>/dev/null \
    | grep -E "bbalert|telebot|bot" \
    | awk '{print $1}' || true)

if [ -z "$services" ]; then
    print_warning "No se encontraron bots instalados como servicios systemd."
    print_info "Los bots apareceran aqui una vez instalados con este gestor."
    echo ""
    read -p "Presiona Enter para continuar..."
    return 0
fi

echo ""
printf "  ${WHITE}%-24s %-12s %-8s %-10s %-10s${NC}\n" "NOMBRE" "ESTADO" "CPU%" "RAM" "REINICIOS"
echo -e "  ${BLUE}--------------------------------------------------------${NC}"

for svc in $services; do
    local name="${svc%.service}"
    local active
    active=$(systemctl is-active "$svc" 2>/dev/null || echo "unknown")
    local pid
    pid=$(systemctl show "$svc" --property=MainPID --value 2>/dev/null || echo "0")
    local restarts
    restarts=$(systemctl show "$svc" --property=NRestarts --value 2>/dev/null || echo "0")
    local cpu="?" ram="?"

    if [ "$pid" != "0" ] && kill -0 "$pid" 2>/dev/null; then
        cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ' || echo "?")
        ram=$(ps -p "$pid" -o rss= 2>/dev/null | awk '{printf "%.0fMB", $1/1024}' 2>/dev/null || echo "?")
    fi

    local color=$RED
    local icon="o"
    if [ "$active" = "active" ]; then
        color=$GREEN
        icon="*"
    fi

    printf "  ${color}%-24s %-12s${NC} %-8s %-10s %-10s\n" \
        "${icon} ${name}" "$active" "${cpu}%" "$ram" "$restarts"
done

echo ""
print_info "Bots gestionados actualmente: $(echo "$services" | wc -l)"
echo ""
read -p "Presiona Enter para continuar..."

}

# ============================================

# NUEVO: Gestion avanzada de logs

# ============================================

manage_logs() {
print_header "📋 GESTION DE LOGS: $FOLDER_NAME"

echo -e "${YELLOW}Opciones disponibles:${NC}"
echo ""
echo "  1)  Ver logs en tiempo real"
echo "  2)  Ver ultimas 50 lineas"
echo "  3)  Ver ultimas 200 lineas"
echo "  4)  Ver solo errores"
echo "  5)  Buscar texto en logs"
echo "  6)  Ver logs por fecha"
echo "  7)  Exportar logs a archivo"
echo "  8)  Resumen de errores por hora"
echo "  0)  Volver al menu"
echo ""
read -p "Selecciona opcion: " log_choice

case $log_choice in
    1)
        print_info "Presiona Ctrl+C para salir."
        sleep 1
        $SUDO journalctl -u "$SERVICE_NAME" -f
        ;;
    2)
        $SUDO journalctl -u "$SERVICE_NAME" -n 50 --no-pager
        read -p "Presiona Enter para continuar..."
        ;;
    3)
        $SUDO journalctl -u "$SERVICE_NAME" -n 200 --no-pager
        read -p "Presiona Enter para continuar..."
        ;;
    4)
        print_info "Errores registrados:"
        echo ""
        $SUDO journalctl -u "$SERVICE_NAME" -p err --no-pager -n 50 || true
        read -p "Presiona Enter para continuar..."
        ;;
    5)
        read -p "Texto a buscar: " search_term
        if [ -n "$search_term" ]; then
            echo ""
            print_info "Resultados para: '$search_term'"
            echo ""
            $SUDO journalctl -u "$SERVICE_NAME" --no-pager -n 5000 2>/dev/null \
                | grep -i "$search_term" | tail -50 || print_warning "Sin resultados."
        fi
        read -p "Presiona Enter para continuar..."
        ;;
    6)
        read -p "Fecha (YYYY-MM-DD): " log_date
        if [[ "$log_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
            $SUDO journalctl -u "$SERVICE_NAME" \
                --since "${log_date} 00:00:00" \
                --until "${log_date} 23:59:59" \
                --no-pager || true
        else
            print_error "Formato de fecha invalido."
        fi
        read -p "Presiona Enter para continuar..."
        ;;
    7)
        local log_file="$HOME/logs_${FOLDER_NAME}_$(date +%Y%m%d_%H%M%S).txt"
        print_step "Exportando logs a $log_file..."
        $SUDO journalctl -u "$SERVICE_NAME" --no-pager > "$log_file" 2>/dev/null || true
        local size
        size=$(du -sh "$log_file" | cut -f1)
        print_success "Logs exportados: $log_file ($size)"
        read -p "Presiona Enter para continuar..."
        ;;
    8)
        echo ""
        print_info "Errores agrupados por hora (ultimas 24h):"
        echo ""
        $SUDO journalctl -u "$SERVICE_NAME" --since "24h ago" -p err --no-pager 2>/dev/null \
            | awk '{print $1, $2, substr($3,1,2)":00"}' \
            | sort | uniq -c | sort -rn | head -20 || print_info "Sin errores en 24h."
        read -p "Presiona Enter para continuar..."
        ;;
    0) return 0 ;;
    *) print_error "Opcion invalida." ;;
esac

}

# ============================================

# CONFIGURAR .ENV (mejorado con read -s)

# ============================================

configure_env() {
print_header "🔑 CONFIGURACION DE VARIABLES DE ENTORNO"

if [ -f "$PROJECT_DIR/.env" ]; then
    print_warning "Ya existe un archivo .env"
    read -p "Deseas reconfigurarlo? (s/N): " recreate
    if [[ ! "$recreate" =~ ^[sS]$ ]]; then
        print_info "Conservando configuracion existente."
        return 0
    fi
fi

print_info "Configurando $FOLDER_NAME..."
echo ""

# TOKEN con lectura segura (sin eco) + validacion
local TELEGRAM_TOKEN=""
local token_valid=false
local attempts=0

while [ "$token_valid" = false ] && [ $attempts -lt 3 ]; do
    read -s -p "🔑 TOKEN de Telegram Bot: " TELEGRAM_TOKEN
    echo ""  # salto de linea tras read -s

    if [ -z "$TELEGRAM_TOKEN" ]; then
        print_error "El token no puede estar vacio."
        ((attempts++))
        continue
    fi

    if validate_telegram_token "$TELEGRAM_TOKEN"; then
        token_valid=true
    else
        ((attempts++))
        if [ $attempts -lt 3 ]; then
            read -p "Reintentar? (S/n): " retry_token
            [[ "$retry_token" =~ ^[nN]$ ]] && break
        fi
    fi
done

if [ "$token_valid" = false ]; then
    print_warning "No se pudo validar el token. Guardando de todos modos (verifica manualmente)."
fi

echo ""
read -p "👤 ADMIN_CHAT_IDS (separados por coma): " ADMIN_IDS
read -p "??  OpenWeatherMap API Key (Enter para omitir): " WEATHER_KEY

# Crear .env
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
EOF

chmod 600 "$PROJECT_DIR/.env"
print_success "Archivo .env creado exitosamente con permisos 600."

return 0

}

# ============================================

# RESTO DE FUNCIONES (originales, mejoradas)

# ============================================

full_install() {
print_header "🚀 INSTALACION COMPLETA: $FOLDER_NAME"

echo -e "${YELLOW}Este proceso realizara:${NC}"
echo "  1. Instalacion de paquetes del sistema necesarios"
echo "  2. Creacion del entorno virtual"
echo "  3. Instalacion de dependencias Python"
echo "  4. Creacion del servicio systemd"
echo "  5. Configuracion de variables de entorno"
echo ""
read -p "Continuar? (S/n): " confirm
[[ "$confirm" =~ ^[nN]$ ]] && { print_info "Instalacion cancelada."; return 1; }

print_header "📦 PASO 1/5: Instalacion de Paquetes del Sistema"
print_step "Actualizando repositorios..."
$SUDO apt update -qq
print_step "Agregando repositorio deadsnakes (Python)..."
$SUDO apt install -y software-properties-common -qq
$SUDO add-apt-repository ppa:deadsnakes/ppa -y > /dev/null 2>&1 || true
$SUDO apt update -qq
print_step "Instalando Python y herramientas..."
$SUDO apt install -y python3.13 python3.13-venv python3.13-dev python3-pip -qq
print_success "Paquetes del sistema instalados."
sleep 1

print_header "🔧 PASO 2/5: Creacion del Entorno Virtual"
if ! create_venv; then
    print_error "Fallo la creacion del entorno virtual."
    read -p "Presiona Enter para volver al menu..."
    return 1
fi
sleep 1

print_header "📥 PASO 3/5: Instalacion de Dependencias"
if ! install_dependencies; then
    print_error "Fallo la instalacion de dependencias."
    read -p "Presiona Enter para volver al menu..."
    return 1
fi
sleep 1

print_header "⚙️  PASO 4/5: Creacion del Servicio Systemd"
if ! create_systemd_service; then
    print_warning "No se pudo crear el servicio automaticamente."
fi
sleep 1

print_header "✅ PASO 5/5: Verificacion de Configuracion"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    print_warning "No se encontro archivo .env"
    read -p "Configurar ahora? (S/n): " config_env
    [[ ! "$config_env" =~ ^[nN]$ ]] && configure_env
else
    print_success "Archivo .env encontrado."
fi

print_header "[OK] INSTALACION COMPLETADA"
print_success "Bot instalado correctamente:"
echo -e "  ${CYAN}Nombre:${NC}     $FOLDER_NAME"
echo -e "  ${CYAN}Servicio:${NC}   $SERVICE_NAME"
echo -e "  ${CYAN}Directorio:${NC} $PROJECT_DIR"
echo ""

read -p "Iniciar el bot ahora? (S/n): " start_now
[[ ! "$start_now" =~ ^[nN]$ ]] && start_bot

echo ""
read -p "Presiona Enter para volver al menu..."

}

create_systemd_service() {
print_step "Generando configuracion del servicio…"

local SERVICE_CONTENT="[Unit]

Description=Bot Telegram - $FOLDER_NAME
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=$PYTHON_BIN $BOT_SCRIPT_PATH
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$FOLDER_NAME

[Install]
WantedBy=multi-user.target"

echo "$SERVICE_CONTENT" > "/tmp/$SERVICE_NAME.service"
print_step "Instalando servicio (requiere sudo)..."
$SUDO cp "/tmp/$SERVICE_NAME.service" "$SERVICE_FILE"

if [ $? -ne 0 ]; then
    print_error "Fallo la instalacion del servicio."
    return 1
fi

$SUDO systemctl daemon-reload
$SUDO systemctl enable "$SERVICE_NAME" &>/dev/null
print_success "Servicio $SERVICE_NAME creado y habilitado."
return 0

}

manage_service() {
local ACTION=$1
case $ACTION in
"start")
print_step "Iniciando $SERVICE_NAME…"
$SUDO systemctl start "$SERVICE_NAME"
sleep 2
;;
"stop")
print_step "Deteniendo $SERVICE_NAME…"
$SUDO systemctl stop "$SERVICE_NAME"
sleep 1
;;
"restart")
print_step "Reiniciando $SERVICE_NAME…"
$SUDO systemctl restart "$SERVICE_NAME"
sleep 2
;;
"status")
$SUDO systemctl status "$SERVICE_NAME" --no-pager -l
return 0
;;
esac

if systemctl is-active --quiet "$SERVICE_NAME"; then
    print_success "Bot corriendo correctamente."
    notify_telegram "✅ <b>$FOLDER_NAME</b> ${ACTION^} exitoso en <code>$(hostname)</code>"
else
    print_error "El bot no esta corriendo."
    print_info "Revisa los logs con: sudo journalctl -u $SERVICE_NAME -n 50"
fi

}

start_bot() {
print_header ">? INICIANDO BOT: $FOLDER_NAME"
prompt_version_update

if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    print_warning "El servicio ya esta corriendo."
    read -p "Deseas reiniciarlo? (s/N): " restart_opt
    [[ "$restart_opt" =~ ^[sS]$ ]] && manage_service "restart"
else
    manage_service "start"
fi

echo ""
read -p "Ver logs en tiempo real? (s/N): " view_logs_opt
[[ "$view_logs_opt" =~ ^[sS]$ ]] && $SUDO journalctl -u "$SERVICE_NAME" -f

}

stop_bot() {
print_header "⏹️  DETENIENDO BOT: $FOLDER_NAME"
manage_service "stop"
echo ""
read -p "Presiona Enter para continuar…"
}

restart_bot() {
print_header "🔄 REINICIANDO BOT: $FOLDER_NAME"
prompt_version_update
manage_service "restart"
echo ""
$SUDO journalctl -u "$SERVICE_NAME" -f
}

status_bot() {
print_header "📊 ESTADO DEL BOT: $FOLDER_NAME"
manage_service "status"
echo ""
read -p "Presiona Enter para continuar…"
}

prompt_version_update() {
print_header "🔄 ACTUALIZACION DE VERSION"
read -p "Deseas actualizar la version del bot? (s/N): " update_choice

if [[ "$update_choice" =~ ^[sS]$ ]]; then
    echo ""
    print_info "Selecciona el tipo de actualizacion:"
    echo ""
    echo -e "  ${GREEN}1)${NC} Simple (patch)   ? Ultimo numero +1  (ej: 1.0.0 ? 1.0.1)"
    echo -e "  ${GREEN}2)${NC} Grande (minor)   ? Segundo numero +1 (ej: 1.0.5 ? 1.1.0)"
    echo -e "  ${GREEN}3)${NC} Completa (major) ? Primer numero +1  (ej: 1.2.3 ? 2.0.0)"
    echo -e "  ${YELLOW}0)${NC} Cancelar"
    echo ""
    read -p "Selecciona una opcion (0-3): " version_choice

    case $version_choice in
        1) update_version "patch" ;;
        2) update_version "minor" ;;
        3) update_version "major" ;;
        0) print_info "Actualizacion cancelada." ;;
        *) print_error "Opcion invalida." ;;
    esac
else
    print_info "Manteniendo version actual."
fi

}

update_version() {
local VERSION_TYPE="${1:-patch}"
local VERSION_SCRIPT="$PROJECT_DIR/update_version.py"

if [ -f "$VERSION_SCRIPT" ]; then
    print_step "Actualizando version del bot (tipo: $VERSION_TYPE)..."
    cd "$PROJECT_DIR"
    if [ -f "$PYTHON_BIN" ]; then
        "$PYTHON_BIN" "$VERSION_SCRIPT" "$VERSION_TYPE"
    else
        python3 "$VERSION_SCRIPT" "$VERSION_TYPE" || print_warning "No se pudo actualizar la version."
    fi
else
    print_warning "No se encontro update_version.py en $PROJECT_DIR"
fi

}

update_dependencies() {
print_header "🔄 ACTUALIZACION DE DEPENDENCIAS"

if [ ! -f "$REQUIREMENTS_PATH" ]; then
    print_error "No se encontro requirements.txt"
    read -p "Presiona Enter para continuar..."
    return 1
fi

print_info "Instalando/Actualizando dependencias..."
if install_dependencies; then
    print_success "Dependencias actualizadas."
    echo ""
    read -p "Reiniciar el bot para aplicar cambios? (S/n): " restart_opt
    [[ ! "$restart_opt" =~ ^[nN]$ ]] && manage_service "restart"
fi

echo ""
read -p "Presiona Enter para continuar..."

}

remove_dependency() {
print_header "🗑️  ELIMINAR DEPENDENCIA"

if [ ! -f "$REQUIREMENTS_PATH" ]; then
    print_error "No se encontro requirements.txt"
    read -p "Presiona Enter para continuar..."
    return 1
fi

mapfile -t lines < <(grep -v '^\s*$' "$REQUIREMENTS_PATH" | grep -v '^\s*#')

if [ ${#lines[@]} -eq 0 ]; then
    print_warning "No hay dependencias instaladas."
    read -p "Presiona Enter para continuar..."
    return 0
fi

print_info "Dependencias actuales:"
echo ""
local i=1
for line in "${lines[@]}"; do
    echo -e "  ${GREEN}$i)${NC} ${YELLOW}$line${NC}"
    ((i++))
done
echo -e "  ${RED}0)${NC} Cancelar"
echo ""

read -p "Numero de dependencia a eliminar: " selection

if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -gt 0 ] && [ "$selection" -le "${#lines[@]}" ]; then
    local SELECTED_LINE="${lines[$((selection-1))]}"
    local PACKAGE_NAME
    PACKAGE_NAME=$(echo "$SELECTED_LINE" | sed -E 's/([a-zA-Z0-9_\-]+).*/\1/')

    print_step "Eliminando $PACKAGE_NAME del venv..."
    "$PIP_BIN" uninstall -y "$PACKAGE_NAME"
    print_step "Eliminando de requirements.txt..."
    grep -vF "$SELECTED_LINE" "$REQUIREMENTS_PATH" > "${REQUIREMENTS_PATH}.tmp"
    mv "${REQUIREMENTS_PATH}.tmp" "$REQUIREMENTS_PATH"
    print_success "Dependencia eliminada."

    read -p "Reiniciar bot? (s/N): " restart_opt
    [[ "$restart_opt" =~ ^[sS]$ ]] && manage_service "restart"
elif [ "$selection" -eq 0 ]; then
    print_info "Operacion cancelada."
else
    print_error "Seleccion invalida."
fi

echo ""
read -p "Presiona Enter para continuar..."

}

uninstall_service() {
print_header "🗑️  DESINSTALAR SERVICIO"

print_warning "Esto eliminara el servicio systemd de $FOLDER_NAME"
print_info "El directorio y archivos del bot NO seran eliminados."
echo ""
read -p "Estas seguro? (s/N): " confirm
[[ ! "$confirm" =~ ^[sS]$ ]] && { print_info "Operacion cancelada."; read -p "Presiona Enter..."; return 0; }

systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null && {
    print_step "Deteniendo servicio..."
    $SUDO systemctl stop "$SERVICE_NAME"
}

$SUDO systemctl disable "$SERVICE_NAME" 2>/dev/null || true
[ -f "$SERVICE_FILE" ] && { $SUDO rm "$SERVICE_FILE"; print_success "Archivo de servicio eliminado."; }
$SUDO systemctl daemon-reload
$SUDO systemctl reset-failed 2>/dev/null || true
print_success "Servicio $SERVICE_NAME desinstalado completamente."

echo ""
read -p "Presiona Enter para continuar..."

}

change_directory() {
PROJECT_DIR=""
FOLDER_NAME=""
SERVICE_NAME=""
select_target_directory
}

# ============================================

# FUNCIONES GIT (originales, sin cambios)

# ============================================

get_git_branch() {
if [ -d "$PROJECT_DIR/.git" ]; then
cd "$PROJECT_DIR"
git branch --show-current 2>/dev/null || echo "N/A"
else
echo "N/A"
fi
}

git_clone_repository() {
print_header "📥 CLONAR REPOSITORIO"
local DEFAULT_REPO="https://github.com/ersus93/bbalert.git"
read -p "URL del repositorio [$DEFAULT_REPO]: " REPO_URL
REPO_URL=${REPO_URL:-$DEFAULT_REPO}
read -p "Directorio destino [~/bbalert]: " DEST_DIR
DEST_DIR=${DEST_DIR:-"$HOME/bbalert"}
DEST_DIR="${DEST_DIR/#~/$HOME}"

if [ -d "$DEST_DIR" ]; then
    print_warning "El directorio $DEST_DIR ya existe."
    read -p "Eliminar y continuar? (s/N): " overwrite
    [[ "$overwrite" =~ ^[sS]$ ]] && rm -rf "$DEST_DIR" || { print_info "Cancelado."; return 1; }
fi

print_step "Clonando $REPO_URL..."
git clone "$REPO_URL" "$DEST_DIR"

if [ $? -eq 0 ]; then
    print_success "Repositorio clonado en $DEST_DIR"
    read -p "Configurar este bot ahora? (S/n): " setup_now
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

force_pull_repository() {
local branch="$1"
local remote="${2:-origin}"

print_warning "Se descartaran TODOS los cambios locales."
read -p "Estas COMPLETAMENTE SEGURO? Escribe 'SI' para confirmar: " confirm_force
[[ "$confirm_force" != "SI" ]] && { print_info "Operacion cancelada."; return 1; }

print_step "Guardando backup de seguridad (stash)..."
git stash push -m "Backup automatico antes de force-pull ($(date '+%Y-%m-%d %H:%M:%S'))" --include-untracked 2>/dev/null || true

print_step "Reseteando a estado limpio..."
if ! git reset --hard "${remote}/${branch}"; then
    git clean -fd || true
    git fetch "${remote}" "${branch}" --force
    git reset --hard "${remote}/${branch}"
fi

print_success "Codigo forzado a la version de GitHub."
return 0

}

diagnose_pull_failure() {
local exit_code=$1
local branch=$2
print_error "El pull fallo (codigo: $exit_code)"
echo ""
print_info "Diagnostico de posibles causas:"
echo ""

! git diff-index --quiet HEAD -- 2>/dev/null && {
    echo -e "  ${RED}?${NC} Tienes cambios locales sin commitear:"
    git status --short | head -10
    echo ""
}

local untracked
untracked=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l || echo "0")
[ "$untracked" -gt 0 ] && echo -e "  ${RED}?${NC} Hay $untracked archivo(s) sin trackear\n"

local unpushed
unpushed=$(git log @{u}..HEAD --oneline 2>/dev/null | wc -l || echo "0")
[ "$unpushed" -gt 0 ] && echo -e "  ${RED}?${NC} Tienes $unpushed commit(s) locales no pusheados\n"

{ [ -d ".git/rebase-merge" ] || [ -d ".git/rebase-apply" ]; } && \
    echo -e "  ${RED}?${NC} Hay un rebase/merge en progreso sin completar\n"

}

git_pull_repository() {
local force_mode="${1:-false}"
print_header "🔄 ACTUALIZAR CODIGO DEL REPOSITORIO"

cd "$PROJECT_DIR" || { print_error "No se pudo acceder a $PROJECT_DIR"; return 1; }
[ ! -d ".git" ] && { print_error "Este directorio no es un repositorio Git."; return 1; }

local current_branch
current_branch=$(git branch --show-current)
print_info "Rama actual: $current_branch"

git remote get-url origin &>/dev/null || { print_error "No hay remote configurado."; return 1; }

print_step "Buscando actualizaciones..."
git fetch origin || { print_error "Fallo el fetch."; return 1; }

git rev-parse --abbrev-ref '@{u}' &>/dev/null || {
    git branch --set-upstream-to="origin/${current_branch}" "$current_branch" || return 1
}

local local_hash remote_hash
local_hash=$(git rev-parse HEAD)
remote_hash=$(git rev-parse '@{u}' 2>/dev/null || echo "")

[ -z "$remote_hash" ] && { print_error "No se pudo obtener el estado remoto"; return 1; }
[ "$local_hash" = "$remote_hash" ] && { print_success "El codigo esta actualizado."; return 0; }

print_info "Nuevos commits disponibles:"
git log HEAD..@{u} --oneline
echo ""

if [[ "$force_mode" != "true" ]]; then
    read -p "Actualizar ahora? (S/n): " confirm
    [[ "$confirm" =~ ^[nN]$ ]] && return 0
fi

if git pull origin "$current_branch"; then
    print_success "Codigo actualizado correctamente."
else
    local pull_exit_code=$?
    diagnose_pull_failure "$pull_exit_code" "$current_branch"
    echo ""

    if [[ "$force_mode" == "true" ]]; then
        force_pull_repository "$current_branch" "origin"
    else
        echo -e "${YELLOW}Opciones disponibles:${NC}"
        echo "  1) Forzar actualizacion (DESCARTAR cambios locales)"
        echo "  2) Ver diferencias"
        echo "  3) Intentar stash"
        echo "  4) Cancelar"
        echo ""
        read -p "Selecciona una opcion (1-4): " resolve_choice

        case "$resolve_choice" in
            1) force_pull_repository "$current_branch" "origin" ;;
            2) git diff --stat; read -p "Presiona Enter..."; return 1 ;;
            3)
                if git stash push -m "Auto-stash antes de pull ($(date '+%Y-%m-%d %H:%M:%S'))"; then
                    git pull origin "$current_branch" && print_success "Pull exitoso" || return 1
                fi
                ;;
            *) print_info "Operacion cancelada."; return 1 ;;
        esac
    fi
fi

print_success "Codigo sincronizado con GitHub"
read -p "Actualizar dependencias? (S/n): " update_deps
[[ ! "$update_deps" =~ ^[nN]$ ]] && install_dependencies

systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null && {
    read -p "Reiniciar el bot? (S/n): " do_restart
    [[ ! "$do_restart" =~ ^[nN]$ ]] && manage_service "restart"
}
return 0

}

git_switch_branch() {
print_header "🌿 CAMBIAR DE RAMA"
cd "$PROJECT_DIR" || return 1
[ ! -d ".git" ] && { print_error "No es un repositorio Git."; return 1; }

local CURRENT_BRANCH
CURRENT_BRANCH=$(git branch --show-current)
print_info "Rama actual: ${CYAN}$CURRENT_BRANCH${NC}"

if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    print_warning "Tienes cambios sin committear:"
    git status --short
    echo ""
    read -p "Descartar cambios y continuar? (s/N): " discard
    [[ ! "$discard" =~ ^[sS]$ ]] && { print_info "Cancelado."; return 0; }
    git checkout -- .
fi

echo ""
print_info "Ramas disponibles:"
echo ""
local BRANCHES=("main" "testing" "dev")
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
[ "$selection" = "0" ] && return 0

local TARGET_BRANCH=""
[[ "$selection" =~ ^[0-9]+$ ]] && TARGET_BRANCH="${BRANCHES[$((selection-1))]}"
[ -z "$TARGET_BRANCH" ] && { print_error "Seleccion invalida."; return 1; }

print_step "Cambiando a rama $TARGET_BRANCH..."
git checkout "$TARGET_BRANCH" && git pull origin "$TARGET_BRANCH"

if [ $? -eq 0 ]; then
    print_success "Ahora en rama: $TARGET_BRANCH"
    read -p "Actualizar dependencias? (S/n): " update_deps
    [[ ! "$update_deps" =~ ^[nN]$ ]] && install_dependencies
fi

}

git_show_status() {
print_header "📊 ESTADO DEL REPOSITORIO"
cd "$PROJECT_DIR" || return 1
[ ! -d ".git" ] && { print_error "No es un repositorio Git."; return 1; }

echo ""
echo -e "${CYAN}Rama actual:${NC}     $(git branch --show-current)"
echo -e "${CYAN}Remote:${NC}          $(git remote get-url origin 2>/dev/null || echo 'N/A')"
echo -e "${CYAN}Ultimo commit:${NC}   $(git log -1 --format='%h - %s (%cr)')"
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

git_show_history() {
print_header "📜 HISTORIAL DE COMMITS"
cd "$PROJECT_DIR" || return 1
[ ! -d ".git" ] && { print_error "No es un repositorio Git."; return 1; }

echo ""
print_info "Ultimos 15 commits:"
echo ""
git log --oneline -15 --decorate --graph
echo ""
read -p "Ver detalles de un commit? (ingresa hash o Enter para continuar): " commit_hash
[ -n "$commit_hash" ] && { git show "$commit_hash"; read -p "Presiona Enter para continuar..."; }

}

manage_environments() {
print_header "🌐 GESTION DE ENTORNOS"
echo ""
echo -e "  ${GREEN}1)${NC} Staging    ${YELLOW}(rama: testing)${NC}"
echo -e "  ${GREEN}2)${NC} Produccion ${YELLOW}(rama: main)${NC}"
echo -e "  ${YELLOW}0)${NC} Volver"
echo ""
read -p "Selecciona entorno: " env_choice

case $env_choice in
    1) local ENV_NAME="staging" ENV_DIR="$HOME/bbalert-staging" ENV_BRANCH="testing" ;;
    2) local ENV_NAME="produccion" ENV_DIR="$HOME/bbalert-prod" ENV_BRANCH="main" ;;
    *) return 0 ;;
esac

print_header "🌍 ENTORNO: $ENV_NAME"

if [ ! -d "$ENV_DIR" ]; then
    print_warning "El entorno no existe."
    read -p "Crear entorno $ENV_NAME? (S/n): " create_env
    [[ ! "$create_env" =~ ^[nN]$ ]] && create_environment "$ENV_DIR" "$ENV_BRANCH"
    return 0
fi

local ENV_SERVICE
ENV_SERVICE=$(basename "$ENV_DIR")
print_info "Directorio: $ENV_DIR"
print_info "Rama: $ENV_BRANCH"
systemctl is-active --quiet "$ENV_SERVICE" 2>/dev/null \
    && echo -e "${GREEN}Estado: En ejecucion${NC}" \
    || echo -e "${RED}Estado: Detenido${NC}"

echo ""
echo "  1) Actualizar codigo (git pull)"
echo "  2) Iniciar servicio"
echo "  3) Detener servicio"
echo "  4) Reiniciar servicio"
echo "  5) Ver logs"
echo "  0) Volver"
echo ""
read -p "Accion: " action

case $action in
    1) cd "$ENV_DIR" && git checkout "$ENV_BRANCH" && git pull origin "$ENV_BRANCH" && print_success "Codigo actualizado." ;;
    2) sudo systemctl start "$ENV_SERVICE" ;;
    3) sudo systemctl stop "$ENV_SERVICE" ;;
    4) sudo systemctl restart "$ENV_SERVICE" ;;
    5) sudo journalctl -u "$ENV_SERVICE" -f ;;
esac

}

create_environment() {
local ENV_DIR=$1
local ENV_BRANCH=$2
print_step "Creando entorno en $ENV_DIR…"
git clone https://github.com/ersus93/bbalert.git "$ENV_DIR"
cd "$ENV_DIR" && git checkout "$ENV_BRANCH"
detect_python
$TARGET_PYTHON -m venv venv
source venv/bin/activate
pip install -r requirements.txt --quiet
print_success "Entorno creado exitosamente."
print_info "Recuerda configurar el archivo .env en $ENV_DIR"
}

# ============================================

# MENU PRINCIPAL (mejorado con nuevas opciones)

# ============================================

show_menu() {
    clear
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}   🤖 GESTOR MULTI-BOT TELEGRAM (v4)        ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Bot Actual:${NC}    $FOLDER_NAME"
    echo -e "${CYAN}Servicio:${NC}     $SERVICE_NAME"
    echo -e "${CYAN}Directorio:${NC}   $PROJECT_DIR"
    echo -e "${CYAN}Rama Git:${NC}     $(get_git_branch)"
    echo ""

    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        local pid
        pid=$(systemctl show "$SERVICE_NAME" --property=MainPID --value 2>/dev/null || echo "0")
        local cpu="?" ram="?"
        if [ "$pid" != "0" ] && kill -0 "$pid" 2>/dev/null; then
            cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ' || echo "?")
            ram=$(ps -p "$pid" -o rss= 2>/dev/null | awk '{printf "%.0fMB", $1/1024}' 2>/dev/null || echo "?")
        fi
        echo -e "${GREEN}● Estado: Bot en ejecucion${NC}  ${CYAN}CPU: ${cpu}%  RAM: ${ram}${NC}"
    else
        echo -e "${RED}○ Estado: Bot detenido${NC}"
    fi

    echo ""
    echo -e "${BLUE}--------------------------------------------${NC}"
    echo -e "${YELLOW}📦 INSTALACION Y CONFIGURACION${NC}"
    echo "  1)  🚀 Instalacion Completa (desde cero)"
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
    echo "  10) 📈 Estadisticas de Recursos (CPU/RAM)"
    echo ""
    echo -e "${YELLOW}🔀 CONTROL DE GIT${NC}"
    echo "  11) 📥 Clonar Repositorio"
    echo "  12) 🔄 Actualizar Codigo (git pull)"
    echo "  13) 🌿 Cambiar de Rama"
    echo "  14) 📊 Ver Estado del Repositorio"
    echo "  15) 📜 Ver Historial de Commits"
    echo ""
    echo -e "${YELLOW}📋 LOGS Y MONITOREO${NC}"
    echo "  16) 📋 Gestion Avanzada de Logs"
    echo "  17) 📊 Dashboard Multi-Bot"
    echo ""
    echo -e "${YELLOW}💾 BACKUP Y RESTAURACION${NC}"
    echo "  18) 💾 Crear Backup"
    echo "  19) 🔄 Restaurar Backup"
    echo ""
    echo -e "${YELLOW}🌐 ENTORNOS Y MANTENIMIENTO${NC}"
    echo "  20) 🗺️  Gestion de Entornos (Staging/Produccion)"
    echo "  21) 🗑️  Eliminar Dependencia"
    echo "  22) 🗑️  Desinstalar Servicio"
    echo ""
    echo -e "${YELLOW}📂 OTROS${NC}"
    echo "  23) 📂 Cambiar Bot/Directorio Objetivo"
    echo "  0)  ❌ Salir"
    echo ""
    echo -e "${BLUE}--------------------------------------------${NC}"

}

# === PROGRAMA PRINCIPAL ===

check_root
check_system_dependencies

if [ "${1:-}" == "--install" ]; then
select_target_directory
full_install
exit 0
fi

if [ "${1:-}" == "--force-pull" ]; then
export FORCE_PULL=true
select_target_directory
git_pull_repository true
exit 0
fi

if [ "${1:-}" == "--backup" ]; then
select_target_directory
backup_bot
exit 0
fi

if [ "${1:-}" == "--stats" ]; then
select_target_directory
show_bot_stats
exit 0
fi

select_target_directory

while true; do
show_menu
read -p "Selecciona una opcion: " choice

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
    10) show_bot_stats ;;
    11) git_clone_repository; read -p "Presiona Enter para continuar..." ;;
    12) git_pull_repository "${FORCE_PULL:-false}" ;;
    13) git_switch_branch ;;
    14) git_show_status ;;
    15) git_show_history ;;
    16) manage_logs ;;
    17) show_all_bots_dashboard ;;
    18) backup_bot ;;
    19) restore_backup ;;
    20) manage_environments ;;
    21) remove_dependency ;;
    22) uninstall_service ;;
    23) change_directory ;;
    0)
        print_info "Hasta luego!"
        exit 0
        ;;
    *)
        print_error "Opcion invalida."
        sleep 1
        ;;
esac

done
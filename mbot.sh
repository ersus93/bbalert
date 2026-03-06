#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║         BBAlert Manager  —  Multi-Bot TUI v5                ║
# ╚══════════════════════════════════════════════════════════════╝

handle_error() { printf "\n\033[1;31m✘\033[0m  Error inesperado en línea ${1:-?}. Volviendo al menú.\n"; sleep 2; }
trap 'handle_error $LINENO' ERR

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
DEFAULT_PYTHON="python3.13"; FALLBACK_PYTHON="python3.12"
CURRENT_USER=$(whoami); BOT_MAIN_FILE="bbalert.py"; REQUIREMENTS_FILE="requirements.txt"
BACKUP_DIR="$HOME/backups"; MAX_BACKUPS=5

# ── COLORES ────────────────────────────────────────────────────────────────────
R='\033[0;31m' RB='\033[1;31m' G='\033[0;32m' GB='\033[1;32m'
Y='\033[0;33m' YB='\033[1;33m' B='\033[0;34m' BB='\033[1;34m'
M='\033[0;35m' C='\033[0;36m'  CB='\033[1;36m' WB='\033[1;37m'
DIM='\033[2m'  BOLD='\033[1m'  NC='\033[0m'

# ── PRIMITIVAS TUI ─────────────────────────────────────────────────────────────
_w()  { tput cols  2>/dev/null || echo 80; }
_clr(){ tput clear 2>/dev/null || clear; }

_hline() {
    local char="${1:-─}" col="${2:-$B}"
    local w; w=$(_w)
    printf "${col}"; printf "%.s${char}" $(seq 1 "$w"); printf "${NC}\n"
}

_center() {
    local text="$1" col="${2:-$WB}"
    local plain; plain=$(printf '%b' "$text" | sed 's/\x1b\[[0-9;]*m//g')
    local w; w=$(_w); local pad=$(( (w - ${#plain}) / 2 ))
    printf '%*s' "$pad" ''; printf "${col}%b${NC}\n" "$text"
}

_ok()   { printf "  ${GB}✔${NC}  %b\n" "$*"; }
_err()  { printf "  ${RB}✘${NC}  %b\n" "$*"; }
_warn() { printf "  ${YB}⚠${NC}  %b\n" "$*"; }
_info() { printf "  ${CB}›${NC}  %b\n" "$*"; }
_step() { printf "\n  ${M}▸${NC}  ${BOLD}%b${NC}\n" "$*"; }
_pause(){ printf "\n"; read -rp "$(printf "  ${DIM}Presiona Enter para continuar...${NC}")" _; }

_spin_start() {
    local msg="${1:-Procesando}"
    ( local f=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏') i=0
      while true; do
          printf "\r  ${CB}%s${NC}  ${DIM}%s...${NC}" "${f[$i]}" "$msg"
          i=$(( (i+1) % 10 )); sleep 0.1
      done ) &
    SPIN_PID=$!
}
_spin_stop() {
    [[ -n "${SPIN_PID:-}" ]] && kill "$SPIN_PID" 2>/dev/null
    wait "${SPIN_PID:-}" 2>/dev/null; unset SPIN_PID
    local w; w=$(_w); printf "\r%*s\r" "$w" ''
}

_item() {
    local num="$1" em="$2" lbl="$3" desc="${4:-}"
    printf "  ${CB}%3s${NC}  %s  ${WB}%-26s${NC}  ${DIM}%s${NC}\n" "${num})" "$em" "$lbl" "$desc"
}

_section() {
    printf "\n  ${YB}%s${NC}\n" "$1"
    printf "  ${DIM}"; printf '%.s─' $(seq 1 $(( $(_w) - 4 )) ); printf "${NC}\n"
}

# ── HEADER ─────────────────────────────────────────────────────────────────────
_header() {
    _clr
    _hline '═' "${BB}"
    printf "\n"
    _center "██████╗ ██████╗  █████╗ ██╗     ███████╗██████╗ ████████╗" "${BB}"
    _center "██╔══██╗██╔══██╗██╔══██╗██║     ██╔════╝██╔══██╗╚══██╔══╝" "${B}"
    _center "██████╔╝██████╔╝███████║██║     █████╗  ██████╔╝   ██║   " "${CB}"
    _center "██╔══██╗██╔══██╗██╔══██║██║     ██╔══╝  ██╔══██╗   ██║   " "${C}"
    _center "██████╔╝██████╔╝██║  ██║███████╗███████╗██║  ██║   ██║   " "${DIM}${C}"
    _center "╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝   ╚═╝  " "${DIM}"
    _center "M U L T I - B O T   M A N A G E R   v5" "${YB}"
    printf "\n"
    _hline '═' "${BB}"
}

# ── STATUS BAR ─────────────────────────────────────────────────────────────────
_status_bar() {
    local now; now=$(date '+%H:%M:%S')
    printf "${B}│${NC}"

    if [[ -n "${FOLDER_NAME:-}" ]]; then
        printf " ${DIM}Bot:${NC} ${WB}%s${NC}" "$FOLDER_NAME"
    else
        printf " ${DIM}Bot:${NC} ${Y}(sin seleccionar)${NC}"
    fi

    if [[ -n "${SERVICE_NAME:-}" ]]; then
        if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
            local pid cpu="?" ram="?"
            pid=$(systemctl show "${SERVICE_NAME}" --property=MainPID --value 2>/dev/null || echo "0")
            if [[ "${pid}" != "0" ]] && kill -0 "${pid}" 2>/dev/null; then
                cpu=$(ps -p "${pid}" -o %cpu= 2>/dev/null | tr -d ' ' || echo "?")
                ram=$(ps -p "${pid}" -o rss= 2>/dev/null | awk '{printf "%.0fMB",$1/1024}' || echo "?")
            fi
            printf "   ${GB}● ACTIVO${NC} ${DIM}cpu:${NC}%s%% ${DIM}ram:${NC}%s" "$cpu" "$ram"
        else
            printf "   ${RB}○ DETENIDO${NC}"
        fi
    fi

    if [[ -n "${PROJECT_DIR:-}" ]] && [[ -d "${PROJECT_DIR}/.git" ]]; then
        local br; br=$(cd "${PROJECT_DIR}" && git branch --show-current 2>/dev/null || echo "?")
        printf "   ${DIM}git:${NC}${C}%s${NC}" "$br"
    fi

    printf "   ${DIM}%s${NC} ${B}│${NC}\n" "$now"
    _hline '─' "${B}${DIM}"
}

# ── MENÚ PRINCIPAL ─────────────────────────────────────────────────────────────
show_menu() {
    _header
    _status_bar

    _section "⚙  INSTALACIÓN Y CONFIGURACIÓN"
    _item  1 "🚀" "Instalación Completa"      "Desde cero: venv, deps, servicio"
    _item  2 "🔧" "Crear/Recrear venv"         "Entorno virtual Python"
    _item  3 "📦" "Instalar Dependencias"      "pip install -r requirements.txt"
    _item  4 "🔑" "Configurar .env"            "TOKEN, ADMIN_IDS, API keys"
    _item  5 "⚙ " "Crear Servicio Systemd"     "Autostart con el sistema"

    _section "▶  CONTROL DEL BOT"
    _item  6 "▶ " "Iniciar Bot"               ""
    _item  7 "⏹ " "Detener Bot"               ""
    _item  8 "🔄" "Reiniciar Bot"             ""
    _item  9 "📋" "Estado del Servicio"       "systemctl status"
    _item 10 "📊" "Estadísticas de Recursos"  "CPU · RAM · Uptime · Errores"

    _section "🌿  CONTROL DE GIT"
    _item 11 "📥" "Clonar Repositorio"        ""
    _item 12 "⬇ " "Actualizar Código"         "git pull"
    _item 13 "🌿" "Cambiar de Rama"           "main / testing / dev"
    _item 14 "📊" "Estado del Repositorio"    "diff, commits pendientes"
    _item 15 "📜" "Historial de Commits"      ""

    _section "🔍  LOGS Y MONITOREO"
    _item 16 "📋" "Gestión de Logs"           "Filtrar · buscar · exportar"
    _item 17 "🌐" "Dashboard Multi-Bot"       "Todos los bots del sistema"

    _section "💾  BACKUP Y MANTENIMIENTO"
    _item 18 "💾" "Crear Backup"              "tar.gz sin venv"
    _item 19 "♻ " "Restaurar Backup"         ""
    _item 20 "🗺 " "Gestión de Entornos"      "Staging · Producción"
    _item 21 "🗑 " "Eliminar Dependencia"     ""
    _item 22 "🗑 " "Desinstalar Servicio"     ""

    _section "📁  OTROS"
    _item 23 "📂" "Cambiar Bot/Directorio"    ""
    printf "\n"
    _hline '─' "${B}${DIM}"
    printf "  ${RB}  0${NC}  ✕  ${DIM}Salir${NC}\n"
    _hline '─' "${B}${DIM}"
    printf "\n  ${CB}›${NC} Selecciona una opción: "
}

# ── UTILIDADES ─────────────────────────────────────────────────────────────────
check_root() {
    if [[ "$EUID" -ne 0 ]]; then SUDO="sudo"
    else SUDO=""; _warn "Ejecutando como root. Se recomienda usuario normal."; fi
}

check_system_dependencies() {
    _step "Verificando dependencias del sistema"
    local missing=()
    for cmd in curl git systemctl tar; do command -v "$cmd" &>/dev/null || missing+=("$cmd"); done
    if [[ ${#missing[@]} -gt 0 ]]; then
        _err "Faltan: ${missing[*]}"
        read -rp "  ¿Instalar ahora? [S/n]: " yn
        [[ ! "$yn" =~ ^[nN]$ ]] && $SUDO apt update -qq && $SUDO apt install -y "${missing[@]}" -qq
    else _ok "Todas las dependencias disponibles."; fi
}

detect_python() {
    _step "Detectando Python"
    if command -v $DEFAULT_PYTHON &>/dev/null; then TARGET_PYTHON=$DEFAULT_PYTHON; _ok "Usando $DEFAULT_PYTHON"; return 0
    elif command -v $FALLBACK_PYTHON &>/dev/null; then TARGET_PYTHON=$FALLBACK_PYTHON; _warn "Usando $FALLBACK_PYTHON"; return 0
    else _err "Python 3.12/3.13 no encontrado"; return 1; fi
}

validate_bot_directory() {
    local dir=$1
    [[ -d "$dir" && -f "$dir/$BOT_MAIN_FILE" && -f "$dir/$REQUIREMENTS_FILE" ]]
}

get_git_branch() {
    [[ -d "${PROJECT_DIR:-}/.git" ]] || { echo "N/A"; return; }
    cd "${PROJECT_DIR}" && git branch --show-current 2>/dev/null || echo "N/A"
}

# ── SELECCIÓN DE DIRECTORIO ────────────────────────────────────────────────────
select_target_directory() {
    _header; _center "SELECCIÓN DE BOT" "${YB}"; printf "\n"

    if validate_bot_directory "$(pwd)"; then
        local detected; detected=$(pwd)
        _ok "Bot detectado en el directorio actual:"; _info "${CB}$detected${NC}"
        printf "\n"; read -rp "  ¿Usar este directorio? [S/n]: " yn
        [[ ! "$yn" =~ ^[nN]$ ]] && PROJECT_DIR="$detected"
    fi

    if [[ -z "${PROJECT_DIR:-}" ]]; then
        _info "Buscando bots en el sistema..."
        local found_bots=()
        for bp in "$HOME" "$HOME/bots" "$HOME/telegram" "/opt" "$(pwd)"; do
            [[ -d "$bp" ]] || continue
            while IFS= read -r -d '' bd; do
                validate_bot_directory "$bd" && found_bots+=("$bd")
            done < <(find "$bp" -maxdepth 2 -name "$BOT_MAIN_FILE" -type f -print0 2>/dev/null | xargs -0 dirname -z 2>/dev/null)
        done
        found_bots=($(printf '%s\n' "${found_bots[@]}" | sort -u 2>/dev/null || true))
        if [[ ${#found_bots[@]} -gt 0 ]]; then
            printf "\n"; _ok "${#found_bots[@]} bot(s) encontrado(s):"; printf "\n"
            for i in "${!found_bots[@]}"; do
                printf "  ${GB}%3d)${NC}  ${WB}%-20s${NC}  ${DIM}%s${NC}\n" \
                    "$((i+1))" "$(basename "${found_bots[$i]}")" "${found_bots[$i]}"
            done
            printf "  ${YB}%3d)${NC}  Ingresar ruta manual\n" "0"; printf "\n"
            read -rp "  Selecciona (0-${#found_bots[@]}): " sel
            [[ "$sel" =~ ^[1-9][0-9]*$ ]] && [[ "$sel" -le "${#found_bots[@]}" ]] && \
                PROJECT_DIR="${found_bots[$((sel-1))]}"
        fi
    fi

    while [[ -z "${PROJECT_DIR:-}" ]]; do
        printf "\n"; _info "Ingresa la ruta completa del bot:"
        read -rpe "  Ruta: " INPUT_DIR
        INPUT_DIR="${INPUT_DIR/#\~/$HOME}"
        INPUT_DIR=$(realpath "$INPUT_DIR" 2>/dev/null || echo "$INPUT_DIR")
        if validate_bot_directory "$INPUT_DIR"; then PROJECT_DIR="$INPUT_DIR"; _ok "Directorio válido."
        else _err "Bot no encontrado en esa ruta."
            read -rp "  ¿Reintentar? [S/n]: " rt
            [[ "$rt" =~ ^[nN]$ ]] && exit 1; fi
    done

    PROJECT_DIR=$(realpath "$PROJECT_DIR"); FOLDER_NAME=$(basename "$PROJECT_DIR")
    SERVICE_NAME="${FOLDER_NAME}"; SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
    VENV_DIR="$PROJECT_DIR/venv"; PYTHON_BIN="$VENV_DIR/bin/python"; PIP_BIN="$VENV_DIR/bin/pip"
    ACTIVATE_SCRIPT="$VENV_DIR/bin/activate"; REQUIREMENTS_PATH="$PROJECT_DIR/$REQUIREMENTS_FILE"
    BOT_SCRIPT_PATH="$PROJECT_DIR/$BOT_MAIN_FILE"

    printf "\n"; _hline '─' "${B}${DIM}"
    _ok "${WB}${FOLDER_NAME}${NC} cargado"
    _info "Ruta: ${CB}${PROJECT_DIR}${NC}"
    _info "Servicio: ${CB}${SERVICE_NAME}${NC}"
    _hline '─' "${B}${DIM}"; sleep 1
}

# ── VENV ───────────────────────────────────────────────────────────────────────
create_venv() {
    _header; _center "ENTORNO VIRTUAL" "${YB}"; printf "\n"
    cd "$PROJECT_DIR" || { _err "No se pudo acceder"; return 1; }
    if [[ -d "$VENV_DIR" ]]; then
        _warn "Ya existe un entorno virtual."
        if [[ ! -f "$ACTIVATE_SCRIPT" ]] || [[ ! -f "$PYTHON_BIN" ]]; then
            read -rp "  ¿Corrupto. Recrear? [S/n]: " yn; [[ ! "$yn" =~ ^[nN]$ ]] && rm -rf "$VENV_DIR" || return 1
        else
            read -rp "  ¿Recrear? [s/N]: " yn; [[ "$yn" =~ ^[sS]$ ]] && rm -rf "$VENV_DIR" || { _info "Usando existente."; return 0; }
        fi
    fi
    detect_python || return 1
    _spin_start "Creando entorno virtual"
    $TARGET_PYTHON -m venv "$VENV_DIR"
    _spin_stop
    [[ -f "$ACTIVATE_SCRIPT" ]] || { _err "venv no creado."; return 1; }
    _ok "Entorno virtual listo."
    source "$ACTIVATE_SCRIPT"
    _spin_start "pip upgrade"
    "$PYTHON_BIN" -m pip install --upgrade pip --quiet
    _spin_stop
    _ok "pip: $("$PIP_BIN" --version | cut -d' ' -f1-2)"
}

# ── DEPENDENCIAS ───────────────────────────────────────────────────────────────
install_dependencies() {
    _step "Instalando dependencias"
    [[ -f "$REQUIREMENTS_PATH" ]] || { _err "requirements.txt no encontrado"; return 1; }
    [[ -f "$PIP_BIN" ]] || { _err "venv no existe. Créalo con opción 2."; return 1; }
    source "$ACTIVATE_SCRIPT"
    _info "Paquetes:"
    grep -v '^\s*#' "$REQUIREMENTS_PATH" | grep -v '^\s*$' | while read -r l; do printf "    ${DIM}·${NC} %s\n" "$l"; done
    printf "\n"
    _spin_start "pip install"
    "$PIP_BIN" install -r "$REQUIREMENTS_PATH" -q; local rc=$?
    _spin_stop
    [[ $rc -eq 0 ]] && _ok "Dependencias instaladas." || _err "Errores en la instalación."
    return $rc
}

# ── VALIDAR TOKEN ──────────────────────────────────────────────────────────────
validate_telegram_token() {
    local token="$1"
    [[ "$token" =~ ^[0-9]{8,10}:[A-Za-z0-9_-]{35}$ ]] || { _err "Formato inválido."; return 1; }
    _spin_start "Verificando token"
    local resp; resp=$(curl -s --max-time 10 "https://api.telegram.org/bot${token}/getMe" 2>/dev/null || echo "")
    _spin_stop
    echo "$resp" | grep -q '"ok":true' && {
        local uname; uname=$(echo "$resp" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
        _ok "Token válido — @${uname}"; return 0
    }
    _err "Token rechazado por Telegram."; return 1
}

notify_telegram() {
    local msg="$1"
    [[ -f "$PROJECT_DIR/.env" ]] || return 0
    local token admins
    token=$(grep '^TOKEN_TELEGRAM=' "$PROJECT_DIR/.env" | cut -d'=' -f2- | tr -d '"')
    admins=$(grep '^ADMIN_CHAT_IDS=' "$PROJECT_DIR/.env" | cut -d'=' -f2- | tr -d '"')
    [[ -z "$token" || -z "$admins" ]] && return 0
    IFS=',' read -ra al <<< "$admins"
    for aid in "${al[@]}"; do
        aid=$(echo "$aid" | tr -d ' ')
        curl -s --max-time 5 -X POST "https://api.telegram.org/bot${token}/sendMessage" \
            -d "chat_id=${aid}&text=${msg}&parse_mode=HTML" > /dev/null 2>&1 || true
    done
}

# ── BACKUP ─────────────────────────────────────────────────────────────────────
backup_bot() {
    _header; _center "BACKUP — ${FOLDER_NAME}" "${YB}"; printf "\n"
    local bdir="$BACKUP_DIR/$FOLDER_NAME"
    local ts; ts=$(date '+%Y%m%d_%H%M%S')
    local bfile="${bdir}/${FOLDER_NAME}_${ts}.tar.gz"
    mkdir -p "$bdir"
    _spin_start "Comprimiendo (sin venv)"
    tar -czf "$bfile" --exclude="$PROJECT_DIR/venv" --exclude="$PROJECT_DIR/__pycache__" \
        --exclude="$PROJECT_DIR/*.pyc" --exclude="$PROJECT_DIR/.git" \
        -C "$(dirname "$PROJECT_DIR")" "$(basename "$PROJECT_DIR")" 2>/dev/null
    _spin_stop
    if [[ $? -eq 0 ]]; then
        local sz; sz=$(du -sh "$bfile" | cut -f1)
        _ok "$(basename "$bfile") — $sz"
        local cnt; cnt=$(ls "$bdir"/*.tar.gz 2>/dev/null | wc -l)
        if [[ "$cnt" -gt "$MAX_BACKUPS" ]]; then
            ls -t "$bdir"/*.tar.gz | tail -n $(( cnt - MAX_BACKUPS )) | xargs rm -f
            _info "Rotación: se mantienen $MAX_BACKUPS backups."
        fi
        printf "\n"; _info "Backups disponibles:"
        ls -lh "$bdir"/*.tar.gz 2>/dev/null | awk '{printf "    %-42s %s\n", $NF, $5}'
    else _err "Falló el backup."; return 1; fi
    _pause
}

restore_backup() {
    _header; _center "RESTAURAR BACKUP — ${FOLDER_NAME}" "${YB}"; printf "\n"
    local bdir="$BACKUP_DIR/$FOLDER_NAME"
    [[ -d "$bdir" ]] && ls "$bdir"/*.tar.gz &>/dev/null || { _err "No hay backups."; _pause; return 1; }
    mapfile -t bkps < <(ls -t "$bdir"/*.tar.gz 2>/dev/null)
    for i in "${!bkps[@]}"; do
        printf "  ${GB}%3d)${NC}  %-40s  ${DIM}%s${NC}\n" "$((i+1))" "$(basename "${bkps[$i]}")" "$(du -sh "${bkps[$i]}" | cut -f1)"
    done
    printf "  ${YB}%3d)${NC}  Cancelar\n" "0"; printf "\n"
    read -rp "  Selecciona: " sel
    [[ ! "$sel" =~ ^[1-9][0-9]*$ ]] || [[ "$sel" -gt "${#bkps[@]}" ]] && { _info "Cancelado."; _pause; return 0; }
    _warn "Esto SOBREESCRIBIRÁ el directorio actual."
    read -rp "  ¿Confirmas? [s/N]: " cn; [[ ! "$cn" =~ ^[sS]$ ]] && { _info "Cancelado."; _pause; return 0; }
    systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null && { _step "Deteniendo bot"; $SUDO systemctl stop "$SERVICE_NAME"; }
    _spin_start "Restaurando"
    tar -xzf "${bkps[$((sel-1))]}" -C "$(dirname "$PROJECT_DIR")" 2>/dev/null
    _spin_stop
    [[ $? -eq 0 ]] && _ok "Restaurado." || _err "Falló la restauración."
    read -rp "  ¿Reiniciar bot? [S/n]: " yn; [[ ! "$yn" =~ ^[nN]$ ]] && manage_service "start"
    _pause
}

# ── ESTADÍSTICAS ───────────────────────────────────────────────────────────────
show_bot_stats() {
    _header; _center "ESTADÍSTICAS — ${FOLDER_NAME}" "${YB}"; printf "\n"
    local pid; pid=$(systemctl show "${SERVICE_NAME}" --property=MainPID --value 2>/dev/null || echo "0")
    local W; W=$(( $(_w) - 4 ))

    printf "${B}╭"; printf '─%.0s' $(seq 1 $W); printf "╮${NC}\n"
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        printf "${B}│${NC}  ${GB}● ACTIVO${NC}%-*s${B}│${NC}\n" $(( W - 8 )) ""
    else
        printf "${B}│${NC}  ${RB}○ DETENIDO${NC}%-*s${B}│${NC}\n" $(( W - 10 )) ""
    fi
    local since; since=$(systemctl show "${SERVICE_NAME}" --property=ActiveEnterTimestamp --value 2>/dev/null || echo "N/A")
    printf "${B}│${NC}  ${DIM}Activo desde:${NC} %-*s${B}│${NC}\n" $(( W - 15 )) "${since}"
    local restarts; restarts=$(systemctl show "${SERVICE_NAME}" --property=NRestarts --value 2>/dev/null || echo "0")
    if [[ "${restarts:-0}" -gt 5 ]] 2>/dev/null; then
        printf "${B}│${NC}  ${DIM}Reinicios:${NC} ${RB}%s ⚠${NC}%-*s${B}│${NC}\n" "$restarts" $(( W - 12 - ${#restarts} )) ""
    else
        printf "${B}│${NC}  ${DIM}Reinicios:${NC} ${CB}%s${NC}%-*s${B}│${NC}\n" "$restarts" $(( W - 12 - ${#restarts} )) ""
    fi
    if [[ "${pid}" != "0" ]] && kill -0 "${pid}" 2>/dev/null; then
        local cpu ram thr
        cpu=$(ps -p "${pid}" -o %cpu= 2>/dev/null | tr -d ' ' || echo "?")
        ram=$(ps -p "${pid}" -o rss= 2>/dev/null | awk '{printf "%.1f MB",$1/1024}' || echo "?")
        thr=$(ps -p "${pid}" -o nlwp= 2>/dev/null | tr -d ' ' || echo "?")
        printf "${B}│${NC}  ${DIM}PID:${NC}${CB}%s${NC}  ${DIM}CPU:${NC}${YB}%s%%${NC}  ${DIM}RAM:${NC}${YB}%s${NC}  ${DIM}Hilos:${NC}${CB}%s${NC}%-*s${B}│${NC}\n" \
            "$pid" "$cpu" "$ram" "$thr" $(( W - 30 - ${#pid} - ${#cpu} - ${#ram} - ${#thr} )) ""
    fi
    local psz vsz; psz=$(du -sh "$PROJECT_DIR" --exclude="$VENV_DIR" 2>/dev/null | cut -f1 || echo "?")
    vsz=$(du -sh "$VENV_DIR" 2>/dev/null | cut -f1 || echo "?")
    printf "${B}│${NC}  ${DIM}Disco bot:${NC}${CB}%s${NC}  ${DIM}venv:${NC}${CB}%s${NC}%-*s${B}│${NC}\n" \
        "$psz" "$vsz" $(( W - 20 - ${#psz} - ${#vsz} )) ""
    printf "${B}╰"; printf '─%.0s' $(seq 1 $W); printf "╯${NC}\n"

    printf "\n"; _info "Errores recientes (24h):"
    local ec; ec=$($SUDO journalctl -u "${SERVICE_NAME}" --since "24h ago" -p err --no-pager -q 2>/dev/null | wc -l || echo "0")
    if [[ "$ec" -gt 0 ]]; then
        _warn "${ec} error(s) en 24h:"
        $SUDO journalctl -u "${SERVICE_NAME}" --since "24h ago" -p err --no-pager -n 5 2>/dev/null | \
            while IFS= read -r l; do printf "  ${DIM}%s${NC}\n" "$l"; done
    else _ok "Sin errores en las últimas 24 horas."; fi
    _pause
}

# ── DASHBOARD MULTI-BOT ────────────────────────────────────────────────────────
show_all_bots_dashboard() {
    _header; _center "DASHBOARD MULTI-BOT" "${YB}"; printf "\n"
    local svcs
    svcs=$(systemctl list-units --type=service --state=loaded --no-pager --no-legend 2>/dev/null \
        | grep -E "bbalert|telebot|bot" | awk '{print $1}' || true)
    if [[ -z "$svcs" ]]; then _warn "No hay bots como servicios systemd."; _pause; return 0; fi
    printf "\n  ${WB}%-26s %-12s %-8s %-10s %-8s${NC}\n" "NOMBRE" "ESTADO" "CPU%" "RAM" "REINIC."
    _hline '─' "${B}${DIM}"
    for svc in $svcs; do
        local name="${svc%.service}"
        local active; active=$(systemctl is-active "$svc" 2>/dev/null || echo "unknown")
        local pid; pid=$(systemctl show "$svc" --property=MainPID --value 2>/dev/null || echo "0")
        local restarts; restarts=$(systemctl show "$svc" --property=NRestarts --value 2>/dev/null || echo "?")
        local cpu="—" ram="—"
        [[ "$pid" != "0" ]] && kill -0 "$pid" 2>/dev/null && {
            cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ' || echo "—")
            ram=$(ps -p "$pid" -o rss= 2>/dev/null | awk '{printf "%.0fMB",$1/1024}' || echo "—")
        }
        local col=$R icon="○"; [[ "$active" = "active" ]] && col=$G && icon="●"
        printf "  ${col}%s %-24s${NC} %-12s %-8s %-10s %-8s\n" \
            "$icon" "$name" "$active" "${cpu}%" "$ram" "$restarts"
    done
    printf "\n"; _info "Total: $(echo "$svcs" | wc -l) bot(s)"; _pause
}

# ── GESTIÓN DE LOGS ────────────────────────────────────────────────────────────
manage_logs() {
    while true; do
        _header; _center "GESTIÓN DE LOGS — ${FOLDER_NAME}" "${YB}"; printf "\n"
        _item  1 "📡" "Tiempo real"           "Ctrl+C para salir"
        _item  2 "📋" "Últimas 50 líneas"    ""
        _item  3 "📋" "Últimas 200 líneas"   ""
        _item  4 "🔴" "Solo errores"         "Últimas 50"
        _item  5 "🔍" "Buscar texto"         ""
        _item  6 "📅" "Por fecha"            "YYYY-MM-DD"
        _item  7 "💾" "Exportar"             "archivo .txt"
        _item  8 "📊" "Errores por hora"     "Últimas 24h"
        _item  0 "✕"  "Volver"              ""
        printf "\n"; read -rp "  Opción: " lc
        case $lc in
            1) _info "Ctrl+C para salir."; sleep 1; $SUDO journalctl -u "$SERVICE_NAME" -f ;;
            2) $SUDO journalctl -u "$SERVICE_NAME" -n 50 --no-pager; _pause ;;
            3) $SUDO journalctl -u "$SERVICE_NAME" -n 200 --no-pager; _pause ;;
            4) $SUDO journalctl -u "$SERVICE_NAME" -p err --no-pager -n 50; _pause ;;
            5) read -rp "  Texto: " st
               [[ -n "$st" ]] && $SUDO journalctl -u "$SERVICE_NAME" --no-pager -n 5000 2>/dev/null \
                   | grep -i "$st" | tail -50 || _warn "Sin resultados."
               _pause ;;
            6) read -rp "  Fecha (YYYY-MM-DD): " ld
               [[ "$ld" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] && \
                   $SUDO journalctl -u "$SERVICE_NAME" --since "${ld} 00:00:00" --until "${ld} 23:59:59" --no-pager \
                   || _err "Formato inválido."; _pause ;;
            7) local lf="$HOME/logs_${FOLDER_NAME}_$(date +%Y%m%d_%H%M%S).txt"
               _spin_start "Exportando"; $SUDO journalctl -u "$SERVICE_NAME" --no-pager > "$lf" 2>/dev/null; _spin_stop
               _ok "Logs en: $lf ($(du -sh "$lf" | cut -f1))"; _pause ;;
            8) printf "\n"; _info "Errores por hora (24h):"
               $SUDO journalctl -u "$SERVICE_NAME" --since "24h ago" -p err --no-pager 2>/dev/null \
                   | awk '{print $1,$2,substr($3,1,2)":00"}' | sort | uniq -c | sort -rn | head -20 \
                   || _ok "Sin errores."
               _pause ;;
            0) return 0 ;;
            *) _err "Opción inválida."; sleep 1 ;;
        esac
    done
}

# ── CONFIGURAR .ENV ────────────────────────────────────────────────────────────
configure_env() {
    _header; _center "VARIABLES DE ENTORNO" "${YB}"; printf "\n"
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        _warn "Ya existe .env"
        read -rp "  ¿Reconfigurar? [s/N]: " yn; [[ ! "$yn" =~ ^[sS]$ ]] && { _info "Conservando."; return 0; }
    fi
    local TOKEN="" tv=false attempts=0
    while [[ "$tv" = false ]] && [[ $attempts -lt 3 ]]; do
        read -rsp "  🔑 TOKEN de Telegram Bot: " TOKEN; printf "\n"
        [[ -z "$TOKEN" ]] && { _err "Token vacío."; ((attempts++)); continue; }
        validate_telegram_token "$TOKEN" && tv=true || ((attempts++))
    done
    [[ "$tv" = false ]] && _warn "Token no validado. Guardando de todos modos."
    printf "\n"
    read -rp "  👤 ADMIN_CHAT_IDS (coma-separados): " ADMIN_IDS
    read -rp "  🌤  OpenWeatherMap API Key (Enter=omitir): " WEATHER_KEY
    cat > "$PROJECT_DIR/.env" << EOF
# ============================================
# $FOLDER_NAME — Variables de Entorno
# Generado: $(date)
# ============================================
TOKEN_TELEGRAM=$TOKEN
ADMIN_CHAT_IDS=$ADMIN_IDS
OPENWEATHER_API_KEY=$WEATHER_KEY
EOF
    chmod 600 "$PROJECT_DIR/.env"
    _ok "Archivo .env creado con permisos 600."
}

# ── INSTALACIÓN COMPLETA ───────────────────────────────────────────────────────
full_install() {
    _header; _center "INSTALACIÓN COMPLETA — ${FOLDER_NAME}" "${YB}"; printf "\n"
    _info "Instalará: paquetes del sistema, venv, dependencias, servicio, .env"
    printf "\n"; read -rp "  ¿Continuar? [S/n]: " yn; [[ "$yn" =~ ^[nN]$ ]] && return 1

    _step "PASO 1/5 — Paquetes del sistema"
    _spin_start "apt update"; $SUDO apt update -qq; _spin_stop
    $SUDO apt install -y software-properties-common python3.13 python3.13-venv python3.13-dev python3-pip -qq
    _ok "Paquetes instalados."

    _step "PASO 2/5 — Entorno virtual"; create_venv || { _err "Falló venv."; _pause; return 1; }
    _step "PASO 3/5 — Dependencias"; install_dependencies || { _err "Falló pip."; _pause; return 1; }
    _step "PASO 4/5 — Servicio Systemd"; create_systemd_service || _warn "No se pudo crear el servicio."
    _step "PASO 5/5 — Verificación .env"
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        _warn "No se encontró .env"
        read -rp "  ¿Configurar ahora? [S/n]: " yn; [[ ! "$yn" =~ ^[nN]$ ]] && configure_env
    else _ok ".env encontrado."; fi

    printf "\n"; _hline '═' "${GB}"; _center "✔  INSTALACIÓN COMPLETADA" "${GB}"; _hline '═' "${GB}"; printf "\n"
    read -rp "  ¿Iniciar el bot ahora? [S/n]: " yn; [[ ! "$yn" =~ ^[nN]$ ]] && start_bot
    _pause
}

# ── SERVICIO SYSTEMD ───────────────────────────────────────────────────────────
create_systemd_service() {
    _step "Generando servicio systemd"
    echo "[Unit]
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
NoNewPrivileges=true
PrivateTmp=true
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$FOLDER_NAME

[Install]
WantedBy=multi-user.target" > "/tmp/$SERVICE_NAME.service"
    $SUDO cp "/tmp/$SERVICE_NAME.service" "$SERVICE_FILE" || { _err "Falló la copia."; return 1; }
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable "$SERVICE_NAME" &>/dev/null
    _ok "Servicio $SERVICE_NAME creado y habilitado."
}

# ── GESTIÓN DE SERVICIO ────────────────────────────────────────────────────────
manage_service() {
    local ACTION=$1
    case $ACTION in
        start)   _step "Iniciando";   $SUDO systemctl start   "$SERVICE_NAME"; sleep 2 ;;
        stop)    _step "Deteniendo";  $SUDO systemctl stop    "$SERVICE_NAME"; sleep 1 ;;
        restart) _step "Reiniciando"; $SUDO systemctl restart "$SERVICE_NAME"; sleep 2 ;;
        status)  $SUDO systemctl status "$SERVICE_NAME" --no-pager -l; return 0 ;;
    esac
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        _ok "Bot corriendo correctamente."
        notify_telegram "✅ <b>$FOLDER_NAME</b> ${ACTION^} en <code>$(hostname)</code>"
    else _err "El bot no está corriendo."; _info "journalctl -u $SERVICE_NAME -n 50"; fi
}

start_bot() {
    _header; _center "INICIAR — ${FOLDER_NAME}" "${YB}"; printf "\n"
    prompt_version_update
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        _warn "Ya está corriendo."
        read -rp "  ¿Reiniciar? [s/N]: " yn; [[ "$yn" =~ ^[sS]$ ]] && manage_service "restart"
    else manage_service "start"; fi
    printf "\n"; read -rp "  ¿Ver logs en tiempo real? [s/N]: " yn
    [[ "$yn" =~ ^[sS]$ ]] && $SUDO journalctl -u "$SERVICE_NAME" -f
}
stop_bot()    { _header; _center "DETENER — ${FOLDER_NAME}" "${YB}"; printf "\n"; manage_service "stop"; _pause; }
restart_bot() { _header; _center "REINICIAR — ${FOLDER_NAME}" "${YB}"; printf "\n"; prompt_version_update; manage_service "restart"; printf "\n"; $SUDO journalctl -u "$SERVICE_NAME" -f; }
status_bot()  { _header; _center "ESTADO — ${FOLDER_NAME}" "${YB}"; printf "\n"; manage_service "status"; _pause; }

# ── VERSIÓN ────────────────────────────────────────────────────────────────────
prompt_version_update() {
    _header; _center "ACTUALIZACIÓN DE VERSIÓN" "${YB}"; printf "\n"
    read -rp "  ¿Actualizar versión? [s/N]: " yn; [[ ! "$yn" =~ ^[sS]$ ]] && { _info "Versión sin cambios."; return 0; }
    printf "\n"
    _item 1 "🔹" "Patch" "1.0.0 → 1.0.1"
    _item 2 "🔸" "Minor" "1.0.5 → 1.1.0"
    _item 3 "🔶" "Major" "1.2.3 → 2.0.0"
    _item 0 "✕"  "Cancelar" ""
    printf "\n"; read -rp "  Tipo: " vc
    case $vc in 1) update_version "patch";; 2) update_version "minor";; 3) update_version "major";; 0) _info "Cancelado.";; esac
}
update_version() {
    local vt="${1:-patch}" vs="$PROJECT_DIR/update_version.py"
    [[ -f "$vs" ]] || { _warn "No se encontró update_version.py"; return; }
    _step "Actualizando versión ($vt)"
    cd "$PROJECT_DIR"
    [[ -f "$PYTHON_BIN" ]] && "$PYTHON_BIN" "$vs" "$vt" || python3 "$vs" "$vt"
}
update_dependencies() {
    _header; _center "ACTUALIZAR DEPENDENCIAS" "${YB}"; printf "\n"
    install_dependencies && {
        _ok "Dependencias actualizadas."
        read -rp "  ¿Reiniciar bot? [S/n]: " yn; [[ ! "$yn" =~ ^[nN]$ ]] && manage_service "restart"
    }; _pause
}
remove_dependency() {
    _header; _center "ELIMINAR DEPENDENCIA" "${YB}"; printf "\n"
    [[ -f "$REQUIREMENTS_PATH" ]] || { _err "requirements.txt no encontrado"; _pause; return 1; }
    mapfile -t lines < <(grep -v '^\s*$' "$REQUIREMENTS_PATH" | grep -v '^\s*#')
    [[ ${#lines[@]} -eq 0 ]] && { _warn "Sin dependencias."; _pause; return 0; }
    local i=1; for l in "${lines[@]}"; do printf "  ${GB}%3d)${NC}  %s\n" "$i" "$l"; ((i++)); done
    printf "  ${RB}%3d)${NC}  Cancelar\n" "0"; printf "\n"
    read -rp "  Número: " sel
    if [[ "$sel" =~ ^[1-9][0-9]*$ ]] && [[ "$sel" -le "${#lines[@]}" ]]; then
        local pkg; pkg=$(echo "${lines[$((sel-1))]}" | sed -E 's/([a-zA-Z0-9_\-]+).*/\1/')
        _step "Eliminando $pkg"; "$PIP_BIN" uninstall -y "$pkg"
        grep -vF "${lines[$((sel-1))]}" "$REQUIREMENTS_PATH" > "${REQUIREMENTS_PATH}.tmp"
        mv "${REQUIREMENTS_PATH}.tmp" "$REQUIREMENTS_PATH"
        _ok "Dependencia eliminada."
        read -rp "  ¿Reiniciar? [s/N]: " yn; [[ "$yn" =~ ^[sS]$ ]] && manage_service "restart"
    else _info "Cancelado."; fi; _pause
}
uninstall_service() {
    _header; _center "DESINSTALAR SERVICIO" "${RB}"; printf "\n"
    _warn "Eliminará el servicio. Los archivos del bot NO se borran."
    read -rp "  ¿Confirmas? [s/N]: " yn; [[ ! "$yn" =~ ^[sS]$ ]] && { _info "Cancelado."; _pause; return 0; }
    systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null && $SUDO systemctl stop "$SERVICE_NAME"
    $SUDO systemctl disable "$SERVICE_NAME" 2>/dev/null; [[ -f "$SERVICE_FILE" ]] && $SUDO rm "$SERVICE_FILE"
    $SUDO systemctl daemon-reload; $SUDO systemctl reset-failed 2>/dev/null
    _ok "Servicio $SERVICE_NAME desinstalado."; _pause
}
change_directory() { PROJECT_DIR=""; FOLDER_NAME=""; SERVICE_NAME=""; select_target_directory; }

# ── GIT ────────────────────────────────────────────────────────────────────────
git_clone_repository() {
    _header; _center "CLONAR REPOSITORIO" "${YB}"; printf "\n"
    local dflt="https://github.com/ersus93/bbalert.git"
    read -rp "  URL [$dflt]: " url; url=${url:-$dflt}
    read -rp "  Destino [~/bbalert]: " dest; dest="${dest:-$HOME/bbalert}"; dest="${dest/#\~/$HOME}"
    [[ -d "$dest" ]] && { read -rp "  Ya existe. ¿Eliminar? [s/N]: " yn; [[ "$yn" =~ ^[sS]$ ]] && rm -rf "$dest" || return 1; }
    _spin_start "Clonando"; git clone "$url" "$dest"; _spin_stop
    [[ $? -eq 0 ]] && _ok "Repositorio en $dest" || _err "Error clonando."; _pause
}
force_pull_repository() {
    local branch="$1" remote="${2:-origin}"
    read -rp "  Escribe 'SI' para descartar cambios: " cn; [[ "$cn" != "SI" ]] && return 1
    git stash push -m "Auto-backup $(date)" --include-untracked 2>/dev/null || true
    git reset --hard "${remote}/${branch}" || { git clean -fd; git fetch "${remote}" "${branch}" --force; git reset --hard "${remote}/${branch}"; }
    _ok "Forzado a versión remota."
}
git_pull_repository() {
    local force="${1:-false}"
    _header; _center "ACTUALIZAR CÓDIGO" "${YB}"; printf "\n"
    cd "$PROJECT_DIR" || return 1; [[ -d ".git" ]] || { _err "No es Git."; _pause; return 1; }
    local branch; branch=$(git branch --show-current); _info "Rama: ${CB}${branch}${NC}"
    _spin_start "git fetch"; git fetch origin; _spin_stop
    git rev-parse --abbrev-ref '@{u}' &>/dev/null || git branch --set-upstream-to="origin/${branch}" "$branch"
    local lh rh; lh=$(git rev-parse HEAD); rh=$(git rev-parse '@{u}' 2>/dev/null || echo "")
    [[ -z "$rh" ]] && { _err "No se pudo verificar remote."; _pause; return 1; }
    [[ "$lh" = "$rh" ]] && { _ok "Código actualizado."; _pause; return 0; }
    _info "Nuevos commits:"; git log HEAD..@{u} --oneline | while IFS= read -r l; do printf "  ${DIM}· %s${NC}\n" "$l"; done
    printf "\n"; [[ "$force" != "true" ]] && { read -rp "  ¿Actualizar? [S/n]: " yn; [[ "$yn" =~ ^[nN]$ ]] && return 0; }
    _spin_start "git pull"; git pull origin "$branch"; local rc=$?; _spin_stop
    if [[ $rc -eq 0 ]]; then _ok "Actualizado."
    else
        _warn "Pull falló."; printf "\n"
        _item 1 "⚡" "Forzar (descarta cambios)"; _item 2 "🔍" "Ver diferencias"; _item 3 "📦" "Stash y pull"; _item 4 "✕" "Cancelar"
        read -rp "  Opción: " ro
        case $ro in
            1) force_pull_repository "$branch" ;; 2) git diff --stat; _pause; return 1 ;;
            3) git stash push -m "Auto-stash $(date)" && git pull origin "$branch" && _ok "Pull exitoso." ;;
            *) _info "Cancelado."; return 1 ;;
        esac
    fi
    read -rp "  ¿Actualizar deps? [S/n]: " yn; [[ ! "$yn" =~ ^[nN]$ ]] && install_dependencies
    systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null && {
        read -rp "  ¿Reiniciar? [S/n]: " yn; [[ ! "$yn" =~ ^[nN]$ ]] && manage_service "restart"
    }; _pause
}
git_switch_branch() {
    _header; _center "CAMBIAR DE RAMA" "${YB}"; printf "\n"
    cd "$PROJECT_DIR" || return 1; [[ -d ".git" ]] || { _err "No es Git."; _pause; return 1; }
    local cur; cur=$(git branch --show-current); _info "Rama actual: ${CB}${cur}${NC}"
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        _warn "Cambios sin committear:"; git status --short
        read -rp "  ¿Descartarlos? [s/N]: " yn; [[ ! "$yn" =~ ^[sS]$ ]] && return 0; git checkout -- .
    fi
    printf "\n"; local branches=("main" "testing" "dev"); local i=1
    for b in "${branches[@]}"; do
        [[ "$b" = "$cur" ]] && printf "  ${GB}  *${NC}  ${WB}%s${NC} ${DIM}(actual)${NC}\n" "$b" || printf "  ${CB}%3d)${NC}  %s\n" "$i" "$b"; ((i++))
    done
    printf "  ${YB}  0)${NC}  Cancelar\n"; printf "\n"; read -rp "  Rama: " sel; [[ "$sel" = "0" ]] && return 0
    local tgt="${branches[$((sel-1))]}"; [[ -z "$tgt" ]] && { _err "Inválido."; return 1; }
    _spin_start "Cambiando"; git checkout "$tgt" && git pull origin "$tgt"; _spin_stop
    _ok "Ahora en: ${CB}${tgt}${NC}"
    read -rp "  ¿Actualizar deps? [S/n]: " yn; [[ ! "$yn" =~ ^[nN]$ ]] && install_dependencies; _pause
}
git_show_status() {
    _header; _center "ESTADO DEL REPOSITORIO" "${YB}"; printf "\n"
    cd "$PROJECT_DIR" || return 1; [[ -d ".git" ]] || { _err "No es Git."; _pause; return 1; }
    printf "  ${DIM}Rama:${NC}   ${CB}%s${NC}\n" "$(git branch --show-current)"
    printf "  ${DIM}Remote:${NC} ${CB}%s${NC}\n" "$(git remote get-url origin 2>/dev/null || echo 'N/A')"
    printf "  ${DIM}Último:${NC} ${WB}%s${NC}\n" "$(git log -1 --format='%h — %s (%cr)')"
    printf "\n"; _info "Modificados:"; git status --short | while IFS= read -r l; do printf "  %s\n" "$l"; done
    printf "\n"; _info "Commits locales no enviados:"; git log @{u}..HEAD --oneline 2>/dev/null | while IFS= read -r l; do printf "  · %s\n" "$l"; done
    printf "\n"; _info "Remotos no descargados:"; git log HEAD..@{u} --oneline 2>/dev/null | while IFS= read -r l; do printf "  · %s\n" "$l"; done
    _pause
}
git_show_history() {
    _header; _center "HISTORIAL DE COMMITS" "${YB}"; printf "\n"
    cd "$PROJECT_DIR" || return 1; [[ -d ".git" ]] || { _err "No es Git."; _pause; return 1; }
    git log --oneline -15 --decorate --graph | while IFS= read -r l; do printf "  %s\n" "$l"; done
    printf "\n"; read -rp "  Ver commit (hash o Enter para continuar): " ch
    [[ -n "$ch" ]] && { git show "$ch"; _pause; }; _pause
}
manage_environments() {
    _header; _center "GESTIÓN DE ENTORNOS" "${YB}"; printf "\n"
    _item 1 "🧪" "Staging"    "rama: testing"; _item 2 "🚀" "Producción" "rama: main"; _item 0 "✕"  "Volver"     ""
    printf "\n"; read -rp "  Entorno: " ec
    local en="" ed="" eb=""
    case $ec in 1) en="staging" ed="$HOME/bbalert-staging" eb="testing";; 2) en="producción" ed="$HOME/bbalert-prod" eb="main";; *) return 0;; esac
    if [[ ! -d "$ed" ]]; then
        _warn "No existe."; read -rp "  ¿Crear? [S/n]: " yn
        [[ ! "$yn" =~ ^[nN]$ ]] && { detect_python; git clone https://github.com/ersus93/bbalert.git "$ed"; cd "$ed"; git checkout "$eb"; $TARGET_PYTHON -m venv venv; source venv/bin/activate; pip install -r requirements.txt --quiet; _ok "Entorno creado."; }
        _pause; return 0
    fi
    local es; es=$(basename "$ed"); _info "Dir: $ed | Rama: $eb"
    systemctl is-active --quiet "$es" 2>/dev/null && _ok "Activo" || _warn "Detenido"; printf "\n"
    _item 1 "⬇ " "git pull"; _item 2 "▶ " "Iniciar"; _item 3 "⏹ " "Detener"; _item 4 "🔄" "Reiniciar"; _item 5 "📋" "Logs"
    read -rp "  Acción: " ac
    case $ac in
        1) cd "$ed" && git checkout "$eb" && git pull origin "$eb" && _ok "Actualizado." ;;
        2) sudo systemctl start "$es";; 3) sudo systemctl stop "$es";;
        4) sudo systemctl restart "$es";; 5) sudo journalctl -u "$es" -f;;
    esac; _pause
}

# ── PROGRAMA PRINCIPAL ─────────────────────────────────────────────────────────
check_root
check_system_dependencies

case "${1:-}" in
    --install)    select_target_directory; full_install; exit 0;;
    --force-pull) select_target_directory; git_pull_repository true; exit 0;;
    --backup)     select_target_directory; backup_bot; exit 0;;
    --stats)      select_target_directory; show_bot_stats; exit 0;;
esac

select_target_directory

while true; do
    show_menu
    read -rp "" choice
    case $choice in
        1)  full_install;;
        2)  _header; create_venv; _pause;;
        3)  update_dependencies;;
        4)  _header; configure_env; _pause;;
        5)  _header; create_systemd_service; _pause;;
        6)  start_bot;;
        7)  stop_bot;;
        8)  restart_bot;;
        9)  status_bot;;
        10) show_bot_stats;;
        11) git_clone_repository;;
        12) git_pull_repository "${FORCE_PULL:-false}";;
        13) git_switch_branch;;
        14) git_show_status;;
        15) git_show_history;;
        16) manage_logs;;
        17) show_all_bots_dashboard;;
        18) backup_bot;;
        19) restore_backup;;
        20) manage_environments;;
        21) remove_dependency;;
        22) uninstall_service;;
        23) change_directory;;
        0)  _header; _center "¡Hasta luego!" "${GB}"; printf "\n"; exit 0;;
        *)  _err "Opción inválida."; sleep 1;;
    esac
done
#!/bin/bash
# â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
# â•‘  BBAlert Manager â€” Common Utilities (Refactored)           â•‘
# â•‘  Funciones puras sin side effects                          â•‘
# â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

set -euo pipefail

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CONFIGURACIÃ“N DEFAULTS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

DEFAULT_PYTHON="${DEFAULT_PYTHON:-python3.13}"
FALLBACK_PYTHON="${FALLBACK_PYTHON:-python3.12}"
MAX_BACKUPS="${MAX_BACKUPS:-5}"
LOG_ROTATION_DAYS="${LOG_ROTATION_DAYS:-7}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FUNCIONES DE UTILIDAD PURAS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# get_terminal_width - Retorna ancho de terminal
get_terminal_width() {
    tput cols 2>/dev/null || echo 80
}

# get_terminal_height - Retorna alto de terminal
get_terminal_height() {
    tput lines 2>/dev/null || echo 24
}

# is_valid_bot_directory - Valida que directorio contiene bot
# Args: $1 - directorio a validar
# Returns: 0 si vÃ¡lido, 1 si no
is_valid_bot_directory() {
    local dir="$1"
    local bot_file="${2:-bbalert.py}"
    local req_file="${3:-requirements.txt}"

    [[ -d "$dir" ]] || return 1
    [[ -f "$dir/$bot_file" ]] || return 1
    [[ -f "$dir/$req_file" ]] || return 1
    return 0
}

# get_system_cpu_usage - Calcula uso de CPU del sistema
# Returns: porcentaje de CPU (0-100)
get_system_cpu_usage() {
    local u1 n1 s1 i1 w1 u2 n2 s2 i2 w2
    read -r _ u1 n1 s1 i1 w1 _ < /proc/stat 2>/dev/null || { echo 0; return; }
    sleep 0.2
    read -r _ u2 n2 s2 i2 w2 _ < /proc/stat 2>/dev/null || { echo 0; return; }
    local dt=$(( (u2+n2+s2+i2+w2) - (u1+n1+s1+i1+w1) ))
    local di=$(( (i2+w2) - (i1+w1) ))
    [[ $dt -le 0 ]] && echo 0 && return
    echo $(( (dt - di) * 100 / dt ))
}

# get_system_ram_usage - Retorna uso de RAM en MB y total
# Returns: "used total" en MB
get_system_ram_usage() {
    local used total
    read -r used total < <(free -m 2>/dev/null | awk 'NR==2{print $3,$2}')
    echo "$used $total"
}

# get_process_cpu_ram - Obtiene CPU y RAM de un proceso
# Args: $1 - PID
# Returns: "cpu ram threads" o "0 0 0" si no existe
get_process_cpu_ram() {
    local pid="$1"
    [[ "$pid" != "0" ]] && kill -0 "$pid" 2>/dev/null || { echo "0 0 0"; return; }
    local cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ' || echo "0")
    local ram=$(ps -p "$pid" -o rss= 2>/dev/null | awk '{printf "%.0f",$1/1024}' || echo "0")
    local threads=$(ps -p "$pid" -o nlwp= 2>/dev/null | tr -d ' ' || echo "0")
    echo "$cpu $ram $threads"
}

# get_disk_usage - Obtiene uso de disco de directorio
# Args: $1 - directorio, $2 - excluir (opcional)
# Returns: tamaÃ±o en formato legible (ej: "15M")
get_disk_usage() {
    local dir="$1"
    local exclude="${2:-}"
    [[ -d "$dir" ]] || { echo "0"; return; }
    if [[ -n "$exclude" ]]; then
        du -sh "$dir" --exclude="$exclude" 2>/dev/null | cut -f1 || echo "0"
    else
        du -sh "$dir" 2>/dev/null | cut -f1 || echo "0"
    fi
}

# get_git_branch - Obtiene rama actual de git
# Args: $1 - directorio del proyecto
# Returns: nombre de rama o "N/A"
get_git_branch() {
    local dir="${1:-.}"
    [[ -d "$dir/.git" ]] || { echo "N/A"; return; }
    (cd "$dir" && git branch --show-current 2>/dev/null || echo "N/A")
}

# get_git_remote_url - Obtiene URL del remote git
# Args: $1 - directorio del proyecto
# Returns: URL o "N/A"
get_git_remote_url() {
    local dir="${1:-.}"
    [[ -d "$dir/.git" ]] || { echo "N/A"; return; }
    (cd "$dir" && git remote get-url origin 2>/dev/null || echo "N/A")
}

# get_git_last_commit - Obtiene Ãºltimo commit
# Args: $1 - directorio del proyecto
# Returns: "hash â€” mensaje (tiempo)" o "N/A"
get_git_last_commit() {
    local dir="${1:-.}"
    [[ -d "$dir/.git" ]] || { echo "N/A"; return; }
    (cd "$dir" && git log -1 --format='%h â€” %s (%cr)' 2>/dev/null || echo "N/A")
}

# get_service_status - Obtiene estado de un servicio systemd
# Args: $1 - nombre del servicio
# Returns: "active|inactive|failed"
get_service_status() {
    local service="$1"
    systemctl is-active "$service" 2>/dev/null || echo "inactive"
}

# get_service_pid - Obtiene PID de un servicio
# Args: $1 - nombre del servicio
# Returns: PID o "0"
get_service_pid() {
    local service="$1"
    systemctl show "$service" --property=MainPID --value 2>/dev/null || echo "0"
}

# get_service_restarts - Obtiene nÃºmero de reinicios
# Args: $1 - nombre del servicio
# Returns: nÃºmero de reinicios
get_service_restarts() {
    local service="$1"
    systemctl show "$service" --property=NRestarts --value 2>/dev/null || echo "0"
}

# get_service_active_since - Obtiene timestamp de Ãºltima activaciÃ³n
# Args: $1 - nombre del servicio
# Returns: timestamp o "N/A"
get_service_active_since() {
    local service="$1"
    systemctl show "$service" --property=ActiveEnterTimestamp --value 2>/dev/null || echo "N/A"
}

# list_available_branches - Lista ramas disponibles (remotas y locales)
# Args: $1 - directorio del proyecto
# Returns: array de nombres de ramas
list_available_branches() {
    local dir="${1:-.}"
    local -a branches=()

    # Intentar ramas remotas primero
    if [[ -d "$dir/.git" ]]; then
        while IFS= read -r branch; do
            branch=$(echo "$branch" | sed 's/origin\///' | tr -d ' ')
            [[ -n "$branch" && "$branch" != "HEAD" ]] && branches+=("$branch")
        done < <(cd "$dir" && git branch -r 2>/dev/null | grep -v "HEAD" | sort -u)
    fi

    # Si no hay remotas, usar locales
    if [[ ${#branches[@]} -eq 0 ]] && [[ -d "$dir/.git" ]]; then
        while IFS= read -r branch; do
            branch=$(echo "$branch" | sed 's/^[ *]*//' | tr -d ' ')
            [[ -n "$branch" ]] && branches+=("$branch")
        done < <(cd "$dir" && git branch 2>/dev/null)
    fi

    printf '%s\n' "${branches[@]}"
}

# get_current_branch - Obtiene rama actual
# Args: $1 - directorio del proyecto
# Returns: nombre de rama
get_current_branch() {
    local dir="${1:-.}"
    [[ -d "$dir/.git" ]] || { echo ""; return; }
    (cd "$dir" && git branch --show-current 2>/dev/null || echo "")
}

# is_git_repo - Verifica si directorio es repo git
# Args: $1 - directorio
# Returns: 0 si es git, 1 si no
is_git_repo() {
    [[ -d "$1/.git" ]]
}

# get_journal_logs - Obtiene logs de systemd/journalctl
# Args: $1 - nombre servicio, $2 - nÃºmero de lÃ­neas (opcional), $3 - solo errores (opcional)
# Returns: logs como string
get_journal_logs() {
    local service="$1"
    local lines="${2:-50}"
    local errors_only="${3:-false}"

    [[ "$errors_only" = "true" ]] && {
        $SUDO journalctl -u "$service" -p err --no-pager -n "$lines" 2>/dev/null || echo ""
    } || {
        $SUDO journalctl -u "$service" --no-pager -n "$lines" 2>/dev/null || echo ""
    }
}

# rotate_journal_logs - Rota logs del sistema
# Args: $1 - dÃ­as a mantener
# Returns: 0 si Ã©xito, 1 si falla
rotate_journal_logs() {
    local days="${1:-7}"
    $SUDO journalctl --rotate 2>/dev/null
    $SUDO journalctl --vacuum-time="${days}d" 2>/dev/null
    return $?
}

# format_bytes - Formatea bytes a formato legible
# Args: $1 - bytes
# Returns: string formateado (ej: "15.5 MB")
format_bytes() {
    local bytes="$1"
    local kb=$((bytes / 1024))
    local mb=$((kb / 1024))
    local gb=$((mb / 1024))

    if [[ $gb -gt 0 ]]; then
        awk "BEGIN {printf \"%.1f GB\", ${bytes}/1024/1024/1024}"
    elif [[ $mb -gt 0 ]]; then
        awk "BEGIN {printf \"%.1f MB\", ${bytes}/1024/1024}"
    elif [[ $kb -gt 0 ]]; then
        awk "BEGIN {printf \"%.1f KB\", ${bytes}/1024}"
    else
        echo "${bytes} B"
    fi
}

# sanitize_filename - Sanitiza nombre de archivo
# Args: $1 - nombre original
# Returns: nombre seguro
sanitize_filename() {
    echo "$1" | sed 's/[^a-zA-Z0-9._-]/_/g'
}

# confirm_action - Pide confirmaciÃ³n al usuario
# Args: $1 - mensaje, $2 - valor por defecto [y/N]
# Returns: 0 si confirmado, 1 si cancelado
confirm_action() {
    local msg="$1"
    local default="${2:-N}"
    local yn

    read -rp "  $msg [${default^^}/n]: " yn
    yn="${yn:-$default}"

    [[ "$yn" =~ ^[yY]$ ]]
}

# check_dependency - Verifica si comando existe
# Args: $1 - nombre de comando
# Returns: 0 si existe, 1 si no
check_dependency() {
    command -v "$1" &>/dev/null
}

# require_dependencies - Verifica mÃºltiples dependencias
# Args: lista de comandos
# Returns: 0 si todos existen, 1 si falta alguno
require_dependencies() {
    local missing=()
    for cmd in "$@"; do
        if ! check_dependency "$cmd"; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Faltan dependencias: ${missing[*]}"
        return 1
    fi
    return 0
}

# escape_markdown - Escapa caracteres especiales de Markdown
# Args: $1 - texto
# Returns: texto escapado
escape_markdown() {
    echo "$1" | sed 's/[_*`[]/\\&/g'
}

# get_yes_no - Obtiene respuesta sÃ­/no
# Args: $1 - prompt, $2 - default [y/N]
# Returns: 0 para sÃ­, 1 para no
get_yes_no() {
    local prompt="$1"
    local default="${2:-N}"
    local resp

    read -rp "  $prompt [${default^^}/n]: " resp
    resp="${resp:-$default}"

    [[ "$resp" =~ ^[yY]$ ]]
}

# log_info - Log simple (solo si LOG_FILE estÃ¡ definido)
# Args: mensaje
log_info() {
    [[ -n "${LOG_FILE:-}" ]] && echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"
}

# log_error - Log de error
# Args: mensaje
log_error() {
    [[ -n "${LOG_FILE:-}" ]] && echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE" >&2
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FIN DEL MÃ“DULO
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

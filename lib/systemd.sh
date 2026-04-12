#!/bin/bash
# â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
# â•‘  BBAlert Manager â€” Systemd Service Module                  â•‘
# â•‘  GestiÃ³n de servicios systemd                              â•‘
# â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

set -euo pipefail

# Nota: common.sh debe ser cargado por el script principal antes de este mÃ³dulo

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FUNCIONES DE GESTIÃ“N DE SERVICIOS SYSTEMD
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# systemd_generate_service_file - Genera contenido del archivo .service
# Args:
#   $1 - nombre del servicio
#   $2 - directorio del proyecto
#   $3 - ruta al python (opcional, default: venv/bin/python)
#   $4 - ruta al script principal (opcional, default: bbalert.py)
# Returns: contenido del service file en stdout
systemd_generate_service_file() {
    local service_name="$1"
    local project_dir="$2"
    local python_bin="${3:-$project_dir/venv/bin/python}"
    local script_path="${4:-$project_dir/bbalert.py}"

    cat <<EOF
[Unit]
Description=Bot Telegram - $service_name
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$project_dir
Environment="PATH=$python_bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=$python_bin $script_path
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$service_name

[Install]
WantedBy=multi-user.target
EOF
}

# systemd_create_service - Crea e instala servicio systemd
# Args:
#   $1 - nombre del servicio
#   $2 - directorio del proyecto
#   $3 - ruta al python (opcional)
#   $4 - ruta al script (opcional)
# Returns: 0 si Ã©xito, 1 si falla
systemd_create_service() {
    local service_name="$1"
    local project_dir="$2"
    local python_bin="${3:-$project_dir/venv/bin/python}"
    local script_path="${4:-$project_dir/bbalert.py}"
    local service_file="/etc/systemd/system/$service_name.service"

    # Generar contenido
    local content
    content=$(systemd_generate_service_file "$service_name" "$project_dir" "$python_bin" "$script_path")

    # Copiar a /etc/systemd/system
    if ! echo "$content" | sudo tee "$service_file" > /dev/null; then
        log_error "FallÃ³ la copia del service file a $service_file"
        return 1
    fi

    # Recargar systemd
    if ! sudo systemctl daemon-reload; then
        log_error "FallÃ³ systemctl daemon-reload"
        return 1
    fi

    # Habilitar
    if ! sudo systemctl enable "$service_name" &>/dev/null; then
        log_warn "No se pudo habilitar el servicio $service_name"
    fi

    log_info "Servicio $service_name creado y habilitado"
    return 0
}

# systemd_manage - Ejecuta acciÃ³n sobre servicio
# Args:
#   $1 - acciÃ³n (start|stop|restart|status|reload)
#   $2 - nombre del servicio
# Returns: 0 si Ã©xito, 1 si falla
systemd_manage() {
    local action="$1"
    local service="$2"

    case "$action" in
        start|stop|restart|reload)
            if sudo systemctl "$action" "$service" 2>/dev/null; then
                log_info "Servicio $service $action exitoso"
                return 0
            else
                log_error "Servicio $service $action fallÃ³"
                return 1
            fi
            ;;
        status)
            sudo systemctl status "$service" --no-pager -l
            return $?
            ;;
        *)
            log_error "AcciÃ³n invÃ¡lida: $action"
            return 1
            ;;
    esac
}

# systemd_is_active - Verifica si servicio estÃ¡ activo
# Args: $1 - nombre del servicio
# Returns: 0 si activo, 1 si no
systemd_is_active() {
    local service="$1"
    systemctl is-active --quiet "$service" 2>/dev/null
}

# systemd_get_info - Obtiene informaciÃ³n completa del servicio
# Args: $1 - nombre del servicio
# Returns: echo de datos en formato "clave=valor"
systemd_get_info() {
    local service="$1"
    local info

    info=$(systemctl show "$service" 2>/dev/null || echo "")

    if [[ -z "$info" ]]; then
        echo "status=unknown"
        return 1
    fi

    # Extraer campos relevantes
    local status=$(echo "$info" | grep '^ActiveState=' | cut -d= -f2)
    local pid=$(echo "$info" | grep '^MainPID=' | cut -d= -f2)
    local restarts=$(echo "$info" | grep '^NRestarts=' | cut -d= -f2)
    local since=$(echo "$info" | grep '^ActiveEnterTimestamp=' | cut -d= -f2)

    echo "status=$status"
    echo "pid=$pid"
    echo "restarts=$restarts"
    echo "since=$since"
}

# systemd_uninstall - Desinstala servicio systemd
# Args: $1 - nombre del servicio
# Returns: 0 si Ã©xito
systemd_uninstall() {
    local service="$1"
    local service_file="/etc/systemd/system/$service.service"

    # Detener si estÃ¡ corriendo
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        sudo systemctl stop "$service" 2>/dev/null || true
    fi

    # Deshabilitar
    sudo systemctl disable "$service" 2>/dev/null || true

    # Eliminar archivo
    if [[ -f "$service_file" ]]; then
        sudo rm -f "$service_file" || {
            log_error "No se pudo eliminar $service_file"
            return 1
        }
    fi

    # Recargar
    sudo systemctl daemon-reload 2>/dev/null || true
    sudo systemctl reset-failed 2>/dev/null || true

    log_info "Servicio $service desinstalado"
    return 0
}

# systemd_list_bots - Lista todos los servicios de bots
# Returns: lista de nombres de servicios (uno por lÃ­nea)
systemd_list_bots() {
    systemctl list-units --type=service --state=loaded --no-pager --no-legend 2>/dev/null \
        | grep -E "bbalert|telebot|bot" \
        | awk '{print $1}' \
        | sed 's/\.service$//' \
        || echo ""
}

# systemd_get_recent_errors - Obtiene errores recientes del servicio
# Args:
#   $1 - nombre del servicio
#   $2 - horas hacia atrÃ¡s (default: 24)
# Returns: nÃºmero de errores
systemd_get_recent_errors() {
    local service="$1"
    local hours="${2:-24}"

    $SUDO journalctl -u "$service" --since "${hours}h ago" -p err --no-pager -q 2>/dev/null \
        | wc -l \
        || echo "0"
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FIN DEL MÃ“DULO
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

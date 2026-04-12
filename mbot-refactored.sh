#!/bin/bash

set -euo pipefail


resolve_script_dir() {
    local source="${BASH_SOURCE[0]}"
    while [[ -L "$source" ]]; do
        local dir
        dir="$(cd -P "$(dirname "$source")" && pwd)"
        source="$(readlink "$source")"
        [[ "$source" != /* ]] && source="$dir/$source"
    done
    cd -P "$(dirname "$source")" && pwd
}

SCRIPT_DIR="$(resolve_script_dir)"

check_modules() {
    local missing=()
    for mod in common.sh ui.sh systemd.sh git.sh backup.sh; do
        [[ -f "$SCRIPT_DIR/lib/$mod" ]] || missing+=("$mod")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "ERROR: Módulos no encontrados en $SCRIPT_DIR/lib/:"
        printf "  - %s\n" "${missing[@]}"
        echo ""
        echo "Asegúrate de que el directorio 'lib/' esté junto al script."
        exit 1
    fi
}

check_modules

# Cargar módulos directamente (los archivos deben estar en formato LF)
for mod in common.sh ui.sh systemd.sh git.sh backup.sh; do
    source "$SCRIPT_DIR/lib/$mod"
done

PROJECT_DIR=""
FOLDER_NAME=""
SERVICE_NAME=""
GIT_BRANCH=""
BOT_STATUS=""
SUDO=""


select_bot_directory() {
    ui_header "Selecci??n de Bot" "inactive" "N/A"

    if is_valid_bot_directory "$(pwd)"; then
        local detected
        detected=$(pwd)
        ui_message "Bot detectado en el directorio actual:\n$detected" "info"
        if ui_yesno "??Usar este directorio?" "yes"; then
            PROJECT_DIR="$detected"
        fi
    fi

    if [[ -z "${PROJECT_DIR:-}" ]]; then
        ui_message "Buscando bots en el sistema..." "info"
        local found_bots=()

        for base in "$HOME" "$HOME/bots" "$HOME/telegram" "/opt" "$(pwd)"; do
            [[ -d "$base" ]] || continue
            while IFS= read -r -d '' botdir; do
                if is_valid_bot_directory "$botdir"; then
                    found_bots+=("$botdir")
                fi
            done < <(find "$base" -maxdepth 2 -name "bbalert.py" -type f -print0 2>/dev/null | xargs -0 dirname 2>/dev/null)
        done

        if [[ ${#found_bots[@]} -gt 0 ]]; then
            mapfile -t found_bots < <(printf '%s\n' "${found_bots[@]}" | sort -u 2>/dev/null || true)
        fi

        if [[ ${#found_bots[@]} -gt 0 ]]; then
            ui_message "Se encontraron ${#found_bots[@]} bot(s):" "info"
            local i=1
            for bot in "${found_bots[@]}"; do
                echo "  $i) $(basename "$bot") ??? $bot"
                ((i++))
            done

            read -rp "  Selecciona (1-${#found_bots[@]}) o 0 para cancelar: " sel
            if [[ "$sel" =~ ^[1-9][0-9]*$ ]] && [[ "$sel" -le "${#found_bots[@]}" ]]; then
                PROJECT_DIR="${found_bots[$((sel-1))]}"
            fi
        fi
    fi

    while [[ -z "${PROJECT_DIR:-}" ]]; do
        read -rp "  Ingresa ruta completa del bot: " input_dir
        input_dir="${input_dir/#\~/$HOME}"
        input_dir=$(command -v realpath >/dev/null && realpath "$input_dir" 2>/dev/null || echo "$input_dir")

        if is_valid_bot_directory "$input_dir"; then
            PROJECT_DIR="$input_dir"
            ui_message "Directorio v??lido: $PROJECT_DIR" "ok"
        else
            ui_message "Bot no encontrado en esa ruta." "err"
            if ! ui_yesno "??Reintentar?" "yes"; then
                exit 1
            fi
        fi
    done

    PROJECT_DIR=$(command -v realpath >/dev/null && realpath "$PROJECT_DIR" 2>/dev/null || echo "$PROJECT_DIR")
    FOLDER_NAME=$(basename "$PROJECT_DIR")
    SERVICE_NAME="$FOLDER_NAME"
    GIT_BRANCH=$(get_git_branch "$PROJECT_DIR")
    BOT_STATUS=$(systemd_is_active "$SERVICE_NAME" && echo "active" || echo "inactive")

    ui_message "Bot cargado:\n  Nombre: $FOLDER_NAME\n  Ruta: $PROJECT_DIR\n  Servicio: $SERVICE_NAME\n  Rama: $GIT_BRANCH" "ok"
}

refresh_bot_status() {
    BOT_STATUS=$(systemd_is_active "$SERVICE_NAME" && echo "active" || echo "inactive")
    GIT_BRANCH=$(get_git_branch "$PROJECT_DIR")
}

action_start_bot() {
    if ! $HAS_SYSTEMD; then
        ui_message "Systemd no disponible. No se puede gestionar el servicio en este sistema." "warn"
        ui_message "Puedes iniciar el bot manualmente ejecutando:\n$VENV_PYTHON $PROJECT_DIR/bbalert.py" "info"
        read -rp "  Presiona Enter para continuar..."
        return 0
    fi
    refresh_bot_status

    if [[ "$BOT_STATUS" == "active" ]]; then
        ui_message "El bot ya est?? corriendo." "warn"
        if ui_yesno "??Reiniciar?" "no"; then
            systemd_manage restart "$SERVICE_NAME"
            ui_message "Bot reiniciado." "ok"
        fi
        return 0
    fi

    local errors=0

    if [[ ! -f "$VENV_PYTHON" ]]; then
        ui_message "Error: No existe entorno virtual en $PROJECT_DIR/venv" "err"
        ((errors++))
    fi

    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        ui_message "Error: No se encontr?? archivo .env" "err"
        ((errors++))
    elif ! grep -q '^TOKEN_TELEGRAM=[^[:space:]]' "$PROJECT_DIR/.env"; then
        ui_message "Error: TOKEN_TELEGRAM no configurado o vac??o en .env" "err"
        ((errors++))
    fi

    if [[ ! -f "$PROJECT_DIR/bbalert.py" ]]; then
        ui_message "Error: Script principal bbalert.py no encontrado" "err"
        ((errors++))
    fi

    if [[ $errors -gt 0 ]]; then
        ui_message "Corrige los errores antes de iniciar." "err"
        return 1
    fi

    if systemd_manage start "$SERVICE_NAME"; then
        ui_message "Bot iniciado exitosamente" "ok"
        sleep 2
        show_logs_realtime
    else
        ui_message "No se pudo iniciar el bot" "err"
        return 1
    fi
}

action_stop_bot() {
    if ! $HAS_SYSTEMD; then
        ui_message "Systemd no disponible. No se puede gestionar el servicio en este sistema." "warn"
        read -rp "  Presiona Enter para continuar..."
        return 0
    fi
    refresh_bot_status

    if [[ "$BOT_STATUS" != "active" ]]; then
        ui_message "El bot ya est?? detenido." "warn"
        return 0
    fi

    if systemd_manage stop "$SERVICE_NAME"; then
        ui_message "Bot detenido." "ok"
    else
        ui_message "No se pudo detener el bot" "err"
    fi
}

action_restart_bot() {
    if ! $HAS_SYSTEMD; then
        ui_message "Systemd no disponible. No se puede gestionar el servicio en este sistema." "warn"
        read -rp "  Presiona Enter para continuar..."
        return 0
    fi
    refresh_bot_status

    if systemd_manage restart "$SERVICE_NAME"; then
        ui_message "Bot reiniciado exitosamente" "ok"
        sleep 2
        show_logs_realtime
    else
        ui_message "No se pudo reiniciar el bot" "err"
    fi
}

action_status_bot() {
    if ! $HAS_SYSTEMD; then
        ui_message "Systemd no disponible. No se puede obtener estado del servicio." "warn"
        read -rp "  Presiona Enter para continuar..."
        return 0
    fi
    refresh_bot_status

    local info
    info=$(systemd_get_info "$SERVICE_NAME" 2>/dev/null || echo "status=unknown")

    local status pid restarts since
    status=$(echo "$info" | grep '^status=' | cut -d= -f2)
    pid=$(echo "$info" | grep '^pid=' | cut -d= -f2)
    restarts=$(echo "$info" | grep '^restarts=' | cut -d= -f2)
    since=$(echo "$info" | grep '^since=' | cut -d= -f2)

    local status_text status_color
    if [[ "$status" == "active" ]]; then
        status_text="??? ACTIVO"
        status_color="${UI_COLOR_GREEN}"
    else
        status_text="??? DETENIDO"
        status_color="${UI_COLOR_RED}"
    fi

    local cpu ram threads
    if [[ "$pid" != "0" ]] && kill -0 "$pid" 2>/dev/null; then
        read -r cpu ram threads <<< "$(get_process_cpu_ram "$pid")"
    else
        cpu="???"
        ram="???"
        threads="???"
    fi

    local disk_bot disk_venv
    disk_bot=$(get_disk_usage "$PROJECT_DIR" "venv")
    disk_venv=$(get_disk_usage "$PROJECT_DIR/venv")

    local errors_24h
    errors_24h=$(systemd_get_recent_errors "$SERVICE_NAME" 24)

    ui_clear
    ui_header "$FOLDER_NAME" "$status" "$GIT_BRANCH"

    cat <<EOF
  Estado:     ${status_color}$status_text${UI_COLOR_RESET}
  PID:        $pid
  CPU:        ${cpu}%
  RAM:        ${ram} MB
  Hilos:      $threads
  Reinicios:  $restarts
  Activo desde: $since

  Disco bot:  $disk_bot
  Disco venv: $disk_venv

  Errores 24h: $errors_24h
EOF

    if [[ "$errors_24h" -gt 0 ]]; then
        echo ""
        echo "  ??ltimos errores:"
        get_journal_logs "$SERVICE_NAME" 5 true | sed 's/^/    /'
    fi

    echo ""
    read -rp "  Presiona Enter para continuar..."
}

action_stats_bot() {
    if ! $HAS_SYSTEMD; then
        ui_message "Systemd no disponible. No se puede obtener estado del servicio." "warn"
        read -rp "  Presiona Enter para continuar..."
        return 0
    fi
    refresh_bot_status

    local info
    info=$(systemd_get_info "$SERVICE_NAME" 2>/dev/null || echo "status=unknown")
    local pid
    pid=$(echo "$info" | grep '^pid=' | cut -d= -f2)

    local cpu ram threads
    if [[ "$pid" != "0" ]] && kill -0 "$pid" 2>/dev/null; then
        read -r cpu ram threads <<< "$(get_process_cpu_ram "$pid")"
    else
        cpu="???"
        ram="???"
        threads="???"
    fi

    local disk_bot disk_venv
    disk_bot=$(get_disk_usage "$PROJECT_DIR" "venv")
    disk_venv=$(get_disk_usage "$PROJECT_DIR/venv")

    local git_info
    git_info=$(git_get_status "$PROJECT_DIR" 2>/dev/null || echo "No es repo git")

    ui_clear
    ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

    cat <<EOF
  ?????? Recursos
  ???  CPU:       ${cpu}%
  ???  RAM:       ${ram} MB
  ???  Hilos:     $threads
  ???  Disco bot: $disk_bot
  ???  Disco venv: $disk_venv
  ???
  ?????? Git
  ???  $(echo "$git_info" | head -5 | sed 's/^/  /')
  ???
  ?????? Servicio
  ???  Nombre:    $SERVICE_NAME
  ???  Estado:    $BOT_STATUS
  ???  PID:       $pid
EOF

    echo ""
    read -rp "  Presiona Enter para continuar..."
}

show_logs_realtime() {
    ui_clear
    ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

    echo ""
    echo "  Mostrando logs en tiempo real..."
    echo "  Presiona Ctrl+C para volver al men??"
    echo ""

    $SUDO journalctl -u "$SERVICE_NAME" -f --no-pager 2>/dev/null || {
        ui_message "No se pudieron obtener logs" "err"
        return 1
    }
}

action_manage_logs() {
    if ! $HAS_SYSTEMD; then
        ui_message "Systemd no disponible. Gesti??n de logs no soportada en este sistema." "warn"
        read -rp "  Presiona Enter para continuar..."
        return 0
    fi
    while true; do
        ui_clear
        ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

        local choice
        choice=$(ui_menu "GESTI??N DE LOGS" "" \
            "1" "Tiempo real (Ctrl+C para salir)" \
            "2" "??ltimas 50 l??neas" \
            "3" "??ltimas 200 l??neas" \
            "4" "Solo errores (??ltimas 50)" \
            "5" "Buscar texto" \
            "6" "Exportar a archivo" \
            "7" "Rotar logs" \
            "0" "Volver" \
        ) || break

        case "$choice" in
            1) show_logs_realtime ;;
            2)
                ui_clear
                ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"
                echo ""
                get_journal_logs "$SERVICE_NAME" 50
                read -rp "  Presiona Enter para continuar..."
                ;;
            3)
                ui_clear
                ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"
                echo ""
                get_journal_logs "$SERVICE_NAME" 200
                read -rp "  Presiona Enter para continuar..."
                ;;
            4)
                ui_clear
                ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"
                echo ""
                get_journal_logs "$SERVICE_NAME" 50 true
                read -rp "  Presiona Enter para continuar..."
                ;;
            5)
                read -rp "  Texto a buscar: " search_text
                if [[ -n "$search_text" ]]; then
                    ui_clear
                    ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"
                    echo ""
                    $SUDO journalctl -u "$SERVICE_NAME" --no-pager -n 5000 2>/dev/null \
                        | grep -i "$search_text" | tail -50 || ui_message "Sin resultados" "warn"
                    read -rp "  Presiona Enter para continuar..."
                fi
                ;;
            6)
                local logfile="$HOME/logs_${FOLDER_NAME}_$(date +%Y%m%d_%H%M%S).txt"
                ui_message "Exportando logs a:\n$logfile" "info"
                if $SUDO journalctl -u "$SERVICE_NAME" --no-pager > "$logfile" 2>/dev/null; then
                    ui_message "Logs exportados a:\n$logfile\n($(du -h "$logfile" | cut -f1))" "ok"
                else
                    ui_message "Error exportando logs" "err"
                fi
                read -rp "  Presiona Enter para continuar..."
                ;;
            7)
                if ui_yesno "??Rotar logs? (mantendr?? ??ltimos $LOG_ROTATION_DAYS d??as)" "yes"; then
                    if rotate_journal_logs "$LOG_ROTATION_DAYS"; then
                        local new_size
                        new_size=$($SUDO journalctl --disk-usage 2>/dev/null | awk '{print $1, $2}' || echo "?")
                        ui_message "Logs rotados.\nNuevo tama??o: $new_size" "ok"
                    else
                        ui_message "Error rotando logs" "err"
                    fi
                fi
                read -rp "  Presiona Enter para continuar..."
                ;;
            0|*) break ;;
        esac
    done
}

action_backup() {
    ui_clear
    ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

    ui_message "Se crear?? un backup de:\n$PROJECT_DIR" "info"

    if ! ui_yesno "??Continuar?" "yes"; then
        return 0
    fi

    local backup_file
    backup_file=$(backup_create "$PROJECT_DIR" "$FOLDER_NAME")

    if [[ -n "$backup_file" ]]; then
        ui_message "Backup creado exitosamente:\n$backup_file" "ok"
    else
        ui_message "Error creando backup" "err"
    fi

    read -rp "  Presiona Enter para continuar..."
}

action_restore_backup() {
    ui_clear
    ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

    local backups
    backups=$(backup_list "$FOLDER_NAME")

    if [[ -z "$backups" ]]; then
        ui_message "No hay backups disponibles para $FOLDER_NAME" "warn"
        read -rp "  Presiona Enter para continuar..."
        return 0
    fi

    ui_message "Backups disponibles:" "info"
    local i=1
    declare -a backup_array=()
    while IFS= read -r backup; do
        [[ -n "$backup" ]] || continue
        local info
        info=$(backup_get_info "$backup")
        local size date path
        read -r size date path <<< "$info"
        echo "  $i) $(basename "$path") ??? $size ??? $date"
        backup_array[$((i-1))]="$path"
        ((i++))
    done <<< "$backups"

    echo ""
    read -rp "  Selecciona backup (0 para cancelar): " sel

    if [[ "$sel" =~ ^[1-9][0-9]*$ ]] && [[ "$sel" -le ${#backup_array[@]} ]]; then
        local selected_backup="${backup_array[$((sel-1))]}"

        ui_message "Esto SOBRESCRIBIR?? el directorio actual.\n??Confirmar?" "warn"

        if ui_yesno "??Continuar?" "no"; then
            if [[ "$BOT_STATUS" == "active" ]]; then
                systemd_manage stop "$SERVICE_NAME" 2>/dev/null || true
            fi

            if backup_restore "$selected_backup" "$(dirname "$PROJECT_DIR")"; then
                ui_message "Backup restaurado exitosamente" "ok"

                if ui_yesno "??Reiniciar bot?" "yes"; then
                    systemd_manage start "$SERVICE_NAME" 2>/dev/null || true
                fi
            else
                ui_message "Error restaurando backup" "err"
            fi
        fi
    fi

    read -rp "  Presiona Enter para continuar..."
}

action_git_pull() {
    refresh_bot_status

    if ! is_git_repo "$PROJECT_DIR"; then
        ui_message "El directorio no es un repositorio git" "err"
        read -rp "  Presiona Enter para continuar..."
        return 1
    fi

    ui_clear
    ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

    local branch
    branch=$(get_current_branch "$PROJECT_DIR")
    ui_message "Rama actual: $branch" "info"

    ui_message "Obteniendo cambios remotos..." "info"
    if ! (cd "$PROJECT_DIR" && git fetch origin 2>/dev/null); then
        ui_message "Error haciendo git fetch" "err"
        read -rp "  Presiona Enter para continuar..."
        return 1
    fi

    local lh rh
    lh=$(cd "$PROJECT_DIR" && git rev-parse HEAD)
    rh=$(cd "$PROJECT_DIR" && git rev-parse "@{u}" 2>/dev/null || echo "")

    if [[ "$lh" == "$rh" ]]; then
        ui_message "C??digo actualizado." "ok"
        read -rp "  Presiona Enter para continuar..."
        return 0
    fi

    ui_message "Nuevos commits disponibles:" "info"
    if [[ -n "$rh" ]]; then
        (cd "$PROJECT_DIR" && git log HEAD..@{u} --oneline 2>/dev/null | sed 's/^/  ?? /')
    fi

    if ! ui_yesno "??Actualizar ahora?" "yes"; then
        return 0
    fi

    ui_message "Actualizando c??digo..." "info"
    if git_pull "$PROJECT_DIR"; then
        ui_message "C??digo actualizado exitosamente" "ok"

        if ui_yesno "??Actualizar dependencias?" "yes"; then
            ui_message "Instalando dependencias..." "info"
            if [[ -f "$VENV_PIP" ]]; then
                (cd "$PROJECT_DIR" && "$VENV_PIP" install -r requirements.txt -q)
                ui_message "Dependencias actualizadas" "ok"
            else
                ui_message "venv no encontrado, ejecuta 'Crear venv' primero" "warn"
            fi
        fi

        if systemd_is_active "$SERVICE_NAME"; then
            if ui_yesno "??Reiniciar bot?" "yes"; then
                systemd_manage restart "$SERVICE_NAME"
                ui_message "Bot reiniciado" "ok"
            fi
        fi
    else
        ui_message "Error actualizando c??digo" "err"
        echo ""
        ui_message "Opciones:\n1) Forzar (descarta cambios locales)\n2) Ver diferencias\n3) Stash y pull\n4) Cancelar" "info"
        read -rp "  Opci??n: " opt
        case "$opt" in
            1)
                git_pull_force "$PROJECT_DIR"
                ui_message "Pull forzado completado" "ok"
                ;;
            2)
                (cd "$PROJECT_DIR" && git diff --stat)
                read -rp "  Presiona Enter para continuar..."
                ;;
            3)
                (cd "$PROJECT_DIR" && git stash && git pull origin "$branch")
                ui_message "Pull con stash exitoso" "ok"
                ;;
            *) ;;
        esac
    fi

    read -rp "  Presiona Enter para continuar..."
}

action_git_switch_branch() {
    refresh_bot_status

    if ! is_git_repo "$PROJECT_DIR"; then
        ui_message "No es repositorio git" "err"
        return 1
    fi

    local current_branch
    current_branch=$(get_current_branch "$PROJECT_DIR")
    ui_message "Rama actual: $current_branch" "info"

    local branches
    branches=$(list_available_branches "$PROJECT_DIR")

    if [[ -z "$branches" ]]; then
        ui_message "No se encontraron ramas" "warn"
        return 1
    fi

    ui_message "Ramas disponibles:" "info"
    local i=1
    declare -a branch_array=()
    while IFS= read -r branch; do
        [[ -n "$branch" ]] || continue
        local marker=""
        [[ "$branch" == "$current_branch" ]] && marker=" (actual)"
        echo "  $i) $branch$marker"
        branch_array[$((i-1))]="$branch"
        ((i++))
    done <<< "$branches"

    echo ""
    read -rp "  Selecciona rama (0 para cancelar): " sel

    if [[ "$sel" =~ ^[1-9][0-9]*$ ]] && [[ "$sel" -le ${#branch_array[@]} ]]; then
        local target_branch="${branch_array[$((sel-1))]}"

        if [[ "$target_branch" == "$current_branch" ]]; then
            ui_message "Ya est??s en esa rama" "warn"
            return 0
        fi

        if ! ui_yesno "??Cambiar a $target_branch?" "yes"; then
            return 0
        fi

        if git_switch_branch "$PROJECT_DIR" "$target_branch" true; then
            ui_message "Cambiado a rama: $target_branch" "ok"

            if ui_yesno "??Actualizar dependencias?" "yes"; then
                if [[ -f "$VENV_PIP" ]]; then
                    (cd "$PROJECT_DIR" && "$VENV_PIP" install -r requirements.txt -q)
                    ui_message "Dependencias actualizadas" "ok"
                fi
            fi
        else
            ui_message "Error cambiando de rama" "err"
        fi
    fi

    read -rp "  Presiona Enter para continuar..."
}

action_create_venv() {
    ui_clear
    ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

    local venv_dir="$PROJECT_DIR/venv"

    if [[ -d "$venv_dir" ]]; then
        ui_message "Ya existe entorno virtual en $venv_dir" "warn"
        if ! ui_yesno "??Recrear?" "no"; then
            return 0
        fi
        rm -rf "$venv_dir"
    fi

    local python_cmd=""
    if check_dependency "python3.13"; then
        python_cmd="python3.13"
    elif check_dependency "python3.12"; then
        python_cmd="python3.12"
    else
        ui_message "Python 3.12 o 3.13 no encontrado. Inst??lalo primero." "err"
        return 1
    fi

    ui_message "Creando entorno virtual con $python_cmd..." "info"

    if $python_cmd -m venv "$venv_dir"; then
        ui_message "Entorno virtual creado" "ok"

        ui_message "Actualizando pip..." "info"
        "$venv_dir/bin/pip" install --upgrade pip -q

        ui_message "venv listo en:\n$venv_dir" "ok"
    else
        ui_message "Error creando entorno virtual" "err"
    fi

    read -rp "  Presiona Enter para continuar..."
}

action_install_deps() {
    ui_clear
    ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

    local venv_pip="$VENV_PIP"
    local req_file="$PROJECT_DIR/requirements.txt"

    if [[ ! -f "$venv_pip" ]]; then
        ui_message "Entorno virtual no existe. Crea el venv primero." "err"
        return 1
    fi

    if [[ ! -f "$req_file" ]]; then
        ui_message "requirements.txt no encontrado en $PROJECT_DIR" "err"
        return 1
    fi

    ui_message "Dependencias a instalar:" "info"
    grep -v '^\s*#' "$req_file" | grep -v '^\s*$' | sed 's/^/  ??? /'

    if ! ui_yesno "??Instalar?" "yes"; then
        return 0
    fi

    ui_message "Instalando... (esto puede tardar)" "info"

    if (cd "$PROJECT_DIR" && "$VENV_PIP" install -r requirements.txt -q); then
        ui_message "Dependencias instaladas exitosamente" "ok"
    else
        ui_message "Error instalando dependencias" "err"
    fi

    read -rp "  Presiona Enter para continuar..."
}

action_configure_env() {
    ui_clear
    ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

    local env_file="$PROJECT_DIR/.env"

    if [[ -f "$env_file" ]]; then
        ui_message "Ya existe .env en:\n$env_file" "warn"
        if ! ui_yesno "??Reconfigurar?" "no"; then
            return 0
        fi
    fi

    ui_message "Configuraci??n de variables de entorno" "info"
    echo ""

    read -rp "  TOKEN_TELEGRAM: " token
    read -rp "  ADMIN_CHAT_IDS (comma-separated): " admin_ids
    read -rp "  OpenWeatherMap API Key (opcional): " weather_key

    if [[ -z "$token" ]]; then
        ui_message "El TOKEN_TELEGRAM no puede estar vac??o." "err"
        read -rp "  Presiona Enter para continuar..."
        return 1
    fi

    cat > "$env_file" <<EOF
TOKEN_TELEGRAM=$token
ADMIN_CHAT_IDS=$admin_ids
OPENWEATHER_API_KEY=$weather_key
EOF

    chmod 600 "$env_file"
    ui_message "Archivo .env creado con permisos 600" "ok"
    read -rp "  Presiona Enter para continuar..."
}

action_create_service() {
    if ! $HAS_SYSTEMD; then
        ui_message "Systemd no disponible. No se puede crear servicio en este sistema." "warn"
        read -rp "  Presiona Enter para continuar..."
        return 0
    fi
    ui_clear
    ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

    local service_file="/etc/systemd/system/$SERVICE_NAME.service"

    if [[ -f "$service_file" ]]; then
        ui_message "Ya existe servicio: $SERVICE_NAME" "warn"
        if ! ui_yesno "??Sobrescribir?" "no"; then
            return 0
        fi
    fi

    if ! systemd_create_service "$SERVICE_NAME" "$PROJECT_DIR" "$VENV_PYTHON"; then
        ui_message "Error creando servicio" "err"
        return 1
    fi

    ui_message "Servicio creado:\n$service_file" "ok"

    if ui_yesno "??Habilitar e iniciar ahora?" "yes"; then
        $SUDO systemctl enable "$SERVICE_NAME" 2>/dev/null || true
        systemd_manage start "$SERVICE_NAME"
        ui_message "Servicio habilitado e iniciado" "ok"
    fi

    read -rp "  Presiona Enter para continuar..."
}


show_main_menu() {
    while true; do
        refresh_bot_status
        ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"

        local choice
        choice=$(ui_menu "MEN?? PRINCIPAL" "Atajos: 1-5 Instalaci??n, 6-10 Control, 11-15 Git, 16-17 Logs, 18-23 Mantenimiento" \
            "1" "Instalaci??n Completa" \
            "2" "Crear/Recrear venv" \
            "3" "Instalar Dependencias" \
            "4" "Configurar .env" \
            "5" "Crear Servicio Systemd" \
            "6" "Iniciar Bot" \
            "7" "Detener Bot" \
            "8" "Reiniciar Bot" \
            "9" "Estado del Bot" \
            "10" "Estad??sticas" \
            "11" "Actualizar C??digo (git pull)" \
            "12" "Cambiar de Rama" \
            "13" "Estado del Repo" \
            "14" "Historial de Commits" \
            "15" "Clonar Repositorio" \
            "16" "Gestionar Logs" \
            "17" "Dashboard Multi-Bot" \
            "18" "Crear Backup" \
            "19" "Restaurar Backup" \
            "20" "Rotar Logs" \
            "21" "Cambiar Bot/Directorio" \
            "0" "Salir" \
        ) || break

        case "$choice" in
            1)  # InstalaciÃ³n completa - por implementar (requiere mÃ¡s pasos)
                ui_message "Funci??n no implementada en esta versi??n.\nUsa las opciones 2-5 individualmente." "warn"
                read -rp "  Presiona Enter para continuar..."
                ;;
            2)  action_create_venv ;;
            3)  action_install_deps ;;
            4)  action_configure_env ;;
            5)  action_create_service ;;
            6)  action_start_bot ;;
            7)  action_stop_bot ;;
            8)  action_restart_bot ;;
            9)  action_status_bot ;;
            10) action_stats_bot ;;
            11) action_git_pull ;;
            12) action_git_switch_branch ;;
            13)
                ui_clear
                ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"
                echo ""
                git_get_status "$PROJECT_DIR" | sed 's/^/  /'
                echo ""
                read -rp "  Presiona Enter para continuar..."
                ;;
            14)
                ui_clear
                ui_header "$FOLDER_NAME" "$BOT_STATUS" "$GIT_BRANCH"
                echo ""
                git_get_history "$PROJECT_DIR" 15 | sed 's/^/  /'
                echo ""
                read -rp "  Presiona Enter para continuar..."
                ;;
            15)
                ui_message "Funci??n no implementada. Usa git clone manualmente." "warn"
                read -rp "  Presiona Enter para continuar..."
                ;;
            16) action_manage_logs ;;
            17)
                ui_message "Funci??n no implementada en esta versi??n." "warn"
                read -rp "  Presiona Enter para continuar..."
                ;;
            18) action_backup ;;
            19) action_restore_backup ;;
            20)
                if ui_yesno "??Rotar logs del sistema? (mantiene ??ltimos $LOG_ROTATION_DAYS d??as)" "yes"; then
                    if rotate_journal_logs "$LOG_ROTATION_DAYS"; then
                        ui_message "Logs rotados" "ok"
                    else
                        ui_message "Error rotando logs" "err"
                    fi
                fi
                read -rp "  Presiona Enter para continuar..."
                ;;
            21)
                PROJECT_DIR=""
                FOLDER_NAME=""
                SERVICE_NAME=""
                select_bot_directory
                ;;
            0)
                ui_clear
                echo "??Hasta luego!"
                exit 0
                ;;
            *)  ui_message "Opci??n inv??lida" "err"
                sleep 1
                ;;
        esac
    done
}


# ============================================================================
# MANEJO DE ERRORES
# ============================================================================

handle_error() {
    local loc="${1:-unknown}"
    printf "\n\033[1;31m✘\033[0m  Error en ${loc}. Volviendo al menú.\n"
    printf "  Detalles: ${BASH_COMMAND:-N/A}\n"
    sleep 3
}

trap 'handle_error "${BASH_SOURCE[1]}:${LINENO}"' ERR

# ============================================================================
# DETECCIÓN DEL ENTORNO
# ============================================================================

detect_environment() {
    # Detectar sistema operativo
    IS_WINDOWS=false
    case "$(uname -s 2>/dev/null || echo "Unknown")" in
        CYGWIN*|MINGW*|MSYS*|Windows_NT*) IS_WINDOWS=true ;;
    esac

    # Detectar systemd
    HAS_SYSTEMD=false
    if command -v systemctl &>/dev/null && [[ -d /run/systemd/system ]]; then
        HAS_SYSTEMD=true
    fi

    # Ajustar SUDO para Windows (no hay sudo)
    if $IS_WINDOWS; then
        SUDO=""
    else
        if [[ $EUID -ne 0 ]]; then
            SUDO="sudo"
        else
            SUDO=""
        fi
    fi

    # Verificar dialog
    if ! check_dependency "dialog" 2>/dev/null; then
        echo "WARNING: 'dialog' no está instalado. Se usará interfaz de texto simple."
        echo "Para mejor experiencia, instala: sudo apt install dialog"
        echo ""
    fi
}

check_system_dependencies() {
    local missing=()
    for cmd in curl git systemctl tar; do
        command -v "$cmd" &>/dev/null || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Faltan dependencias del sistema: ${missing[*]}"
        echo "Instálalas con: sudo apt install ${missing[*]}"
        return 1
    fi
    return 0
}

# ============================================================================
# INICIALIZACIÓN DEL ENTORNO VIRTUAL
# ============================================================================

init_venv_paths() {
    # Configurar rutas de venv según sistema operativo
    if $IS_WINDOWS; then
        VENV_PYTHON="$PROJECT_DIR/venv/Scripts/python.exe"
        VENV_PIP="$PROJECT_DIR/venv/Scripts/pip.exe"
    else
        VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
        VENV_PIP="$PROJECT_DIR/venv/bin/pip"
    fi
}

main() {
    detect_environment
    check_system_dependencies || echo "Advertencia: Algunas dependencias faltan"

    select_bot_directory
    init_venv_paths

    show_main_menu
}

# ============================================================================
# ENTRY POINT
# ============================================================================

# Si el script se ejecuta directamente (no es sourced), ejecutar main
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Manejar argumentos de lÃ­nea de comandos
    case "${1:-}" in
        --install)
            select_bot_directory
            # InstalaciÃ³n completa (por implementar, usar opciones individuales)
            ui_message "Usa las opciones 2-5 del menÃº para instalar." "info"
            read -rp "  Presiona Enter para continuar..."
            show_main_menu
            ;;
        --backup)
            select_bot_directory
            action_backup
            ;;
        --stats)
            select_bot_directory
            action_stats_bot
            ;;
        --help|-h)
            echo "BBAlert Manager - Script de gestiÃ³n de bots"
            echo "Uso: $0 [OPCIÃ“N]"
            echo ""
            echo "Opciones:"
            echo "  --install    Iniciar proceso de instalaciÃ³n"
            echo "  --backup     Crear backup del bot"
            echo "  --stats      Mostrar estadÃ­sticas"
            echo "  --help, -h   Mostrar esta ayuda"
            echo ""
            echo "Sin argumentos: iniciar menÃº interactivo"
            exit 0
            ;;
        *)  # Sin argumentos, iniciar menÃº interactivo
            main "$@"
            ;;
    esac
fi



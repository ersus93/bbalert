#!/bin/bash
# â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
# â•‘  BBAlert Manager â€” UI Module (Dialog-based)                â•‘
# â•‘  Interfaz simplificada usando dialog                       â•‘
# â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

set -euo pipefail

# Nota: common.sh debe ser cargado por el script principal antes de este mÃ³dulo
# No cargar aquÃ­ para evitar problemas de rutas relativas

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CONFIGURACIÃ“N UI
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

UI_DIALOG_CMD="${UI_DIALOG_CMD:-dialog}"
UI_TITLE="BBAlert Manager"
UI_BUTTON_LABEL="Selecciona una opciÃ³n"
UI_HEIGHT=20
UI_WIDTH=60

# Colores para fallback (si dialog no estÃ¡ disponible)
UI_COLOR_RED='\033[1;31m'
UI_COLOR_GREEN='\033[1;32m'
UI_COLOR_YELLOW='\033[1;33m'
UI_COLOR_BLUE='\033[1;34m'
UI_COLOR_RESET='\033[0m'

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FUNCIONES UI PURAS (SOLO RENDERIZADO)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# ui_check_dialog - Verifica si dialog estÃ¡ disponible
ui_check_dialog() {
    if ! check_dependency "$UI_DIALOG_CMD"; then
        echo "ERROR: '$UI_DIALOG_CMD' no estÃ¡ instalado."
        echo "InstÃ¡lalo con: sudo apt install dialog"
        return 1
    fi
    return 0
}

# ui_clear - Limpia pantalla
ui_clear() {
    clear
}

# ui_header - Muestra encabezado con informaciÃ³n del bot
# Args: $1 - nombre del bot, $2 - estado (active/inactive), $3 - rama git
ui_header() {
    local FOLDER_NAME="$1"
    local status="$2"
    local branch="$3"

    ui_clear

    local status_text status_color
    if [[ "$status" == "active" ]]; then
        status_text="â— ACTIVO"
        status_color="$UI_COLOR_GREEN"
    else
        status_text="â—‹ DETENIDO"
        status_color="$UI_COLOR_RED"
    fi

    cat <<EOF
${UI_COLOR_BLUE}â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—${UI_COLOR_RESET}
${UI_COLOR_BLUE}â•‘${UI_COLOR_RESET}  $UI_TITLE â€” $FOLDER_NAME
${UI_COLOR_BLUE}â•‘${UI_COLOR_RESET}  Rama: $branch | Estado: ${status_color}$status_text${UI_COLOR_RESET}
${UI_COLOR_BLUE}â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•${UI_COLOR_RESET}

EOF
}

# ui_menu - Muestra menÃº con opciones usando dialog
# Args:
#   $1 - tÃ­tulo del menÃº
#   $2 - texto de ayuda (opcional)
#   $3... - pares "tag" "descripciÃ³n"
# Returns: tag seleccionado en stdout, o empty si cancel
ui_menu() {
    local title="$1"
    local help_text="${2:-}"
    shift 2

    # Crear archivo temporal para opciones
    local temp_file
    temp_file=$(mktemp)

    # Escribir opciones: tag descripciÃ³n
    while [[ $# -gt 0 ]]; do
        echo "$1 $2" >> "$temp_file"
        shift 2
    done

    # AÃ±adir opciÃ³n de salida
    echo "0 Salir" >> "$temp_file"

    local height=$((UI_HEIGHT - 6))
    local width=$UI_WIDTH

    if ui_check_dialog >/dev/null 2>&1; then
        # Usar dialog
        local selected
        selected=$(dialog --clear \
            --title "$UI_TITLE" \
            --menu "$title\n\n$help_text" \
            "$height" "$width" "$((height-2))" \
            --file "$temp_file" \
            2>&1 >/dev/tty) || {
            rm -f "$temp_file"
            echo "0"
            return 1
        }
        rm -f "$temp_file"
        echo "${selected:-0}"
    else
        # Fallback a menÃº de texto simple
        ui_clear
        ui_header "${FOLDER_NAME:-sin bot}" "${BOT_STATUS:-inactive}" "${GIT_BRANCH:-N/A}"
        echo ""
        echo "  $title"
        echo ""
        cat "$temp_file" | while IFS=' ' read -r tag desc; do
            echo "    $tag) $desc"
        done
        echo ""
        read -rp "  OpcionÃ³n: " selected
        rm -f "$temp_file"
        echo "${selected:-0}"
    fi
}

# ui_message - Muestra mensaje informativo
# Args: $1 - mensaje, $2 - tipo (info|ok|warn|err)
ui_message() {
    local msg="$1"
    local type="${2:-info}"
    local color

    case "$type" in
        ok)    color="$UI_COLOR_GREEN";;
        warn)  color="$UI_COLOR_YELLOW";;
        err)   color="$UI_COLOR_RED";;
        *)     color="$UI_COLOR_BLUE";;
    esac

    if ui_check_dialog >/dev/null 2>&1; then
        case "$type" in
            ok)    dialog --title "$UI_TITLE" --msgbox "$msg" 8 60 ;;
            warn)  dialog --title "$UI_TITLE" --colors --msgbox "\Zb\Z7$msg\Zn" 8 60 ;;
            err)   dialog --title "$UI_TITLE" --colors --msgbox "\Zb\Z1$msg\Zn" 8 60 ;;
            *)     dialog --title "$UI_TITLE" --msgbox "$msg" 8 60 ;;
        esac
    else
        echo ""
        echo "=== $UI_TITLE ==="
        echo "$msg"
        echo ""
        read -rp "Presiona Enter para continuar..."
    fi
}

# ui_progress - Muestra progreso con spinner
# Args: $1 - mensaje, $2 - comando a ejecutar (con args)
ui_progress() {
    local msg="$1"
    shift

    if ui_check_dialog >/dev/null 2>&1; then
        dialog --title "$UI_TITLE" --progressbox "$msg" 15 60 "$@" 2>&1 >/dev/tty
    else
        echo "$msg"
        "$@"
    fi
}

# ui_yesno - Pregunta sÃ­/no
# Args: $1 - pregunta, $2 - valor por defecto (yes/no)
# Returns: 0 si yes, 1 si no
ui_yesno() {
    local question="$1"
    local default="${2:-no}"

    if ui_check_dialog >/dev/null 2>&1; then
        local default_tag
        [[ "$default" == "yes" ]] && default_tag="yes" || default_tag="no"
        dialog --title "$UI_TITLE" --yesno "$question" 8 60 --default "$default_tag" 2>&1 >/dev/tty
    else
        local yn
        read -rp "  $question [${default^^}/n]: " yn
        yn="${yn:-$default}"
        [[ "$yn" =~ ^[yY]$ ]]
    fi
}

# ui_input - Pide entrada de texto
# Args: $1 - pregunta, $2 - valor por defecto (opcional)
# Returns: texto en stdout
ui_input() {
    local prompt="$1"
    local default="${2:-}"

    if ui_check_dialog >/dev/null 2>&1; then
        local input
        input=$(dialog --title "$UI_TITLE" --inputbox "$prompt" 8 60 "$default" 2>&1 >/dev/tty) || {
            echo ""
            return 1
        }
        echo "$input"
    else
        read -rp "  $prompt: " input
        echo "${input:-$default}"
    fi
}

# ui_password - Pide contraseÃ±a (sin echo)
# Args: $1 - prompt
# Returns: password en stdout
ui_password() {
    local prompt="$1"

    if ui_check_dialog >/dev/null 2>&1; then
        dialog --title "$UI_TITLE" --passwordbox "$prompt" 8 60 2>&1 >/dev/tty
    else
        stty -echo
        read -rp "  $prompt: " password
        stty echo
        echo "$password"
    fi
}

# ui_textbox - Muestra texto en caja (para logs, ayuda)
# Args: $1 - tÃ­tulo, $2 - texto, $3 - altura, $4 - ancho
ui_textbox() {
    local title="$1"
    local text="$2"
    local height="${3:-20}"
    local width="${4:-70}"

    if ui_check_dialog >/dev/null 2>&1; then
        echo "$text" | dialog --title "$UI_TITLE â€” $title" --textbox - "$height" "$width" 2>&1 >/dev/tty
    else
        echo "=== $title ==="
        echo "$text"
        echo ""
        read -rp "Presiona Enter para continuar..."
    fi
}

# ui_gauge - Muestra barra de progreso
# Args: $1 - tÃ­tulo, $2 - texto, $3 - porcentaje (0-100)
ui_gauge() {
    local title="$1"
    local text="$2"
    local percent="${3:-0}"

    if ui_check_dialog >/dev/null 2>&1; then
        (
            for i in $(seq 0 10 100); do
                echo "$i"
                echo "XXX"
                echo "$text"
                echo "XXX"
                sleep 0.1
            done
        ) | dialog --title "$UI_TITLE â€” $title" --gauge "$text" 10 60 "$percent" 2>&1 >/dev/tty
    fi
}

# ui_radiolist - Lista de opciones con radio buttons
# Args:
#   $1 - tÃ­tulo
#   $2 - texto de ayuda
#   $3... - pares "tag" "descripciÃ³n" "on|off"
# Returns: tag seleccionado
ui_radiolist() {
    local title="$1"
    local help_text="${2:-}"
    shift 2

    local temp_file
    temp_file=$(mktemp)

    while [[ $# -gt 0 ]]; do
        echo "$1 $2 $3" >> "$temp_file"
        shift 3
    done

    local height=$((UI_HEIGHT - 6))
    local width=$UI_WIDTH

    if ui_check_dialog >/dev/null 2>&1; then
        local selected
        selected=$(dialog --clear \
            --title "$UI_TITLE" \
            --radiolist "$title\n\n$help_text" \
            "$height" "$width" "$((height-2))" \
            --file "$temp_file" \
            2>&1 >/dev/tty) || {
            rm -f "$temp_file"
            echo ""
            return 1
        }
        rm -f "$temp_file"
        echo "$selected"
    else
        echo ""
        return 1
    fi
}

# ui_checklist - Lista con checkboxes
# Args:
#   $1 - tÃ­tulo
#   $2 - texto de ayuda
#   $3... - pares "tag" "descripciÃ³n" "on|off"
# Returns: tags seleccionados (separados por espacio)
ui_checklist() {
    local title="$1"
    local help_text="${2:-}"
    shift 2

    local temp_file
    temp_file=$(mktemp)

    while [[ $# -gt 0 ]]; do
        echo "$1 $2 $3" >> "$temp_file"
        shift 3
    done

    local height=$((UI_HEIGHT - 6))
    local width=$UI_WIDTH

    if ui_check_dialog >/dev/null 2>&1; then
        local selected
        selected=$(dialog --clear \
            --title "$UI_TITLE" \
            --checklist "$title\n\n$help_text" \
            "$height" "$width" "$((height-2))" \
            --file "$temp_file" \
            2>&1 >/dev/tty) || {
            rm -f "$temp_file"
            echo ""
            return 1
        }
        rm -f "$temp_file"
        # Retornar como array (tags separados por espacio)
        echo "$selected"
    else
        echo ""
        return 1
    fi
}

# ui_pause - Pausa con mensaje
# Args: $1 - mensaje (opcional)
ui_pause() {
    local msg="${1:-Presiona Enter para continuar...}"
    if ui_check_dialog >/dev/null 2>&1; then
        dialog --title "$UI_TITLE" --pause "$msg" 5 60 2>&1 >/dev/tty
    else
        read -rp "  $msg"
    fi
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FIN DEL MÃ“DULO
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

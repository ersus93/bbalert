#!/bin/bash
# â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
# â•‘  BBAlert Manager â€” Backup & Restore Module                 â•‘
# â•‘  GestiÃ³n de backups y restauraciÃ³n                         â•‘
# â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

set -euo pipefail

# Nota: common.sh debe ser cargado por el script principal antes de este mÃ³dulo

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CONFIGURACIÃ“N BACKUP
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

BACKUP_BASE_DIR="${BACKUP_DIR:-$HOME/backups}"
MAX_BACKUPS="${MAX_BACKUPS:-5}"

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FUNCIONES DE BACKUP
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# backup_create - Crea backup de un proyecto
# Args:
#   $1 - directorio del proyecto
#   $2 - nombre del bot (para nombre de archivo)
#   $3 - excluir (patrÃ³n, default: venv,__pycache__,.git)
# Returns: ruta del backup creado o vacÃ­o si falla
backup_create() {
    local project_dir="$1"
    local bot_name="$2"
    local exclude="${3:-venv __pycache__ *.pyc .git}"

    [[ -d "$project_dir" ]] || {
        log_error "Directorio no existe: $project_dir"
        echo ""
        return 1
    }

    local backup_dir="$BACKUP_BASE_DIR/$bot_name"
    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_file="${backup_dir}/${bot_name}_${timestamp}.tar.gz"

    # Crear directorio de backups
    mkdir -p "$backup_dir"

    log_info "Creando backup: $backup_file"

    # Construir argumentos de exclude
    local exclude_args=()
    for pat in $exclude; do
        exclude_args+=(--exclude="$pat")
    done

    # Crear tar
    if tar -czf "$backup_file" \
        "${exclude_args[@]}" \
        -C "$(dirname "$project_dir")" \
        "$(basename "$project_dir")" 2>/dev/null; then

        local size
        size=$(du -sh "$backup_file" | cut -f1)
        log_info "Backup creado: $(basename "$backup_file") â€” $size"
        echo "$backup_file"
        return 0
    else
        log_error "FallÃ³ la creaciÃ³n del backup"
        rm -f "$backup_file" 2>/dev/null || true
        echo ""
        return 1
    fi
}

# backup_list - Lista backups disponibles para un bot
# Args:
#   $1 - nombre del bot
# Returns: lista de archivos de backup (uno por lÃ­nea)
backup_list() {
    local bot_name="$1"
    local backup_dir="$BACKUP_BASE_DIR/$bot_name"

    if [[ ! -d "$backup_dir" ]] || [[ -z "$(ls -A "$backup_dir" 2>/dev/null)" ]]; then
        echo ""
        return 0
    fi

    ls -t "$backup_dir"/*.tar.gz 2>/dev/null || echo ""
}

# backup_rotate - Rota backups manteniendo solo los N mÃ¡s recientes
# Args:
#   $1 - nombre del bot
#   $2 - nÃºmero mÃ¡ximo de backups (default: MAX_BACKUPS)
# Returns: nÃºmero de backups eliminados
backup_rotate() {
    local bot_name="$1"
    local max_keep="${2:-$MAX_BACKUPS}"
    local backup_dir="$BACKUP_BASE_DIR/$bot_name"
    local deleted=0

    if [[ ! -d "$backup_dir" ]]; then
        return 0
    fi

    local count
    count=$(ls "$backup_dir"/*.tar.gz 2>/dev/null | wc -l)

    if [[ "$count" -gt "$max_keep" ]]; then
        local to_delete=$((count - max_keep))
        ls -t "$backup_dir"/*.tar.gz | tail -n "$to_delete" | while read -r file; do
            rm -f "$file" 2>/dev/null
            ((deleted++))
        done
        log_info "RotaciÃ³n: eliminados $deleted backups antiguos"
    fi

    return "$deleted"
}

# backup_restore - Restaura un backup
# Args:
#   $1 - archivo de backup (.tar.gz)
#   $2 - directorio destino (opcional, default: directorio original)
# Returns: 0 si Ã©xito, 1 si falla
backup_restore() {
    local backup_file="$1"
    local dest_dir="${2:-}"

    [[ -f "$backup_file" ]] || {
        log_error "Backup no encontrado: $backup_file"
        return 1
    }

    # Si no se especifica destino, extraer en directorio actual
    if [[ -z "$dest_dir" ]]; then
        dest_dir="$(pwd)"
    fi

    log_info "Restaurando backup a $dest_dir..."

    # Detectar directorio dentro del tar
    local tar_content
    tar -tzf "$backup_file" 2>/dev/null | head -1 | while read -r first_entry; do
        # Extraer primer componente del path
        local top_dir
        top_dir=$(echo "$first_entry" | cut -d/ -f1)
        echo "$top_dir"
    done

    # Extraer
    if tar -xzf "$backup_file" -C "$dest_dir" 2>/dev/null; then
        log_info "Backup restaurado exitosamente"
        return 0
    else
        log_error "FallÃ³ la restauraciÃ³n del backup"
        return 1
    fi
}

# backup_validate - Valida integridad de un backup
# Args: $1 - archivo de backup
# Returns: 0 si vÃ¡lido, 1 si corrupto
backup_validate() {
    local backup_file="$1"

    [[ -f "$backup_file" ]] || {
        log_error "Archivo no existe: $backup_file"
        return 1
    }

    # Probar lectura del tar
    if tar -tzf "$backup_file" &>/dev/null; then
        log_info "Backup vÃ¡lido: $backup_file"
        return 0
    else
        log_error "Backup corrupto: $backup_file"
        return 1
    fi
}

# backup_get_info - Obtiene informaciÃ³n de un backup
# Args: $1 - archivo de backup
# Returns: "size date path"
backup_get_info() {
    local backup_file="$1"

    if [[ ! -f "$backup_file" ]]; then
        echo ""
        return 1
    fi

    local size date
    size=$(du -sh "$backup_file" 2>/dev/null | cut -f1 || echo "?")
    date=$(stat -c %y "$backup_file" 2>/dev/null | cut -d' ' -f1 || echo "?")

    echo "$size $date $backup_file"
}

# backup_cleanup_all - Limpia backups antiguos de todos los bots
# Args: $1 - dÃ­as mÃ¡ximos a mantener (default: 30)
# Returns: nÃºmero de archivos eliminados
backup_cleanup_all() {
    local days="${1:-30}"
    local deleted=0
    local cutoff_date

    cutoff_date=$(date -d "$days days ago" +%Y%m%d 2>/dev/null || date -v-"$days"d +%Y%m%d 2>/dev/null || echo "")

    if [[ -z "$cutoff_date" ]]; then
        log_warn "No se pudo calcular fecha de corte"
        return 0
    fi

    if [[ -d "$BACKUP_BASE_DIR" ]]; then
        find "$BACKUP_BASE_DIR" -name "*.tar.gz" -type f 2>/dev/null | while read -r file; do
            local file_date
            file_date=$(stat -c %y "$file" 2>/dev/null | cut -d'-' -f1-3 | tr -d '-' || echo "")
            if [[ -n "$file_date" ]] && [[ "$file_date" -lt "$cutoff_date" ]]; then
                rm -f "$file" 2>/dev/null
                ((deleted++))
            fi
        done
    fi

    log_info "Limpieza de backups: eliminados $deleted archivos antiguos"
    return "$deleted"
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FIN DEL MÃ“DULO
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

#!/bin/bash
# â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
# â•‘  BBAlert Manager â€” Git Operations Module                   â•‘
# â•‘  Operaciones git encapsuladas                               â•‘
# â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

set -euo pipefail

# Nota: common.sh debe ser cargado por el script principal antes de este mÃ³dulo

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FUNCIONES GIT PURAS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# git_clone - Clona un repositorio
# Args:
#   $1 - URL del repositorio
#   $2 - directorio destino
# Returns: 0 si Ã©xito, 1 si falla
git_clone() {
    local url="$1"
    local dest="$2"

    if [[ -d "$dest" ]]; then
        log_error "El directorio '$dest' ya existe"
        return 1
    fi

    if git clone "$url" "$dest" 2>/dev/null; then
        log_info "Repositorio clonado en $dest"
        return 0
    else
        log_error "Error clonando $url"
        return 1
    fi
}

# git_pull - Hace pull de la rama actual
# Args:
#   $1 - directorio del proyecto
#   $2 - remote (default: origin)
#   $3 - branch (default: rama actual)
# Returns: 0 si Ã©xito, 1 si falla
git_pull() {
    local dir="$1"
    local remote="${2:-origin}"
    local branch="${3:-$(get_current_branch "$dir")}"

    if [[ ! -d "$dir/.git" ]]; then
        log_error "No es repositorio git: $dir"
        return 1
    fi

    (
        cd "$dir" || exit 1
        git fetch "$remote" "$branch" 2>/dev/null || {
            log_error "FallÃ³ git fetch $remote $branch"
            return 1
        }

        if git pull "$remote" "$branch" 2>/dev/null; then
            log_info "Pull exitoso: $remote/$branch"
            return 0
        else
            log_error "FallÃ³ git pull $remote $branch"
            return 1
        fi
    )
}

# git_pull_force - Fuerza pull descartando cambios locales
# Args:
#   $1 - directorio del proyecto
#   $2 - remote (default: origin)
#   $3 - branch (default: rama actual)
# Returns: 0 si Ã©xito
git_pull_force() {
    local dir="$1"
    local remote="${2:-origin}"
    local branch="${3:-$(get_current_branch "$dir")}"

    (
        cd "$dir" || exit 1

        # Stash cambios no committeados
        git stash push -m "Auto-backup $(date)" --include-untracked 2>/dev/null || true

        # Reset hard
        if git reset --hard "$remote/$branch" 2>/dev/null; then
            log_info "Forzado a $remote/$branch"
            return 0
        else
            # Intentar limpiar y forzar fetch
            git clean -fd
            git fetch "$remote" "$branch" --force 2>/dev/null
            git reset --hard "$remote/$branch"
            log_info "Forzado a $remote/$branch (con clean)"
            return 0
        fi
    )
}

# git_switch_branch - Cambia a otra rama
# Args:
#   $1 - directorio del proyecto
#   $2 - nombre de la rama destino
#   $3 - pull despuÃ©s de checkout (true/false, default: true)
# Returns: 0 si Ã©xito, 1 si falla
git_switch_branch() {
    local dir="$1"
    local target_branch="$2"
    local do_pull="${3:-true}"

    if [[ ! -d "$dir/.git" ]]; then
        log_error "No es repositorio git: $dir"
        return 1
    fi

    (
        cd "$dir" || exit 1

        # Verificar cambios sin committear
        if ! git diff-index --quiet HEAD -- 2>/dev/null; then
            log_warn "Hay cambios sin committear. Descartando..."
            git checkout -- .
        fi

        # Checkout
        if ! git checkout "$target_branch" 2>/dev/null; then
            log_error "FallÃ³ checkout a $target_branch"
            return 1
        fi

        # Pull si se solicita
        if [[ "$do_pull" == "true" ]]; then
            git pull origin "$target_branch" 2>/dev/null || {
                log_warn "Pull fallÃ³, usando solo checkout local"
            }
        fi

        log_info "Cambiado a rama: $target_branch"
        return 0
    )
}

# git_get_status - Obtiene estado detallado del repositorio
# Args: $1 - directorio del proyecto
# Returns: string con estado formateado
git_get_status() {
    local dir="$1"

    if [[ ! -d "$dir/.git" ]]; then
        echo "No es repositorio git"
        return 1
    fi

    (
        cd "$dir" || exit 1

        local branch remote_url last_commit
        branch=$(git branch --show-current 2>/dev/null || echo "?")
        remote_url=$(git remote get-url origin 2>/dev/null || echo "N/A")
        last_commit=$(git log -1 --format='%h â€” %s (%cr)' 2>/dev/null || echo "N/A")

        echo "Rama: $branch"
        echo "Remote: $remote_url"
        echo "Ãšltimo: $last_commit"
        echo ""
        echo "Modificados:"
        git status --short 2>/dev/null | sed 's/^/  /' || echo "  (ninguno)"
        echo ""
        echo "Commits locales no enviados:"
        git log @{u}..HEAD --oneline 2>/dev/null | sed 's/^/  Â· /' || echo "  (ninguno)"
        echo ""
        echo "Remotos no descargados:"
        git log HEAD..@{u} --oneline 2>/dev/null | sed 's/^/  Â· /' || echo "  (ninguno)"
    )
}

# git_get_history - Obtiene historial de commits
# Args:
#   $1 - directorio del proyecto
#   $2 - nÃºmero de commits (default: 15)
# Returns: historial formateado
git_get_history() {
    local dir="$1"
    local count="${2:-15}"

    if [[ ! -d "$dir/.git" ]]; then
        echo "No es repositorio git"
        return 1
    fi

    (
        cd "$dir" || exit 1
        git log --oneline -"$count" --decorate --graph 2>/dev/null || echo "Sin historial"
    )
}

# git_has_changes - Verifica si hay cambios sin committear
# Args: $1 - directorio del proyecto
# Returns: 0 si hay cambios, 1 si no
git_has_changes() {
    local dir="$1"

    if [[ ! -d "$dir/.git" ]]; then
        return 1
    fi

    (
        cd "$dir" || exit 1
        ! git diff-index --quiet HEAD -- 2>/dev/null
    )
}

# git_has_remote - Verifica si repo tiene remote configurado
# Args: $1 - directorio del proyecto
# Returns: 0 si tiene remote, 1 si no
git_has_remote() {
    local dir="$1"

    if [[ ! -d "$dir/.git" ]]; then
        return 1
    fi

    (
        cd "$dir" || exit 1
        git remote get-url origin &>/dev/null
    )
}

# git_get_upstream - Obtiene upstream de rama actual
# Args: $1 - directorio del proyecto
# Returns: "remote/branch" o vacÃ­o si no hay upstream
git_get_upstream() {
    local dir="$1"

    if [[ ! -d "$dir/.git" ]]; then
        echo ""
        return 1
    fi

    (
        cd "$dir" || exit 1
        git rev-parse --abbrev-ref '@{u}' 2>/dev/null || echo ""
    )
}

# git_ensure_upstream - Asegura que rama tenga upstream
# Args: $1 - directorio del proyecto
# Returns: 0 si se configurÃ³, 1 si ya existÃ­a o fallÃ³
git_ensure_upstream() {
    local dir="$1"
    local branch

    branch=$(get_current_branch "$dir")
    [[ -z "$branch" ]] && return 1

    if git_get_upstream "$dir" &>/dev/null; then
        return 0  # Ya tiene upstream
    fi

    (
        cd "$dir" || exit 1
        git branch --set-upstream-to="origin/$branch" "$branch" 2>/dev/null
    )
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FIN DEL MÃ“DULO
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# MBot.sh Professional Audit - Design Document

**Date:** 2026-03-15  
**Author:** AI Development Team  
**Status:** Approved for Implementation

---

## Overview

Comprehensive audit and improvement plan for `mbot.sh` - the BBAlert multi-bot TUI manager. This document outlines the design changes to transform the script into a professional-grade bot management tool.

---

## Current State Assessment

### Strengths (Preserve These)
- ✅ Responsive 2-column/1-column layout based on terminal width
- ✅ Professional box-drawing characters and UI
- ✅ Warm/matte color palette (easy on eyes)
- ✅ Spinner animations and progress bars
- ✅ Real-time system metrics (CPU, RAM)
- ✅ Comprehensive feature set (23 menu options)
- ✅ Multi-bot support and dashboard
- ✅ Backup/restore functionality
- ✅ Git integration
- ✅ Systemd service management

### Issues Identified

| Priority | Issue | Location | Impact |
|----------|-------|----------|--------|
| **HIGH** | Missing `set -euo pipefail` | Line 1 | Error handling |
| **HIGH** | Typo: `full_instal` in case statement | Line 1063 | Script breaks |
| **HIGH** | Empty backup dir not checked | Line 577 | Potential crash |
| **MED** | Fixed-width assumptions break <60 chars | Multiple | Responsiveness |
| **MED** | No health check before start | `start_bot()` | UX |
| **MED** | No auto-recovery for crashed services | `manage_service()` | Reliability |
| **LOW** | Inconsistent confirmation prompts | Multiple | UX |
| **LOW** | No keyboard shortcuts displayed | Menu | UX |
| **LOW** | No log rotation management | `manage_logs()` | Features |

---

## Design Specifications

### 1. Critical Bug Fixes

#### 1.1 Add Strict Error Handling
```bash
# Add at line 2 (after shebang)
set -euo pipefail

# Update error trap to handle all cases
trap 'handle_error "${BASH_SOURCE[1]}:${LINENO}"' ERR
```

#### 1.2 Fix Typo in Case Statement
```bash
# Line 1063: Change from:
--install)    select_target_directory; full_instal...
# To:
--install)    select_target_directory; full_install...
```

#### 1.3 Empty Backup Directory Check
```bash
# In restore_backup(), add before mapfile:
if [[ ! -d "$bdir" ]] || [[ -z "$(ls -A "$bdir" 2>/dev/null)" ]]; then
    _warn "No hay backups disponibles para $FOLDER_NAME"
    _pause
    return 0
fi
```

---

### 2. Responsive TUI Enhancements

#### 2.1 Three-Column Layout (≥120 chars)
```bash
if [[ $W -ge 116 ]]; then
    # 3 columns: Install | Control | Git/Monitoring
    local CW1=$(( (IW - 2) / 3 ))
    local CW2=$(( (IW - 2) / 3 ))
    local CW3=$(( IW - 2 - CW1 - CW2 ))
    # ... render 3-column menu
fi
```

#### 2.2 Dynamic Text Truncation
```bash
# Add ellipsis truncation for narrow terminals
_truncate() {
    local text="$1" max="$2"
    local plain; plain=$(printf '%b' "$text" | sed 's/\x1b\[[0-9;]*m//g')
    [[ ${#plain} -gt $max ]] && text="${text:0:$((max-3))}..."
    echo "$text"
}
```

#### 2.3 Minimum Width Check
```bash
_check_terminal_width() {
    local w; w=$(_w)
    if [[ $w -lt 60 ]]; then
        printf "\n  ${RB}⚠ Terminal muy estrecho (${w} cols)${NC}\n"
        printf "  ${DIM}Se recomienda ≥80 columnas para mejor experiencia.${NC}\n"
        printf "  ${DIM}Algunos elementos pueden no mostrarse correctamente.${NC}\n\n"
        read -rp "  ¿Continuar de todos modos? [S/n]: " cw
        [[ "$cw" =~ ^[nN]$ ]] && exit 1
    fi
}
```

---

### 3. Professional Features

#### 3.1 Health Check Panel
```bash
_health_check() {
    local issues=0
    _step "Verificando salud del bot"
    
    # Python version
    if [[ -f "$PYTHON_BIN" ]]; then
        _ok "Python: $($PYTHON_BIN --version 2>&1)"
    else
        _err "Python no encontrado en venv"; ((issues++))
    fi
    
    # Virtual environment
    if [[ -f "$ACTIVATE_SCRIPT" ]]; then
        _ok "Entorno virtual: OK"
    else
        _err "Entorno virtual no encontrado"; ((issues++))
    fi
    
    # .env file
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        _ok "Archivo .env: presente"
        # Validate critical variables
        if grep -q '^TOKEN_TELEGRAM=' "$PROJECT_DIR/.env"; then
            _ok "TOKEN_TELEGRAM: configurado"
        else
            _warn "TOKEN_TELEGRAM: faltante"
            ((issues++))
        fi
    else
        _err ".env no encontrado"; ((issues++))
    fi
    
    # Main script
    if [[ -f "$BOT_SCRIPT_PATH" ]]; then
        _ok "Script principal: presente"
    else
        _err "Script principal no encontrado"; ((issues++))
    fi
    
    # Dependencies
    if [[ -f "$PIP_BIN" ]] && source "$ACTIVATE_SCRIPT" 2>/dev/null; then
        local missing=$("$PIP_BIN" check 2>&1 | grep -c "NOT INSTALLED" || echo "0")
        if [[ "$missing" == "0" ]]; then
            _ok "Dependencias: todas instaladas"
        else
            _warn "Dependencias: $missing faltantes"
        fi
    fi
    
    return $issues
}
```

#### 3.2 Auto-Recovery System
```bash
_auto_recovery_check() {
    if ! systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        local last_start; last_start=$(systemctl show "$SERVICE_NAME" --property=ActiveEnterTimestamp --value 2>/dev/null)
        local now; now=$(date +%s)
        local start_ts; start_ts=$(date -d "$last_start" +%s 2>/dev/null || echo "0")
        local diff=$((now - start_ts))
        
        # If bot was active in last 5 minutes but now stopped, suggest recovery
        if [[ $diff -lt 300 && $diff -gt 10 ]]; then
            _warn "El bot se detuvo inesperadamente (hace ${diff}s)"
            read -rp "  ¿Intentar recuperación automática? [S/n]: " rec
            [[ ! "$rec" =~ ^[nN]$ ]] && manage_service "start"
        fi
    fi
}
```

#### 3.3 Quick Actions Bar
```bash
# Add to show_menu() after menu options
_show_quick_actions() {
    printf "\n  ${DIM}Atajos:${NC} "
    printf "${CB}1-5${NC} Instalación  "
    printf "${CB}6-10${NC} Control  "
    printf "${CB}11-15${NC} Git  "
    printf "${CB}16-17${NC} Logs  "
    printf "${CB}18-23${NC} Mantenimiento  "
    printf "${RB}0${NC} Salir\n"
}
```

---

### 4. Code Organization Improvements

#### 4.1 Function Documentation Standard
```bash
# _function_name - Brief description
# Parameters:
#   $1 - parameter_name: description
# Returns:
#   0 on success, non-zero on error
# Side effects:
#   What files/variables are modified
```

#### 4.2 Section Headers
```bash
# ═══════════════════════════════════════════════════════════════
# SECTION: ERROR HANDLING & UTILITIES
# ═══════════════════════════════════════════════════════════════
```

#### 4.3 Consistent Error Messages
```bash
# Format: [ICON] Context: Specific message. Action hint.
_err_config() { _err "Configuración: $1. Verifica el archivo .env."; }
_err_service() { _err "Servicio $SERVICE_NAME: $1. Usa journalctl para detalles."; }
_err_git() { _err "Git: $1. Verifica tu conexión y permisos."; }
_err_file() { _err "Archivo: $1 no encontrado en $2."; }
```

---

### 5. New Features

#### 5.1 Start/Stop All Bots
```bash
manage_all_bots() {
    local action="$1"
    local svcs; svcs=$(systemctl list-units --type=service --state=loaded --no-pager --no-legend | \
        grep -E "bbalert|telebot|bot" | awk '{print $1}' | cut -d'.' -f1)
    
    local total=0 success=0 failed=0
    for svc in $svcs; do
        ((total++))
        _info "$action $svc..."
        if $SUDO systemctl "$action" "$svc" 2>/dev/null; then
            ((success++))
        else
            ((failed++))
            _err "Falló $svc"
        fi
    done
    
    _ok "Completado: $success/$total exitosos"
    [[ $failed -gt 0 ]] && _warn "$failed fallaron"
}
```

#### 5.2 Log Rotation
```bash
rotate_logs() {
    _header; _center "ROTACIÓN DE LOGS" "${YB}"; printf "\n"
    
    local journal_size; journal_size=$($SUDO journalctl --disk-usage 2>/dev/null | awk '{print $1, $2}' || echo "0")
    _info "Tamaño actual de logs: ${CB}$journal_size${NC}"
    
    read -rp "  ¿Rotar logs? (mantendrá últimos 7 días) [S/n]: " rl
    [[ ! "$rl" =~ ^[nN]$ ]] || return 0
    
    _spin_start "Rotando"
    $SUDO journalctl --rotate 2>/dev/null
    $SUDO journalctl --vacuum-time=7d 2>/dev/null
    _spin_stop
    
    local new_size; new_size=$($SUDO journalctl --disk-usage 2>/dev/null | awk '{print $1, $2}' || echo "0")
    _ok "Logs rotados. Nuevo tamaño: ${CB}$new_size${NC}"
    _pause
}
```

#### 5.3 Pre-Start Configuration Validation
```bash
_validate_before_start() {
    local errors=0
    
    # Check Python
    if ! command -v "$PYTHON_BIN" &>/dev/null; then
        _err "Python no encontrado. Crea el entorno virtual primero."
        ((errors++))
    fi
    
    # Check .env
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        _err ".env no encontrado. Configura el bot primero."
        ((errors++))
    elif ! grep -q '^TOKEN_TELEGRAM=' "$PROJECT_DIR/.env"; then
        _err "TOKEN_TELEGRAM no configurado en .env"
        ((errors++))
    fi
    
    # Check main script
    if [[ ! -f "$BOT_SCRIPT_PATH" ]]; then
        _err "Script principal no encontrado: $BOT_SCRIPT_PATH"
        ((errors++))
    fi
    
    return $errors
}
```

---

## Implementation Plan

### Phase 1: Critical Fixes (Priority: HIGH)
1. Add `set -euo pipefail`
2. Fix `full_instal` typo
3. Add empty backup directory check
4. Add proper error propagation

### Phase 2: Responsive Improvements (Priority: MED)
1. Add 3-column layout for ≥120 chars
2. Implement text truncation with ellipsis
3. Add minimum width check (60 chars)
4. Test on various terminal sizes

### Phase 3: Professional Features (Priority: MED)
1. Implement health check panel
2. Add auto-recovery system
3. Add quick actions bar
4. Add pre-start validation

### Phase 4: New Features (Priority: LOW)
1. Start/Stop all bots
2. Log rotation utility
3. Enhanced dashboard with multi-bot actions

### Phase 5: Code Quality (Priority: LOW)
1. Add function documentation
2. Consistent error message format
3. Section headers for better navigation
4. Variable naming improvements

---

## Testing Strategy

### Manual Testing Checklist
- [ ] Terminal width 60, 80, 100, 120, 150 chars
- [ ] Terminal height 20, 30, 50 lines
- [ ] All 23 menu options functional
- [ ] Error scenarios (missing files, no network)
- [ ] Multi-bot dashboard with 0, 1, 5+ bots
- [ ] Backup/restore cycle
- [ ] Git operations (clone, pull, branch switch)
- [ ] Service management (start, stop, restart, status)

### Automated Testing (if applicable)
- ShellCheck validation
- Bash unit tests for critical functions
- Syntax validation: `bash -n mbot.sh`

---

## Backward Compatibility

All changes maintain backward compatibility:
- Existing command-line arguments preserved
- All 23 original menu options unchanged
- Configuration file locations unchanged
- Service names and structure unchanged
- Data files not modified

---

## Success Criteria

1. **Zero critical bugs** from audit list
2. **Responsive** on terminals 60-200 chars wide
3. **Professional UX** with health checks and auto-recovery
4. **Clean code** with proper documentation
5. **All tests pass** (manual checklist complete)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing functionality | Test each function individually before integration |
| Terminal compatibility issues | Test on multiple terminal emulators |
| User confusion from UI changes | Keep core menu structure, add features incrementally |
| Script becomes too large | Extract utility functions, maintain clear sections |

---

## Approval

**Design approved for implementation.**

All improvements focus on:
- Professional reliability (error handling, health checks)
- Better responsiveness (3-column layout, dynamic text)
- Enhanced UX (quick actions, auto-recovery)
- Code maintainability (documentation, organization)

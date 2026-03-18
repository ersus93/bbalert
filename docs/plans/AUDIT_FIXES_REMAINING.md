# 🔧 BBAlert Audit — Fixes Remaining

**Audit Version:** 1.2.3  
**Date:** 2026-03-15  
**Current Status:** FASE 1 Complete (7/7 bugs fixed) + Partial FASE 2  
**Commit:** `cd1e94a` on branch `test`

---

## ✅ COMPLETED FIXES (FASE 1 + BUG-09, BUG-13)

### Critical Bugs Fixed (FASE 1)

1. **BUG-03** - `core/errors.py`: Fixed invalid `from typing import T` → Now declares `T = TypeVar('T')`
2. **BUG-04** - `core/errors.py`: Removed non-existent `UserIsBot` from exception handling
3. **BUG-01** - All files: Renamed functions to conventional snake_case
   - `obtener_monedAS_usuario` → `obtener_monedas_usuario`
   - `actualizar_monedAS` → `actualizar_monedas`
4. **BUG-02** - `bbalert.py`: Fixed blocked user deletion (`str(chat_id)` instead of `chat_id`)
5. **BUG-05** - `core/loops.py`: Added `update_alert_status()` to prevent infinite alert loop
6. **BUG-06** - `utils/subscription_manager.py`: Implemented `'alerts_capacity'` validation
7. **BUG-07** - `core/api_client.py`: Added `fmt()` helper to handle 'N/A' prices safely
8. **BUG-09** - `utils/file_manager.py`: Auto-create `data/` directory on startup
9. **BUG-13** - `handlers/trading.py`: Fixed Monday calculation in `/mk` command

---

## ⏳ REMAINING FIXES (FASE 2, 3, 4)

### FASE 2 — Logic & Consistency (6 bugs remaining)

#### BUG-10 — Refactor `_obtener_precios` heuristic
**File:** `core/api_client.py`  
**Issue:** Using `len(monedas) == 3` as heuristic is fragile  
**Fix:** Create explicit functions `obtener_precios_alerta()` and `obtener_precios_control()`

```python
# Current (fragile):
return None if len(monedas) == 3 else {}

# Fixed:
def obtener_precios_alerta():
    """Always returns dict or {} on error."""
    result = _obtener_precios(["BTC", "TON", "HIVE", "HBD"], CMC_API_KEY_ALERTA)
    return result if result else {}

def obtener_precios_control(monedas):
    """Always returns dict or {} on error."""
    result = _obtener_precios(monedas, CMC_API_KEY_CONTROL)
    return result if result else {}
```

---

#### BUG-12 — Use timezone for consistent dates
**File:** `core/loops.py`  
**Issue:** `timezone` imported but not used, naive datetime comparisons  
**Fix:** Standardize on UTC throughout

```python
# Import:
from datetime import datetime, timedelta, timezone

# When saving:
datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

# When reading:
last_run = datetime.strptime(last_timestamp_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
now = datetime.now(timezone.utc)
```

---

#### BUG-15 — Normalize language_code when registering users
**Files:** `handlers/general.py`, `utils/user_data.py`  
**Issue:** `language_code` can be `None` or regional (`'es-419'`)  
**Fix:** Add normalization function

```python
def _normalizar_lang(code: str) -> str:
    if not code:
        return 'es'
    base = code.split('-')[0].lower()  # 'es-419' → 'es'
    return base if base in ('es', 'en') else 'es'
```

Apply in `registrar_usuario()` before saving.

---

#### BUG-08/18 — Fix variable naming in alerta_loop
**File:** `core/loops.py:249`  
**Issue:** `get_hbd_alert_recipients()` returns `int` list, but variable named `user_id_str`  
**Fix:** Rename variable for clarity

```python
# Current (confusing):
for user_id_str in recipients:  # user_id_str is actually int
    await _enviar_mensaje_telegram_async_ref(alerta_msg, [user_id_str], ...)

# Fixed:
for user_id in recipients:  # Clear naming
    await _enviar_mensaje_telegram_async_ref(alerta_msg, [str(user_id)], ...)
```

---

### FASE 3 — Code Cleanup (Multiple bugs)

#### BUG-25 — Remove unused `timezone` import
**File:** `core/loops.py:4`  
**Fix:** Remove after implementing BUG-12, or keep if used

---

#### BUG-26 — Remove redundant `_MIGRATION_TIMESTAMPS_DONE`
**File:** `utils/file_manager.py:57`  
**Issue:** Variable declared but migration logic is in `user_data.py`  
**Fix:** Remove the duplicate declaration

---

#### BUG-27/28/29/30 — Remove dead code and unused imports

| File | Remove |
|------|--------|
| `handlers/alerts.py` | `uuid`, `openpyxl`, `ConversationHandler`, `CallbackQueryHandler`, `set_admin_util`, `_enviar_mensaje_telegram_async_ref` |
| `handlers/user_settings.py` | `openpyxl` |
| `utils/file_manager.py` | `openpyxl`, `_USUARIOS_CACHE` (duplicate) |
| `bbalert.py` | `BTCAdvancedAnalyzer` (if not used directly) |
| `handlers/alerts.py` | `COIN, TARGET_PRICE = range(2)` |

---

#### BUG-16/17/19/20/21/22/23/24 — Code inconsistencies

| Bug | Issue | Fix |
|-----|-------|-----|
| BUG-16 | `_USUARIOS_CACHE` declared in both `user_data.py` and `file_manager.py` | Remove from `file_manager.py` |
| BUG-17 | `delete_all_alerts` defined in two modules | Keep only in `alert_manager.py` |
| BUG-19 | `weather_subscribe_command` imported but not registered | Add handler in `bbalert.py` |
| BUG-20 | `check_rate_limit` imported but not used | Apply as middleware or remove |
| BUG-21 | `BTCAdvancedAnalyzer` imported in `bbalert.py` but not used | Remove import |
| BUG-22 | `openpyxl` imported in multiple files without use | Remove unused imports |
| BUG-23 | `ads_manager.py` uses CRLF line endings | Convert to LF: `sed -i 's/\r//' utils/ads_manager.py` |

---

### FASE 4 — Feature Activation (Optional enhancements)

#### 4.1 — Connect `weather_subscribe_command` as handler
**File:** `bbalert.py`  
**Fix:** Add handler registration

```python
app.add_handler(CommandHandler("wsub", weather_subscribe_command))
```

---

#### 4.2 — Activate rate limiting as middleware
**File:** `bbalert.py`  
**Fix:** Apply `check_rate_limit` to handlers

```python
from core.rate_limiter import check_rate_limit

async def rate_limit_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        allowed, reason = check_rate_limit(update.effective_user.id, "command")
        if not allowed:
            await update.effective_message.reply_text(
                f"⏳ Demasiadas solicitudes. Espera un momento.\n_{reason}_",
                parse_mode=ParseMode.MARKDOWN
            )
            return
```

---

#### 4.3 — Initialize all data files on startup
**File:** `utils/file_manager.py` — enhance `inicializar_archivos()`  
**Fix:** Create all JSON files with empty defaults

```python
def inicializar_archivos():
    from core.config import DATA_DIR, USUARIOS_PATH, PRICE_ALERTS_PATH, ...
    
    os.makedirs(DATA_DIR, exist_ok=True)
    
    archivos_vacios = {
        USUARIOS_PATH: {},
        PRICE_ALERTS_PATH: {},
        CUSTOM_ALERT_HISTORY_PATH: {},
        # ... all paths
    }
    for path, default in archivos_vacios.items():
        if not os.path.exists(path):
            with open(path, 'w') as f:
                json.dump(default, f, indent=4)
```

---

## 📋 VERIFICATION CHECKLIST

After applying all fixes, verify:

```bash
# 1. Test imports
python3 -c "from core.errors import retry_async; print('✅ errors.py OK')"

# 2. Test function names
python3 -c "from utils.user_data import obtener_monedas_usuario; print('✅ user_data.py OK')"

# 3. Run bot in foreground for manual testing
python bbalert.py

# Manual tests:
# - /start → Should register user correctly
# - /ver → Should show prices without NameError
# - /mismonedas → Should show coins without errors
# - /alerta BTC 50000 → Should create alert and respect limits
# - Wait for alert to trigger → Should not spam (only once)
# - /mk on weekend → Should show correct days until Monday
```

---

## 🚀 NEXT STEPS

1. **Apply remaining FASE 2 fixes** (BUG-10, BUG-12, BUG-15, BUG-08/18)
2. **Apply FASE 3 cleanup** (remove dead code, unused imports)
3. **Optional: Apply FASE 4 enhancements** (activate disconnected features)
4. **Run full test suite** (if tests exist)
5. **Create GitHub Issues** for tracking
6. **Merge to `dev` branch** (manual by user)
7. **Deploy to VPS** via `git pull`

---

**Current Branch:** `test`  
**Last Commit:** `cd1e94a` — "fix(audit): corregir 8 bugs críticos de auditoría v1.2.3"  
**Files Modified:** 13  
**Lines Changed:** +93, -50

---

*Document generated: 2026-03-15*  
*Auditor: AI Code Assistant*

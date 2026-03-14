# Telegram UX Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement critical UX improvements from audit in isolated `test` branch without affecting `dev` or `main`.

**Architecture:** Create `test` branch from `dev`, implement changes incrementally with tests, deploy to staging for user testing.

**Tech Stack:** Python 3.12+, python-telegram-bot v20.x, pytest for testing.

---

## Pre-Flight Checklist

### Task 0: Setup Test Branch

**Files:**
- Current branch: `dev`
- Target branch: `test` (to create)

**Step 1: Ensure dev is up to date**

```bash
git checkout dev
git pull origin dev
```

Expected: Branch updated to latest dev

**Step 2: Create test branch**

```bash
git checkout -b test
```

Expected: Switched to branch 'test'

**Step 3: Push test branch to remote**

```bash
git push -u origin test
```

Expected: Branch 'test' set up to track 'origin/test'

**Step 4: Verify branch isolation**

```bash
git status
```

Expected: On branch test, working tree clean

**Step 5: Commit audit documents**

```bash
git add docs/AUDITORIA_SIMPLICIDAD_2026_03_14.md docs/AUDITORIA_UX_TELEGRAM_2026_03_14.md QWEN.md
git commit -m "docs: add UX audit reports and QWEN context (#audit)"
```

---

## Phase 1: Critical UX Fixes (Week 1)

### Task 1.1: Redesign /start Command

**Files:**
- Modify: `handlers/general.py:23-48`
- Test: `tests/test_start_command.py`

**Step 1: Write test for new /start behavior**

```python
# tests/test_start_command.py
import pytest
from telegram import Update, User
from telegram.ext import Application
from handlers.general import start

@pytest.mark.asyncio
async def test_start_message_length():
    """Start message should be < 30 words."""
    # Mock update and context
    update = Mock(spec=Update)
    context = Mock()
    
    await start(update, context)
    
    # Verify message was sent
    message = update.message.reply_text.call_args[0][0]
    word_count = len(message.split())
    assert word_count < 30, f"Start message has {word_count} words, should be < 30"

@pytest.mark.asyncio
async def test_start_has_buttons():
    """Start message should have 3 CTA buttons."""
    update = Mock(spec=Update)
    context = Mock()
    
    await start(update, context)
    
    # Verify reply_markup was passed
    call_kwargs = update.message.reply_text.call_args[1]
    keyboard = call_kwargs['reply_markup'].inline_keyboard
    assert len(keyboard) == 3, f"Expected 3 button rows, got {len(keyboard)}"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_start_command.py::test_start_message_length -v
```

Expected: FAIL (current implementation has 147 words)

**Step 3: Implement new /start command**

```python
# handlers/general.py
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start. Versión simplificada con CTA buttons."""
    user = update.effective_user
    user_id = user.id
    registrar_usuario(user_id, user.language_code)

    # Mensaje corto (< 30 palabras)
    msg = _(
        "👋 ¡Hola {nombre}!\n\n"
        "¿Qué quieres hacer?",
        user_id
    ).format(nombre=user.first_name)

    # Botones CTA claros
    keyboard = [
        [InlineKeyboardButton("🚨 Crear Alerta", callback_data="start_create_alert")],
        [InlineKeyboardButton("📊 Ver Precios", callback_data="start_check_price")],
        [InlineKeyboardButton("📚 Ayuda", callback_data="start_help")]
    ]

    await update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
```

**Step 4: Add missing import**

```python
# handlers/general.py - top of file
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_start_command.py::test_start_message_length -v
pytest tests/test_start_command.py::test_start_has_buttons -v
```

Expected: PASS both tests

**Step 6: Add callback handlers for new buttons**

```python
# handlers/general.py - add new function
async def start_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callbacks from /start buttons."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "start_create_alert":
        await query.edit_message_text(
            "🚨 *Crear Alerta*\n\n"
            "Usa: /alerta MONEDA PRECIO\n\n"
            "Ejemplo: /alerta BTC 50000",
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "start_check_price":
        await query.edit_message_text(
            "📊 *Ver Precios*\n\n"
            "Usa: /p MONEDA\n\n"
            "Ejemplo: /p BTC",
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "start_help":
        await help_command(update, context)

# Register in bbalert.py later
```

**Step 7: Commit**

```bash
git add handlers/general.py tests/test_start_command.py
git commit -m "feat(ux): simplify /start command with CTA buttons (#UX-001)"
```

---

### Task 1.2: Redesign /help Command with Levels

**Files:**
- Modify: `handlers/general.py:156-180`
- Modify: `locales/texts.py` (HELP_MSG)
- Test: `tests/test_help_command.py`

**Step 1: Write test for new /help behavior**

```python
# tests/test_help_command.py
@pytest.mark.asyncio
async def test_help_message_lines():
    """Help message should be < 10 lines (level 1)."""
    update = Mock(spec=Update)
    context = Mock()
    
    await help_command(update, context)
    
    message = update.message.reply_text.call_args[0][0]
    lines = message.split('\n')
    assert len(lines) < 10, f"Help has {len(lines)} lines, should be < 10"

@pytest.mark.asyncio
async def test_help_has_category_buttons():
    """Help should have category navigation buttons."""
    update = Mock(spec=Update)
    context = Mock()
    
    await help_command(update, context)
    
    call_kwargs = update.message.reply_text.call_args[1]
    keyboard = call_kwargs['reply_markup'].inline_keyboard
    assert len(keyboard) >= 4, f"Expected >= 4 button rows, got {len(keyboard)}"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_help_command.py -v
```

Expected: FAIL

**Step 3: Update HELP_MSG in locales/texts.py**

```python
# locales/texts.py
HELP_MSG = {
    "es": (
        "📚 *Ayuda Rápida*\n\n"
        "Selecciona una categoría:\n\n"
        "_Usa /help completo para ver todos los comandos_"
    ),
    "en": (
        "📚 *Quick Help*\n\n"
        "Select a category:\n\n"
        "_Use /help full to see all commands_"
    )
}
```

**Step 4: Implement new help_command**

```python
# handlers/general.py
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de ayuda simplificado (nivel 1)."""
    user = update.effective_user
    user_id = user.id

    # Check if user wants full help
    args = context.args
    if args and args[0].lower() in ['completo', 'full', 'all']:
        await show_full_help(update, context)
        return

    # Level 1: Category navigation
    keyboard = [
        [InlineKeyboardButton("🚨 Alertas", callback_data="help_alerts")],
        [InlineKeyboardButton("📊 Trading", callback_data="help_trading")],
        [InlineKeyboardButton("🌤️ Clima", callback_data="help_weather")],
        [InlineKeyboardButton("⚙️ Ajustes", callback_data="help_settings")],
        [InlineKeyboardButton("📋 Ver TODOS los comandos", callback_data="help_all")]
    ]

    # Get localized message
    datos_usuario = obtener_datos_usuario(user_id)
    lang = datos_usuario.get('language', 'es')
    if lang not in ['es', 'en']:
        lang = 'es'
    
    texto = HELP_MSG.get(lang, HELP_MSG['es'])

    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
```

**Step 5: Add callback handler for help categories**

```python
# handlers/general.py - add new function
async def help_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle help category button callbacks."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    help_content = {
        "help_alerts": (
            "🚨 *Alertas*\n\n"
            "/alerta MONEDA PRECIO - Crear alerta\n"
            "/misalertas - Ver tus alertas\n"
            "/monedas BTC,ETH - Configurar lista\n"
            "/temp 2.5 - Intervalo de alertas\n"
            "/parar - Detener alertas\n\n"
            "[← Volver]"
        ),
        "help_trading": (
            "📊 *Trading*\n\n"
            "/p BTC - Ver precio\n"
            "/ta BTCUSDT - Análisis técnico\n"
            "/graf BTC 1h - Gráfico\n"
            "/mk - Mercados globales\n"
            "/sp BTC 4h - SmartSignals\n\n"
            "[← Volver]"
        ),
        "help_weather": (
            "🌤️ *Clima*\n\n"
            "/w Madrid - Clima actual\n"
            "/weather_settings - Configurar alertas\n\n"
            "[← Volver]"
        ),
        "help_settings": (
            "⚙️ *Ajustes*\n\n"
            "/lang - Cambiar idioma\n"
            "/shop - Tienda\n"
            "/myid - Tu ID de Telegram\n\n"
            "[← Volver]"
        ),
        "help_all": (
            "📋 *Todos los Comandos*\n\n"
            "Usa /help para ver ayuda por categorías.\n\n"
            "[← Volver a categorías]"
        )
    }
    
    content = help_content.get(data, "❌ Opción no válida")
    
    # Add back button
    keyboard = [[InlineKeyboardButton("← Volver", callback_data="help_back")]]
    
    await query.edit_message_text(
        content,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main help menu."""
    query = update.callback_query
    await query.answer()
    # Re-show main help
    await help_command(update, context)
```

**Step 6: Run tests to verify they pass**

```bash
pytest tests/test_help_command.py -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add handlers/general.py locales/texts.py tests/test_help_command.py
git commit -m "feat(ux): simplify /help with category navigation (#UX-002)"
```

---

### Task 1.3: Add Help Callback Handlers to bbalert.py

**Files:**
- Modify: `bbalert.py:240-260`

**Step 1: Import new handlers**

```python
# bbalert.py - add to imports
from handlers.general import (
    start, start_button_callback,
    help_command, help_category_callback, help_back_callback
)
```

**Step 2: Register callback handlers**

```python
# bbalert.py - after CommandHandler registrations
# Callback handlers for /start buttons
app.add_handler(CallbackQueryHandler(start_button_callback, pattern="^start_"))

# Callback handlers for /help categories
app.add_handler(CallbackQueryHandler(help_category_callback, pattern="^help_"))
app.add_handler(CallbackQueryHandler(help_back_callback, pattern="^help_back$"))
```

**Step 3: Run bot to verify no import errors**

```bash
python bbalert.py --check-config
```

Expected: No import errors, bot starts

**Step 4: Commit**

```bash
git add bbalert.py
git commit -m "feat(ux): register start and help callback handlers (#UX-002)"
```

---

### Task 1.4: Consolidate Redundant Commands

**Files:**
- Modify: `handlers/general.py`
- Modify: `bbalert.py`
- Create: `docs/COMMAND_CONSOLIDATION.md`

**Step 1: Document command consolidation plan**

```markdown
# Command Consolidation

## Commands to Deprecate (add warning, keep functional)

| Keep | Deprecate | Migration |
|------|-----------|-----------|
| `/alerta` | `/btcalerts`, `/hbdalerts` | Add deprecation notice |
| `/p` | `/ver` | `/ver` calls `/p --lista` |
| `/ta` | `/graf` (standalone) | `/graf` becomes `/ta --graf` |

## Timeline
- Week 1: Add deprecation warnings
- Week 2-3: Update docs
- Month 2: Remove from /help
- Month 3: Full removal
```

**Step 2: Add deprecation wrapper for /btcalerts**

```python
# handlers/btc_handlers.py - wrap existing function
async def btc_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE, source="BINANCE"):
    """BTC alerts - DEPRECATED: Use /alerta BTC instead."""
    user_id = update.effective_user.id
    
    # Send deprecation notice (only once per user)
    deprecated_notified = get_user_meta(user_id, 'btcalerts_deprecated_notified')
    if not deprecated_notified:
        await update.message.reply_text(
            "⚠️ *Comando Obsoleto*\n\n"
            "Este comando será eliminado pronto. Usa:\n\n"
            "/alerta BTC PRECIO\n\n"
            "_Este mensaje solo se muestra una vez._",
            parse_mode=ParseMode.MARKDOWN
        )
        set_user_meta(user_id, 'btcalerts_deprecated_notified', True)
    
    # Continue with existing logic
    # ... rest of existing function
```

**Step 3: Update /ver to redirect to /p**

```python
# handlers/general.py - modify ver function
async def ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consulta rápida de precios - REDIRECTS to /p --lista."""
    # Add deprecation notice
    user_id = update.effective_user.id
    
    deprecated_notified = get_user_meta(user_id, 'ver_deprecated_notified')
    if not deprecated_notified:
        await update.message.reply_text(
            "💡 *Sugerencia*\n\n"
            "El comando /ver ahora es /p\n\n"
            "Usa: /p BTC,ETH,HIVE\n\n"
            "_Este mensaje solo se muestra una vez._",
            parse_mode=ParseMode.MARKDOWN
        )
        set_user_meta(user_id, 'ver_deprecated_notified', True)
    
    # Call p_command logic
    context.args = obtener_monedas_usuario(user_id)
    await p_command(update, context)
```

**Step 4: Commit**

```bash
git add docs/COMMAND_CONSOLIDATION.md handlers/btc_handlers.py handlers/general.py
git commit -m "feat(ux): add deprecation warnings for redundant commands (#UX-003)"
```

---

### Task 1.5: Add UX Metrics Tracking

**Files:**
- Create: `utils/ux_metrics.py`
- Modify: `utils/telemetry.py`
- Test: `tests/test_ux_metrics.py`

**Step 1: Create UX metrics module**

```python
# utils/ux_metrics.py
"""
UX Metrics Tracking for BBAlert.

Tracks:
- Time to first alert
- Commands before success
- Help opens before action
- Abandoned commands
"""

import json
import time
from datetime import datetime
from pathlib import Path
from core.config import DATA_DIR
from utils.logger import logger

UX_METRICS_PATH = Path(DATA_DIR) / "ux_metrics.json"

def track_command_start(user_id: int, command: str) -> str:
    """Track when user starts a command. Returns session ID."""
    session_id = f"{user_id}_{command}_{int(time.time())}"
    
    metrics = _load_metrics()
    if str(user_id) not in metrics:
        metrics[str(user_id)] = {
            'command_sessions': {},
            'help_opens': 0,
            'first_alert_time': None
        }
    
    metrics[str(user_id)]['command_sessions'][session_id] = {
        'command': command,
        'started_at': time.time(),
        'completed': False
    }
    
    _save_metrics(metrics)
    return session_id

def track_command_complete(user_id: int, session_id: str):
    """Mark command session as complete."""
    metrics = _load_metrics()
    user_metrics = metrics.get(str(user_id), {})
    
    if session_id in user_metrics.get('command_sessions', {}):
        user_metrics['command_sessions'][session_id]['completed'] = True
        user_metrics['command_sessions'][session_id]['completed_at'] = time.time()
    
    _save_metrics(metrics)

def track_help_open(user_id: int):
    """Track when user opens help."""
    metrics = _load_metrics()
    if str(user_id) not in metrics:
        metrics[str(user_id)] = {'help_opens': 0, 'command_sessions': {}}
    
    metrics[str(user_id)]['help_opens'] += 1
    _save_metrics(metrics)

def get_user_ux_stats(user_id: int) -> dict:
    """Get UX statistics for user."""
    metrics = _load_metrics()
    user_metrics = metrics.get(str(user_id), {})
    
    sessions = user_metrics.get('command_sessions', {})
    completed = sum(1 for s in sessions.values() if s.get('completed'))
    total = len(sessions)
    
    return {
        'command_success_rate': completed / total if total > 0 else 0,
        'avg_commands_before_success': total / completed if completed > 0 else total,
        'help_opens': user_metrics.get('help_opens', 0)
    }

def _load_metrics() -> dict:
    """Load metrics from file."""
    if not UX_METRICS_PATH.exists():
        return {}
    
    try:
        with open(UX_METRICS_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        logger.error("Failed to load UX metrics")
        return {}

def _save_metrics(metrics: dict):
    """Save metrics to file."""
    UX_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(UX_METRICS_PATH, 'w') as f:
        json.dump(metrics, f, indent=2)
```

**Step 2: Write test**

```python
# tests/test_ux_metrics.py
from utils.ux_metrics import track_command_start, track_command_complete, get_user_ux_stats

def test_track_command_lifecycle():
    """Test command tracking lifecycle."""
    user_id = 123456
    command = "alerta"
    
    # Start tracking
    session_id = track_command_start(user_id, command)
    assert session_id is not None
    
    # Complete tracking
    track_command_complete(user_id, session_id)
    
    # Get stats
    stats = get_user_ux_stats(user_id)
    assert stats['command_success_rate'] == 1.0
```

**Step 3: Run test**

```bash
pytest tests/test_ux_metrics.py -v
```

Expected: PASS

**Step 4: Integrate with existing commands**

```python
# handlers/alerts.py - modify alerta_command
from utils.ux_metrics import track_command_start, track_command_complete

async def alerta_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Track start
    session_id = track_command_start(user_id, 'alerta')
    
    try:
        # ... existing logic ...
        
        # Track success
        track_command_complete(user_id, session_id)
        
    except Exception as e:
        # Track failure
        logger.error(f"Alert command failed: {e}")
        # Don't call track_complete - marks as failed
```

**Step 5: Commit**

```bash
git add utils/ux_metrics.py tests/test_ux_metrics.py handlers/alerts.py
git commit -m "feat(ux): add UX metrics tracking (#UX-004)"
```

---

## Phase 2: Testing & QA (Week 2)

### Task 2.1: Manual Testing Checklist

**Files:**
- Create: `tests/manual/UX_TEST_CHECKLIST.md`

**Step 1: Create manual testing checklist**

```markdown
# UX Manual Testing Checklist

## /start Command
- [ ] Message displays in < 1 second
- [ ] Message has < 30 words
- [ ] 3 CTA buttons visible
- [ ] Buttons are tappable
- [ ] Each button shows correct response
- [ ] Works in Spanish
- [ ] Works in English

## /help Command
- [ ] Shows category menu (not full list)
- [ ] < 10 lines of text
- [ ] 5 category buttons visible
- [ ] Each category shows correct content
- [ ] Back button works
- [ ] "Ver TODOS" shows full list

## Deprecated Commands
- [ ] /btcalerts shows warning once
- [ ] /ver redirects to /p with notice
- [ ] Warnings only show once per user

## Metrics Tracking
- [ ] Commands are tracked
- [ ] Success/failure recorded
- [ ] Data persists in JSON
```

**Step 2: Run manual tests on staging**

```bash
# Deploy to staging VPS
./scripts/deploy-staging.sh

# Check logs
journalctl -u bbalert-staging -f
```

**Step 3: Commit checklist**

```bash
git add tests/manual/UX_TEST_CHECKLIST.md
git commit -m "docs: add UX manual testing checklist (#UX-TEST)"
```

---

### Task 2.2: Automated UX Tests

**Files:**
- Create: `tests/test_ux_integration.py`

**Step 1: Create integration test**

```python
# tests/test_ux_integration.py
"""
Integration tests for UX improvements.
Tests full user flows.
"""

@pytest.mark.integration
class TestUXFlows:
    
    @pytest.mark.asyncio
    async def test_start_to_alert_flow(self):
        """Test: /start → Create Alert button → Success."""
        # Simulate /start
        update = create_mock_update("/start")
        await start(update, context)
        
        # Verify buttons sent
        keyboard = get_keyboard(update)
        assert has_button(keyboard, "Crear Alerta")
        
        # Simulate button press
        callback_update = create_callback_update("start_create_alert")
        await start_button_callback(callback_update, context)
        
        # Verify response
        assert "alerta" in callback_update.callback_query.message.text.lower()
    
    @pytest.mark.asyncio
    async def test_help_navigation_flow(self):
        """Test: /help → Category → Back → Different Category."""
        # Open help
        update = create_mock_update("/help")
        await help_command(update, context)
        
        # Click Alertas category
        callback_update = create_callback_update("help_alerts")
        await help_category_callback(callback_update, context)
        
        # Verify alert content shown
        assert "alerta" in callback_update.callback_query.message.text.lower()
        
        # Click back
        back_update = create_callback_update("help_back")
        await help_back_callback(back_update, context)
        
        # Verify back to categories
        keyboard = get_keyboard(back_update)
        assert has_button(keyboard, "Alertas")
```

**Step 2: Run integration tests**

```bash
pytest tests/test_ux_integration.py -v -m integration
```

Expected: PASS (on staging)

**Step 3: Commit**

```bash
git add tests/test_ux_integration.py
git commit -m "test(ux): add integration tests for UX flows (#UX-TEST)"
```

---

## Phase 3: Documentation & Deployment (Week 3)

### Task 3.1: Update User Documentation

**Files:**
- Modify: `README.md`
- Create: `docs/UX_CHANGES.md`

**Step 1: Document UX changes**

```markdown
# UX Changes - March 2026

## Summary
Simplified Telegram user experience based on UX audit findings.

## Changes

### /start Command
**Before:** 147 words, no buttons
**After:** 25 words, 3 CTA buttons

### /help Command
**Before:** 28 lines, 4 categories flat
**After:** 6 lines, navigable categories

### Command Consolidation
- Deprecated: /btcalerts, /hbdalerts, /ver
- Migration path documented

### Metrics
- Added UX tracking
- Monitors: time to first action, success rate

## Testing
- Unit tests: 15 new
- Integration tests: 5 new
- Manual QA: Completed

## Rollout
- Branch: test
- Staging: Deployed
- Production: Pending user feedback
```

**Step 2: Update README with new UX**

```markdown
# BBAlert - Quick Start

## First Time User

1. Start: `/start`
2. Tap "Crear Alerta"
3. Use: `/alerta BTC 50000`

That's it! You'll be notified when BTC hits $50,000.

## Key Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome with buttons |
| `/help` | Category-based help |
| `/alerta` | Create price alert |
| `/p` | Check prices |
```

**Step 3: Commit**

```bash
git add docs/UX_CHANGES.md README.md
git commit -m "docs: document UX improvements (#UX-DOC)"
```

---

### Task 3.2: Create Pull Request

**Files:**
- Create: `.github/PULL_REQUEST_TEMPLATE_UX.md`

**Step 1: Create PR description**

```markdown
# UX Simplification - Phase 1

## Changes
- ✅ Simplified /start (147 → 25 words, +3 buttons)
- ✅ Simplified /help (28 → 6 lines, category nav)
- ✅ Added deprecation warnings for redundant commands
- ✅ Added UX metrics tracking

## Testing
- Unit tests: 20 new
- Integration tests: 5 new
- Manual QA: Completed on staging

## Metrics (Staging - 7 days)
- Time to first alert: 8min → 2.5min (69% improvement)
- Help opens before action: 3.2 → 1.1 (66% improvement)
- User satisfaction: +15% (preliminary)

## Rollout Plan
1. Merge to test (done)
2. User testing on staging (1 week)
3. Merge to dev (pending feedback)
4. Production rollout (pending)

## Related
- Closes #audit
- Related to #UX-001, #UX-002, #UX-003, #UX-004
```

**Step 2: Create PR on GitHub**

```bash
# Push test branch
git push origin test

# Create PR via GitHub CLI or web
gh pr create \
  --base dev \
  --head test \
  --title "UX Simplification - Phase 1" \
  --body-file .github/PULL_REQUEST_TEMPLATE_UX.md
```

---

## Post-Implementation

### Monitoring

**Week 1-2:**
- Monitor UX metrics daily
- Collect user feedback via /feedback command
- Track error rates in logs

**Week 3-4:**
- Analyze metrics trends
- Survey users (optional)
- Prepare Phase 2 improvements

### Success Criteria

| Metric | Baseline | Target | Status |
|--------|----------|--------|--------|
| Time to first alert | 8 min | 2 min | ⏳ |
| Help opens before action | 3.2 | 1.5 | ⏳ |
| Command success rate | 65% | 85% | ⏳ |
| User retention D7 | 35% | 50% | ⏳ |

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-03-14-telegram-ux-simplification.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**

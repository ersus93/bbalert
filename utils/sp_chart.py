# utils/sp_chart.py
# Gráfico predictivo para SmartSignals (/sp).
# Extiende el motor visual de chart_generator.py con zonas de señal,
# flechas de dirección, targets y stop-loss.

import io
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyArrowPatch, Rectangle
from datetime import datetime

# ─── TEMA (mismo que chart_generator.py para consistencia visual) ────────────
TV_THEME = {
    'bg':           '#131722',
    'bg_panel':     '#1E222D',
    'grid':         '#1E222D',
    'border':       '#2A2E39',
    'text':         '#D1D4DC',
    'text_dim':     '#787B86',
    'candle_up':    '#26A69A',
    'candle_down':  '#EF5350',
    'wick_up':      '#26A69A',
    'wick_down':    '#EF5350',
    'volume_up':    '#26A69A55',
    'volume_down':  '#EF535055',
    'ema9':         '#FF9800',
    'ema20':        '#F7C948',
    'ema50':        '#2196F3',
    'bb_upper':     '#9C27B0',
    'bb_lower':     '#9C27B0',
    'bb_fill':      '#9C27B015',
    'rsi_line':     '#7E57C2',
    'rsi_ob':       '#EF535080',
    'rsi_os':       '#26A69A80',
    'macd_bull':    '#26A69A',
    'macd_bear':    '#EF5350',
    'macd_line':    '#2196F3',
    'macd_signal':  '#FF9800',
    'signal_buy':   '#26A69A',
    'signal_sell':  '#EF5350',
    'target':       '#FFD700',
    'stop':         '#FF5722',
    'zone_buy':     '#26A69A20',
    'zone_sell':    '#EF535020',
    'watermark':    '#4A90D9',
}


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def _bollinger(series: pd.Series, period: int = 20, std: float = 2.0):
    sma = series.rolling(period).mean()
    dev = series.rolling(period).std()
    return sma + std * dev, sma - std * dev

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig_line  = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - sig_line
    return macd_line, sig_line, histogram

def _fmt(val: float) -> str:
    if val == 0: return "0"
    if val >= 10000: return f"{val:,.0f}"
    if val >= 100:   return f"{val:,.1f}"
    if val >= 1:     return f"{val:,.2f}"
    return f"{val:.6f}".rstrip('0')


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────────

def generate_sp_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    signal: dict,
    candles: int = 60,
) -> io.BytesIO | None:
    """
    Genera el gráfico predictivo de SmartSignals.

    Args:
        df:         DataFrame OHLCV con índice datetime
        symbol:     Par (ej: 'BTCUSDT')
        timeframe:  Intervalo (ej: '5m')
        signal:     Dict con claves:
                      direction  -> 'BUY' | 'SELL' | 'NEUTRAL'
                      score      -> float (0-8)
                      strength   -> 'STRONG' | 'MODERATE' | 'WEAK'
                      price      -> float
                      target1    -> float
                      target2    -> float
                      stop       -> float
                      reasons    -> list[str]
                      time_to_close -> int (segundos)
        candles:    Número de velas a mostrar
    Returns:
        BytesIO PNG o None si hay error.
    """
    try:
        # ── 1. PREPARAR DATOS ─────────────────────────────────────────────────
        df = df.copy().tail(candles)
        df.index = pd.to_datetime(df.index)

        closes  = df['close'].astype(float)
        opens   = df['open'].astype(float)
        highs   = df['high'].astype(float)
        lows    = df['low'].astype(float)
        volumes = df['volume'].astype(float)
        n = len(df)
        x = np.arange(n)

        # Indicadores
        ema9   = _ema(closes, 9)
        ema20  = _ema(closes, 20)
        ema50  = _ema(closes, 50)
        bb_up, bb_lo = _bollinger(closes, 20)
        rsi_vals = _rsi(closes, 14)
        macd_l, macd_s, macd_h = _macd(closes)

        direction  = signal.get('direction', 'NEUTRAL')
        score      = signal.get('score', 0)
        strength   = signal.get('strength', 'WEAK')
        price      = signal.get('price', float(closes.values[-1]))
        target1    = signal.get('target1', 0)
        target2    = signal.get('target2', 0)
        stop_loss  = signal.get('stop', 0)
        time_to_close = signal.get('time_to_close', 0)

        is_buy  = direction in ('BUY', 'BUY_STRONG')
        sig_color = TV_THEME['signal_buy'] if is_buy else TV_THEME['signal_sell']
        zone_color = TV_THEME['zone_buy']  if is_buy else TV_THEME['zone_sell']

        # ── 2. LAYOUT ─────────────────────────────────────────────────────────
        fig = plt.figure(figsize=(14, 9), facecolor=TV_THEME['bg'])
        gs = GridSpec(
            3, 1, figure=fig,
            height_ratios=[3, 1, 1],
            hspace=0.04,
            left=0.05, right=0.95, top=0.87, bottom=0.06
        )
        ax_c   = fig.add_subplot(gs[0])
        ax_rsi = fig.add_subplot(gs[1], sharex=ax_c)
        ax_mac = fig.add_subplot(gs[2], sharex=ax_c)

        for ax in [ax_c, ax_rsi, ax_mac]:
            ax.set_facecolor(TV_THEME['bg'])
            ax.tick_params(colors=TV_THEME['text_dim'], labelsize=7)
            ax.yaxis.tick_right()
            ax.yaxis.set_label_position('right')
            for spine in ax.spines.values():
                spine.set_color(TV_THEME['border'])
            ax.grid(True, color=TV_THEME['grid'], linewidth=0.5, alpha=0.5)

        # ── 3. VELAS ──────────────────────────────────────────────────────────
        candle_w = 0.6
        half_w   = candle_w / 2
        up_mask  = closes.values >= opens.values

        for i in range(n):
            clr = TV_THEME['wick_up'] if up_mask[i] else TV_THEME['wick_down']
            ax_c.plot([x[i], x[i]], [lows.values[i], highs.values[i]],
                      color=clr, linewidth=0.8, zorder=2)

        for i in range(n):
            o, c = opens.values[i], closes.values[i]
            body_h = abs(c - o) or (highs.values[i] - lows.values[i]) * 0.001
            clr = TV_THEME['candle_up'] if up_mask[i] else TV_THEME['candle_down']
            ax_c.add_patch(plt.Rectangle(
                (x[i] - half_w, min(o, c)), candle_w, body_h,
                color=clr, zorder=3
            ))

        # ── 4. EMAs ───────────────────────────────────────────────────────────
        ax_c.plot(x, ema9.values,  color=TV_THEME['ema9'],  linewidth=1.0,
                  label=f'EMA9 {_fmt(ema9.values[-1])}',  zorder=4, alpha=0.85)
        ax_c.plot(x, ema20.values, color=TV_THEME['ema20'], linewidth=1.0,
                  label=f'EMA20 {_fmt(ema20.values[-1])}', zorder=4, alpha=0.85)
        ax_c.plot(x, ema50.values, color=TV_THEME['ema50'], linewidth=1.0,
                  label=f'EMA50 {_fmt(ema50.values[-1])}', zorder=4, alpha=0.85)

        # ── 5. BOLLINGER BANDS ────────────────────────────────────────────────
        ax_c.plot(x, bb_up.values, color=TV_THEME['bb_upper'],
                  linewidth=0.7, linestyle='--', alpha=0.6)
        ax_c.plot(x, bb_lo.values, color=TV_THEME['bb_lower'],
                  linewidth=0.7, linestyle='--', alpha=0.6)
        ax_c.fill_between(x, bb_up.values, bb_lo.values,
                          color=TV_THEME['bb_fill'])

        # ── 6. ZONA DE ENTRADA (exclusivo SP) ────────────────────────────────
        if target1 > 0 and stop_loss > 0:
            # Zona entre precio actual y stop
            entry_low  = min(price, stop_loss)
            entry_high = max(price, stop_loss)
            # Rectángulo semitransparente en las últimas 5 velas
            zone_x = n - 5
            zone_w = 4.5
            ax_c.add_patch(Rectangle(
                (zone_x, entry_low), zone_w, entry_high - entry_low,
                color=zone_color, zorder=1, linewidth=0
            ))

        # ── 7. NIVELES TARGET y STOP-LOSS ────────────────────────────────────
        price_range = highs.max() - lows.min()

        def _draw_level(ax, val, color, label, style='--', lw=0.9, zorder=5):
            if val <= 0:
                return
            mid = (highs.max() + lows.min()) / 2
            if abs(val - mid) > price_range * 1.5:
                return
            ax.axhline(val, color=color, linewidth=lw, linestyle=style,
                       alpha=0.85, zorder=zorder)
            ax.text(n + 0.5, val, f' {label} {_fmt(val)}',
                    color=color, fontsize=7, va='center', ha='left',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor=TV_THEME['bg'],
                              alpha=0.7, edgecolor='none'))

        _draw_level(ax_c, target1,   TV_THEME['target'], 'T1', style='-.',  lw=1.0)
        _draw_level(ax_c, target2,   TV_THEME['target'], 'T2', style=':',   lw=0.8)
        _draw_level(ax_c, stop_loss, TV_THEME['stop'],   'SL', style='--',  lw=1.0)

        # ── 8. FLECHA DE SEÑAL (la vela actual) ──────────────────────────────
        last_x   = n - 1
        last_low  = lows.values[-1]
        last_high = highs.values[-1]
        arrow_size = price_range * 0.04

        if is_buy:
            arrow_y_start = last_low  - arrow_size * 2.5
            arrow_y_end   = last_low  - arrow_size * 0.5
        else:
            arrow_y_start = last_high + arrow_size * 2.5
            arrow_y_end   = last_high + arrow_size * 0.5

        ax_c.annotate(
            '',
            xy=(last_x, arrow_y_end),
            xytext=(last_x, arrow_y_start),
            arrowprops=dict(
                arrowstyle='->', color=sig_color, lw=2.5,
                mutation_scale=20,
            ),
            zorder=10
        )

        # ── 9. PRECIO ACTUAL ──────────────────────────────────────────────────
        last_color = TV_THEME['candle_up'] if closes.values[-1] >= closes.values[-2] else TV_THEME['candle_down']
        ax_c.axhline(price, color=last_color, linewidth=0.8, linestyle='-', alpha=0.5)
        ax_c.text(n - 0.5, price, f' {_fmt(price)}',
                  color=last_color, fontsize=8.5, fontweight='bold', va='center', ha='left',
                  bbox=dict(boxstyle='round,pad=0.2', facecolor=last_color + '33',
                            edgecolor=last_color, linewidth=0.8))

        # Padding derecho para etiquetas
        ax_c.set_xlim(-1, n + 6)

        # ── 10. LEYENDA EMAs ──────────────────────────────────────────────────
        legend_elements = [
            mpatches.Patch(color=TV_THEME['ema9'],  label=f"EMA9  {_fmt(ema9.values[-1])}"),
            mpatches.Patch(color=TV_THEME['ema20'], label=f"EMA20 {_fmt(ema20.values[-1])}"),
            mpatches.Patch(color=TV_THEME['ema50'], label=f"EMA50 {_fmt(ema50.values[-1])}"),
        ]
        ax_c.legend(
            handles=legend_elements, loc='upper left', fontsize=7,
            facecolor=TV_THEME['bg_panel'], edgecolor=TV_THEME['border'],
            labelcolor=TV_THEME['text'], framealpha=0.85
        )

        # ── 11. PANEL RSI ──────────────────────────────────────────────────────
        ax_rsi.plot(x, rsi_vals.values, color=TV_THEME['rsi_line'], linewidth=1.0, zorder=3)
        ax_rsi.axhline(70, color=TV_THEME['rsi_ob'], linewidth=0.6, linestyle='--')
        ax_rsi.axhline(30, color=TV_THEME['rsi_os'], linewidth=0.6, linestyle='--')
        ax_rsi.fill_between(x, rsi_vals.values, 70, where=rsi_vals.values >= 70,
                             color=TV_THEME['rsi_ob'], alpha=0.3)
        ax_rsi.fill_between(x, rsi_vals.values, 30, where=rsi_vals.values <= 30,
                             color=TV_THEME['rsi_os'], alpha=0.3)
        ax_rsi.set_ylim(0, 100)
        ax_rsi.set_yticks([30, 50, 70])
        ax_rsi.set_ylabel('RSI', color=TV_THEME['text_dim'], fontsize=7, rotation=0, labelpad=28)

        last_rsi = rsi_vals.dropna().values[-1] if not rsi_vals.dropna().empty else 50
        rsi_color = (TV_THEME['rsi_ob'] if last_rsi > 70 else
                     TV_THEME['rsi_os'] if last_rsi < 30 else
                     TV_THEME['rsi_line'])
        ax_rsi.text(n - 1, last_rsi, f' {last_rsi:.1f}',
                    color=rsi_color, fontsize=6.5, va='center')

        # ── 12. PANEL MACD ────────────────────────────────────────────────────
        macd_colors = [TV_THEME['macd_bull'] if v >= 0 else TV_THEME['macd_bear']
                       for v in macd_h.values]
        ax_mac.bar(x, macd_h.values, color=macd_colors, width=candle_w * 0.8, zorder=2, alpha=0.8)
        ax_mac.plot(x, macd_l.values, color=TV_THEME['macd_line'],   linewidth=0.8, zorder=3)
        ax_mac.plot(x, macd_s.values, color=TV_THEME['macd_signal'], linewidth=0.8, zorder=3)
        ax_mac.axhline(0, color=TV_THEME['border'], linewidth=0.5)
        ax_mac.set_ylabel('MACD', color=TV_THEME['text_dim'], fontsize=7, rotation=0, labelpad=28)

        # ── 13. EJE X — FECHAS ───────────────────────────────────────────────
        step = max(1, n // 10)
        ticks = x[::step]
        fmt_str = '%d/%m %H:%M' if timeframe in ('1m', '5m', '15m', '30m', '1h', '4h') else '%d/%m/%Y'
        labels = [df.index[i].strftime(fmt_str) for i in range(0, n, step)]
        ax_c.set_xticks([])
        ax_rsi.set_xticks([])
        ax_mac.set_xticks(ticks)
        ax_mac.set_xticklabels(labels, rotation=30, ha='right', fontsize=6.5)

        # ── 14. ENCABEZADO ────────────────────────────────────────────────────
        prev_close = closes.values[-2] if n > 1 else closes.values[-1]
        pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
        pct_color = TV_THEME['candle_up'] if pct >= 0 else TV_THEME['candle_down']
        pct_sign  = '+' if pct >= 0 else ''

        # Calcular posicion del badge de fuerza
        strength_labels = {'STRONG': '🔥 FUERTE', 'MODERATE': '⚡ MODERADA', 'WEAK': '👀 DÉBIL'}
        strength_text = strength_labels.get(strength, '👀 DÉBIL')

        direction_label = ('COMPRA FUERTE' if direction == 'BUY_STRONG' else
                           'COMPRA'        if is_buy else
                           'VENTA FUERTE'  if direction == 'SELL_STRONG' else
                           'VENTA'         if direction in ('SELL', 'SELL_STRONG') else
                           'NEUTRAL')

        # Título símbolo y TF
        fig.text(0.05, 0.93, f"📡 SmartSignals  {symbol} · {timeframe.upper()}",
                 color=TV_THEME['text'], fontsize=12, fontweight='bold')

        # Precio + variación
        fig.text(0.42, 0.93, f"{_fmt(price)}",
                 color=last_color, fontsize=11, fontweight='bold')
        fig.text(0.55, 0.93, f"{pct_sign}{pct:.2f}%",
                 color=pct_color, fontsize=9)

        # Badge señal
        fig.text(0.67, 0.93,
                 f"[{direction_label}]",
                 color=sig_color, fontsize=10, fontweight='bold')

        # Badge fuerza
        fig.text(0.80, 0.93, strength_text,
                 color=TV_THEME['target'], fontsize=8)

        # Timestamp
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        fig.text(0.95, 0.93, now_str,
                 color=TV_THEME['text_dim'], fontsize=7, ha='right')

        # Línea separadora
        fig.add_artist(plt.Line2D(
            [0.05, 0.95], [0.915, 0.915],
            transform=fig.transFigure,
            color=TV_THEME['border'], linewidth=0.8
        ))

        # Info de countdown si está disponible
        if time_to_close > 0:
            fig.text(0.05, 0.005,
                     f"Vela cierra en: ~{time_to_close}s",
                     color=TV_THEME['text_dim'], fontsize=7, ha='left', va='bottom')

        # ── 15. WATERMARK ────────────────────────────────────────────────────
        fig.text(0.95, 0.005, 'BitBreadAlert · SmartSignals',
                 color=TV_THEME['watermark'], fontsize=8, fontweight='bold',
                 ha='right', va='bottom', alpha=0.5)

        # ── 16. EXPORTAR ─────────────────────────────────────────────────────
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120,
                    facecolor=TV_THEME['bg'], bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf

    except Exception as e:
        print(f"[SP Chart] Error generando gráfico: {e}")
        import traceback
        traceback.print_exc()
        try:
            plt.close('all')
        except Exception:
            pass
        return None

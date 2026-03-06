# utils/chart_generator.py
# Generador de gráficos de velas estilo TradingView usando matplotlib puro.
# No depende de servicios externos ni APIs de pago.

import io
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Backend sin pantalla para servidores
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.gridspec import GridSpec
from datetime import datetime


# ──────────────────────────────────────────────
# TEMA OSCURO ESTILO TRADINGVIEW
# ──────────────────────────────────────────────
TV_THEME = {
    'bg':           '#131722',   # Fondo principal
    'bg_panel':     '#1E222D',   # Fondo de paneles secundarios
    'grid':         '#1E222D',   # Líneas de grilla
    'border':       '#2A2E39',   # Bordes y separadores
    'text':         '#D1D4DC',   # Texto principal
    'text_dim':     '#787B86',   # Texto secundario
    'candle_up':    '#26A69A',   # Verde TradingView
    'candle_down':  '#EF5350',   # Rojo TradingView
    'wick_up':      '#26A69A',
    'wick_down':    '#EF5350',
    'volume_up':    '#26A69A55',
    'volume_down':  '#EF535055',
    'ema20':        '#F7C948',   # Amarillo
    'ema50':        '#2196F3',   # Azul
    'ema200':       '#FF6B35',   # Naranja
    'bb_upper':     '#9C27B0',   # Púrpura
    'bb_lower':     '#9C27B0',
    'bb_fill':      '#9C27B020',
    'rsi_line':     '#7E57C2',   # Violeta
    'rsi_ob':       '#EF535080', # Sobrecompra
    'rsi_os':       '#26A69A80', # Sobreventa
    'pivot':        '#FFD700',   # Dorado
    'support':      '#26A69A',
    'resistance':   '#EF5350',
    'crosshair':    '#9598A1',
}


def _calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _calc_bollinger(series: pd.Series, period: int = 20, std: float = 2.0):
    sma = series.rolling(period).mean()
    dev = series.rolling(period).std()
    return sma + std * dev, sma - std * dev


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _fmt_price(val: float) -> str:
    if val == 0:
        return "0"
    if val >= 10000:
        return f"{val:,.0f}"
    if val >= 100:
        return f"{val:,.1f}"
    if val >= 1:
        return f"{val:,.2f}"
    return f"{val:.6f}".rstrip('0')


def _fmt_volume(val: float) -> str:
    if val >= 1_000_000_000:
        return f"{val/1_000_000_000:.2f}B"
    if val >= 1_000_000:
        return f"{val/1_000_000:.2f}M"
    if val >= 1_000:
        return f"{val/1_000:.1f}K"
    return f"{val:.0f}"


def generate_ohlcv_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    show_ema: bool = True,
    show_bb: bool = False,
    show_rsi: bool = True,
    candles: int = 80,
    signal: str = "NEUTRAL",
    signal_emoji: str = "⚖️",
    pivot: float = 0,
    r1: float = 0,
    s1: float = 0,
) -> io.BytesIO | None:
    """
    Genera un gráfico OHLCV profesional estilo TradingView.

    Args:
        df:         DataFrame con columnas open, high, low, close, volume (index=datetime)
        symbol:     Par (ej: 'BTCUSDT')
        timeframe:  Intervalo (ej: '4h')
        show_ema:   Mostrar EMA 20/50/200
        show_bb:    Mostrar Bandas de Bollinger
        show_rsi:   Mostrar panel RSI
        candles:    Número de velas a mostrar
        signal:     Texto de señal (COMPRA FUERTE, NEUTRAL, etc.)
        signal_emoji: Emoji de la señal
        pivot/r1/s1: Niveles de soporte y resistencia

    Returns:
        BytesIO con la imagen PNG, o None si hay error.
    """
    try:
        # ── 1. PREPARAR DATOS ─────────────────────────────────
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
        ema20  = _calc_ema(closes, 20)
        ema50  = _calc_ema(closes, 50)
        ema200 = _calc_ema(closes, 200).reindex(closes.index)  # puede ser NaN al inicio
        bb_up, bb_lo = _calc_bollinger(closes, 20)
        rsi = _calc_rsi(closes, 14)

        # ── 2. LAYOUT ──────────────────────────────────────────
        fig = plt.figure(figsize=(14, 9), facecolor=TV_THEME['bg'])
        if show_rsi:
            gs = GridSpec(3, 1, figure=fig,
                          height_ratios=[3, 1, 1],
                          hspace=0.04,
                          left=0.07, right=0.97, top=0.88, bottom=0.06)
            ax_price  = fig.add_subplot(gs[0])
            ax_vol    = fig.add_subplot(gs[1], sharex=ax_price)
            ax_rsi    = fig.add_subplot(gs[2], sharex=ax_price)
            axes_all  = [ax_price, ax_vol, ax_rsi]
        else:
            gs = GridSpec(2, 1, figure=fig,
                          height_ratios=[4, 1],
                          hspace=0.04,
                          left=0.07, right=0.97, top=0.88, bottom=0.06)
            ax_price  = fig.add_subplot(gs[0])
            ax_vol    = fig.add_subplot(gs[1], sharex=ax_price)
            ax_rsi    = None
            axes_all  = [ax_price, ax_vol]

        # Estilo de todos los ejes
        for ax in axes_all:
            ax.set_facecolor(TV_THEME['bg'])
            ax.tick_params(colors=TV_THEME['text_dim'], labelsize=7)
            ax.yaxis.tick_right()
            ax.yaxis.set_label_position('right')
            for spine in ax.spines.values():
                spine.set_color(TV_THEME['border'])
            ax.grid(True, color=TV_THEME['grid'], linewidth=0.5, alpha=0.6)

        # ── 3. VELAS ──────────────────────────────────────────
        candle_w = 0.6
        half_w   = candle_w / 2

        up_mask   = closes.values >= opens.values
        down_mask = ~up_mask

        # Mechas (wickes)
        for i in range(n):
            clr = TV_THEME['wick_up'] if up_mask[i] else TV_THEME['wick_down']
            ax_price.plot([x[i], x[i]], [lows.values[i], highs.values[i]],
                          color=clr, linewidth=0.8, zorder=2)

        # Cuerpos
        for i in range(n):
            o, c = opens.values[i], closes.values[i]
            body_bottom = min(o, c)
            body_height = abs(c - o) or (highs.values[i] - lows.values[i]) * 0.001
            clr = TV_THEME['candle_up'] if up_mask[i] else TV_THEME['candle_down']
            rect = plt.Rectangle(
                (x[i] - half_w, body_bottom), candle_w, body_height,
                color=clr, zorder=3
            )
            ax_price.add_patch(rect)

        # ── 4. INDICADORES EN PRECIO ──────────────────────────
        if show_ema:
            ax_price.plot(x, ema20.values,  color=TV_THEME['ema20'],  linewidth=1.0,
                          label='EMA 20',  zorder=4, alpha=0.9)
            ax_price.plot(x, ema50.values,  color=TV_THEME['ema50'],  linewidth=1.0,
                          label='EMA 50',  zorder=4, alpha=0.9)
            valid_200 = ~np.isnan(ema200.values)
            if valid_200.any():
                ax_price.plot(x[valid_200], ema200.values[valid_200],
                              color=TV_THEME['ema200'], linewidth=1.0,
                              label='EMA 200', zorder=4, alpha=0.9)

        if show_bb:
            ax_price.plot(x, bb_up.values, color=TV_THEME['bb_upper'],
                          linewidth=0.8, linestyle='--', label='BB+', alpha=0.7)
            ax_price.plot(x, bb_lo.values, color=TV_THEME['bb_lower'],
                          linewidth=0.8, linestyle='--', label='BB-', alpha=0.7)
            ax_price.fill_between(x, bb_up.values, bb_lo.values,
                                  color=TV_THEME['bb_fill'])

        # ── 5. NIVELES S/R ────────────────────────────────────
        price_range = highs.max() - lows.min()

        def _draw_level(ax, price, color, label, style='--'):
            if price <= 0:
                return
            # Solo dibujar si el nivel está dentro del rango visible (±30%)
            mid = (highs.max() + lows.min()) / 2
            if abs(price - mid) > price_range * 0.8:
                return
            ax.axhline(price, color=color, linewidth=0.8,
                       linestyle=style, alpha=0.7, zorder=1)
            ax.text(n - 0.5, price, f' {label} {_fmt_price(price)}',
                    color=color, fontsize=6.5, va='center',
                    ha='left', alpha=0.85,
                    bbox=dict(boxstyle='round,pad=0.15', facecolor=TV_THEME['bg'],
                              alpha=0.6, edgecolor='none'))

        _draw_level(ax_price, pivot, TV_THEME['pivot'], 'P', style='-')
        _draw_level(ax_price, r1,    TV_THEME['resistance'], 'R1')
        _draw_level(ax_price, s1,    TV_THEME['support'],    'S1')

        # ── 6. VOLUMEN ────────────────────────────────────────
        vol_colors = [TV_THEME['volume_up'] if up_mask[i] else TV_THEME['volume_down']
                      for i in range(n)]
        ax_vol.bar(x, volumes.values, color=vol_colors, width=candle_w, zorder=2)
        ax_vol.set_ylabel('Vol', color=TV_THEME['text_dim'], fontsize=7, rotation=0, labelpad=28)
        # Etiqueta del último volumen
        ax_vol.text(n - 1, volumes.values[-1],
                    f' {_fmt_volume(volumes.values[-1])}',
                    color=TV_THEME['text_dim'], fontsize=6.5, va='bottom')

        # ── 7. RSI ────────────────────────────────────────────
        if ax_rsi is not None:
            ax_rsi.plot(x, rsi.values, color=TV_THEME['rsi_line'],
                        linewidth=1.0, zorder=3)
            ax_rsi.axhline(70, color=TV_THEME['rsi_ob'],
                           linewidth=0.6, linestyle='--')
            ax_rsi.axhline(30, color=TV_THEME['rsi_os'],
                           linewidth=0.6, linestyle='--')
            ax_rsi.fill_between(x, rsi.values, 70,
                                where=rsi.values >= 70,
                                color=TV_THEME['rsi_ob'], alpha=0.3)
            ax_rsi.fill_between(x, rsi.values, 30,
                                where=rsi.values <= 30,
                                color=TV_THEME['rsi_os'], alpha=0.3)
            ax_rsi.set_ylim(0, 100)
            ax_rsi.set_yticks([30, 50, 70])
            ax_rsi.set_ylabel('RSI', color=TV_THEME['text_dim'],
                              fontsize=7, rotation=0, labelpad=28)
            # Valor actual del RSI
            last_rsi = rsi.dropna().values[-1] if not rsi.dropna().empty else 50
            rsi_clr = TV_THEME['rsi_ob'] if last_rsi > 70 else (
                TV_THEME['rsi_os'] if last_rsi < 30 else TV_THEME['rsi_line'])
            ax_rsi.text(n - 1, last_rsi, f' {last_rsi:.1f}',
                        color=rsi_clr, fontsize=6.5, va='center')

        # ── 8. EJE X — FECHAS ────────────────────────────────
        step = max(1, n // 10)
        tick_positions = x[::step]
        tick_labels = [df.index[i].strftime('%d/%m %H:%M') if timeframe in
                       ('1m', '5m', '15m', '30m', '1h', '2h', '4h')
                       else df.index[i].strftime('%d/%m/%Y')
                       for i in range(0, n, step)]
        ax_price.set_xticks([])
        ax_vol.set_xticks([])
        bottom_ax = ax_rsi if ax_rsi else ax_vol
        bottom_ax.set_xticks(tick_positions)
        bottom_ax.set_xticklabels(tick_labels, rotation=30, ha='right', fontsize=6.5)

        # ── 9. PRECIO ACTUAL ──────────────────────────────────
        last_price = closes.values[-1]
        last_color = TV_THEME['candle_up'] if closes.values[-1] >= closes.values[-2] else TV_THEME['candle_down']
        ax_price.axhline(last_price, color=last_color, linewidth=0.8,
                         linestyle='-', alpha=0.5)
        ax_price.text(n - 0.5, last_price,
                      f' {_fmt_price(last_price)}',
                      color=last_color, fontsize=8.5, fontweight='bold',
                      va='center', ha='left',
                      bbox=dict(boxstyle='round,pad=0.2',
                                facecolor=last_color + '33',
                                edgecolor=last_color, linewidth=0.8))

        # Padding derecho para etiquetas
        ax_price.set_xlim(-1, n + 4)

        # ── 10. LEYENDA DE INDICADORES ────────────────────────
        if show_ema:
            legend_elements = [
                mpatches.Patch(color=TV_THEME['ema20'],  label=f"EMA20  {_fmt_price(ema20.values[-1])}"),
                mpatches.Patch(color=TV_THEME['ema50'],  label=f"EMA50  {_fmt_price(ema50.values[-1])}"),
            ]
            if not np.isnan(ema200.values[-1]):
                legend_elements.append(
                    mpatches.Patch(color=TV_THEME['ema200'],
                                   label=f"EMA200 {_fmt_price(ema200.values[-1])}")
                )
            legend = ax_price.legend(
                handles=legend_elements,
                loc='upper left', fontsize=7,
                facecolor=TV_THEME['bg_panel'],
                edgecolor=TV_THEME['border'],
                labelcolor=TV_THEME['text'],
                framealpha=0.85
            )

        # ── 11. TÍTULO Y CABECERA ─────────────────────────────
        # Variación % de la última vela
        prev_close = closes.values[-2] if n > 1 else closes.values[-1]
        pct_change = ((last_price - prev_close) / prev_close * 100) if prev_close else 0
        pct_color  = TV_THEME['candle_up'] if pct_change >= 0 else TV_THEME['candle_down']
        pct_sign   = '+' if pct_change >= 0 else ''

        # Signal color
        signal_up = any(s in signal.upper() for s in ('COMPRA', 'BUY'))
        signal_dn = any(s in signal.upper() for s in ('VENTA', 'SELL'))
        sig_color = TV_THEME['candle_up'] if signal_up else (
            TV_THEME['candle_down'] if signal_dn else TV_THEME['text_dim'])

        # Título principal
        fig.text(0.07, 0.93,
                 f"{symbol} · {timeframe.upper()}",
                 color=TV_THEME['text'], fontsize=13, fontweight='bold')

        # Precio + variación
        fig.text(0.31, 0.93,
                 f"{_fmt_price(last_price)}",
                 color=last_color, fontsize=12, fontweight='bold')
        fig.text(0.44, 0.93,
                 f"{pct_sign}{pct_change:.2f}%",
                 color=pct_color, fontsize=10)

        # Señal - usamos solo texto para compatibilidad con fuentes del servidor
        fig.text(0.58, 0.93,
                 f"[{signal}]",
                 color=sig_color, fontsize=9, fontweight='bold')

        # Timestamp
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        fig.text(0.97, 0.93, now_str,
                 color=TV_THEME['text_dim'], fontsize=7,
                 ha='right')

        # Línea separadora debajo del título
        fig.add_artist(
            plt.Line2D([0.07, 0.97], [0.915, 0.915],
                       transform=fig.transFigure,
                       color=TV_THEME['border'], linewidth=0.8)
        )

        # ── 12. WATERMARK ─────────────────────────────────────
        # Marca de agua abajo-izquierda, visible pero sin molestar
        fig.text(0.03, 0.015, 'BitBreadAlert',
                 color='#4A90D9', fontsize=9, fontweight='bold',
                 ha='left', va='bottom', alpha=0.55,
                 bbox=dict(boxstyle='round,pad=0.3',
                           facecolor='#131722', alpha=0.0,
                           edgecolor='none'))

        # ── 13. EXPORTAR ──────────────────────────────────────
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=130,
                    facecolor=TV_THEME['bg'],
                    bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf

    except Exception as e:
        print(f"❌ Error generando gráfico: {e}")
        import traceback
        traceback.print_exc()
        try:
            plt.close('all')
        except Exception:
            pass
        return None
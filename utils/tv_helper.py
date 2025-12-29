# utils/tv_helper.py
from tradingview_ta import TA_Handler, Interval, Exchange

def get_tv_data(symbol, interval_str="4h"):
    """
    Obtiene niveles y ahora también INDICADORES de TradingView.
    """
    # Mapeo de intervalos
    intervals = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "8h": "4h",   # FALLBACK: Redirigimos 8h a 4h para evitar crash
        "12h": "4h",  # FALLBACK: Redirigimos 12h a 4h para evitar crash
        "1d": "1d",
        "1w": "1w"  
    }
    
    interval = intervals.get(interval_str, "4h")
    
    # Manejo de Exchange (BINANCE para crypto)
    exchange = "BINANCE"
    screener = "CRYPTO"
    
    try:
        handler = TA_Handler(
            symbol=symbol,
            exchange=exchange,
            screener=screener,
            interval=interval,
            timeout=None
        )
        
        analysis = handler.get_analysis()
        ind = analysis.indicators
        
        # --- CÁLCULOS EXTRA PARA DATA PRO ---
        
        # 1. MACD State (Histograma aproximado)
        # TV da MACD.macd y MACD.signal. Si macd > signal = Alcista
        macd_val = ind.get("MACD.macd", 0)
        macd_sig = ind.get("MACD.signal", 0)
        macd_hist = macd_val - macd_sig
        
        
        # 2. SMA Trend
        close = ind.get("close", 0)
        sma50 = ind.get("SMA50", 0)
        sma200 = ind.get("SMA200", 0)
        
        # Estructura de retorno COMPLETA
        return {
            # Precios y Niveles (Lo que ya tenías)
            "current_price": close,
            "R3": ind.get("Pivot.M.Classic.R3", 0),
            "R2": ind.get("Pivot.M.Classic.R2", 0),
            "R1": ind.get("Pivot.M.Classic.R1", 0),
            "P":  ind.get("Pivot.M.Classic.Middle", 0),
            "S1": ind.get("Pivot.M.Classic.S1", 0),
            "S2": ind.get("Pivot.M.Classic.S2", 0),
            "S3": ind.get("Pivot.M.Classic.S3", 0),
            
            # Indicadores PRO (Nuevo)
            "RSI": ind.get("RSI", 50),
            "MACD_hist": macd_hist,
            "SMA50": sma50,
            "SMA200": sma200,
            "ATR": ind.get("ATR", ind.get("ATR[14]", 0)),
            "vol_change": ind.get("Volume", 0), # Volumen simple
            "recommendation": analysis.summary.get("RECOMMENDATION", "NEUTRAL"), # BUY, STRONG_BUY, etc.
            "buy_count": analysis.summary.get("BUY", 0),
            "sell_count": analysis.summary.get("SELL", 0)
            
        }
        
    except Exception as e:
        print(f"Error TV Helper: {e}")
        return None
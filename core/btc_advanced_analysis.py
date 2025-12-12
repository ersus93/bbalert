import numpy as np
import pandas as pd
import pandas_ta as ta
from typing import Dict, Tuple, List, Optional

class BTCAdvancedAnalyzer:
    """
    Análisis técnico avanzado para BTC con indicadores, divergencias y niveles dinámicos.
    """
    
    def __init__(self, dataframe: pd.DataFrame):
        """
        dataframe debe tener columnas: open, high, low, close, volume
        """
        self.df = dataframe.copy()
        self.calculate_indicators()
    
    def calculate_indicators(self):
        """Calcula todos los indicadores de manera segura."""
        # RSI
        self.df['RSI'] = ta.rsi(self.df['close'], length=14)
        
        # MACD
        macd_result = ta.macd(self.df['close'], fast=12, slow=26, signal=9)
        if macd_result is not None:
            self.df = pd.concat([self.df, macd_result], axis=1)
        else:
            self.df['MACD_12_26_9'] = 0
            self.df['MACDh_12_26_9'] = 0
        
        # Bandas de Bollinger
        bb = ta.bbands(self.df['close'], length=20, std=2)
        if bb is not None:
            self.df = pd.concat([self.df, bb], axis=1)
        
        # ATR
        self.df['ATR'] = ta.atr(self.df['high'], self.df['low'], self.df['close'], length=14)
        
        # SMA
        self.df['SMA_50'] = ta.sma(self.df['close'], length=50)
        self.df['SMA_200'] = ta.sma(self.df['close'], length=200)
        
        # Volumen
        self.df['Volume_SMA'] = self.df['volume'].rolling(window=20).mean()
        
        # MFI
        self.df['MFI'] = ta.mfi(self.df['high'], self.df['low'], self.df['close'], self.df['volume'], length=14)
        
        # ADX
        adx_result = ta.adx(self.df['high'], self.df['low'], self.df['close'], length=14)
        if adx_result is not None:
            self.df = pd.concat([self.df, adx_result], axis=1)
    
    def get_current_values(self) -> Dict:
        """Retorna los valores actuales de los últimos datos."""
        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2] if len(self.df) > 1 else curr
        
        return {
            'price': float(curr['close']),
            'rsi': float(curr['RSI']) if 'RSI' in curr and not pd.isna(curr['RSI']) else 50,
            'macd': float(curr.get('MACD_12_26_9', 0)) if 'MACD_12_26_9' in curr else 0,
            'macd_hist': float(curr.get('MACDh_12_26_9', 0)) if 'MACDh_12_26_9' in curr else 0,
            'atr': float(curr['ATR']) if 'ATR' in curr and not pd.isna(curr['ATR']) else 0,
            'volume': float(curr['volume']),
            'sma_50': float(curr['SMA_50']) if 'SMA_50' in curr and not pd.isna(curr['SMA_50']) else 0,
            'sma_200': float(curr['SMA_200']) if 'SMA_200' in curr and not pd.isna(curr['SMA_200']) else 0,
            'mfi': float(curr['MFI']) if 'MFI' in curr and not pd.isna(curr['MFI']) else 50,
            'volume_ratio': float(curr['volume'] / curr['Volume_SMA']) if curr['Volume_SMA'] > 0 else 1,
            'prev_rsi': float(prev['RSI']) if 'RSI' in prev and not pd.isna(prev['RSI']) else 50,
            'prev_price': float(prev['close']),
        }
    
    def detect_rsi_divergence(self, lookback=5) -> Optional[Tuple[str, str]]:
        """
        Detecta divergencias de RSI (Bullish/Bearish).
        Retorna: ('BULLISH' | 'BEARISH', 'descripción') o None
        """
        if len(self.df) < lookback + 1:
            return None
        
        recent = self.df.iloc[-lookback:].copy()
        
        # Buscar mínimos/máximos locales
        price_min_idx = recent['close'].idxmin()
        rsi_min_idx = recent['RSI'].idxmin()
        price_max_idx = recent['close'].idxmax()
        rsi_max_idx = recent['RSI'].idxmax()
        
        # --- Divergencia BULLISH (precio baja, RSI sube) ---
        if price_min_idx < rsi_min_idx:
            # El precio tocó mínimo ANTES que RSI
            price_min = self.df.loc[price_min_idx, 'close']
            curr_price = self.df.iloc[-1]['close']
            
            if curr_price > price_min and not pd.isna(self.df.loc[rsi_min_idx, 'RSI']):
                rsi_min = self.df.loc[rsi_min_idx, 'RSI']
                curr_rsi = self.df.iloc[-1]['RSI']
                
                if curr_rsi > rsi_min and curr_rsi < 50:  # RSI en zona neutra/baja
                    return ('BULLISH', 'RSI sube pero precio sigue bajo (Debilidad de venta)')
        
        # --- Divergencia BEARISH (precio sube, RSI baja) ---
        if price_max_idx < rsi_max_idx:
            # El precio tocó máximo ANTES que RSI
            price_max = self.df.loc[price_max_idx, 'close']
            curr_price = self.df.iloc[-1]['close']
            
            if curr_price < price_max and not pd.isna(self.df.loc[rsi_max_idx, 'RSI']):
                rsi_max = self.df.loc[rsi_max_idx, 'RSI']
                curr_rsi = self.df.iloc[-1]['RSI']
                
                if curr_rsi < rsi_max and curr_rsi > 50:  # RSI en zona neutra/alta
                    return ('BEARISH', 'RSI baja pero precio sigue alto (Debilidad de compra)')
        
        return None
    
    def get_momentum_signal(self) -> Tuple[str, str]:
        """
        Analiza el momentum usando MACD, RSI y precio vs SMAs.
        Retorna: ('STRONG_BULL' | 'BULL' | 'NEUTRAL' | 'BEAR' | 'STRONG_BEAR', descripción)
        """
        curr = self.get_current_values()
        
        # Puntuación
        score = 0
        reasons = []
        
        # --- RSI (0-3 puntos) ---
        if curr['rsi'] > 70:
            score += 0
            reasons.append("RSI sobrecomprado")
        elif curr['rsi'] > 60:
            score += 2
            reasons.append("RSI alcista moderado")
        elif curr['rsi'] > 50:
            score += 1
            reasons.append("RSI levemente alcista")
        elif curr['rsi'] > 40:
            score -= 1
            reasons.append("RSI levemente bajista")
        elif curr['rsi'] > 30:
            score -= 2
            reasons.append("RSI bajista moderado")
        else:
            score += 0
            reasons.append("RSI sobreventa")
        
        # --- MACD (0-3 puntos) ---
        if curr['macd_hist'] > 0:
            score += 2 if curr['macd_hist'] > curr['macd'] * 0.5 else 1
            reasons.append("MACD alcista")
        else:
            score -= 2 if curr['macd_hist'] < curr['macd'] * 0.5 else 1
            reasons.append("MACD bajista")
        
        # --- Precio vs SMAs (0-4 puntos) ---
        if curr['price'] > curr['sma_50'] > curr['sma_200']:
            score += 4
            reasons.append("SMA: Trends UP ✓")
        elif curr['price'] > curr['sma_50']:
            score += 2
            reasons.append("SMA: Price > 50MA")
        elif curr['price'] > curr['sma_200']:
            score += 1
            reasons.append("SMA: Price > 200MA")
        else:
            score -= 3
            reasons.append("SMA: Trends DOWN")
        
        # --- Volumen (0-2 puntos) ---
        if curr['volume_ratio'] > 1.2:
            score += 2
            reasons.append("Volumen alto (Confirmación)")
        elif curr['volume_ratio'] < 0.8:
            score -= 1
            reasons.append("Volumen bajo (Débil)")
        
        # --- Clasificación Final ---
        if score >= 8:
            signal = "STRONG_BULL"
            emoji = "🚀"
        elif score >= 4:
            signal = "BULL"
            emoji = "📈"
        elif score >= -3:
            signal = "NEUTRAL"
            emoji = "⚖️"
        elif score >= -7:
            signal = "BEAR"
            emoji = "📉"
        else:
            signal = "STRONG_BEAR"
            emoji = "🕳️"
        
        return (signal, emoji, score, reasons)
    
    def get_support_resistance_dynamic(self) -> Dict:
        """
        Calcula soportes y resistencias dinámicos usando pivotes y máximos/mínimos recientes.
        """
        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        # Pivote estándar
        h, l, c = curr['high'], curr['low'], curr['close']
        p = (h + l + c) / 3
        
        # Soportes y resistencias estándar
        r1 = (2 * p) - l
        r2 = p + (h - l)
        s1 = (2 * p) - h
        s2 = p - (h - l)
        
        # Máximos y mínimos de 20 velas (nivel dinámico)
        recent_high = self.df.iloc[-20:]['high'].max()
        recent_low = self.df.iloc[-20:]['low'].min()
        
        return {
            'pivot': p,
            'r1': r1,
            'r2': r2,
            's1': s1,
            's2': s2,
            'recent_high': recent_high,
            'recent_low': recent_low,
            'atr': curr['ATR'] if 'ATR' in curr and not pd.isna(curr['ATR']) else 0
        }
    
    def get_risk_reward_ratio(self, entry_price: float, target_level: float) -> float:
        """Calcula ratio riesgo/recompensa basado en ATR."""
        curr = self.get_current_values()
        atr = curr['atr']
        
        if atr == 0:
            return 1.0
        
        distance_to_target = abs(target_level - entry_price)
        return distance_to_target / atr if atr > 0 else 1.0

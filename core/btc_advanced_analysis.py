# core/btc_advanced_analysis.py

import numpy as np
import pandas as pd
import pandas_ta as ta
from typing import Dict, Tuple, List

class BTCAdvancedAnalyzer:
    """
    Análisis técnico PROFESIONAL (Nivel TradingView) para BTC.
    Versión ROBUSTA: Maneja errores de datos nulos y estandariza nombres.
    """
    
    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe.copy()
        # Asegurar índices correctos
        if not isinstance(self.df.index, pd.DatetimeIndex):
            if 'time' in self.df.columns:
                self.df['time'] = pd.to_datetime(self.df['time'])
                self.df.set_index('time', inplace=True)
        
        # Limpieza básica inicial
        self.df = self.df.astype(float, errors='ignore')
        
        self.calculate_indicators()
    
    def calculate_indicators(self):
        """Calcula indicadores y RENOMBRA las columnas para evitar errores de clave."""
        
        # 1. EMAs (Medias Móviles Exponenciales)
        # Si no hay suficientes datos para EMA 200, rellenamos con el precio de cierre para no romper el código
        for length in [9, 20, 50, 200]:
            ema = ta.ema(self.df['close'], length=length)
            if ema is not None:
                self.df[f'EMA_{length}'] = ema
            else:
                self.df[f'EMA_{length}'] = self.df['close'] # Fallback seguro
            
        # 2. Osciladores de Momentum
        # RSI
        self.df['RSI'] = ta.rsi(self.df['close'], length=14)
        
        # Stochastic (K y D) - Renombramos explícitamente
        stoch = ta.stoch(self.df['high'], self.df['low'], self.df['close'], k=14, d=3, smooth_k=3)
        if stoch is not None:
            # pandas_ta devuelve nombres como STOCHk_14_3_3. Los buscamos por posición o prefijo.
            self.df['STOCH_K'] = stoch.iloc[:, 0]  # La primera col suele ser K
            self.df['STOCH_D'] = stoch.iloc[:, 1]  # La segunda es D
        else:
            self.df['STOCH_K'] = 50
            self.df['STOCH_D'] = 50

        # CCI
        cci = ta.cci(self.df['high'], self.df['low'], self.df['close'], length=20)
        self.df['CCI'] = cci if cci is not None else 0
        
        # Awesome Oscillator (AO)
        ao = ta.ao(self.df['high'], self.df['low'])
        self.df['AO'] = ao if ao is not None else 0

        # 3. Fuerza de Tendencia (ADX)
        adx_df = ta.adx(self.df['high'], self.df['low'], self.df['close'], length=14)
        if adx_df is not None:
            # ADX suele devolver 3 columnas: ADX, DMP, DMN. Nos interesa la primera.
            self.df['ADX'] = adx_df.iloc[:, 0] 
        else:
            self.df['ADX'] = 0
        
        # 4. MACD
        macd = ta.macd(self.df['close'], fast=12, slow=26, signal=9)
        if macd is not None:
            # MACD devuelve: MACD, Histogram, Signal
            self.df['MACD_LINE'] = macd.iloc[:, 0]
            self.df['MACD_HIST'] = macd.iloc[:, 1]
            self.df['MACD_SIGNAL'] = macd.iloc[:, 2]
        else:
            self.df['MACD_HIST'] = 0
            
        # 5. Volatilidad (ATR)
        self.df['ATR'] = ta.atr(self.df['high'], self.df['low'], self.df['close'], length=14)

        # === LIMPIEZA FINAL DE NULOS ===
        # Reemplazamos cualquier NaN restante con 0 o valores neutros para evitar crash
        self.df.fillna(0, inplace=True)

    def get_current_values(self):
        """Devuelve la última fila como diccionario asegurando tipos nativos (no numpy)."""
        last_row = self.df.iloc[-1].to_dict()
        # Convertir tipos numpy a nativos de python (evita errores de serialización JSON a veces)
        clean_dict = {}
        for k, v in last_row.items():
            try:
                clean_dict[k] = float(v)
            except:
                clean_dict[k] = 0.0
        return clean_dict

    def get_momentum_signal(self) -> Tuple[str, str, Tuple[int, int], List[str]]:
        """
        Algoritmo de Puntuación Compuesto (Estilo TradingView).
        """
        # Obtenemos valores asegurados (sin NaNs)
        curr = self.get_current_values()
        price = curr.get('close', 0)
        
        buy_score = 0
        sell_score = 0
        reasons = []
        
        # --- GRUPO 1: TENDENCIA (Moving Averages) ---
        mas = [9, 20, 50, 200]
        ma_bullish_count = 0
        
        for ma in mas:
            val = curr.get(f'EMA_{ma}', 0)
            if val > 0: # Solo si existe un valor válido
                if price > val:
                    buy_score += 1
                    ma_bullish_count += 1
                else:
                    sell_score += 1
        
        if ma_bullish_count == 4:
            reasons.append("Tendencia Alcista (Sobre todas las EMAs)")
        elif ma_bullish_count == 0:
            reasons.append("Tendencia Bajista (Bajo todas las EMAs)")
            
        # --- GRUPO 2: OSCILADORES (Momentum) ---
        
        # RSI (14)
        rsi = curr.get('RSI', 50)
        if rsi < 30: 
            buy_score += 1
            reasons.append("RSI Sobrevendido (Oportunidad)")
        elif rsi > 70:
            sell_score += 1
            reasons.append("RSI Sobrecomprado (Cuidado)")
        elif 50 < rsi < 70:
            buy_score += 1
        elif 30 < rsi < 50:
            sell_score += 1
            
        # CCI
        cci = curr.get('CCI', 0)
        if cci < -100: buy_score += 1
        elif cci > 100: sell_score += 1
            
        # Stochastic
        k = curr.get('STOCH_K', 50)
        if k < 20:
            buy_score += 1
            reasons.append("Estocástico Sobrevendido")
        elif k > 80:
            sell_score += 1
            
        # Awesome Oscillator
        ao = curr.get('AO', 0)
        if ao > 0: buy_score += 1
        else: sell_score += 1
            
        # MACD
        hist = curr.get('MACD_HIST', 0)
        if hist > 0: buy_score += 1
        else: sell_score += 1

        # --- GRUPO 3: FUERZA (ADX) ---
        adx = curr.get('ADX', 0)
        if adx > 25:
            if ma_bullish_count >= 3:
                buy_score += 2
                reasons.append(f"ADX Fuerte ({adx:.1f}) confirma Alza")
            elif ma_bullish_count <= 1:
                sell_score += 2
                reasons.append(f"ADX Fuerte ({adx:.1f}) confirma Baja")

        # --- CÁLCULO FINAL DE SEÑAL ---
        net_score = buy_score - sell_score
        
        if net_score >= 6:
            signal = "COMPRA FUERTE"
            emoji = "🚀"
        elif net_score >= 2:
            signal = "COMPRA"
            emoji = "📈"
        elif net_score >= -2:
            signal = "NEUTRAL"
            emoji = "⚖️"
        elif net_score >= -6:
            signal = "VENTA"
            emoji = "📉"
        else:
            signal = "VENTA FUERTE"
            emoji = "🐻"
            
        return (signal, emoji, (buy_score, sell_score), reasons)

    def get_support_resistance_dynamic(self) -> Dict:
        """
        Calcula Pivotes de Fibonacci basados en la vela CERRADA anterior.
        Estos niveles son estáticos para toda la duración de la vela actual (4H).
        """
        if len(self.df) < 2:
            return {}
            
        # Tomamos la penúltima fila (la última vela cerrada completa)
        prev = self.df.iloc[-2]
        
        # Datos para cálculo
        high = float(prev['high'])
        low = float(prev['low'])
        close = float(prev['close'])
        
        # Fórmula PIVOTS FIBONACCI
        p = (high + low + close) / 3
        rango = high - low
        
        return {
            'current_price': float(self.df.iloc[-1]['close']), # Precio vela actual
            'P': p,
            'R1': p + (rango * 0.382),
            'R2': p + (rango * 0.618),
            'R3': p + (rango * 1.000),
            'S1': p - (rango * 0.382),
            'S2': p - (rango * 0.618),
            'S3': p - (rango * 1.000),
            'atr': self.df.iloc[-1].get('ATR', 0)
        }
    
    # Añadido para que btc_loop.py no falle si llama a esta función
    def detect_rsi_divergence(self, lookback=5):
        return None
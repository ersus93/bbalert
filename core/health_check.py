# core/health_check.py
"""
Sistema de Health Check para BBAlert.
Proporciona verificación del estado del sistema y sus dependencias.
"""

import asyncio
import os
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from telegram import Bot
from telegram.error import TelegramError
from utils.logger import logger
from core.config import DATA_DIR, VERSION

# ============================================================
# CONSTANTES
# ============================================================

CHECK_TIMEOUT = 10  # Timeout para cada check en segundos


class HealthStatus:
    """Estados posibles de un check."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ============================================================
# HEALTH CHECKS
# ============================================================

async def check_telegram_api(bot: Bot) -> Dict[str, Any]:
    """Verifica conexión con API de Telegram."""
    try:
        me = await bot.get_me()
        return {
            "status": HealthStatus.HEALTHY,
            "message": f"Bot '{me.username}' conectado",
            "details": {"bot_id": me.id, "bot_name": me.first_name}
        }
    except TelegramError as e:
        return {
            "status": HealthStatus.CRITICAL,
            "message": f"Error conectando con Telegram: {e}",
            "details": {}
        }
    except Exception as e:
        return {
            "status": HealthStatus.CRITICAL,
            "message": f"Error inesperado: {e}",
            "details": {}
        }


def check_data_files() -> Dict[str, Any]:
    """Verifica que los archivos de datos existan y sean accesibles."""
    critical_files = [
        "users.json",
        "price_alerts.json",
    ]
    
    optional_files = [
        "weather_subs.json",
        "btc_subs.json",
        "valerts_state.json",
    ]
    
    issues = []
    warnings = []
    
    data_dir = Path(DATA_DIR)
    
    if not data_dir.exists():
        return {
            "status": HealthStatus.CRITICAL,
            "message": f"Data directory does not exist: {data_dir}",
            "details": {}
        }
    
    # Check critical files
    for filename in critical_files:
        filepath = data_dir / filename
        if not filepath.exists():
            issues.append(f"Missing critical: {filename}")
        elif not os.access(filepath, os.R_OK | os.W_OK):
            issues.append(f"No read/write: {filename}")
    
    # Check optional files
    for filename in optional_files:
        filepath = data_dir / filename
        if not filepath.exists():
            warnings.append(f"Missing optional: {filename}")
    
    if issues:
        status = HealthStatus.CRITICAL
        message = f"Data files issues: {', '.join(issues)}"
    elif warnings:
        status = HealthStatus.WARNING
        message = f"Optional files missing: {', '.join(warnings)}"
    else:
        status = HealthStatus.HEALTHY
        message = "All data files accessible"
    
    return {
        "status": status,
        "message": message,
        "details": {
            "data_dir": str(data_dir),
            "issues": issues,
            "warnings": warnings
        }
    }


def check_disk_space() -> Dict[str, Any]:
    """Verifica espacio en disco."""
    try:
        data_dir = Path(DATA_DIR)
        if data_dir.exists():
            stat = os.statvfs(str(data_dir))
            free_bytes = stat.f_bavail * stat.f_frsize
            free_mb = free_bytes / (1024 * 1024)
            free_gb = free_mb / 1024
            
            if free_gb < 1:
                status = HealthStatus.CRITICAL
                message = f"Low disk space: {free_gb:.2f}GB free"
            elif free_gb < 5:
                status = HealthStatus.WARNING
                message = f"Disk space warning: {free_gb:.2f}GB free"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space OK: {free_gb:.2f}GB free"
            
            return {
                "status": status,
                "message": message,
                "details": {"free_gb": round(free_gb, 2)}
            }
        
        return {
            "status": HealthStatus.UNKNOWN,
            "message": f"Data dir not found: {data_dir}",
            "details": {}
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNKNOWN,
            "message": f"Could not check disk: {e}",
            "details": {}
        }


def check_memory_usage() -> Dict[str, Any]:
    """Verifica uso de memoria."""
    try:
        memory = psutil.virtual_memory()
        percent = memory.percent
        available_mb = memory.available / (1024 * 1024)
        
        if percent > 90:
            status = HealthStatus.CRITICAL
            message = f"Memory critical: {percent}% used"
        elif percent > 75:
            status = HealthStatus.WARNING
            message = f"Memory warning: {percent}% used"
        else:
            status = HealthStatus.HEALTHY
            message = f"Memory OK: {percent}% used"
        
        return {
            "status": status,
            "message": message,
            "details": {
                "percent": percent,
                "available_mb": round(available_mb, 2)
            }
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNKNOWN,
            "message": f"Could not check memory: {e}",
            "details": {}
        }


def check_log_files() -> Dict[str, Any]:
    """Verifica logs y tamaño de archivos."""
    try:
        log_dir = Path("logs")
        
        if not log_dir.exists():
            return {
                "status": HealthStatus.WARNING,
                "message": "Logs directory does not exist",
                "details": {}
            }
        
        log_files = list(log_dir.glob("*.log"))
        total_size = sum(f.stat().st_size for f in log_files)
        total_mb = total_size / (1024 * 1024)
        
        # Warn if logs are larger than 100MB
        if total_mb > 100:
            status = HealthStatus.WARNING
            message = f"Large log files: {total_mb:.1f}MB"
        else:
            status = HealthStatus.HEALTHY
            message = f"Logs OK: {total_mb:.1f}MB ({len(log_files)} files)"
        
        return {
            "status": status,
            "message": message,
            "details": {
                "total_mb": round(total_mb, 2),
                "file_count": len(log_files)
            }
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNKNOWN,
            "message": f"Could not check logs: {e}",
            "details": {}
        }


async def check_external_apis() -> Dict[str, Any]:
    """Verifica APIs externas (placeholder - implementar según necesidad)."""
    # Este check puede expandirse para verificar:
    # - CoinMarketCap API
    # - OpenWeatherMap API
    # - TradingView
    # - Otros servicios externos
    
    return {
        "status": HealthStatus.HEALTHY,
        "message": "External APIs check skipped (add implementations as needed)",
        "details": {}
    }


# ============================================================
# HEALTH CHECK ORQUESTADOR
# ============================================================

async def run_health_check(bot: Bot = None) -> Dict[str, Any]:
    """
    Ejecuta todos los health checks y retorna el estado general.
    
    Args:
        bot: Instancia del bot de Telegram para verificar API
        
    Returns:
        Dict con estado general y detalles de cada check
    """
    checks = {}
    overall_status = HealthStatus.HEALTHY
    
    # Run checks
    if bot:
        checks["telegram_api"] = await check_telegram_api(bot)
    
    checks["data_files"] = check_data_files()
    checks["disk_space"] = check_disk_space()
    checks["memory"] = check_memory_usage()
    checks["logs"] = check_log_files()
    checks["external_apis"] = await check_external_apis()
    
    # Determine overall status
    statuses = [check["status"] for check in checks.values()]
    
    if HealthStatus.CRITICAL in statuses:
        overall_status = HealthStatus.CRITICAL
    elif HealthStatus.WARNING in statuses:
        overall_status = HealthStatus.WARNING
    elif HealthStatus.UNKNOWN in statuses:
        overall_status = HealthStatus.UNKNOWN
    else:
        overall_status = HealthStatus.HEALTHY
    
    return {
        "overall": overall_status,
        "version": VERSION,
        "timestamp": datetime.now().isoformat(),
        "checks": checks
    }


def format_health_message(health_result: Dict[str, Any]) -> str:
    """Formatea el resultado del health check para mostrar en Telegram."""
    status_emoji = {
        HealthStatus.HEALTHY: "✅",
        HealthStatus.WARNING: "⚠️",
        HealthStatus.CRITICAL: "❌",
        HealthStatus.UNKNOWN: "❓"
    }
    
    overall = health_result["overall"]
    emoji = status_emoji.get(overall, "❓")
    
    lines = [
        f"🔍 *Health Check - BBAlert v{health_result['version']}*",
        f"{emoji} *Estado: {overall.upper()}*",
        "",
        "📋 *Detalles:*",
    ]
    
    for check_name, check_result in health_result["checks"].items():
        check_emoji = status_emoji.get(check_result["status"], "❓")
        lines.append(f"{check_emoji} {check_name}: {check_result['message']}")
    
    lines.extend([
        "",
        f"🕐 _Última verificación: {health_result['timestamp']}_"
    ])
    
    return "\n".join(lines)

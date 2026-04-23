import gc
import os
import sys
import shutil
import logging
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BotCleaner:
    """
    Auto-limpieza de memoria y archivos basura.

    Úsalo al arrancar el bot y en intervalos programados.

    """


    def __init__(self, base_dir: str = None, max_log_days: int = 3):

        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.max_log_days = max_log_days
        self.cleaned_mb = 0.0


    # ── Memoria ──────────────────────────────────────────────────────────────


    def free_memory(self) -> dict:
        """Fuerza garbage collection y libera ciclos de referencia."""

        before = self._rss_mb()


        gc.collect(0)  # generación joven
        gc.collect(1)  # media
        gc.collect(2)  # vieja (full GC)


        # Devuelve memoria de bloques libres al SO (solo CPython)
        try:
            import ctypes
            ctypes.cdll.LoadLibrary("libc.so.6").malloc_trim(0)
        except Exception:
            pass


        after = self._rss_mb()
        freed = round(before - after, 2)
        logger.info(f"🧠 Memoria liberada: {freed} MB (antes: {before}, ahora: {after})")
        return {"before_mb": before, "after_mb": after, "freed_mb": freed}


    # ── Archivos basura ───────────────────────────────────────────────────────


    def clean_pyc(self) -> int:
        """Elimina .pyc y carpetas __pycache__."""
        count = 0
        for p in self.base_dir.rglob("__pycache__"):
            shutil.rmtree(p, ignore_errors=True)
            count += 1
        for p in self.base_dir.rglob("*.pyc"):
            p.unlink(missing_ok=True)
            count += 1
        logger.info(f"🗑️  Caché Python eliminada: {count} entradas")
        return count


    def clean_temp_files(self, extensions=(".tmp", ".log.bak", ".swp")) -> int:
        """Elimina archivos temporales del directorio del bot."""
        count = 0
        for ext in extensions:
            for p in self.base_dir.rglob(f"*{ext}"):
                try:
                    p.unlink()
                    count += 1
                except Exception:
                    pass
        logger.info(f"🗑️  Temporales eliminados: {count} archivos")
        return count


    def clean_old_logs(self) -> int:
        """Elimina logs con más de max_log_days días."""
        cutoff = datetime.now() - timedelta(days=self.max_log_days)
        count = 0
        for p in self.base_dir.rglob("*.log"):
            try:
                if datetime.fromtimestamp(p.stat().st_mtime) < cutoff:
                    p.unlink()
                    count += 1
            except Exception:
                pass
        logger.info(f"📋 Logs viejos eliminados: {count}")
        return count


    def clean_system_tmp(self) -> int:
        """Limpia /tmp del sistema (archivos propios del proceso)."""
        count = 0
        pid = os.getpid()
        tmp = Path(tempfile.gettempdir())
        for p in tmp.glob(f"*{pid}*"):
            try:
                p.unlink() if p.is_file() else shutil.rmtree(p)
                count += 1
            except Exception:
                pass
        return count


    # ── Full cleanup ──────────────────────────────────────────────────────────


    def full_cleanup(self) -> dict:
        """Ejecuta toda la limpieza. Llama esto al arrancar o periódicamente."""
        logger.info("🚀 Iniciando auto-limpieza del bot...")
        result = {
            "memory": self.free_memory(),
            "pyc_removed": self.clean_pyc(),
            "temps_removed": self.clean_temp_files(),
            "old_logs_removed": self.clean_old_logs(),
            "tmp_removed": self.clean_system_tmp(),
        }
        logger.info(f"✅ Limpieza completa: {result}")
        return result


    # ── Helpers ───────────────────────────────────────────────────────────────


    @staticmethod
    def _rss_mb() -> float:
        try:
            with open(f"/proc/{os.getpid()}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return round(int(line.split()[1]) / 1024, 2)
        except Exception:
            pass
        return 0.0
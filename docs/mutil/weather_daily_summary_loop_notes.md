# ── En el import de weather_loop_v2, añade weather_daily_summary_loop ──────
# ANTES:
# from core.weather_loop_v2 import weather_alerts_loop
# DESPUÉS:
from core.weather_loop_v2 import weather_alerts_loop, weather_daily_summary_loop
# ── Dentro de post_init, reemplaza el bloque de clima ─────────────────────
# ANTES (una sola tarea):
# asyncio.create_task(weather_alerts_loop(app.bot))
# logger.info("
Bucle de alertas de clima iniciado.")
#
# DESPUÉS (dos tareas independientes):
# Alertas de emergencia: lluvia, tormenta, UV — cada 15 min
asyncio.create_task(weather_alerts_loop(app.bot))
logger.info("
Bucle de alertas de emergencia de clima iniciado (15 min).")
# Resumen diario — verificación cada 30 min, envío solo en la ventana horaria
asyncio.create_task(weather_daily_summary_loop(app.bot))
logger.info("
Bucle de resumen diario de clima iniciado (30 min).")

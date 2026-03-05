analisis, plan y modificacion

Revisé el código del módulo de clima. El problema de spam y alertas imprecisas es claro y tiene
varias causas. Aquí el plan detallado:
🔍
Diagnóstico de Problemas
1. UV Alto enviado en cualquier momento del día
En weather_loop_v2.py hay una verificación is_daytime pero el UV se consulta con get_uv_index()
que devuelve el UV actual, no el máximo del día. A las 7am el UV puede ser 0 pero el loop lo
compara contra un valor que a veces viene cacheado de horas antes.
2. Alertas de lluvia/tormenta spam
El cooldown de 6 horas funciona, pero el loop corre cada 5 minutos y el forecast devuelve los
mismos 4 bloques hasta que OpenWeather actualiza (cada 3h). Esto significa que en 5 ciclos
seguidos puede ver “lluvia en 2h” y disparar la alerta si el cooldown expiró.
3. El resumen diario tiene un bug que genera spam
# Este bloque tiene lógica invertida:
if is_time_window and alert_types.get('daily_summary', True):
should_send = should_send_alert(user_id, 'daily_summary', cooldown_hours=20)
if should_send:
...
else:
# ← El log de "saltado" está en el ELSE del if should_send
# pero está al mismo nivel de indentación del if is_time_window
# por un error de indentación con el comentario
add_log_line(f"
⏳
Resumen diario saltado...")
El else con el log está mal indentado: se ejecuta cuando is_time_window es False, no cuando el
cooldown está activo. Esto no causa spam directo pero oculta cuándo sí se envía.
4. Alertas de lluvia sin filtro de proximidad temporal
Se alerta si hay lluvia en cualquiera de los próximos 4 bloques (= hasta 12h). Una alerta “va a llover
en 10 horas” a las 6am no es útil.
5. Cache de UV desactualizado
WeatherAPICache tiene TTL de 15 minutos pero el UV cambia muy lento. Sin embargo, si el cache
expiró justo antes del amanecer, la primera llamada puede traer un UV de la tarde anterior.
6. weather_loop_v2.py no usa el sistema avanzado de weather_manager.py
El loop usa should_send_alert() (lógica V1 simple por cooldown) pero weather_manager.py tiene un
sistema V3 con IDs de eventos únicos, stages (early/imminent) y deduplicación por coordenadas

que nunca se llama desde el loop.
Plan de Correcciones Punto a Punto
PASO 1 — Corregir la lógica de UV (weather_loop_v2.py)
Actualmente:
if alert_types.get('uv_high', True) and is_daytime and uv_val >= 6:
Correcciones necesarias:
∙
Agregar ventana horaria: solo alertar UV entre las 10:00 y 16:00 hora local (cuando el UV
realmente puede ser peligroso)
∙
Agregar umbral dinámico: si local_now.hour < 10 or local_now.hour > 16, nunca alertar UV
sin importar el valor
∙
El valor de uv_val viene de get_uv_index() que usa el endpoint /uvi de OWM — este
endpoint ya está deprecado en la API gratuita. Migrar a leer el UV desde el forecast si está
disponible
PASO 2 — Agregar filtro temporal a alertas de lluvia/tormenta (weather_loop_v2.py)
Actualmente busca lluvia en los próximos 4 bloques sin importar a qué hora son. Cambiar a:
∙
Solo alertar si la lluvia ocurre en las próximas 3 horas (1 bloque de forecast = 3h)
∙
Comparar upcoming_rain['dt'] con datetime.now() y verificar que la diferencia sea < 3h
∙
Esto convierte alertas de “va a llover hoy” en “va a llover en 2h”
PASO 3 — Corregir el bug de indentación del resumen diario (weather_loop_v2.py)
El bloque else con el log está al nivel incorrecto. La estructura correcta debería ser:
if is_time_window:
if alert_types.get('daily_summary', True):
if should_send_alert(...):
# enviar
else:
# log de cooldown ← AQUÍ debe estar el else
else:
pass # No es la hora correcta, silencio total
PASO 4 — Separar el resumen diario de las alertas de emergencia
Actualmente todo corre en el mismo loop de 5 minutos. Separar en dos frecuencias:
∙
Alertas de emergencia (lluvia, tormenta, UV): cada 15-20 minutos es suficiente, no cada 5

∙
Resumen diario: verificar solo una vez por hora exacta
Esto reduce llamadas a la API a un 75% y elimina el riesgo de spam por ciclos rápidos.
PASO 5 — Conectar el sistema V3 de weather_manager.py al loop
El WeatherAlertManager tiene should_send_weather_alert() y mark_weather_alert_sent() con IDs
únicos de evento. El loop ignora todo esto y usa la función simple should_send_alert(). Migrar el
loop para usar:
∙
should_send_alert_advanced() en lugar de should_send_alert()
∙
mark_alert_sent_advanced() en lugar de update_last_alert_time()
Esto activa la deduplicación por evento específico (mismo tipo + misma hora + mismas
coordenadas = mismo evento, no se repite).
PASO 6 — Agregar lógica de “etapas” para lluvia/tormenta
Con el sistema V3 disponible en weather_manager.py, implementar:
∙
Etapa early: lluvia en 3-6 horas → mensaje informativo (“esta tarde puede llover”)
∙
Etapa imminent: lluvia en menos de 1h → alerta urgente (”¡va a llover en menos de 1
hora!”)
Cada etapa solo se envía una vez por evento usando el event_id.
PASO 7 — Corregir el TTL del cache de UV (weather_api.py)
El cache de UV tiene TTL de 15 minutos igual que el clima. El UV cambia muy lentamente (índice
horario). Cambiar:
∙
UV: TTL de 60 minutos
∙
Clima actual: TTL de 10 minutos (es lo que más cambia)
∙
Forecast: TTL de 30 minutos (OWM lo actualiza cada 3h de todas formas)
También agregar invalidación del cache al cruzar medianoche para evitar datos de ayer.
PASO 8 — Agregar contexto horario al resumen diario
El resumen actualmente siempre muestra el mismo template. Adaptarlo según la hora configurada:
∙
Mañana (6-10h): mostrar pronóstico de todo el día de hoy
∙
Tarde (12-18h): enfocarse en tarde/noche + mañana siguiente
∙
Noche (20-22h): mostrar exclusivamente el pronóstico del día siguiente
Esto hace el resumen realmente útil según cuándo se recibe.
PASO 9 — Agregar cooldowns diferenciados por tipo de alerta
Actualmente todas las alertas tienen cooldown_hours=6. Valores más realistas:
∙
rain: 4h (la lluvia puede cambiar rápido)
∙
storm: 3h (tormentas son cortas e intensas, necesitas saber si viene otra)
∙
uv_high: 12h (el UV alto es un fenómeno de día completo, una alerta por día es suficiente)
∙
daily_summary: 22h (una vez al día con margen)
∙
temp_high/temp_low: 8h
PASO 10 — Limpiar el log spam del loop
El loop actualmente genera un log por cada usuario en cada ciclo aunque no pase nada. Cambiar a

logs condicionales: solo loguear cuando se envía algo o cuando hay un error. Los ciclos “normales”
sin eventos deben ser silenciosos.
Orden de Prioridad de Implementación
|Prioridad|Paso |Impacto |
|---------|-------|------------------------------------------------|
|
Crítico|Paso 3 |Bug de indentación que oculta el control de spam|
|
Crítico|Paso 2 |Alertas de lluvia en tiempo real vs. en 10h |
|
Crítico|Paso 1 |UV a las 6am con sol inexistente |
|
Alto |Paso 4 |Frecuencia del loop separada |
|
Alto |Paso 5 |Activar deduplicación V3 ya implementada |
|
Alto |Paso 9 |Cooldowns diferenciados |
|
Medio |Paso 6 |Sistema de etapas early/imminent |
|
Medio |Paso 7 |TTL de cache optimizado |
|
Mejora |Paso 8 |Resumen contextual por hora |
|
Mejora |Paso 10|Log limpio |
¿Quieres que empiece a implementar los cambios directamente en los archivos, comenzando por
los de prioridad crítica?
Vamos por partes. Empiezo con los 3 críticos y los de alta prioridad en un solo pase.
Ahora el cache con TTLs diferenciados:
Y finalmente el ajuste en bbalert.py para arrancar el nuevo loop separado:



Resumen de todo lo aplicado
Pasos críticos
Paso 1 — UV solo entre 10:00 y 16:00 hora local
La alerta UV ahora exige is_daytime (ya existía) y que la hora local esté entre 10h y 16h. Nunca más
UV al amanecer.
Paso 2 — Lluvia/tormenta solo en las próximas 3 horas
La función _entry_within_hours() compara el timestamp del forecast con datetime.now(). Si la lluvia
es en 8 horas, no se alerta ahora.

Paso 3 — Bug de indentación del resumen diario corregido
El else con el log estaba fuera del if should_send. Ahora la lógica es: si no es la ventana horaria →
silencio total. Si es la ventana pero el cooldown está activo → continue silencioso.
Pasos de alta prioridad
Paso 4 — Dos loops separados
weather_alerts_loop corre cada 15 min, weather_daily_summary_loop cada 30 min. Las alertas de
emergencia no compiten con el resumen y las llamadas a la API bajan ~75%.
Paso 5 — Sistema V3 activado
El loop ahora usa should_send_alert_advanced() y mark_alert_sent_advanced() en lugar de las
funciones simples V1. La deduplicación por event_id (hash de usuario + tipo + hora del evento +
coordenadas) está activa.
Paso 7 — TTL diferenciados en cache
weather: 10 min · forecast: 30 min · uvi: 60 min · air_pollution: 30 min. Además hay invalidación
automática al cruzar medianoche para UV y forecast.
Paso 8 — Resumen contextual según hora
Mañana (6-11h) → pronóstico del día completo. Tarde (12-18h) → tarde/noche + mañana. Noche
(20-22h) → bloques del día siguiente.
Paso 9 — Cooldowns diferenciados
rain: 4h · storm: 3h · uv_high: 12h · daily_summary: 22h · temp_high/low: 8h.
Paso 10 — Logs silenciosos en ciclos normales
Solo se loguea cuando se envía algo o hay un error. Los ciclos sin eventos no generan ruido.

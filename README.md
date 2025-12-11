# 🤖 BitBread Alert - Bot de Telegram Multifuncional

## 📋 Descripción General
BitBread Alert es un bot de Telegram multifuncional que combina monitoreo de criptomonedas, alertas de clima y herramientas de trading en una sola plataforma. Diseñado con una arquitectura asíncrona robusta, ofrece notificaciones en tiempo real, análisis técnico avanzado y gestión automatizada.

## ✨ Características Principales

### 🔔 **Sistema de Alertas Multiplataforma**
- **Alertas BTC**: Monitoreo de niveles clave (pivot, soportes/resistencias) con notificaciones automáticas
- **Alertas de Clima**: Pronóstico diario y alertas específicas (lluvia, UV, tormenta, nieve)
- **Alertas Personalizadas**: Configuración de límites de precio para cualquier criptomoneda

### 📊 **Herramientas de Trading**
- Análisis técnico avanzado (`/ta`) con indicadores múltiples
- Gráficos automáticos (`/graf`) desde TradingView
- Monitoreo de mercados globales (`/mk`)
- Tasas de cambio informal (`/tasa`) para Cuba

### 🌦️ **Sistema de Clima Inteligente**
- Pronóstico detallado por ciudad
- Alertas automáticas para condiciones climáticas adversas
- Configuración personalizada de notificaciones
- Resumen diario automatizado

### 📰 **Gestión de Feeds RSS/Atom**
- Configuración de múltiples fuentes RSS por usuario.
- Personalización de plantillas de notificación con formato HTML.
- Filtros por palabra clave para bloquear noticias.
- Monitoreo en tiempo real.

### ⚙️ **Gestión Avanzada**
- Multi-idioma (ES/EN)
- Sistema de anuncios rotativos
- Gestión de usuarios y logs
- Panel de administración completo

---

## 🚀 Instalación Rápida

### Prerrequisitos
- Servidor VPS con Ubuntu/Debian
- Acceso SSH con permisos sudo
- Python 3.12 o superior

### 1. Clonar Repositorio
```bash
cd /home/$USER
git clone https://github.com/ersus93/bbalert.git
cd bbalert
```

### 2. Configurar Permisos
```bash
chmod +x bbalert.sh
```

### 3. Configurar Variables de Entorno
```bash
cp .env.example .env
nano .env
```
**Contenido del archivo .env:** (ver apit.env.example)
```env
TOKEN_TELEGRAM=tu_token_aqui
ADMIN_CHAT_IDS=tu_id_telegram,otro_id
OPENWEATHER_API_KEY=tu_clave_openweather
STATE=production
```

### 4. Ejecutar Instalador
```bash
./bbalert.sh
```
Selecciona la opción **1** para instalación completa.

---

## 🤖 Configuración del Bot de Telegram

### Paso 1: Crear el Bot con BotFather
1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot`
3. Sigue las instrucciones:
   - **Nombre del bot**: `BitBread Alert`
   - **Username**: `tu_bot_bot` (debe terminar en 'bot')

### Paso 2: Obtener el Token
4. BotFather te proporcionará un token como:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456
   ```
   **¡Guárdalo en un lugar seguro!**

### Paso 3: Configurar el Bot
5. Configura los comandos recomendados en BotFather:
   ```
   start - Iniciar bot
   help - Ayuda
   btcalerts - Alertas BTC
   w - Clima
   ta - Análisis técnico
   alerta - Crear alerta personalizada
   weather_sub - Suscribirse a clima
   lang - Cambiar idioma
   rss - Gestión de Feeds RSS
   ```

### Paso 4: Obtener Tu Chat ID
6. Inicia conversación con tu bot y envía `/start`
7. Envía `/myid` para obtener tu Chat ID
8. Añade tu Chat ID a `ADMIN_CHAT_IDS` en el archivo `.env`

---

## ⚙️ Configuración de APIs Externas

### OpenWeather API (Para Clima)
1. Regístrate en [OpenWeather](https://openweathermap.org/api)
2. Obtén tu API Key gratuita
3. Añádela al archivo `.env`:
   ```
   OPENWEATHER_API_KEY=tu_clave_aqui
   ```

---

## 📁 Estructura del Proyecto
```
bbbalert/
├── bbalert.py                       # Punto de entrada principal
├── bbalert.sh                       # Script de gestión
├── .env                             # Variables de entorno
├── requirements.txt                 # Dependencias Python
├── babel.cfg                        # Configuracion de idioma
│
├── core/                            # Núcleo del sistema
│   ├── btc_loop.py                  # Monitor BTC
│   ├── loops.py                     # Bucles de fondo
│   ├── api_client.py                # Gestion de api para alertas
│   ├── i18n.py                      # Gestion de traduccion
│   ├── rss_loop.py                  # Monitor RSS/Atom (¡NUEVO\!)
│   └── config.py                    # Configuración
│
├── handlers/                        # Manejadores de comandos
│   ├── btc_handlers.py              # Comandos BTC
│   ├── weather.py                   # Comandos clima
│   ├── alerts.py                    # Alertas personalizadas
│   ├── general.py                   # Comandos de uso general
│   ├── pay.py                       # Gestion de pagos
│   ├── user_settings                # Comandos de ajustes
│   ├── admin.py                     # Comandos de administración
│   ├── trading.py                   # Herramientas trading
│   └── rss.py                       # Gestión de Feeds RSS 
│
├── utils/                           # Utilidades
│   ├── btc_manager.py               # Gestión BTC
│   ├── weather_manager.py           # Gestión clima
│   ├── ads_manager.py               # Gestion de ads
│   ├── image_generator.py           # Gestion de generacion de imagen
│   ├── file_manager.py              # Gestión archivos
│   └── rss_manager.py               # Gestión de datos RSS 
│
└── data/                            # Datos persistentes
    ├── users.json                   # Usuarios
    ├── weather_subs.json            # Suscriptores clima
    ├── btc_subs.json                # Suscriptores BTC
    ├── ads.json                     # Anuncios
    ├── btc_alert_state.json         # Status de la slertas BTC
    ├── custom_alert_history.json    # Historial de alertas
    ├── eltoque_history.json         # Historial de elToque
    ├── hbd_thresholds.json          # Humbrales de HBD
    ├── hbd_price_history.json       # Historial de hbd
    ├── last_price.json              # Último precio de lista de monedas
    ├── img.png                      # Plantilla para imagen de tasas
    ├── weather_last_alerts.json     # Alertas de clima
    ├── weather_subs.json            # Suscriptores clima
    └── rss_data.json                # Datos de Feeds RSS 
```

---

## 🎯 Comandos Principales

### 👤 **Comandos de Usuario**
| Comando | Descripción |
|---------|-------------|
| `/start` | Inicia el bot y detecta idioma |
| `/lang` | Cambia idioma (ES/EN) |
| `/myid` | Muestra tu ID de Telegram |
| `/help` | Muestra ayuda general |
| `/rss` | Gestión y configuración de tus Feeds RSS |

### 💰 **Criptomonedas y Trading**
| Comando | Descripción |
|---------|-------------|
| `/btcalerts` | Gestión de alertas BTC |
| `/ta [par]` | Análisis técnico avanzado |
| `/graf [par] [tf]` | Gráfico de TradingView |
| `/p [moneda]` | Precio detallado |
| `/mk` | Estado de mercados globales |
| `/tasa` | Tasas de cambio Cuba |

### 🌤️ **Clima**
| Comando | Descripción |
|---------|-------------|
| `/w [ciudad]` | Clima actual de una ciudad |
| `/weather_sub` | Suscripción a alertas clima |
| `/weather_settings` | Configurar alertas clima |

### ⏰ **Alertas Personalizadas**
| Comando | Descripción |
|---------|-------------|
| `/alerta BTC 50000` | Crear alerta de precio |
| `/misalertas` | Ver alertas activas |
| `/monedas BTC,ETH` | Configurar monedas a monitorear |
| `/temp 2.5` | Intervalo de alertas (horas) |

---

## 🔧 Gestión del Sistema

### Script de Gestión (`bbalert.sh`)
```bash
# Menú de opciones:
# 1. 🛠  Instalar Todo (Desde 0)
# 2. ▶️ Iniciar Bot
# 3. ⏹️ Detener Bot
# 4. 🔄 Reiniciar Bot
# 5. 📊 Ver Estado
# 6. 📜 Ver Logs en tiempo real
# 7. 📥 Verificar/Instalar Dependencias
# 8. 🗑️ Eliminar Dependencias
# 9. ❌ Salir
```

### Comandos Systemd
```bash
# Ver estado del servicio
sudo systemctl status bbalert

# Ver logs en tiempo real
sudo journalctl -u bbalert -f

# Reiniciar servicio
sudo systemctl restart bbalert

# Detener servicio
sudo systemctl stop bbalert
```

### Comandos de Administración
| Comando | Descripción (Solo Admins) |
|---------|-------------------|
| `/users` | Estadísticas de usuarios |
| `/logs` | Ver logs del sistema |
| `/ad add [texto]` | Añadir anuncio |
| `/ms` | Envío masivo a usuarios |

---

## 🌐 Sistema Multi-idioma
El bot detecta automáticamente el idioma del usuario basado en:
- Configuración regional de Telegram
- Idioma del dispositivo
- Preferencia manual (`/lang`)

**Idiomas soportados:**
- 🇪🇸 Español
- 🇺🇸 English

---

## ⚡ Sistema de Alertas BTC

### Niveles Calculados Automáticamente
- **Pivot Point**: Punto de equilibrio
- **Soportes (S1, S2, S3)**: Niveles de compra
- **Resistencias (R1, R2, R3)**: Niveles de venta

### Condiciones de Alerta
- Ruptura de niveles clave
- Cambio de tendencia
- Volatilidad alta detectada

### Configuración de Suscripción
Los usuarios pueden activar/desactivar alertas BTC desde:
- Comando `/btcalerts`
- Menú interactivo
- Callback buttons

---

## 🌦️ Sistema de Clima Inteligente

### Datos Incluidos
- Temperatura actual y sensación térmica
- Humedad y velocidad del viento
- Índice UV y calidad del aire
- Pronóstico de 24 horas
- Hora de salida y puesta del sol

### Tipos de Alertas Clima
- 🌧️ **Lluvia**: Precipitaciones detectadas
- ⛈️ **Tormenta**: Condiciones eléctricas
- ☀️ **UV Alto**: Índice UV > 6
- ❄️ **Nieve/Escarcha**: Temperaturas bajo cero
- 🌫️ **Niebla**: Visibilidad reducida
- 🔥 **Calor Intenso**: Temperatura > 35°C
- ❄️ **Frío Intenso**: Temperatura < 5°C

### Resumen Diario Automático
- Enviado a hora configurada (por defecto 07:00)
- Incluye pronóstico del día
- Recomendaciones personalizadas

---

## 🛠️ Solución de Problemas

### Error: "ModuleNotFoundError"
```bash
# Desde el script de gestión
./bbalert.sh
# Seleccionar opción 7 (Verificar/Instalar Dependencias)
```

### Error: "Token inválido"
1. Verificar token en `apit.env`
2. Confirmar que el bot esté activo en BotFather
3. Reiniciar servicio

### Error: "API rate limit exceeded"
1. Reducir frecuencia de consultas
2. Usar API Keys alternativas
3. Implementar caché local

### Logs de Depuración
```bash
# Ver logs completos
sudo journalctl -u bbalert -n 100

# Seguir logs en tiempo real
sudo journalctl -u bbalert -f
```

---

## 🔄 Actualización del Bot

### Método 1: Git Pull
```bash
cd /home/$USER/bbalert
git pull
./bbalert.sh
# Seleccionar opción 4 (Reiniciar Bot)
```

### Método 2: Reinstalación Limpia
```bash
cd /home/$USER
rm -rf bbalert
git clone https://github.com/tu_usuario/bbalert.git
cd bbalert
chmod +x bbalert.sh
./bbalert.sh
```

---

## 📈 Estadísticas y Monitoreo

### Archivos de Datos
- `data/users.json`: Usuarios registrados y preferencias
- `data/btc_subs.json`: Suscriptores alertas BTC
- `data/btc_alerts_state`: Registro de velas
- `data/weather_subs.json`: Suscriptores clima
- `data/price_alerts.json`: Alertas personalizadas
- `data/ads.json`: Anuncios
- `data/custom_alert_history.json`: Registro de alertas
- `data/eltoque_history.json`: Registro de tasas
- `data/hbd_thresholds.json`: Humbrales HBD
- `data/img.png`: Plantilla para Tasas elToque
- `data/last_prices.json`: Últimos precios de lista de monedas
- `data/weather_subs.json`: Suscriptores alertas de clima

### Métricas Clave
- Usuarios activos (últimos 30 días)
- Alertas enviadas (24h)
- Tasa de entrega de mensajes
- Uptime del servicio

---

## 🔒 Seguridad y Mejores Prácticas

### Recomendaciones
1. **Nunca compartas** tu token de bot públicamente
2. Usa variables de entorno para datos sensibles
3. Limita acceso SSH al servidor
4. Mantén actualizadas las dependencias
5. Realiza backups regulares de datos

### Backup de Datos
```bash
# Backup manual
cd /home/$USER/bbalert
tar -czf backup_$(date +%Y%m%d).tar.gz data/ logs/
```

### Restauración
```bash
# Descomprimir backup
tar -xzf backup_20231201.tar.gz

# Restaurar datos
cp -r data/ /home/$USER/bbalert/
```

---

## 🤝 Contribuir al Proyecto

### Cómo Contribuir
1. Haz fork del repositorio
2. Crea una rama para tu feature
3. Realiza tus cambios
4. Envía un Pull Request

### Estándares de Código
- Usar snake_case para variables y funciones
- Comentar funciones complejas
- Mantener compatibilidad con Python 3.12+
- Sigue la estructura de archivos existente

---

## 📄 Licencia
Este proyecto está bajo la licencia MIT. Ver archivo `LICENSE` para más detalles.

---

## 👨‍💻 Autor y Contacto
- **Autor**: [ersus]
- **GitHub**: [@ersus93](https://github.com/ersus93)
- **Telegram**: [@iamersus](https://t.me/iamersus)

### Agradecimientos
- Comunidad de Telegram
- Usuarios beta testers

---

## 🔮 Roadmap Futuro

### Próximas Características
- ✅ **Completado**: Alertas sobre la variacion de HBD (HIVE Dollar)
- ✅ **Completado**: Alertas de lita de moneda personalizada
- ✅ **Completado**: Consulta de precios de criptos listadas en CMC (CoinMarketCap)
- ✅ **Completado**: Alertad de precio de cualquier cripto 
- ✅ **Completado**: Sistema de anuncios aleatoeios en los mensajes de alertas
- ✅ **Completado**: Sistema de análisis de trading
- ✅ **Completado**: Implementacion de sistemas de pago con Telegram Stars
- ✅ **Completado**: Sistema de clima
- ✅ **Completado**: Alertas BTC avanzadas
- ⏳ **Planeado**: Sistema de activación o desactivación de metodos de pago
- ⏳ **Planeado**: Integración con más exchanges
- ⏳ **Planeado**: Sistema de pagos con HIVE Blockchain
- ⏳ **Planeado**: Sistemas RSS para notas o noticias de interes (aún en análisis si por usuario o dirigido a todos)
- ⏳ **Planeado**: Panel de gestion telegram web para el bot


### Mejoras Técnicas
- Migración a PostgreSQL
- Sistema de caché distribuido
- Microservicios independientes
- Dockerización completa

---

## ❓ Preguntas Frecuentes

### ¿Necesito un servidor dedicado?
No necesariamente, pero recomendamos un VPS con al menos:
- 1 GB RAM
- 20 GB SSD
- Ubuntu 20.04+

### ¿Es gratuito el bot?
Sí, el bot es de código abierto y gratuito. Solo necesitas pagar por:
- Servidor VPS (~$5-10/mes)
- APIs premium (opcional)

### ¿Cómo reporto un error?
1. Revisa los logs primero
2. Abre un issue en GitHub
3. Proporciona información detallada

### ¿Puedo usar el bot comercialmente?
Sí, bajo los términos de la licencia MIT.

---

**⭐ Si te gusta este proyecto, considera darle una estrella en GitHub!**

**📢 Únete a nuestro canal de Telegram para actualizaciones: [@bbalertchannel](https://t.me/bbalertchannel)**

---
*Última actualización: 2025-12-10 21:16*
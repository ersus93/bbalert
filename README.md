<<<<<<< HEAD
# bbalert
# Bot de Alertas de Precios (BitBreadAlert)

Este es un bot de Telegram diseñado para monitorear precios de criptomonedas (como HBD) y enviar alertas a los usuarios. También incluye funciones de administración y consulta de datos.

## 🚀 Características Principales

* **Alertas de Precio:** Los usuarios pueden configurar alertas de cualquier moneda crypto para recibir notificaciones cuando un activo alcanza un precio objetivo.
* **Consultas de Precio:** Comandos para verificar precios actuales (`/p`) y ver gráficos (`/graf`).
* **Gestión de Usuarios:** Comandos para que los usuarios gestionen sus preferencias y alertas (`/misalertas`, `/mismonedas`, `/parar`).
* **Panel de Administración:** Comandos protegidos para que el administrador gestione el bot (`/users`, `/logs`, `/ms`).
* **Historial de Precios:** Almacena el historial de precios para análisis.

## ⚙️ Instalación y Puesta en Marcha

Sigue estos pasos para ejecutar el bot localmente:

1.  **Clonar el repositorio:**
    ```bash
    git clone [https://github.com/ersus93/bbalert.git](https://github.com/ersus93/bbalert.git)
    cd TU_REPOSITORIO
    ```

2.  **Crear un entorno virtual:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # En Windows: venv\Scripts\activate
    ```

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar variables de entorno:**
    * Renombra el archivo `apit.env.example` a `apit.env`.
    * Edita el archivo `apit.env` con tus propias claves API y tokens.

    **`apit.env.example`:**
    ```ini
    # Token de tu Bot de Telegram, obtenido de @BotFather
    TELEGRAM_BOT_TOKEN="TU_TOKEN_DE_TELEGRAM_AQUI"

    # ID de Telegram del administrador del bot
    ADMIN_TELEGRAM_ID="TU_ID_DE_TELEGRAM_AQUI"

    # Clave de API para el servicio de precios (ej. CoinMarketCap)
    CMC_API_KEY="TU_CLAVE_DE_API_AQUI"
    ```

5.  **Crear la carpeta de datos:**
    El `.gitignore` ignora esta carpeta, así que debes crearla manualmente:
    ```bash
    mkdir data
    ```
    *Nota: El bot creará los archivos `.json` vacíos al iniciarse si no existen.*

## ▶️ Uso

Para iniciar el bot, simplemente ejecuta el script principal:

```bash
python bbalert.py
=======
﻿# bbalert
Bot de Alertas de Precios (BitBreadAlert)

Este es un bot de Telegram para monitorizar precios de criptomonedas (por ejemplo HBD) y enviar alertas a usuarios. Incluye comandos de administración, consultas de precio y almacenamiento de historial en JSON.

##  Características principales

- Alertas de precio personalizables (`/alerta`, `/misalertas`).
- Consultas y gráficas (`/p`, `/graf`).
- Gestión de preferencias de usuario (`/mismonedas`, `/parar`).
- Comandos de administrador (`/users`, `/logs`, `/ms`).
- Historial de precios guardado en la carpeta `data/`.

##  Requisitos

- Python 3.8+ instalado.
- Dependencias listadas en `requirements.txt`.

## Instalación y puesta en marcha

1. Clonar el repositorio:

```bash
git clone https://github.com/ersus93/bbalert.git
cd bbalert
```

2. Crear y activar un entorno virtual:

```powershell
python -m venv venv
# PowerShell
.\venv\Scripts\Activate.ps1
# Si prefieres usar cmd.exe
.\venv\Scripts\activate
# En sistemas UNIX/Linux/macOS
source venv/bin/activate
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno

El proyecto usa un archivo `apit.env` en la raíz del proyecto. Crea `apit.env` (o edítalo) con las claves necesarias. Ejemplo de contenido mínimo:

```ini
# Token del bot (obtenido de @BotFather)
TOKEN_TELEGRAM="TU_TOKEN_DE_TELEGRAM_AQUI"

# IDs de administrador (separados por comas)
ADMIN_CHAT_IDS=123456789,987654321

# Claves de CoinMarketCap (o tu proveedor de precios)
CMC_API_KEY_ALERTA="TU_CMC_API_KEY_ALERTA"
CMC_API_KEY_CONTROL="TU_CMC_API_KEY_CONTROL"

# (Opcional) API key para screenshots
SCREENSHOT_API_KEY="TU_SCREENSHOT_API_KEY"
```

Nota: los nombres de las variables deben coincidir con el archivo `core/config.py` (por ejemplo `TOKEN_TELEGRAM`, `ADMIN_CHAT_IDS`, `CMC_API_KEY_ALERTA`, `CMC_API_KEY_CONTROL`).

5. Crear la carpeta de datos (si no existe):

```bash
mkdir data
```

El bot intentará crear los archivos JSON necesarios (`users.json`, `price_alerts.json`, etc.) la primera vez que se ejecute.

## 📊 Estructura de datos

En la carpeta `data.example/` encontrarás ejemplos documentados de los archivos JSON que usa el bot:

- `users.json` - Configuración de usuarios y preferencias
- `price_alerts.json` - Alertas de precio configuradas
- `custom_alert_history.json` - Último precio conocido por moneda
- `hbd_price_history.json` - Historial de precios HBD y otras monedas

Lee `data.example/README.md` para más detalles sobre la estructura de cada archivo.

##  Uso

## 🛠 Troubleshooting (rápido)

- Archivo de entorno: si tienes errores relacionados con variables de entorno, copia `apit.env.example` a `apit.env` y completa los valores. Asegúrate de no subir `apit.env` al repositorio.
- Errores de importación: verifica que estés ejecutando el script desde la raíz del proyecto (la misma carpeta que contiene `bbalert.py`).
- Permisos/archivos: crea la carpeta `data/` si el bot no puede crear archivos. En Windows PowerShell:

```powershell
mkdir data
```

- Dependencias: si falta algún paquete, revisa `requirements.txt` y ejecuta `pip install -r requirements.txt`.
- Logs: el bot escribe mensajes en consola; revisa la salida para pistas y compárteme el error si quieres que lo investigue.

Inicia el bot ejecutando:

```powershell
python bbalert.py
```

Verás mensajes en consola y el bot empezará a escuchar por actualizaciones.

## Notas

- Si trabajas en Windows, usa PowerShell o cmd según prefieras; las instrucciones anteriores incluyen las dos variantes.
- Si ves errores relacionados con variables de entorno, confirma que `apit.env` está en la raíz del proyecto y que sus variables están correctamente nombradas.

Si quieres que adapte este README para desplegar en un servidor (systemd, Docker, etc.), dime y lo preparo.
>>>>>>> 1f8aee0 (Primer commit)

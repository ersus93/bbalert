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

# 🤖 bbalert: Bot de Alertas de Precios (BitBreadAlert)

Este es un **bot de Telegram** diseñado para la **monitorización de precios de criptomonedas** (como HBD) y el envío de **alertas personalizadas** a los usuarios. Incluye comandos de administración, consultas de precio en tiempo real y almacenamiento de historial en formato JSON.

---

## ✨ Características Principales

* **Alertas de Precio:** Los usuarios pueden configurar alertas personalizadas para recibir notificaciones cuando un activo alcanza un precio objetivo.
* **Consultas y Gráficas:** Comandos para verificar precios actuales y visualizar gráficos históricos.
* **Gestión de Usuario:** Funcionalidades para que los usuarios gestionen sus preferencias y alertas.
* **Funciones de Administración:** Comandos protegidos para que el administrador gestione el bot, revise logs y la base de usuarios.
* **Historial de Precios:** Almacenamiento persistente del historial de precios en la carpeta `data/`.

---

## ⌨️ Comandos

### Para Usuarios
* `/start`: Inicia el bot y muestra la ayuda.
* `/p`: Consulta el precio actual de las monedas configuradas.
* `/alerta`: Configura una nueva alerta de precio.
* `/misalertas`: Muestra las alertas activas.
* `/graf`: Genera un gráfico histórico del precio.
* `/mismonedas`: Gestiona las monedas a seguir.
* `/parar`: Detiene las notificaciones o alertas.

### Para Administración
* `/users`: Muestra la lista de usuarios.
* `/logs`: Revisa los logs del bot.
* `/ms`: Envía un mensaje masivo a todos los usuarios.

---

## 📊 Estructura de Datos

La carpeta `data.example/` contiene ejemplos documentados de los archivos JSON utilizados por el bot:

* `users.json`: Configuración y preferencias de los usuarios.
* `price_alerts.json`: Alertas de precio configuradas.
* `custom_alert_history.json`: Último precio conocido por moneda para el control de alertas.
* `hbd_price_history.json`: Historial de precios de HBD y otras criptomonedas.

**Referencia:** Consulte `data.example/README.md` para obtener detalles completos sobre la estructura de cada archivo.

---

## ⚙️ Instalación y Configuración

### Requisitos

* Python 3.8+ instalado.
* Dependencias listadas en `requirements.txt`.

### 1. Instalación

1.  **Clonar el repositorio:**
    ```bash
    git clone [https://github.com/ersus93/bbalert.git](https://github.com/ersus93/bbalert.git)
    cd bbalert
    ```

2.  **Crear y activar un entorno virtual:**
    | Plataforma | Creación | Activación |
    | :--- | :--- | :--- |
    | **UNIX/Linux/macOS** | `python3 -m venv venv` | `source venv/bin/activate` |
    | **Windows (PowerShell)** | `python -m venv venv` | `.\venv\Scripts\Activate.ps1` |
    | **Windows (CMD)** | `python -m venv venv` | `.\venv\Scripts\activate` |

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

### 2. Configuración

1.  **Configurar variables de entorno:**
    * Renombre `apit.env.example` a **`.env`** (o `apit.env` si lo prefiere).
    * Edite el archivo `.env` con sus tokens y claves.

    **Ejemplo de `.env`:**
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
    *Nota: Los nombres de las variables deben coincidir con los definidos en `core/config.py`.*

2.  **Crear la carpeta de datos (si no existe):**
    ```bash
    mkdir data
    ```
    El bot creará los archivos JSON necesarios automáticamente al iniciarse si no existen.

---

## ▶️ Ejecución

Para iniciar el bot y que comience a escuchar las actualizaciones de Telegram, ejecute:

```bash
python3 bbalert.py
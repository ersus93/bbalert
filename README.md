\# 🤖 bbalert: Bot de Alertas de Precios (BitBreadAlert)



Este es un \*\*bot de Telegram\*\* diseñado para la \*\*monitorización de precios de criptomonedas\*\* (como HBD) y el envío de \*\*alertas personalizadas\*\* a los usuarios. Incluye comandos de administración, consultas de precio en tiempo real y almacenamiento de historial en formato JSON.



\## ✨ Características Principales



\* \*\*Alertas de Precio:\*\* Los usuarios pueden configurar alertas personalizadas mediante los comandos `/alerta` y `/misalertas` para recibir notificaciones cuando un activo alcanza un precio objetivo.

\* \*\*Consultas y Gráficas:\*\* Comandos para verificar precios actuales (`/p`) y visualizar gráficos históricos (`/graf`).

\* \*\*Gestión de Usuario:\*\* Funcionalidades para que los usuarios gestionen sus preferencias y alertas (`/mismonedas`, `/parar`).

\* \*\*Funciones de Administración:\*\* Comandos protegidos para que el administrador gestione el bot, revise logs y la base de usuarios (`/users`, `/logs`, `/ms`).

\* \*\*Historial de Precios:\*\* Almacenamiento persistente del historial de precios en la carpeta `data/`.



\## 📊 Estructura de Datos



La carpeta `data.example/` contiene ejemplos documentados de los archivos JSON utilizados por el bot:



\* `users.json`: Configuración y preferencias de los usuarios.

\* `price\_alerts.json`: Alertas de precio configuradas.

\* `custom\_alert\_history.json`: Último precio conocido por moneda para el control de alertas.

\* `hbd\_price\_history.json`: Historial de precios de HBD y otras criptomonedas.



\*\*Referencia:\*\* Consulte `data.example/README.md` para obtener detalles completos sobre la estructura de cada archivo.



\*\*\*



\## ⚙️ Instalación y Puesta en Marcha



\### Requisitos



\* Python 3.8+ instalado.

\* Dependencias listadas en `requirements.txt`.



\### Pasos de Instalación



1\.  \*\*Clonar el repositorio:\*\*



&nbsp;   ```bash

&nbsp;   git clone \[https://github.com/ersus93/bbalert.git](https://github.com/ersus93/bbalert.git)

&nbsp;   cd bbalert

&nbsp;   ```



2\.  \*\*Crear y activar un entorno virtual:\*\*



&nbsp;   | Plataforma | Creación | Activación |

&nbsp;   | :--- | :--- | :--- |

&nbsp;   | \*\*UNIX/Linux/macOS\*\* | `python3 -m venv venv` | `source venv/bin/activate` |

&nbsp;   | \*\*Windows (PowerShell)\*\* | `python -m venv venv` | `.\\venv\\Scripts\\Activate.ps1` |

&nbsp;   | \*\*Windows (CMD)\*\* | `python -m venv venv` | `.\\venv\\Scripts\\activate` |



3\.  \*\*Instalar dependencias:\*\*



&nbsp;   ```bash

&nbsp;   pip install -r requirements.txt

&nbsp;   ```



4\.  \*\*Configurar variables de entorno:\*\*



&nbsp;   \* Renombre `apit.env.example` a \*\*`apit.env`\*\*.

&nbsp;   \* Edite `apit.env` con sus tokens y claves.



&nbsp;   \*\*Ejemplo de `apit.env`:\*\*

&nbsp;   ```ini

&nbsp;   # Token del bot (obtenido de @BotFather)

&nbsp;   TOKEN\_TELEGRAM="TU\_TOKEN\_DE\_TELEGRAM\_AQUI"



&nbsp;   # IDs de administrador (separados por comas)

&nbsp;   ADMIN\_CHAT\_IDS=123456789,987654321



&nbsp;   # Claves de CoinMarketCap (o tu proveedor de precios)

&nbsp;   CMC\_API\_KEY\_ALERTA="TU\_CMC\_API\_KEY\_ALERTA"

&nbsp;   CMC\_API\_KEY\_CONTROL="TU\_CMC\_API\_KEY\_CONTROL"



&nbsp;   # (Opcional) API key para screenshots

&nbsp;   SCREENSHOT\_API\_KEY="TU\_SCREENSHOT\_API\_KEY"

&nbsp;   ```

&nbsp;   \*Nota: Los nombres de las variables deben coincidir con los definidos en `core/config.py`.\*



5\.  \*\*Crear la carpeta de datos (si no existe):\*\*



&nbsp;   ```bash

&nbsp;   mkdir data

&nbsp;   ```

&nbsp;   El bot creará los archivos JSON necesarios automáticamente al iniciarse si no existen.



\## ▶️ Uso



Para iniciar el bot y que comience a escuchar las actualizaciones de Telegram, ejecute:



```bash

python bbalert.py


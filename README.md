# 🤖 bbalert: Price Alert Bot (BitBreadAlert)

This is a **Telegram bot** designed for **monitoring cryptocurrency prices** (like HBD) and sending **custom alerts** to users. It includes admin commands, real-time price queries, and history storage in JSON format.

-----

## ✨ Main Features

  * **Price Alerts:** Users can set custom alerts to receive notifications when an asset reaches a target price.
  * **Queries and Charts:** Commands to check current prices and visualize historical charts.
  * **User Management:** Features for users to manage their preferences and alerts.
  * **Admin Functions:** Protected commands for the administrator to manage the bot, review logs, and see the user base.
  * **Price History:** Persistent storage of price history in the `data/` folder.

-----
Proyect 

![alt text](<Untitled diagram-2025-11-23-184058.png>)

-----

## ⌨️ Commands

Here is a list of all available commands. Admin commands offer extended functionality.

| Command | Description | Admin Only |
| :--- | :--- | :--- |
| `/start` | Starts interaction with the bot. | |
| `/ver` | Shows the last recorded price for (BTC, TON, HIVE, HBD). | |
| `/tasa` | Displays exchange rates from ElToque. | |
| `/p` | Displays price data for a specific coin. | |
| `/alerta` | Creates a new price crossover alert. | |
| `/misalertas` | Shows all your active alerts. | |
| `/monedas` | Edits your list of coins for periodic reports. | |
| `/temp` | Adjusts the time frame for your periodic coin reports. | |
| `/graf` | Displays charts. | |
| `/hbdalerts` | Enables or disables the default HBD alerts. | |
| `/parar` | Stops all periodic alerts for your coin list. | |
| `/myid` | Shows your Telegram user data. | |
| `/lang` | Changes the bot's language. | |
| `/users` | Shows your registration data. | **Yes**¹ |
| `/logs` | Displays general bot information. | **Yes**² |
| `/ms` | Sends a broadcast message to all users. | **Yes** |

¹*Admin view lists all registered users.*<br>
²*Admin view shows detailed bot logs.*

-----

## 📊 Data Structure

The `data.example/` folder contains documented examples of the JSON files used by the bot:

  * `users.json`: User configurations and preferences.
  * `price_alerts.json`: Configured price alerts.
  * `custom_alert_history.json`: Last known price for each coin (used for alert control).
  * `hbd_price_history.json`: Price history for HBD and other cryptocurrencies.
  * `eltoque_history.json`: Last known price (used for alert control)..

**Reference:** See `data.example/README.md` for complete details on each file's structure.

-----

## ⚙️ Installation and Setup

### Requirements

  * Python 3.8+ installed.
  * Dependencies listed in `requirements.txt`.

### 1\. Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/ersus93/bbalert.git
    cd bbalert
    ```

2.  **Create and activate a virtual environment:**
    | Platform | Creation | Activation |
    | :--- | :--- | :--- |
    | **UNIX/Linux/macOS** | `python3 -m venv venv` | `source venv/bin/activate` |
    | **Windows (PowerShell)** | `python -m venv venv` | `.\venv\Scripts\Activate.ps1` |
    | **Windows (CMD)** | `python -m venv venv` | `.\venv\Scripts\activate` |

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

### 2\. Configuration

1.  **Set up environment variables:**

      * Rename `apit.env.example` to **`.env`** (or `apit.env` if you prefer).
      * Edit the `.env` file with your tokens and keys.

    **Example `.env`:**

    ```ini
    # Bot Token (from @BotFather)
    TOKEN_TELEGRAM="YOUR_TELEGRAM_TOKEN_HERE"

    # Admin IDs (comma-separated)
    ADMIN_CHAT_IDS=123456789,987654321

    # CoinMarketCap Keys (or your price provider)
    CMC_API_KEY_ALERTA="YOUR_CMC_API_KEY_ALERTA"
    CMC_API_KEY_CONTROL="YOUR_CMC_API_KEY_CONTROL"

    # (Optional) API key for screenshots
    SCREENSHOT_API_KEY="YOUR_SCREENSHOT_API_KEY"
    ```

    *Note: The variable names must match those defined in `core/config.py`.*

2.  **Create the data folder (if it doesn't exist):**

    ```bash
    mkdir data
    ```

    The bot will create the necessary JSON files automatically on first run if they don't exist.

-----

## ▶️ Running the Bot

To start the bot and have it begin listening for Telegram updates, run:

```bash
python3 bbalert.py
```
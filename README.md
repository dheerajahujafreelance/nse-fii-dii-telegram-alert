# 📊 NSE FII/DII Daily Telegram Alert

An automated Python-based Telegram notification system that fetches daily Foreign Institutional Investor (FII/FPI) and Domestic Institutional Investor (DII) trading activity from the National Stock Exchange (NSE) India.

The system uses GitHub Actions to execute automatically every weekday at **8:00 PM Indian Standard Time (IST)** and delivers the report directly to a configured Telegram chat or group.

---

## 🚀 Features

- Automatically fetches FII/FPI and DII trading activity from NSE India.
- Retrieves data for the NSE Capital Market Segment.
- Displays Buy Value, Sell Value and Net Value.
- Identifies institutional investors as Net Buyers or Net Sellers.
- Sends formatted daily reports through Telegram Bot API.
- Supports Telegram groups and individual chats.
- Runs automatically through GitHub Actions.
- Includes retry handling for temporary NSE connectivity issues.
- Avoids sending previous trading day's data as a new report.
- Supports manual workflow execution for testing.

---

## ⏰ Automated Schedule

The GitHub Actions workflow runs Monday through Friday.

| Indian Time (IST) | UTC Time | Frequency |
|---|---|---|
| 8:00 PM | 14:30 UTC | Monday–Friday |

### Cron Expression

```yaml
- cron: '30 14 * * 1-5'
```

**Note:** GitHub Actions uses UTC for scheduling. Scheduled executions may occasionally be delayed. NSE data availability may also vary on market holidays.

---

## 📈 Telegram Alert Format

The Telegram notification contains:

| Category | Buy Value | Sell Value | Net Value |
|---|---:|---:|---:|
| DII | ₹ Crores | ₹ Crores | ₹ Crores |
| FII/FPI | ₹ Crores | ₹ Crores | ₹ Crores |

The notification also highlights:

- 🟢 Net Buyer
- 🔴 Net Seller
- ⚪ Neutral

All values are reported in Indian Rupees Crores.

---

## 🛠️ Technology Stack

- **Python 3.12** – Data fetching and processing.
- **Requests** – HTTP requests to NSE.
- **NSE India API** – FII/FPI and DII trading data.
- **Telegram Bot API** – Message delivery.
- **GitHub Actions** – Automated scheduling and execution.

---

## 📂 Project Structure

```text
nse-fii-dii-telegram-alert/
│
├── main.py
├── requirements.txt
├── README.md
│
└── .github/
    └── workflows/
        └── daily_alert.yml
```

---

## ⚙️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/nse-fii-dii-telegram-alert.git

cd nse-fii-dii-telegram-alert
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Telegram Bot

Create a Telegram bot using [@BotFather](https://t.me/BotFather).

Obtain the following:

- Telegram Bot Token
- Telegram Chat ID or Group Chat ID

Add the bot to your Telegram group and grant the necessary permissions.

### 4. Configure GitHub Secrets

Navigate to:

**Repository → Settings → Secrets and variables → Actions**

Create these repository secrets:

| Secret Name | Description |
|---|---|
| `BOT_TOKEN` | Telegram Bot API token |
| `CHAT_ID` | Telegram user/group chat ID |

Never expose your Telegram bot token in public source code.

### 5. Enable GitHub Actions

Navigate to the Actions tab and enable the workflow.

The alert will automatically run according to the configured weekday schedule.

---

## 🧪 Manual Execution

To test the workflow:

1. Open the GitHub repository.
2. Navigate to Actions.
3. Select NSE FII DII Telegram Alert.
4. Click Run workflow.
5. Monitor the execution logs.

A successful execution should deliver the report to the configured Telegram chat.

---

## 🔗 Data Source

Official NSE India FII/FPI and DII Trading Activity:

https://www.nseindia.com/reports/fii-dii

API endpoint currently used:

https://www.nseindia.com/api/fiidiiTradeReact

**Important:** The API endpoint is an NSE website endpoint and is not guaranteed to remain unchanged. NSE may modify its access restrictions or response format.

---

## ⚠️ Important Notes

- Reports are based on NSE Capital Market Segment data.
- The workflow is scheduled for weekdays only.
- NSE data is generally updated after market hours.
- If the latest report is unavailable, the script sends a warning rather than presenting stale data as current.
- NSE figures may be revised following subsequent confirmations.
- GitHub Actions scheduled runs are subject to platform availability and scheduling delays.

---

## 🔮 Future Enhancements

Potential improvements:

- Automatic retry mechanism for delayed NSE reports.
- Nifty 50 and Bank Nifty daily closing summary.
- FII/FPI index futures and options activity.
- India VIX tracking.
- Market sentiment and institutional flow analysis.
- Historical FII/DII data storage.
- Daily, weekly and monthly institutional flow summaries.

---

## 👨‍💻 Author

**CompoundMindFin**

Automated Indian Market Intelligence and Institutional Flow Tracking.

---

*Disclaimer: This project is intended for informational and educational purposes only. It does not provide investment advice or trading recommendations.*

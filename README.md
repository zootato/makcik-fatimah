# 🧕 Mak Cik Fatimah — Singapore Halal Food Finder Bot

A Telegram bot with the personality of a Singaporean Malay auntie who knows exactly where to find the best halal food in Singapore. 🇸🇬🍛

Powered by the `singapore-halal-establishments` dataset and geocoded via the OneMap API.

---

## ✨ Features

- 🎲 **Guided or Freestyle Recommendations** — Let Mak Cik pick for you based on cuisine, area, and halal certification, or just go full surprise!
- 📍 **Location-Based Search** — Send your live location and Mak Cik finds the nearest halal food spots, sorted by distance.
- 🔍 **Keyword Search** — Craving nasi lemak or briyani? Just type it!
- 🗺️ **Google Maps Links** — One-tap navigation to any recommended stall.
- 🧕 **Mak Cik Personality** — Warm, funny Singlish/Malay auntie dialogue that feels like talking to your own neighbour.

---

# 🚀 Quick Start

## Prerequisites

- Python 3.10+
- A Telegram Bot Token from `@BotFather`

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/zootato/makcik-fatimah.git
cd makcik-fatimah

# 2. Create a virtual environment
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env

# Edit .env and add your BOT_TOKEN and DATA_SOURCE_URL

# 5. Run the bot
python bot.py
```

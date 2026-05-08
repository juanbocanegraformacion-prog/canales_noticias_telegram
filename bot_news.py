import os

# En lugar de poner los strings directo, usamos os.environ
DB_URL = os.getenv('DB_URL')
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')

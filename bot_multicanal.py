import os
import feedparser
import psycopg2
import requests
from bs4 import BeautifulSoup
from telegram import Bot
import asyncio

# --- CONFIGURACIÓN DE CANALES ---
# Formato: "Categoría": ["URL_RSS", "ID_DEL_CANAL"]
CANALES_CONFIG = {
    "Deportes": ["https://news.google.com/rss/headlines/section/topic/SPORTS?hl=es-419", os.getenv("CH_DEPORTES")],
    "Farándula": ["https://news.google.com/rss/search?q=farandula+ENTERTAINMENT&hl=es-419", os.getenv("CH_ENTRETENIMIENTO")],
    "Mundo": ["https://news.google.com/rss/headlines/section/topic/WORLD?hl=es-419", os.getenv("CH_MUNDO")],
    "Finanzas": ["https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=es-419", os.getenv("CH_FINANZAS")],
    "Fitness": ["https://news.google.com/rss/search?q=fitness+y+salud&hl=es-419", os.getenv("CH_FITNESS")],
    "Tecnología": ["https://news.google.com/rss/search?q=tecnologia&hl=es-419", os.getenv("CH_TECNOLOGIA")] 
}

DB_URL = os.getenv("DB_URL")
TOKEN = os.getenv("TELEGRAM_TOKEN") # Un solo bot puede administrar los 5 canales

async def procesar_canal(categoria, url_rss, channel_id):
    bot = Bot(token=TOKEN)
    feed = feedparser.parse(url_rss)
    
    print(f"--- Procesando {categoria} ---")
    
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            for entry in feed.entries[:3]: # 3 noticias por cada categoría por ejecución
                # Verificar si ya existe
                cur.execute("SELECT id FROM noticias_publicadas WHERE noticia_hash = %s", (entry.link,))
                if cur.fetchone(): continue
                
                # Extraer Imagen
                imagen = None
                try:
                    res = requests.get(entry.link, timeout=5)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    img_tag = soup.find("meta", property="og:image")
                    imagen = img_tag["content"] if img_tag else None
                except: pass

                caption = f"<b>{categoria.upper()}</b>\n\n🆕 {entry.title}\n\n📍 <a href='{entry.link}'>Leer más</a>"
                
                try:
                    if imagen:
                        await bot.send_photo(chat_id=channel_id, photo=imagen, caption=caption, parse_mode='HTML')
                    else:
                        await bot.send_message(chat_id=channel_id, text=caption, parse_mode='HTML')
                    
                    # Guardar en DB
                    cur.execute("INSERT INTO noticias_publicadas (noticia_hash, categoria) VALUES (%s, %s)", (entry.link, categoria))
                    conn.commit()
                except Exception as e:
                    print(f"Error en {categoria}: {e}")

async def main():
    tasks = []
    for cat, info in CANALES_CONFIG.items():
        tasks.append(procesar_canal(cat, info[0], info[1]))
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())

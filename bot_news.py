import os
import feedparser
import psycopg2
import requests
from bs4 import BeautifulSoup
from telegram import Bot
import asyncio
import random

# Configuración mediante variables de entorno (GitHub Secrets)
DB_URL = os.getenv("DB_URL")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

def noticia_ya_publicada(url_hash):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM noticias_publicadas WHERE noticia_hash = %s", (url_hash,))
            return cur.fetchone() is not None

def guardar_noticia_y_contar(url_hash):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO noticias_publicadas (noticia_hash) VALUES (%s)", (url_hash,))
            cur.execute("UPDATE contador_publicaciones SET total_enviadas = total_enviadas + 1 RETURNING total_enviadas")
            return cur.fetchone()[0]

def extraer_imagen(url):
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        img = soup.find("meta", property="og:image")
        return img["content"] if img else None
    except: return None

async def publicar_anuncio():
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT texto_anuncio, imagen_url, link_afiliado FROM anuncios_disponibles WHERE activo = TRUE")
            ads = cur.fetchall()
            if ads:
                ad = random.choice(ads)
                bot = Bot(token=TOKEN)
                txt = f"<b>📢 PUBLICIDAD</b>\n\n{ad[0]}\n\n👉 <a href='{ad[2]}'>Ver más</a>"
                await bot.send_photo(chat_id=CHANNEL_ID, photo=ad[1], caption=txt, parse_mode='HTML')

async def procesar():
    feed = feedparser.parse('https://news.google.com/rss/search?q=tecnologia&hl=es-419')
    bot = Bot(token=TOKEN)
    
    for entry in feed.entries[:5]:
        if not noticia_ya_publicada(entry.link):
            img = extraer_imagen(entry.link)
            caption = f"<b>🆕 {entry.title}</b>\n\n📍 <a href='{entry.link}'>Leer noticia</a>"
            
            try:
                if img: await bot.send_photo(chat_id=CHANNEL_ID, photo=img, caption=caption, parse_mode='HTML')
                else: await bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode='HTML')
                
                conteo = guardar_noticia_y_contar(entry.link)
                if conteo % 10 == 0: await publicar_anuncio()
            except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(procesar())

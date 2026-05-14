import os
import feedparser
import psycopg2
import requests
from bs4 import BeautifulSoup
from telegram import Bot
import asyncio
import random

# --- CONFIGURACIÓN DE CANALES ---
CANALES_CONFIG = {
    "Deportes": ["https://news.google.com/rss/headlines/section/topic/SPORTS?hl=es-419", os.getenv("CH_DEPORTES")],
    "Farándula": ["https://news.google.com/rss/search?q=farandula+ENTERTAINMENT&hl=es-419", os.getenv("CH_ENTRETENIMIENTO")],
    "Mundo": ["https://news.google.com/rss/headlines/section/topic/WORLD?hl=es-419", os.getenv("CH_MUNDO")],
    "Finanzas": ["https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=es-419", os.getenv("CH_FINANZAS")],
    "Fitness": ["https://news.google.com/rss/search?q=fitness+y+salud&hl=es-419", os.getenv("CH_FITNESS")],
    "Tecnología": ["https://news.google.com/rss/search?q=tecnologia&hl=es-419", os.getenv("CH_TECNOLOGIA")]
}

DB_URL = os.getenv("DB_URL")
TOKEN = os.getenv("TELEGRAM_TOKEN")

# --- LISTA DE GANCHOS (HOOKS) PARA CLICKS ---
GANCHOS = [
    "¡Entérate de todos los detalles aquí! 👇",
    "No vas a creer lo que pasó. Mira la nota completa: 🚀",
    "Lee la noticia completa en nuestro portal: 📍",
    "¿Quieres saber más? Haz clic abajo: 🔥",
    "Toda la información disponible aquí: 👇",
    "Actualización de último minuto: ⏱️"
]

def extraer_imagen(url):
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        img = soup.find("meta", property="og:image")
        return img["content"] if img else None
    except: return None

def guardar_noticia_y_contar(url_hash, categoria):
    """Guarda la noticia y retorna el nuevo conteo total para decidir si poner anuncio."""
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            # Registrar noticia
            cur.execute("INSERT INTO noticias_publicadas (noticia_hash, categoria) VALUES (%s, %s)", (url_hash, categoria))
            # Actualizar y obtener contador global
            cur.execute("UPDATE contador_publicaciones SET total_enviadas = total_enviadas + 1 WHERE id = 1 RETURNING total_enviadas")
            return cur.fetchone()[0]

async def publicar_anuncio(channel_id):
    """Selecciona un anuncio activo al azar y lo publica en el canal actual."""
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT texto_anuncio, imagen_url, link_afiliado FROM anuncios_disponibles WHERE activo = TRUE")
                ads = cur.fetchall()
                if ads:
                    ad = random.choice(ads)
                    bot = Bot(token=TOKEN)
                    txt = f"<b>📢 PUBLICIDAD</b>\n\n{ad[0]}\n\n👉 <a href='{ad[2]}'>MÁS INFORMACIÓN AQUÍ</a>"
                    await bot.send_photo(chat_id=channel_id, photo=ad[1], caption=txt, parse_mode='HTML')
                    print(f"💰 Anuncio publicado en el canal {channel_id}")
    except Exception as e:
        print(f"❌ Error al publicar anuncio: {e}")

async def procesar_canal(categoria, url_rss, channel_id):
    if not channel_id: return

    bot = Bot(token=TOKEN)
    feed = feedparser.parse(url_rss)
    
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                # Procesar noticias (máximo 3 por ejecución)
                for entry in feed.entries[:3]:
                    # 1. Evitar duplicados (Verificamos noticia_hash)
                    cur.execute("SELECT id FROM noticias_publicadas WHERE noticia_hash = %s", (entry.link,))
                    if cur.fetchone(): continue
                    
                    img = extraer_imagen(entry.link)
                    gancho = random.choice(GANCHOS)
                    
                    # 2. Formatear con HOOK
                    caption = f"🚀 <b>{categoria.upper()}</b>\n\n🆕 {entry.title}\n\n{gancho}\n📍 <a href='{entry.link}'>Leer noticia completa</a>"
                    
                    try:
                        # 3. Enviar noticia
                        if img:
                            await bot.send_photo(chat_id=channel_id, photo=img, caption=caption, parse_mode='HTML')
                        else:
                            await bot.send_message(chat_id=channel_id, text=caption, parse_mode='HTML')
                        
                        # 4. Contabilizar y verificar anuncio
                        conteo = guardar_noticia_y_contar(entry.link, categoria)
                        print(f"✅ {categoria}: Noticia enviada (Total: {conteo})")
                        
                        # Cada 10 noticias publicadas GLOBALMENTE, pone un anuncio en el canal actual
                        if conteo % 10 == 0:
                            await publicar_anuncio(channel_id)
                            
                    except Exception as e:
                        print(f"❌ Error Telegram: {e}")
    except Exception as e:
        print(f"🔥 Error DB: {e}")

async def main():
    tareas = [procesar_canal(cat, info[0], info[1]) for cat, info in CANALES_CONFIG.items()]
    await asyncio.gather(*tareas)

if __name__ == "__main__":
    asyncio.run(main())

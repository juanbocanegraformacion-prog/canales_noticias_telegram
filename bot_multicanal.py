import os
import feedparser
import psycopg2
import requests
from bs4 import BeautifulSoup
from telegram import Bot
import asyncio

# --- CONFIGURACIÓN DE CANALES ---
# Mapeo de Categoría -> [URL del RSS, ID del Canal (Secret)]
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

def extraer_imagen(url):
    """Realiza scraping básico para obtener la imagen destacada (OpenGraph)."""
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        img = soup.find("meta", property="og:image")
        return img["content"] if img else None
    except Exception:
        return None

async def procesar_canal(categoria, url_rss, channel_id):
    """Procesa las noticias de un canal específico."""
    if not channel_id:
        print(f"⚠️ Error: No se encontró el ID para {categoria}. Revisa tus Secrets.")
        return

    bot = Bot(token=TOKEN)
    feed = feedparser.parse(url_rss)
    
    print(f"--- Iniciando scraping de: {categoria} ---")
    
    # Conexión a la base de datos Supabase
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                # Tomamos las últimas 3 noticias de cada feed para evitar saturar
                for entry in feed.entries[:3]:
                    # 1. Verificar si la noticia ya fue publicada
                    cur.execute("SELECT id FROM noticias_publicadas WHERE noticia_hash = %s", (entry.link,))
                    if cur.fetchone():
                        continue
                    
                    # 2. Intentar obtener imagen
                    imagen = extraer_imagen(entry.link)
                    
                    # 3. Formatear mensaje
                    header = f"🚀 <b>{categoria.upper()}</b>"
                    cuerpo = f"{entry.title}"
                    footer = f"📍 <a href='{entry.link}'>Leer noticia completa</a>"
                    caption = f"{header}\n\n🆕 {cuerpo}\n\n{footer}"
                    
                    # 4. Enviar a Telegram
                    try:
                        if imagen:
                            await bot.send_photo(chat_id=channel_id, photo=imagen, caption=caption, parse_mode='HTML')
                        else:
                            await bot.send_message(chat_id=channel_id, text=caption, parse_mode='HTML', disable_web_page_preview=False)
                        
                        # 5. Registrar en DB tras envío exitoso
                        cur.execute("INSERT INTO noticias_publicadas (noticia_hash, categoria) VALUES (%s, %s)", (entry.link, categoria))
                        conn.commit()
                        print(f"✅ Publicado en {categoria}: {entry.title[:30]}...")
                    
                    except Exception as e:
                        print(f"❌ Error al enviar mensaje a Telegram ({categoria}): {e}")
                        
    except Exception as e:
        print(f"🔥 Error de conexión a la Base de Datos: {e}")

async def main():
    # Creamos tareas para procesar todos los canales en paralelo
    tareas = []
    for cat, info in CANALES_CONFIG.items():
        tareas.append(procesar_canal(cat, info[0], info[1]))
    
    await asyncio.gather(*tareas)

if __name__ == "__main__":
    if not TOKEN or not DB_URL:
        print("❌ CRÍTICO: Faltan variables de entorno esenciales (TOKEN o DB_URL).")
    else:
        asyncio.run(main())

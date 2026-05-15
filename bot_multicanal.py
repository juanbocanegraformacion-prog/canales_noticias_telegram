import os
import feedparser
import requests
import asyncio
import random
from bs4 import BeautifulSoup
from telegram import Bot
from supabase import create_client, Client

# --- CONFIGURACIÓN DE CONEXIÓN ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TOKEN = os.getenv("TELEGRAM_TOKEN")

CANALES_CONFIG = {
    "Deportes": ["https://news.google.com/rss/headlines/section/topic/SPORTS?hl=es-419", os.getenv("CH_DEPORTES")],
    "Farándula": ["https://news.google.com/rss/search?q=farandula+ENTERTAINMENT&hl=es-419", os.getenv("CH_ENTRETENIMIENTO")],
    "Mundo": ["https://news.google.com/rss/headlines/section/topic/WORLD?hl=es-419", os.getenv("CH_MUNDO")],
    "Finanzas": ["https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=es-419", os.getenv("CH_FINANZAS")],
    "Fitness": ["https://news.google.com/rss/search?q=fitness+y+salud&hl=es-419", os.getenv("CH_FITNESS")],
    "Tecnología": ["https://news.google.com/rss/search?q=tecnologia&hl=es-419", os.getenv("CH_TECNOLOGIA")]
}

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

def noticia_ya_publicada(url_hash):
    res = supabase.table("noticias_publicadas").select("id").eq("noticia_hash", url_hash).execute()
    return len(res.data) > 0

def guardar_noticia_y_contar(url_hash, categoria):
    # Registrar noticia
    supabase.table("noticias_publicadas").insert({"noticia_hash": url_hash, "categoria": categoria}).execute()
    # Obtener contador actual
    res_count = supabase.table("contador_publicaciones").select("total_enviadas").eq("id", 1).execute()
    nuevo_total = res_count.data[0]["total_enviadas"] + 1
    # Actualizar contador
    supabase.table("contador_publicaciones").update({"total_enviadas": nuevo_total}).eq("id", 1).execute()
    return nuevo_total

async def publicar_anuncio(channel_id):
    try:
        res = supabase.table("anuncios_disponibles").select("*").eq("activo", True).execute()
        if res.data:
            ad = random.choice(res.data)
            bot = Bot(token=TOKEN)
            txt = f"<b>📢 PUBLICIDAD</b>\n\n{ad['texto_anuncio']}\n\n👉 <a href='{ad['link_afiliado']}'>MÁS INFORMACIÓN AQUÍ</a>"
            await bot.send_photo(chat_id=channel_id, photo=ad['imagen_url'], caption=txt, parse_mode='HTML')
            print(f"💰 Anuncio enviado a {channel_id}")
    except Exception as e: print(f"❌ Error Anuncio: {e}")

async def procesar_canal(categoria, url_rss, channel_id):
    if not channel_id: return
    bot = Bot(token=TOKEN)
    feed = feedparser.parse(url_rss)
    
    for entry in feed.entries[:3]:
        if noticia_ya_publicada(entry.link): continue
        
        img = extraer_imagen(entry.link)
        gancho = random.choice(GANCHOS)
        caption = f"🚀 <b>{categoria.upper()}</b>\n\n🆕 {entry.title}\n\n{gancho}\n📍 <a href='{entry.link}'>Leer noticia completa</a>"
        
        try:
            if img:
                await bot.send_photo(chat_id=channel_id, photo=img, caption=caption, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=channel_id, text=caption, parse_mode='HTML')
            
            conteo = guardar_noticia_y_contar(entry.link, categoria)
            print(f"✅ {categoria}: Publicado ({conteo})")
            
            if conteo % 10 == 0:
                await publicar_anuncio(channel_id)
        except Exception as e: print(f"❌ Error Telegram ({categoria}): {e}")

async def main():
    tareas = [procesar_canal(cat, info[0], info[1]) for cat, info in CANALES_CONFIG.items()]
    await asyncio.gather(*tareas)

if __name__ == "__main__":
    asyncio.run(main())


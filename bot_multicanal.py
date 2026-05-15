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

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ CRÍTICO: Falta configurar SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en las variables de entorno.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

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
    except: 
        return None

def noticia_ya_publicada(url_hash):
    if not supabase: 
        return False
    try:
        res = supabase.table("noticias_publicadas").select("id").eq("noticia_hash", url_hash).execute()
        return len(res.data) > 0
    except Exception as e:
        print(f"⚠️ Error al verificar existencia de noticia en base de datos: {e}")
        return False

def guardar_noticia_y_contar(url_hash, categoria):
    if not supabase: 
        return 0
    try:
        # Registrar noticia procesada
        supabase.table("noticias_publicadas").insert({"noticia_hash": url_hash, "categoria": categoria}).execute()
        
        # Consultar la tabla de control de forma dinámica
        res_count = supabase.table("contador_publicaciones").select("id, total_enviadas").execute()
        
        if res_count.data:
            fila_id = res_count.data[0]["id"]
            nuevo_total = res_count.data[0]["total_enviadas"] + 1
            supabase.table("contador_publicaciones").update({"total_enviadas": nuevo_total}).eq("id", fila_id).execute()
        else:
            # Inicialización de contingencia si la tabla de control está vacía
            nuevo_total = 1
            supabase.table("contador_publicaciones").insert({"total_enviadas": nuevo_total}).execute()
            
        return nuevo_total
    except Exception as e:
        print(f"⚠️ Error de persistencia en Supabase (guardar_noticia_y_contar): {e}")
        return 0

async def publicar_anuncio(bot, channel_id):
    if not supabase: 
        return
    try:
        res = supabase.table("anuncios_disponibles").select("*").eq("activo", True).execute()
        if res.data:
            ad = random.choice(res.data)
            txt = f"<b>📢 PUBLICIDAD</b>\n\n{ad['texto_anuncio']}\n\n👉 <a href='{ad['link_afiliado']}'>MÁS INFORMACIÓN AQUÍ</a>"
            
            if ad.get('imagen_url'):
                await bot.send_photo(chat_id=channel_id, photo=ad['imagen_url'], caption=txt, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=channel_id, text=txt, parse_mode='HTML')
            print(f"💰 Anuncio integrado enviado al canal {channel_id}")
    except Exception as e: 
        print(f"❌ Error al procesar la inserción de anuncio publicitario: {e}")

async def procesar_canal(bot, categoria, url_rss, channel_id):
    if not channel_id: 
        print(f"⚠️ Advertencia: Omitiendo categoría '{categoria}' porque su variable de entorno de ID de canal está vacía.")
        return
        
    print(f"🔄 Sincronizando fuente RSS de la categoría: {categoria}...")
    try:
        feed = feedparser.parse(url_rss)
    except Exception as e:
        print(f"❌ Error al parsear el feed RSS de {categoria}: {e}")
        return
    
    for entry in feed.entries[:3]:
        try:
            if noticia_ya_publicada(entry.link): 
                continue
            
            img = extraer_imagen(entry.link)
            gancho = random.choice(GANCHOS)
            caption = f"🚀 <b>{categoria.upper()}</b>\n\n🆕 {entry.title}\n\n{gancho}\n📍 <a href='{entry.link}'>Leer noticia completa</a>"
            
            if img:
                await bot.send_photo(chat_id=channel_id, photo=img, caption=caption, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=channel_id, text=caption, parse_mode='HTML')
            
            conteo = guardar_noticia_y_contar(entry.link, categoria)
            print(f"✅ {categoria}: Publicado con éxito. Contador acumulado: {conteo}")
            
            if conteo > 0 and conteo % 10 == 0:
                await publicar_anuncio(bot, channel_id)
                
        except Exception as e: 
            print(f"❌ Error procesando entrada individual en el canal ({categoria}): {e}")

async def main():
    if not TOKEN:
        print("❌ CRÍTICO: No se localizó la variable de entorno TELEGRAM_TOKEN.")
        return
        
    print("🚀 Levantando el servicio asíncrono del Bot Multicanal...")
    
    # Inicialización centralizada de la sesión de red del Bot
    async with Bot(token=TOKEN) as bot:
        tareas = [procesar_canal(bot, cat, info[0], info[1]) for cat, info in CANALES_CONFIG.items()]
        await asyncio.gather(*tareas)
        
    print("🏁 Flujo de ejecución concurrente completado con éxito.")

if __name__ == "__main__":
    asyncio.run(main())

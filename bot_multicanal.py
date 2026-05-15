import os
import feedparser
import requests
import asyncio
import random
from bs4 import BeautifulSoup
from telegram import Bot
from supabase import create_client, Client

# --- CONFIGURACIÓN DE CONEXIÓN (Claves integradas como Fallback) ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://vjtqhjykwqutxvrufgpv.supabase.co")
SUPABASE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZqdHFoanlrd3F1dHh2cnVmZ3B2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODUyNDkwMCwiZXhwIjoyMDk0MTAwOTAwfQ.jhxHBIBE2liTHdD8WV2CyYSF9xx9Wxfl8HwJ4sXnhbo"
)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TOKEN = os.getenv("TELEGRAM_TOKEN", "8846389275:AAHwaZEzo8728Pur6N1RfMKGC7T2xY2bW54")

# Diccionario de canales configurado con tus IDs de Telegram correspondientes
CANALES_CONFIG = {
    "Deportes": [
        "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=es-419", 
        os.getenv("CH_DEPORTES", "-1003992580175")
    ],
    "Farándula": [
        "https://news.google.com/rss/search?q=farandula+ENTERTAINMENT&hl=es-419", 
        os.getenv("CH_ENTRETENIMIENTO", "-1003994588815")
    ],
    "Mundo": [
        "https://news.google.com/rss/headlines/section/topic/WORLD?hl=es-419", 
        os.getenv("CH_MUNDO", "-1003880714970")
    ],
    "Finanzas": [
        "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=es-419", 
        os.getenv("CH_FINANZAS", "-1003956746586")
    ],
    "Fitness": [
        "https://news.google.com/rss/search?q=fitness+y+salud&hl=es-419", 
        os.getenv("CH_FITNESS", "-1003957425191")
    ],
    "Tecnología": [
        "https://news.google.com/rss/search?q=tecnologia&hl=es-419", 
        os.getenv("CH_TECNOLOGIA", "-1003919652847")
    ]
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
    try:
        res = supabase.table("noticias_publicadas").select("id").eq("noticia_hash", url_hash).execute()
        return len(res.data) > 0
    except Exception as e:
        print(f"⚠️ Error verificando duplicados en Supabase: {e}")
        return False

def guardar_noticia_y_contar(url_hash, categoria):
    try:
        # Registrar noticia
        supabase.table("noticias_publicadas").insert({"noticia_hash": url_hash, "categoria": categoria}).execute()
        
        # Obtener contador de forma dinámica para evitar desbordamiento de índices
        res_count = supabase.table("contador_publicaciones").select("id, total_enviadas").execute()
        
        if res_count.data:
            fila_id = res_count.data[0]["id"]
            nuevo_total = res_count.data[0]["total_enviadas"] + 1
            supabase.table("contador_publicaciones").update({"total_enviadas": nuevo_total}).eq("id", fila_id).execute()
        else:
            nuevo_total = 1
            supabase.table("contador_publicaciones").insert({"total_enviadas": nuevo_total}).execute()
            
        return nuevo_total
    except Exception as e:
        print(f"⚠️ Error actualizando base de datos (noticias/contadores): {e}")
        return 0

async def publicar_anuncio(bot, channel_id):
    try:
        res = supabase.table("anuncios_disponibles").select("*").eq("activo", True).execute()
        if res.data:
            ad = random.choice(res.data)
            txt = f"<b>📢 PUBLICIDAD</b>\n\n{ad['texto_anuncio']}\n\n👉 <a href='{ad['link_afiliado']}'>MÁS INFORMACIÓN AQUÍ</a>"
            
            if ad.get('imagen_url'):
                await bot.send_photo(chat_id=channel_id, photo=ad['imagen_url'], caption=txt, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=channel_id, text=txt, parse_mode='HTML')
            print(f"💰 Anuncio enviado al canal: {channel_id}")
    except Exception as e: 
        print(f"❌ Error al enviar anuncio: {e}")

async def procesar_canal(bot, categoria, url_rss, channel_id):
    if not channel_id: 
        print(f"⚠️ Salto de canal: La categoría {categoria} no tiene ID configurado.")
        return
        
    print(f"🔄 Leyendo noticias de la categoría: {categoria}...")
    try:
        feed = feedparser.parse(url_rss)
    except Exception as e:
        print(f"❌ Error parseando RSS de {categoria}: {e}")
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
            print(f"✅ {categoria}: Publicado con éxito. (Total global: {conteo})")
            
            if conteo > 0 and conteo % 10 == 0:
                await publicar_anuncio(bot, channel_id)
                
        except Exception as e: 
            print(f"❌ Error enviando mensaje individual a Telegram ({categoria}): {e}")

async def main():
    print("🚀 Iniciando la ejecución del Bot Multicanal...")
    
    # Abrir la sesión de red de Telegram correctamente usando un context manager asíncrono
    async with Bot(token=TOKEN) as bot:
        tareas = [procesar_canal(bot, cat, info[0], info[1]) for cat, info in CANALES_CONFIG.items()]
        await asyncio.gather(*tareas)
        
    print("🏁 Proceso de envío finalizado.")

if __name__ == "__main__":
    asyncio.run(main())

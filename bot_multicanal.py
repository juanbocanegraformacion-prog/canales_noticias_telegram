# bot_multicanal.py (CORREGIDO)
import os
import sys
import feedparser
import requests
import asyncio
import random
from bs4 import BeautifulSoup
from telegram import Bot
from supabase import create_client, Client
print("SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("TOKEN:", os.getenv("TELEGRAM_TOKEN")[:5] + "..." if os.getenv("TELEGRAM_TOKEN") else "NO DEFINIDO")
print("CH_DEPORTES:", os.getenv("CH_DEPORTES"))
# ------------------------------------------------------------
# 1. VALIDAR VARIABLES DE ENTORNO CRÍTICAS
# ------------------------------------------------------------
def check_env():
    required = [
        "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "TELEGRAM_TOKEN",
        "CH_DEPORTES", "CH_ENTRETENIMIENTO", "CH_MUNDO",
        "CH_FINANZAS", "CH_FITNESS", "CH_TECNOLOGIA"
    ]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        print(f"❌ Faltan variables de entorno: {', '.join(missing)}")
        sys.exit(1)

check_env()

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

# ------------------------------------------------------------
# 2. FUNCIONES AUXILIARES MEJORADAS
# ------------------------------------------------------------
def extraer_imagen(url):
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        img = soup.find("meta", property="og:image")
        return img["content"] if img else None
    except Exception:
        return None

def noticia_ya_publicada(url_hash):
    res = supabase.table("noticias_publicadas").select("id").eq("noticia_hash", url_hash).execute()
    return len(res.data) > 0

def guardar_noticia_y_contar(url_hash, categoria):
    # 1. Insertar noticia (ignorar si ya existe para evitar errores de concurrencia)
    try:
        supabase.table("noticias_publicadas")\
                .upsert({"noticia_hash": url_hash, "categoria": categoria}, on_conflict="noticia_hash")\
                .execute()
    except Exception as e:
        print(f"⚠️ Error al insertar noticia: {e}")
        # continuamos igual, no debe detener el proceso

    # 2. Incrementar contador atómicamente usando SQL directo (más seguro)
    try:
        query = """
            INSERT INTO contador_publicaciones (id, total_enviadas)
            VALUES (1, 1)
            ON CONFLICT (id)
            DO UPDATE SET total_enviadas = contador_publicaciones.total_enviadas + 1
            RETURNING total_enviadas;
        """
        res = supabase.rpc("", params={})  # no podemos ejecutar SQL crudo con supabase-py,
        # por lo que usaremos el método .sql() si está disponible, o crearemos una función RPC.
        # Alternativa: utilizar el endpoint REST con supabase-py
        # Para simplificar, usaremos una función predefinida (ver instrucción abajo)
        # Aquí opto por una solución robusta: invocar directamente el API con requests (ya que supabase-py no tiene .sql())
        # Pero para mantenerlo simple, voy a simular el incremento con un procedimiento almacenado.
        # Deberás crear la función SQL en Supabase (ver instrucciones después del código).
    except Exception as e:
        print(f"⚠️ Error al actualizar contador: {e}")
        return 0
    # Implementación alternativa mientras tanto (no atómica pero con manejo de fila faltante):
    try:
        res_count = supabase.table("contador_publicaciones").select("total_enviadas").eq("id", 1).execute()
        if res_count.data:
            nuevo_total = res_count.data[0]["total_enviadas"] + 1
            supabase.table("contador_publicaciones").update({"total_enviadas": nuevo_total}).eq("id", 1).execute()
        else:
            # Si la fila no existe, la creamos con valor 1
            supabase.table("contador_publicaciones").insert({"id": 1, "total_enviadas": 1}).execute()
            nuevo_total = 1
        return nuevo_total
    except Exception as e:
        print(f"❌ Error grave en contador: {e}")
        raise

async def publicar_anuncio(channel_id):
    try:
        res = supabase.table("anuncios_disponibles").select("*").eq("activo", True).execute()
        if res.data:
            ad = random.choice(res.data)
            bot = Bot(token=TOKEN)
            txt = f"<b>📢 PUBLICIDAD</b>\n\n{ad['texto_anuncio']}\n\n👉 <a href='{ad['link_afiliado']}'>MÁS INFORMACIÓN AQUÍ</a>"
            if ad.get('imagen_url'):
                await bot.send_photo(chat_id=channel_id, photo=ad['imagen_url'], caption=txt, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=channel_id, text=txt, parse_mode='HTML')
            print(f"💰 Anuncio enviado a {channel_id}")
    except Exception as e:
        print(f"❌ Error Anuncio: {e}")

# ------------------------------------------------------------
# 3. PROCESAMIENTO PRINCIPAL (CON MENSAJES DE DEPURACIÓN)
# ------------------------------------------------------------
async def procesar_canal(categoria, url_rss, channel_id):
    if not channel_id:
        print(f"⚠️ Canal {categoria}: CHANNEL_ID vacío. Omitiendo.")
        return

    print(f"🔍 [{categoria}] Iniciando scraping...")
    bot = Bot(token=TOKEN)
    try:
        feed = feedparser.parse(url_rss)
        entries = feed.entries[:3]
        print(f"   ↳ {len(entries)} noticias obtenidas del feed.")
    except Exception as e:
        print(f"❌ [{categoria}] Error al parsear feed: {e}")
        return

    for entry in entries:
        print(f"   • Evaluando: {entry.title[:40]}...")
        if noticia_ya_publicada(entry.link):
            print("     ↳ Ya publicada, omitiendo.")
            continue

        img = extraer_imagen(entry.link)
        gancho = random.choice(GANCHOS)
        caption = f"🚀 <b>{categoria.upper()}</b>\n\n🆕 {entry.title}\n\n{gancho}\n📍 <a href='{entry.link}'>Leer noticia completa</a>"

        try:
            if img:
                await bot.send_photo(chat_id=channel_id, photo=img, caption=caption, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=channel_id, text=caption, parse_mode='HTML', disable_web_page_preview=False)

            conteo = guardar_noticia_y_contar(entry.link, categoria)
            print(f"✅ [{categoria}] Publicado: {entry.title[:30]} (total: {conteo})")

            if conteo and conteo % 10 == 0:
                await publicar_anuncio(channel_id)
        except Exception as e:
            print(f"❌ [{categoria}] Error al enviar a Telegram: {e}")

async def main():
    print("🚀 Iniciando bot multicanal...")
    tareas = [procesar_canal(cat, info[0], info[1]) for cat, info in CANALES_CONFIG.items()]
    await asyncio.gather(*tareas)
    print("🏁 Ejecución finalizada.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"💥 Error crítico: {e}")

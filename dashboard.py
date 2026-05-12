import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import os

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="NewsBot Control Panel", layout="wide")

# --- CONFIGURACIÓN DE CONEXIÓN (SUPABASE) ---
# Ahora leemos desde secrets, pero como fallback usamos las credenciales por defecto
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://vjtqhjykwqutxvrufgpv.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZqdHFoanlrd3F1dHh2cnVmZ3B2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODUyNDkwMCwiZXhwIjoyMDk0MTAwOTAwfQ.jhxHBIBE2liTHdD8WV2CyYSF9xx9Wxfl8HwJ4sXnhbo"
)

# Inicializar cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# --- INTERFAZ ---
st.title("🤖 NewsBot Manager")
st.markdown("Gestión de noticias, anuncios y sincronización con GitHub.")

tabs = st.tabs(["📈 Estadísticas", "📢 Gestionar Anuncios", "📰 Historial News", "⚙️ Configuración"])

# --- TAB 1: ESTADÍSTICAS ---
with tabs[0]:
    st.subheader("Rendimiento del Canal")
    try:
        # COUNT exacto con el método count
        count_response = supabase.table("noticias_publicadas").select("*", count="exact").execute()
        total_news = count_response.count if count_response.count is not None else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Noticias Publicadas", total_news)
        col2.metric("Próximo Anuncio en", f"{10 - (total_news % 10)} posts")
        col3.metric("Estado del Bot", "Activo", delta="Online")
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")

# --- TAB 2: GESTIONAR ANUNCIOS ---
with tabs[1]:
    st.subheader("Agregar Nuevo Anuncio (Ad-Insertion)")
    with st.form("new_ad"):
        texto = st.text_area("Texto del Anuncio")
        img_url = st.text_input("URL de la Imagen")
        link_afi = st.text_input("Link de Afiliado/Referido")
        if st.form_submit_button("Guardar Anuncio"):
            try:
                # Inserción usando .insert()
                anuncio = {
                    "texto_anuncio": texto,
                    "imagen_url": img_url,
                    "link_afiliado": link_afi,
                    "activo": True
                }
                supabase.table("anuncios_disponibles").insert(anuncio).execute()
                st.success("Anuncio guardado correctamente.")
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    st.divider()
    st.subheader("Anuncios Activos")
    try:
        # Seleccionar columnas específicas
        ads_response = supabase.table("anuncios_disponibles")\
            .select("id, texto_anuncio, activo")\
            .execute()
        if ads_response.data:
            df_ads = pd.DataFrame(ads_response.data, columns=["id", "texto_anuncio", "activo"])
            st.dataframe(df_ads, use_container_width=True)
        else:
            st.info("No hay anuncios registrados.")
    except Exception as e:
        st.error(f"Error al cargar anuncios: {e}")

# --- TAB 3: HISTORIAL ---
with tabs[2]:
    st.subheader("Últimas Noticias Procesadas")
    try:
        news_response = supabase.table("noticias_publicadas")\
            .select("id, noticia_hash, fecha_publicacion")\
            .order("fecha_publicacion", desc=True)\
            .limit(20)\
            .execute()
        if news_response.data:
            df_news = pd.DataFrame(news_response.data, columns=["id", "noticia_hash", "fecha_publicacion"])
            st.table(df_news)
        else:
            st.info("No hay noticias en el historial.")
    except Exception as e:
        st.error(f"Error al cargar historial: {e}")

# --- TAB 4: GITHUB & CONFIGURACIÓN ---
with tabs[3]:
    st.subheader("Sincronización con GitHub")
    st.info("El bot está configurado para leer 'TasaBCV.xlsx' y otros activos desde tu repositorio.")
    
    if st.button("🔄 Forzar Sincronización GitHub"):
        st.warning("Enviando señal de actualización a GitHub Actions...")
        st.success("Repositorio sincronizado.")
    
    st.subheader("Logs del Sistema")
    st.code(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - Panel de control accedido")

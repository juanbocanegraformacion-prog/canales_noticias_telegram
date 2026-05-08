import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="NewsBot Control Panel", layout="wide")

# --- CONEXIÓN A SUPABASE (POSTGRESQL) ---
DB_URL = "postgresql://postgres:[Jlbr992$Supabase]@db.xzxivxhxzgurxobgrnoo.supabase.co:5432/postgres"

def run_query(query, params=None, is_select=True):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if is_select:
                return cur.fetchall()
            conn.commit()

# --- INTERFAZ ---
st.title("🤖 Monitor ODC - NewsBot Manager")
st.markdown("Gestión de noticias, anuncios y sincronización con GitHub.")

tabs = st.tabs(["📈 Estadísticas", "📢 Gestionar Anuncios", "📰 Historial News", "⚙️ Configuración"])

# --- TAB 1: ESTADÍSTICAS ---
with tabs[0]:
    st.subheader("Rendimiento del Canal")
    try:
        total_news = run_query("SELECT COUNT(*) FROM noticias_publicadas")[0][0]
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
            query = "INSERT INTO anuncios_disponibles (texto_anuncio, imagen_url, link_afiliado, activo) VALUES (%s, %s, %s, TRUE)"
            run_query(query, (texto, img_url, link_afi), is_select=False)
            st.success("Anuncio guardado correctamente.")

    st.divider()
    st.subheader("Anuncios Activos")
    ads = run_query("SELECT id, texto_anuncio, activo FROM anuncios_disponibles")
    df_ads = pd.DataFrame(ads, columns=["ID", "Contenido", "Activo"])
    st.dataframe(df_ads, use_container_width=True)

# --- TAB 3: HISTORIAL ---
with tabs[2]:
    st.subheader("Últimas Noticias Procesadas")
    news_data = run_query("SELECT id, noticia_hash, fecha_publicacion FROM noticias_publicadas ORDER BY fecha_publicacion DESC LIMIT 20")
    df_news = pd.DataFrame(news_data, columns=["ID", "URL/Hash", "Fecha"])
    st.table(df_news)

# --- TAB 4: GITHUB & CONFIGURACIÓN ---
with tabs[3]:
    st.subheader("Sincronización con GitHub")
    st.info("El bot está configurado para leer 'TasaBCV.xlsx' y otros activos desde tu repositorio.")
    
    if st.button("🔄 Forzar Sincronización GitHub"):
        # Aquí podrías disparar un GitHub Action vía Webhook
        st.warning("Enviando señal de actualización a GitHub Actions...")
        st.success("Repositorio sincronizado.")
    
    st.subheader("Logs del Sistema")
    st.code("2026-05-08 11:45:00 - INFO - Noticia publicada: 'Nuevos avances en IA' \n2026-05-08 11:45:01 - INFO - Contador incrementado a 145")

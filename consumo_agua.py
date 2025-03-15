import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
from PIL import Image
import pytz

# Configuração da página
st.set_page_config(
    page_title="Pedrito, o Fiscal da Hidratação",
    page_icon="🚰",
    layout="wide"
)

# Exibir imagem do Pedrito
pedrito_img = Image.open("pedrito.jpg")
st.image(pedrito_img, width=150)
st.title("💧 Pedrito, o Fiscal da Hidratação")

# Configurações do Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_API_KEY = st.secrets["SUPABASE_API_KEY"]
SUPABASE_TABLE = "consumo_agua"
SUPABASE_USERS_TABLE = "usuarios"

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
}

# Fuso horário UTC-3 (Brasil)
UTC_MINUS_3 = pytz.timezone("America/Sao_Paulo")

# Obter IP do usuário
def get_user_ip():
    try:
        response = requests.get("https://api64.ipify.org?format=json")
        if response.status_code == 200:
            return response.json().get("ip", "desconhecido")
    except:
        return "desconhecido"

USER_IP = get_user_ip()

# Buscar usuario_id com base no IP
def get_usuario_id(user_ip):
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_USERS_TABLE}?user_ip=eq.{user_ip}&select=id", headers=HEADERS)
    if response.status_code == 200 and response.json():
        return response.json()[0]["id"]
    return None

USUARIO_ID = get_usuario_id(USER_IP)

# Conversão de medidas
MEDIDAS = {
    "Gole (30ml)": 30,
    "Copo pequeno (100ml)": 100,
    "Copo grande (200ml)": 200,
    "Garrafa pequena (500ml)": 500,
    "Garrafa grande (1L)": 1000,
    "Mililitros (digite abaixo)": None,
}

# Registrar consumo
def registrar_consumo(quantidade_ml, usuario_id):
    agora_utc = datetime.now(pytz.utc)
    agora_local = agora_utc.astimezone(UTC_MINUS_3)
    data = {
        "data_hora": agora_local.isoformat(),
        "quantidade_ml": quantidade_ml,
        "usuario_id": usuario_id
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}", json=data, headers=HEADERS)
    return response.status_code == 201

# Obter histórico
def obter_historico(usuario_id):
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?usuario_id=eq.{usuario_id}&select=*", headers=HEADERS)
    if response.status_code == 200:
        return pd.DataFrame(response.json())
    return pd.DataFrame()

# Entrada do usuário
quantidade = st.number_input("Quantas unidades você tomou?", min_value=1, step=1, value=1)
medida = st.selectbox("Selecione a medida:", list(MEDIDAS.keys()))

if MEDIDAS[medida] is None:
    quantidade_ml = st.number_input("Digite a quantidade em ml:", min_value=1, step=1)
else:
    quantidade_ml = quantidade * MEDIDAS[medida]

if st.button("Registrar"):
    if USUARIO_ID and registrar_consumo(quantidade_ml, USUARIO_ID):
        st.success(f"Registrado: {quantidade_ml}ml!")
    else:
        st.error("Erro ao registrar consumo. Confirme se seu IP está cadastrado.")

# Histórico de consumo
if USUARIO_ID:
    historico = obter_historico(USUARIO_ID)
else:
    historico = pd.DataFrame()

if not historico.empty:
    historico['data_hora'] = pd.to_datetime(historico['data_hora']).dt.tz_convert(UTC_MINUS_3)
    historico = historico.sort_values(by="data_hora", ascending=False)

    historico["data"] = historico["data_hora"].dt.date
    historico["hora"] = historico["data_hora"].dt.hour

    hoje = datetime.now(UTC_MINUS_3).date()
    ontem = hoje - timedelta(days=1)

    consumo_diario = historico.groupby("data")["quantidade_ml"].sum().reset_index()
    
    total_hoje = consumo_diario[consumo_diario["data"] == hoje]["quantidade_ml"].sum()
    total_ontem = consumo_diario[consumo_diario["data"] == ontem]["quantidade_ml"].sum()
    media_diaria = consumo_diario["quantidade_ml"].mean()

    # Alerta de hidratação
    meta_diaria = 3000
    if total_hoje < meta_diaria:
        st.warning(f"⚠️ Falta {meta_diaria - total_hoje}ml para bater a meta de 3L hoje!")

    # Ranking de gamificação
    def obter_ranking():
        response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=usuario_id,data_hora,quantidade_ml", headers=HEADERS)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df["data_hora"] = pd.to_datetime(df["data_hora"]).dt.date
            ranking = df.groupby("usuario_id")["quantidade_ml"].sum().reset_index()
            ranking["media_diaria"] = ranking["quantidade_ml"] / df["data_hora"].nunique()
            ranking = ranking.sort_values(by="media_diaria", ascending=False)
            return ranking
        return pd.DataFrame()

    ranking = obter_ranking()

    if not ranking.empty:
        st.subheader("🏆 Ranking de Hidratação")
        ranking["Posição"] = range(1, len(ranking) + 1)
        ranking_display = ranking[["Posição", "usuario_id", "media_diaria"]]

        # Destacar usuário atual
        ranking_display["Destaque"] = ranking_display["usuario_id"].apply(lambda x: "⭐" if x == USUARIO_ID else "")
        st.table(ranking_display)

    # Indicadores
    st.subheader("📊 Indicadores de Consumo")
    col1, col2, col3 = st.columns(3)
    col1.metric("💦 Total de hoje", f"{total_hoje:.0f} ml")
    col2.metric("📊 Média diária", f"{media_diaria:.0f} ml")
    
    # Gráficos
    consumo_hoje = historico[historico["data"] == hoje].groupby("hora")["quantidade_ml"].sum().reset_index()
    todas_horas = pd.DataFrame({"hora": list(range(24))})
    consumo_hoje = todas_horas.merge(consumo_hoje, on="hora", how="left").fillna(0)
    
    fig_hora = px.bar(consumo_hoje, x="hora", y="quantidade_ml", title="Total Consumido por Hora (Hoje)")
    st.plotly_chart(fig_hora)

    st.subheader("📋 Histórico Completo")
    st.dataframe(historico)

else:
    st.write("Nenhum registro encontrado.")

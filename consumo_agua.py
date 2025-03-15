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
USERS_TABLE = "usuarios"

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

# Obter usuario_id a partir do IP
def obter_usuario_id(user_ip):
    url = f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?select=id&user_ip=eq.{user_ip}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200 and response.json():
        return response.json()[0]["id"]
    return None

# Buscar usuario_id
usuario_id = obter_usuario_id(USER_IP)

# Exibir usuario_id no app
st.sidebar.subheader("📌 Seu usuário ID")
if usuario_id:
    st.sidebar.code(usuario_id)
else:
    st.sidebar.write("⚠️ Usuário não encontrado no banco.")

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

# Obter histórico filtrado pelo usuario_id
def obter_historico(usuario_id):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?usuario_id=eq.{usuario_id}&select=*"
    response = requests.get(url, headers=HEADERS)
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
    if usuario_id:
        if registrar_consumo(quantidade_ml, usuario_id):
            st.success(f"Registrado: {quantidade_ml}ml!")
        else:
            st.error("Erro ao registrar consumo.")
    else:
        st.error("Usuário não encontrado. Não foi possível registrar o consumo.")

# Histórico de consumo
historico = obter_historico(usuario_id)

if not historico.empty:
    historico['data_hora'] = pd.to_datetime(historico['data_hora']).dt.tz_convert(UTC_MINUS_3)
    historico = historico.sort_values(by="data_hora", ascending=False)

    # Criar colunas de data e hora
    historico["data"] = historico["data_hora"].dt.date
    historico["hora"] = historico["data_hora"].dt.hour

    # Data de hoje e ontem
    hoje = datetime.now(UTC_MINUS_3).date()
    ontem = hoje - timedelta(days=1)

    # Criar index de horas para garantir todas as horas no gráfico
    todas_horas = pd.DataFrame({"hora": list(range(24))})

    # Cálculos para indicadores
    consumo_diario = historico.groupby("data")["quantidade_ml"].sum().reset_index()
    
    total_hoje = consumo_diario[consumo_diario["data"] == hoje]["quantidade_ml"].sum()
    media_diaria = consumo_diario["quantidade_ml"].mean()

    # Alerta de hidratação
    meta_hidratacao = 3000
    falta_meta = max(0, meta_hidratacao - total_hoje)
    if falta_meta > 0:
        st.warning(f"🚰 Falta {falta_meta}ml para atingir a meta diária de 3L!")

    # Ranking de gamificação
    url_ranking = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=usuario_id,data,quantidade_ml"
    response_ranking = requests.get(url_ranking, headers=HEADERS)
    
    if response_ranking.status_code == 200:
        df_ranking = pd.DataFrame(response_ranking.json())
        if not df_ranking.empty:
            ranking = df_ranking.groupby("usuario_id")["quantidade_ml"].mean().reset_index()
            ranking = ranking.sort_values(by="quantidade_ml", ascending=False).reset_index(drop=True)
            ranking.index += 1  # Ajustar ranking para começar em 1
            
            # Destacar o usuário atual
            ranking["Destaque"] = ranking["usuario_id"].apply(lambda x: "👑" if x == usuario_id else "")
            
            st.subheader("🏆 Ranking de Consumo Médio Diário")
            st.dataframe(ranking, hide_index=True)

    # Exibir gráficos
    st.subheader("📊 Histórico de Consumo")

    consumo_hoje = historico[historico["data"] == hoje].groupby("hora")["quantidade_ml"].sum().reset_index()
    consumo_hoje = todas_horas.merge(consumo_hoje, on="hora", how="left").fillna(0)
    fig_hora = px.bar(consumo_hoje, x="hora", y="quantidade_ml", title="Total Consumido por Hora (Hoje)")
    st.plotly_chart(fig_hora)

    st.subheader("📋 Histórico Completo")
    st.dataframe(historico)

else:
    st.write("Nenhum registro encontrado.")

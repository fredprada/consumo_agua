import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
from PIL import Image
import pytz
from supabase import create_client

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

supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# Função para obter todos os usuários cadastrados
def obter_usuarios():
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_USERS_TABLE}?select=usuario_id,nome",
                            headers={"apikey": SUPABASE_API_KEY, "Authorization": f"Bearer {SUPABASE_API_KEY}"})
    if response.status_code == 200:
        return response.json()
    return []

usuarios = obter_usuarios()

# Interface para selecionar ou criar usuário
opcoes_usuarios = [user["nome"] for user in usuarios] if usuarios else []
nome_usuario = st.selectbox("Selecione seu nome:", opcoes_usuarios, index=None, placeholder="Escolha ou digite para criar")

if nome_usuario and nome_usuario not in opcoes_usuarios:
    if any(user["nome"] == nome_usuario for user in usuarios):
        st.error("Este nome já existe! Escolha um dos usuários cadastrados.")
        nome_usuario = None
    else:
        response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_USERS_TABLE}", json={"nome": nome_usuario},
                                 headers={"apikey": SUPABASE_API_KEY, "Authorization": f"Bearer {SUPABASE_API_KEY}",
                                          "Content-Type": "application/json"})
        if response.status_code == 201:
            st.success(f"Usuário {nome_usuario} criado com sucesso!")
            usuarios.append({"usuario_id": response.json()[0]["usuario_id"], "nome": nome_usuario})
        else:
            st.error("Erro ao criar usuário.")
            nome_usuario = None

# Obtém o usuário_id selecionado
usuario_id = next((user["usuario_id"] for user in usuarios if user["nome"] == nome_usuario), None)

if usuario_id:
    st.write(f"👤 **Usuário:** {nome_usuario}")

# Fuso horário UTC-3 (Brasil)
UTC_MINUS_3 = pytz.timezone("America/Sao_Paulo")

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
    if usuario_id is None:
        st.error("Você precisa selecionar um usuário para registrar o consumo.")
        return False

    agora_utc = datetime.now(pytz.utc)
    agora_local = agora_utc.astimezone(UTC_MINUS_3)
    data = {
        "data_hora": agora_local.isoformat(),
        "quantidade_ml": quantidade_ml,
        "usuario_id": usuario_id
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}", json=data, headers={
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json",
    })
    return response.status_code == 201

# Obter histórico
def obter_historico():
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=*", headers={
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
    })
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
    if registrar_consumo(quantidade_ml, usuario_id):
        st.success(f"Registrado: {quantidade_ml}ml!")
    else:
        st.error("Erro ao registrar consumo.")

# Histórico de consumo
historico = obter_historico()

if not historico.empty:
    historico['data_hora'] = pd.to_datetime(historico['data_hora']).dt.tz_convert(UTC_MINUS_3)
    historico = historico.sort_values(by="data_hora", ascending=False)

    # Criar colunas de data, hora e ID
    historico["data"] = historico["data_hora"].dt.date
    historico["hora"] = historico["data_hora"].dt.hour

    # Filtrar histórico do usuário
    historico_usuario = historico[historico["usuario_id"] == usuario_id] if usuario_id else pd.DataFrame()

    # Data de hoje e ontem
    hoje = datetime.now(UTC_MINUS_3).date()
    ontem = hoje - timedelta(days=1)

    # **Cálculos para indicadores**
    consumo_diario = historico.groupby("data")["quantidade_ml"].sum().reset_index()
    
    total_hoje = consumo_diario[consumo_diario["data"] == hoje]["quantidade_ml"].sum()
    total_ontem = consumo_diario[consumo_diario["data"] == ontem]["quantidade_ml"].sum()
    media_diaria = consumo_diario["quantidade_ml"].mean()

    # **Alerta de hidratação**
    meta = 3000  # Meta de 3 litros
    falta_para_meta = max(0, meta - total_hoje)
    if falta_para_meta > 0:
        st.warning(f"🚰 Faltam {falta_para_meta}ml para bater a meta de 3L hoje!")

    # **Ranking de gamificação**
    ranking = historico.groupby("usuario_id")["quantidade_ml"].mean().reset_index()
    ranking = ranking.sort_values(by="quantidade_ml", ascending=False)
    ranking["Posição"] = range(1, len(ranking) + 1)

    st.subheader("🏆 Ranking de Hidratação (Média Diária)")
    if usuario_id in ranking["usuario_id"].values:
        posicao_usuario = ranking[ranking["usuario_id"] == usuario_id]["Posição"].values[0]
        st.info(f"📢 Sua posição no ranking: **{posicao_usuario}º lugar!**")

    st.dataframe(ranking[["Posição", "usuario_id", "quantidade_ml"]].rename(columns={"quantidade_ml": "Média Diária (ml)"}))

    # **Exibir Indicadores**
    st.subheader("📊 Indicadores de Consumo")
    col1, col2, col3 = st.columns(3)
    col1.metric("💦 Total de hoje", f"{total_hoje:.0f} ml")
    col2.metric("📊 Média diária", f"{media_diaria:.0f} ml")
    col3.metric("📉 Falta para meta", f"{falta_para_meta} ml")

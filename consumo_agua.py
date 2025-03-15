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

# Obter informações do usuário autenticado
user = supabase.auth.get_user()
if user and user.user:
    usuario_id = user.user.id
    st.write(f"**Seu ID de usuário:** `{usuario_id}`")
else:
    usuario_id = None
    st.warning("Usuário não autenticado. Faça login para registrar seu consumo.")

# Verificar se o usuário já tem um nome cadastrado
def obter_nome_usuario(usuario_id):
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_USERS_TABLE}?usuario_id=eq.{usuario_id}&select=nome",
                            headers={"apikey": SUPABASE_API_KEY, "Authorization": f"Bearer {SUPABASE_API_KEY}"})
    if response.status_code == 200 and response.json():
        return response.json()[0]["nome"]
    return None

def registrar_nome_usuario(usuario_id, nome):
    data = {"usuario_id": usuario_id, "nome": nome}
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_USERS_TABLE}", json=data,
                             headers={"apikey": SUPABASE_API_KEY, "Authorization": f"Bearer {SUPABASE_API_KEY}",
                                      "Content-Type": "application/json"})
    return response.status_code == 201

nome_usuario = obter_nome_usuario(usuario_id) if usuario_id else None

if usuario_id:
    if nome_usuario:
        st.write(f"👤 **Usuário:** {nome_usuario}")
    else:
        nome_input = st.text_input("Parece que você ainda não tem um nome cadastrado. Digite seu nome:")
        if st.button("Salvar Nome"):
            if nome_input:
                if registrar_nome_usuario(usuario_id, nome_input):
                    st.success(f"Nome {nome_input} registrado com sucesso!")
                    nome_usuario = nome_input
                else:
                    st.error("Erro ao registrar nome.")

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
        st.error("Você precisa estar autenticado para registrar o consumo.")
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

    # **Gráficos**
    consumo_hoje = historico[historico["data"] == hoje].groupby("hora")["quantidade_ml"].sum().reset_index()
    fig_hora = px.bar(consumo_hoje, x="hora", y="quantidade_ml", title="Total Consumido por Hora (Hoje)")
    st.plotly_chart(fig_hora)

else:
    st.write("Nenhum registro encontrado.")

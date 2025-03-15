import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
import pytz
from PIL import Image

# Configuração da página
st.set_page_config(page_title="Pedrito, o Fiscal da Hidratação", page_icon="🚰", layout="wide")

# Carregar e exibir a imagem do Pedrito
pedrito_img = Image.open("pedrito.jpg")
st.image(pedrito_img, width=150)
st.title("💧 Pedrito, o Fiscal da Hidratação")

# Configurações do Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_API_KEY = st.secrets["SUPABASE_API_KEY"]
SUPABASE_TABLE = "consumo_agua"

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
}

# Fuso horário UTC-3 (Brasil)
UTC_MINUS_3 = pytz.timezone("America/Sao_Paulo")

# Função para buscar todos os usuários cadastrados
def obter_usuarios():
    query = "?select=usuario_id"
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}{query}", headers=HEADERS)
    if response.status_code == 200:
        df = pd.DataFrame(response.json())
        return sorted(df["usuario_id"].unique()) if not df.empty else []
    return []

# 1️⃣ Seleção de usuário
usuarios = obter_usuarios()
usuario_selecionado = st.selectbox("Selecione um usuário:", usuarios) if usuarios else ""
filtrar = st.button("🔍 Filtrar")

# 2️⃣ Input de consumo
st.subheader("➕ Registrar Consumo")
usuario_manual = st.text_input("Usuário: (preencha caso seu usuario nao exista, senao deixe vazio)", "")

medidas = {
    "Gole (30ml)": 30, "Copo pequeno (100ml)": 100, "Copo grande (200ml)": 200,
    "Garrafa pequena (500ml)": 500, "Garrafa grande (1L)": 1000, "Mililitros (digite abaixo)": None,
}

qtd_medida = st.number_input("Quantidade:", min_value=1, step=1, value=1)
medida = st.selectbox("Selecione a medida:", list(medidas.keys()))
quantidade_ml = (medidas[medida] if medidas[medida] else st.number_input("Digite a quantidade em ml:", min_value=1, step=1)) * qtd_medida

usuario_id = usuario_manual if usuario_manual else usuario_selecionado

if usuario_id and st.button("Registrar"):
    agora_local = datetime.now(UTC_MINUS_3).isoformat()
    data = {"usuario_id": usuario_id, "data_hora": agora_local, "quantidade_ml": quantidade_ml}
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}", json=data, headers=HEADERS)

    if response.status_code == 201:
        st.success(f"Registrado: {quantidade_ml}ml!")
    else:
        st.error("Erro ao registrar consumo.")

# 3️⃣ Função para obter histórico de consumo
def obter_historico():
    query = "?select=*"
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}{query}", headers=HEADERS)
    if response.status_code == 200:
        return pd.DataFrame(response.json())
    return pd.DataFrame()

# 4️⃣ Indicadores de consumo do usuário
META_DIARIA = 3000  # Meta de consumo em ml

if usuario_id and filtrar:
    st.subheader("📊 Indicadores de Consumo")
    historico = obter_historico()

    if not historico.empty:
        historico["data_hora"] = pd.to_datetime(historico["data_hora"]).dt.tz_convert(UTC_MINUS_3)
        historico["data"] = historico["data_hora"].dt.date

        hoje = datetime.now(UTC_MINUS_3).date()
        agora = datetime.now(UTC_MINUS_3)

        consumo_hoje = historico[(historico["data"] == hoje) & (historico["usuario_id"] == usuario_id)]["quantidade_ml"].sum()
        consumo_diario = historico.groupby("data")["quantidade_ml"].sum()
        media_outros_dias = consumo_diario[consumo_diario.index != hoje].mean()

        if pd.notna(media_outros_dias) and media_outros_dias > 0:
            variacao = ((consumo_hoje - media_outros_dias) / media_outros_dias) * 100
            emoji = "😃" if consumo_hoje >= media_outros_dias else "😢"
        else:
            variacao = 0
            emoji = ""

        percentual_meta = (consumo_hoje / META_DIARIA) * 100
        restante_meta = max(META_DIARIA - consumo_hoje, 0)

        horas_restantes = max(1, 24 - agora.hour)
        consumo_por_hora = restante_meta / horas_restantes

        col1, col2, col3 = st.columns(3)
        col1.metric(label="Consumo de Hoje", value=f"{consumo_hoje}ml", delta=f"{variacao:.1f}% {emoji}")
        col2.metric(label="Meta Diária (3L)", value=f"{percentual_meta:.1f}%")
        col3.metric(label="Necessário por Hora", value=f"{consumo_por_hora:.0f}ml/h |  {restante_meta}ml")
    else:
        st.write("Nenhum registro encontrado.")

# 5️⃣ Ranking de Consumo Médio Diário (sem filtro)
st.subheader("🏆 Ranking de Consumo Médio Diário")
historico = obter_historico()

if not historico.empty:
    historico["data_hora"] = pd.to_datetime(historico["data_hora"]).dt.tz_convert(UTC_MINUS_3)
    historico["data"] = historico["data_hora"].dt.date

    consumo_por_dia = historico.groupby(["usuario_id", "data"])["quantidade_ml"].sum().reset_index()
    ranking = consumo_por_dia.groupby("usuario_id")["quantidade_ml"].mean().reset_index()
    ranking = ranking.sort_values(by="quantidade_ml", ascending=False).reset_index(drop=True)
    ranking.index += 1
    ranking.columns = ["Usuário", "Média Diário (ml)"]

    st.dataframe(ranking)
else:
    st.write("Nenhum registro disponível para o ranking.")

# 6️⃣ Histórico de Consumo
if usuario_id and filtrar:
    st.subheader("📊 Histórico de Consumo")
    historico_usuario = historico[historico["usuario_id"] == usuario_id]

    if not historico_usuario.empty:
        consumo_dia = historico_usuario.groupby("data")["quantidade_ml"].sum().reset_index()
        fig_dia = px.bar(consumo_dia, x="data", y="quantidade_ml", title="Consumo Total por Dia")
        fig_dia.update_traces(texttemplate='%{y}', textposition='outside')  
        st.plotly_chart(fig_dia)

        historico_usuario["hora"] = historico_usuario["data_hora"].dt.hour
        todas_horas = pd.DataFrame({"hora": list(range(24))})
        media_hora = historico_usuario.groupby("hora")["quantidade_ml"].mean().reset_index()
        media_hora = todas_horas.merge(media_hora, on="hora", how="left").fillna(0)

        fig_media_hora = px.bar(media_hora, x="hora", y="quantidade_ml", title="Média de Consumo por Hora")
        fig_media_hora.update_traces(texttemplate='%{y}', textposition='outside')  
        st.plotly_chart(fig_media_hora)

        # st.dataframe(historico_usuario)
    else:
        st.write("Nenhum registro encontrado para este usuário.")

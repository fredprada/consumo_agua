import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
import pytz
from PIL import Image

# Configuração da página
st.set_page_config(
    page_title="Pedrito, o Fiscal da Hidratação",
    page_icon="🚰",
    layout="wide"
)

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

# Medidas disponíveis
MEDIDAS = {
    "Gole (30ml)": 30,
    "Copo pequeno (100ml)": 100,
    "Copo grande (200ml)": 200,
    "Garrafa pequena (500ml)": 500,
    "Garrafa grande (1L)": 1000,
    "Mililitros (digite abaixo)": None,
}

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
usuario_selecionado = st.selectbox("Selecione seu ID:", usuarios) if usuarios else ""
usuario_manual = st.text_input("Ou digite seu ID:", "")

# Definir o usuário final
usuario_id = usuario_manual if usuario_manual else usuario_selecionado

# Botão para filtrar os dados
filtrar = st.button("🔍 Filtrar")

# 2️⃣ Criar novo usuário (placeholder para lógica futura)
if st.button("Criar Novo Usuário"):
    st.success("Usuário criado! (Funcionalidade futura)")

# 3️⃣ Input de consumo
if usuario_id:
    st.subheader("➕ Registrar Consumo")

    medida = st.selectbox("Selecione a medida:", list(MEDIDAS.keys()))
    qtd_medida = st.number_input("Quantidade:", min_value=1, step=1, value=1)
    quantidade_ml = (MEDIDAS[medida] if MEDIDAS[medida] else st.number_input("Digite a quantidade em ml:", min_value=1, step=1)) * qtd_medida

    if st.button("Registrar"):
        agora_local = datetime.now(UTC_MINUS_3).isoformat()
        data = {"usuario_id": usuario_id, "data_hora": agora_local, "quantidade_ml": quantidade_ml}
        response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}", json=data, headers=HEADERS)

        if response.status_code == 201:
            st.success(f"Registrado: {quantidade_ml}ml!")
        else:
            st.error("Erro ao registrar consumo.")

# 4️⃣ Função para obter histórico de consumo
def obter_historico():
    query = "?select=*"
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}{query}", headers=HEADERS)
    if response.status_code == 200:
        return pd.DataFrame(response.json())
    return pd.DataFrame()

# 5️⃣ Indicadores de consumo do usuário
if usuario_id and filtrar:
    st.subheader("📊 Indicadores de Consumo")
    historico = obter_historico()

    if not historico.empty:
        historico["data_hora"] = pd.to_datetime(historico["data_hora"]).dt.tz_convert(UTC_MINUS_3)
        historico["data"] = historico["data_hora"].dt.date

        hoje = datetime.now(UTC_MINUS_3).date()
        consumo_hoje = historico[(historico["usuario_id"] == usuario_id) & (historico["data"] == hoje)]["quantidade_ml"].sum()
        consumo_diario = historico[historico["usuario_id"] == usuario_id].groupby("data")["quantidade_ml"].sum()
        media_outros_dias = consumo_diario[consumo_diario.index != hoje].mean()

        if pd.notna(media_outros_dias) and media_outros_dias > 0:
            variacao = ((consumo_hoje - media_outros_dias) / media_outros_dias) * 100
            emoji = "😃" if consumo_hoje >= media_outros_dias else "😢"
        else:
            variacao = 0
            emoji = ""

        st.metric(label="Consumo de Hoje", value=f"{consumo_hoje}ml", delta=f"{variacao:.1f}% {emoji}")

    else:
        st.write("Nenhum registro encontrado.")

# 6️⃣ Ranking dos Usuários - Consumo Médio Diário
if filtrar:
    st.subheader("🏆 Ranking de Consumo Médio Diário")

    if not historico.empty:
        consumo_por_dia = historico.groupby(["usuario_id", "data"])["quantidade_ml"].sum().reset_index()
        ranking = consumo_por_dia.groupby("usuario_id")["quantidade_ml"].mean().reset_index()
        ranking = ranking.sort_values(by="quantidade_ml", ascending=False).reset_index(drop=True)
        ranking.index += 1  # Para começar do 1 ao invés de 0
        ranking.columns = ["Usuário", "Média Diário (ml)"]

        st.dataframe(ranking)

    else:
        st.write("Nenhum registro disponível para o ranking.")

# 7️⃣ Histórico de Consumo (AGORA FILTRADO PARA O USUÁRIO SELECIONADO)
if usuario_id and filtrar:
    st.subheader("📊 Histórico de Consumo")

    # Filtrar histórico apenas do usuário
    historico_usuario = historico[historico["usuario_id"] == usuario_id]

    if not historico_usuario.empty:
        # Consumo total por dia
        consumo_dia = historico_usuario.groupby("data")["quantidade_ml"].sum().reset_index()
        fig_dia = px.bar(consumo_dia, x="data", y="quantidade_ml", title="Consumo Total por Dia")
        st.plotly_chart(fig_dia)

        # Média de consumo por hora
        historico_usuario["hora"] = historico_usuario["data_hora"].dt.hour
        media_hora = historico_usuario.groupby("hora")["quantidade_ml"].mean().reindex(range(24), fill_value=0).reset_index()
        media_hora.columns = ["hora", "quantidade_ml"]

        fig_media_hora = px.bar(media_hora, x="hora", y="quantidade_ml", title="Média de Consumo por Hora")
        st.plotly_chart(fig_media_hora)

        # Total por hora do dia de hoje
        consumo_hoje_hora = historico_usuario[historico_usuario["data"] == hoje].groupby("hora")["quantidade_ml"].sum().reindex(range(24), fill_value=0).reset_index()
        consumo_hoje_hora.columns = ["hora", "quantidade_ml"]

        fig_hoje_hora = px.bar(consumo_hoje_hora, x="hora", y="quantidade_ml", title="Consumo por Hora Hoje")
        st.plotly_chart(fig_hoje_hora)

        # Exibir histórico completo
        st.dataframe(historico_usuario)

    else:
        st.write("Nenhum registro encontrado para este usuário.")

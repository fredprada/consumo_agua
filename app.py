import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
from PIL import Image

# 🔧 Configuração da página
st.set_page_config(page_title="Pedrito, o Fiscal da Hidratação", page_icon="🚰", layout="wide")

# 📷 Imagem do Pedrito
pedrito_img = Image.open("assets/pedrito.jpg")
st.image(pedrito_img, width=150)
st.title("💧 Pedrito, o Fiscal da Hidratação")

# 🔑 Configurações do Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_API_KEY = st.secrets["SUPABASE_API_KEY"]
SUPABASE_TABLE = "consumo_agua"

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
}

# 🕒 Fuso horário UTC-3 (Brasil)
UTC_MINUS_3 = pytz.timezone("America/Sao_Paulo")

# 📌 Função para buscar usuários cadastrados
def obter_usuarios():
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=usuario_id", headers=HEADERS)
    if response.status_code == 200:
        df = pd.DataFrame(response.json())
        return sorted(df["usuario_id"].unique()) if not df.empty else []
    return []

# 📌 Função para obter histórico de consumo
def obter_historico():
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=*", headers=HEADERS)
    if response.status_code == 200:
        df = pd.DataFrame(response.json())
        if not df.empty:
            df["data_hora"] = pd.to_datetime(df["data_hora"]).dt.tz_convert(UTC_MINUS_3)
            df["data"] = df["data_hora"].dt.date
            df["hora"] = df["data_hora"].dt.hour  # Adicionando a coluna de hora para o gráfico de consumo por hora
        return df
    return pd.DataFrame()

# 1️⃣ Seleção de Usuário
usuarios = obter_usuarios()
usuario_selecionado = st.selectbox("Selecione um usuário:", usuarios) if usuarios else ""
filtrar = st.button("🔍 Filtrar")

# 2️⃣ Registro de Consumo
st.subheader("➕ Registrar Consumo")
usuario_manual = st.text_input("Usuário (se não existir, digite aqui)", "")

medidas = {
    "Gole (30ml)": 30,
    "Copo pequeno (100ml)": 100,
    "Copo grande (200ml)": 200,
    "Garrafa pequena (500ml)": 500,
    "Garrafa grande (1L)": 1000,
    "Mililitros (digite abaixo)": None,
}

qtd_medida = st.number_input("Quantidade:", min_value=1, step=1, value=1)
medida = st.selectbox("Selecione a medida:", list(medidas.keys()))
quantidade_ml = (medidas[medida] if medidas[medida] else st.number_input("Digite a quantidade em ml:", min_value=1, step=1)) * qtd_medida

usuario_id = usuario_manual if usuario_manual else usuario_selecionado

if usuario_id and st.button("Registrar"):
    data = {
        "usuario_id": usuario_id,
        "data_hora": datetime.now(UTC_MINUS_3).isoformat(),
        "quantidade_ml": quantidade_ml
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}", json=data, headers=HEADERS)

    if response.status_code == 201:
        st.success(f"Registrado: {quantidade_ml}ml!")
    else:
        st.error("Erro ao registrar consumo.")

# 3️⃣ Indicadores de Consumo
META_DIARIA = 3000  # Meta de consumo (ml)
historico = obter_historico()  # Carregar histórico globalmente

if usuario_id and filtrar:
    st.subheader("📊 Indicadores de Consumo")

    if not historico.empty:
        hoje = datetime.now(UTC_MINUS_3).date()
        consumo_hoje = historico[(historico["data"] == hoje) & (historico["usuario_id"] == usuario_id)]["quantidade_ml"].sum()

        # 🔥 Dias de Ofensiva
        historico_usuario = historico[historico["usuario_id"] == usuario_id].groupby("data")["quantidade_ml"].sum().reset_index()
        historico_usuario = historico_usuario.tail(14)  # Mostrar apenas os últimos 14 dias
        historico_usuario["atingiu_meta"] = historico_usuario["quantidade_ml"] >= META_DIARIA

        dias_ofensiva = 0
        for _, row in historico_usuario.iloc[:-1][::-1].iterrows():
            if row["atingiu_meta"]:
                dias_ofensiva += 1
            else:
                break
        st.metric("Dias de Ofensiva", dias_ofensiva)

        # 📊 Gráfico: Consumo Acumulado ao Longo do Dia
        st.subheader("📈 Consumo Acumulado ao Longo do Dia")

        historico_hoje = historico[(historico["data"] == hoje) & (historico["usuario_id"] == usuario_id)]
        consumo_acumulado = historico_hoje.groupby("hora")["quantidade_ml"].sum().cumsum().reset_index()

        # Média histórica do consumo acumulado por hora
        media_historica = historico[historico["usuario_id"] == usuario_id].groupby(["data", "hora"])["quantidade_ml"].sum().groupby("hora").mean().cumsum().reset_index()

        fig_acumulado = go.Figure()

        # Linha de consumo acumulado do dia
        fig_acumulado.add_trace(go.Scatter(
            x=consumo_acumulado["hora"],
            y=consumo_acumulado["quantidade_ml"],
            mode="lines+markers",
            name="Consumo Acumulado Hoje",
            line=dict(color="blue", width=2),
            marker=dict(size=6)
        ))

        # Linha tracejada da média histórica
        fig_acumulado.add_trace(go.Scatter(
            x=media_historica["hora"],
            y=media_historica["quantidade_ml"],
            mode="lines",
            name="Média Acumulada",
            line=dict(color="gray", width=1.5, dash="dash")
        ))

        fig_acumulado.update_layout(
            title="Consumo Acumulado ao Longo do Dia",
            xaxis_title="Hora do Dia",
            yaxis_title="Consumo Acumulado (ml)",
            xaxis=dict(tickmode="linear", dtick=1),
            yaxis=dict(range=[0, META_DIARIA]),
            template="plotly_white"
        )

        st.plotly_chart(fig_acumulado)

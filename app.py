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
    try:
        response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=usuario_id", headers=HEADERS)
        response.raise_for_status()
        df = pd.DataFrame(response.json())
        return sorted(df["usuario_id"].unique()) if not df.empty else []
    except requests.RequestException as e:
        st.error(f"Erro ao buscar usuários: {e}")
        return []

# 📌 Função para obter histórico de consumo
def obter_historico():
    try:
        response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=*", headers=HEADERS)
        response.raise_for_status()
        df = pd.DataFrame(response.json())

        if not df.empty:
            df["data_hora"] = pd.to_datetime(df["data_hora"], utc=True).dt.tz_convert(UTC_MINUS_3)
            df["data"] = df["data_hora"].dt.date
        return df
    except requests.RequestException as e:
        st.error(f"Erro ao buscar histórico: {e}")
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
    try:
        response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}", json=data, headers=HEADERS)
        response.raise_for_status()
        st.success(f"Registrado: {quantidade_ml}ml!")
    except requests.RequestException as e:
        st.error(f"Erro ao registrar consumo: {e}")

# 3️⃣ Indicadores de Consumo
META_DIARIA = 3000  # Meta de consumo (ml)

if usuario_id and filtrar:
    st.subheader("📊 Indicadores de Consumo")
    historico = obter_historico()

    if not historico.empty:
        hoje = datetime.now(UTC_MINUS_3).date()
        consumo_hoje = historico[(historico["data"] == hoje) & (historico["usuario_id"] == usuario_id)]["quantidade_ml"].sum()
        
        # 🔥 Dias de Ofensiva (sem contar o dia atual)
        historico_usuario = historico[historico["usuario_id"] == usuario_id].groupby("data")["quantidade_ml"].sum().reset_index()
        historico_usuario["atingiu_meta"] = historico_usuario["quantidade_ml"] >= META_DIARIA

        dias_ofensiva = 0
        for _, row in historico_usuario.iloc[:-1][::-1].iterrows():  # Exclui o dia atual
            if row["atingiu_meta"]:
                dias_ofensiva += 1
            else:
                break
        st.metric("Dias de Ofensiva", dias_ofensiva)

        # 📊 Gráfico: Consumo por Dia (barra do dia atual em cinza, outras em azul)
        consumo_usuario = historico_usuario.copy()
        consumo_usuario["cor"] = consumo_usuario["data"].apply(lambda x: "gray" if x == hoje else "#1f77b4")  # Azul fixo

        fig_dia = px.bar(consumo_usuario, x="data", y="quantidade_ml", title="Consumo Total por Dia", text_auto=True)
        fig_dia.update_traces(marker=dict(color=consumo_usuario["cor"]))

        st.plotly_chart(fig_dia)

        # 📊 Gráfico: Evolução do Consumo Diário (%) da Meta
        consumo_usuario["percentual_meta"] = (consumo_usuario["quantidade_ml"] / META_DIARIA) * 100
        fig_meta = px.line(
            consumo_usuario,
            x="data",
            y="percentual_meta",
            markers=True,
            title="Evolução do Consumo Diário (%) da Meta",
            text=consumo_usuario["percentual_meta"].round(1).astype(str) + "%"
        )

        # Linha da meta
        fig_meta.add_trace(go.Scatter(
            x=consumo_usuario["data"],
            y=[100] * len(consumo_usuario),
            mode="lines",
            line=dict(dash="dash", color="red"),
            name="Meta 100%"
        ))

        st.plotly_chart(fig_meta)

    # 🏆 Ranking Semanal
    st.subheader("🏆 Ranking Semanal de Consumo")
    inicio_semana = hoje - timedelta(days=hoje.weekday())  # Segunda-feira correta

    consumo_semana = historico[historico["data"] >= inicio_semana].groupby("usuario_id")["quantidade_ml"].sum().reset_index()
    consumo_semana["quantidade_litros"] = (consumo_semana["quantidade_ml"] / 1000).apply(lambda x: f"{x:.1f}")
    consumo_semana = consumo_semana.sort_values("quantidade_ml", ascending=False).reset_index(drop=True)
    consumo_semana.index += 1  # Ajusta ranking para começar em 1

    st.table(consumo_semana.rename(columns={"usuario_id": "Usuário", "quantidade_litros": "Litros Consumidos"}))

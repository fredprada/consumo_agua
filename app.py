import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
from PIL import Image

# Configuração da página
st.set_page_config(page_title="Pedrito, o Fiscal da Hidratação", page_icon="🚰", layout="wide")

# Imagem do Pedrito
pedrito_img = Image.open("assets/pedrito.jpg")
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

# Função para buscar usuários cadastrados
def obter_usuarios():
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=usuario_id", headers=HEADERS)
    if response.status_code == 200:
        df = pd.DataFrame(response.json())
        return sorted(df["usuario_id"].unique()) if not df.empty else []
    return []

# Função para obter histórico de consumo
def obter_historico():
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=*", headers=HEADERS)
    if response.status_code == 200:
        df = pd.DataFrame(response.json())
        if not df.empty:
            df["data_hora"] = pd.to_datetime(df["data_hora"]).dt.tz_convert(UTC_MINUS_3)
            df["data"] = df["data_hora"].dt.date
            df["hora"] = df["data_hora"].dt.hour
        return df
    return pd.DataFrame()

# Seleção de Usuário
usuarios = obter_usuarios()
usuario_selecionado = st.selectbox("Selecione um usuário:", usuarios) if usuarios else ""
filtrar = st.button("🔍 Filtrar")

# Registro de Consumo
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

# Indicadores de Consumo
META_DIARIA = 3000
historico = obter_historico()

if usuario_id and filtrar:
    st.subheader("📊 Indicadores de Consumo")

    if not historico.empty:
        hoje = datetime.now(UTC_MINUS_3).date()
        consumo_hoje = historico[(historico["data"] == hoje) & (historico["usuario_id"] == usuario_id)]["quantidade_ml"].sum()

        # Dias de Ofensiva
        historico_usuario = historico[historico["usuario_id"] == usuario_id].groupby("data")["quantidade_ml"].sum().reset_index()
        historico_usuario = historico_usuario.tail(14)
        historico_usuario["atingiu_meta"] = historico_usuario["quantidade_ml"] >= META_DIARIA

        dias_ofensiva = 0
        for _, row in historico_usuario.iloc[:-1][::-1].iterrows():
            if row["atingiu_meta"]:
                dias_ofensiva += 1
            else:
                break
        st.metric("Dias de Ofensiva", dias_ofensiva)

        # Gráfico: Consumo por Dia
        fig_dia = px.bar(historico_usuario, x="data", y="quantidade_ml", title="Consumo Total por Dia", text_auto=True)
        st.plotly_chart(fig_dia)

        # Gráfico: Evolução do Consumo Diário (%) da Meta
        historico_usuario["percentual_meta"] = (historico_usuario["quantidade_ml"] / META_DIARIA) * 100
        fig_meta = px.line(
            historico_usuario,
            x="data",
            y="percentual_meta",
            markers=True,
            title="Evolução do Consumo Diário (%) da Meta"
        )
        fig_meta.update_yaxes(range=[0, max(120, historico_usuario["percentual_meta"].max() + 0.1)])
        st.plotly_chart(fig_meta)

        # Gráfico: Consumo Médio por Hora
        st.subheader("⏳ Consumo Médio por Hora")
        consumo_por_hora = historico[historico["usuario_id"] == usuario_id].groupby("hora")["quantidade_ml"].mean().reset_index()
        fig_hora = px.bar(consumo_por_hora, x="hora", y="quantidade_ml", title="Consumo Médio por Hora", text_auto=True)
        st.plotly_chart(fig_hora)

# Ranking Semanal
st.subheader("🏆 Ranking Semanal de Consumo")
hoje = datetime.now(UTC_MINUS_3).date()
inicio_semana = hoje - timedelta(days=hoje.weekday())

consumo_semana = historico[historico["data"] >= inicio_semana].groupby("usuario_id")["quantidade_ml"].sum().reset_index()
consumo_semana["quantidade_litros"] = (consumo_semana["quantidade_ml"] / 1000).apply(lambda x: f"{x:.1f}")
consumo_semana = consumo_semana.sort_values("quantidade_ml", ascending=False).reset_index(drop=True)
consumo_semana.index += 1

st.table(consumo_semana.rename(columns={"usuario_id": "Usuário", "quantidade_litros": "Litros Consumidos"}))

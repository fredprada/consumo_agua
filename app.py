import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import pytz
from PIL import Image
from datetime import timedelta

# 🔧 Configuração da página
st.set_page_config(page_title="Pedrito, o Fiscal da Hidratação", page_icon="🚰", layout="wide")

# 📷 Carregar e exibir a imagem do Pedrito
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

# 📌 Função para buscar todos os usuários cadastrados
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
            df["hora"] = df["data_hora"].dt.hour
        return df
    return pd.DataFrame()

# 1️⃣ Seleção de Usuário
usuarios = obter_usuarios()
usuario_selecionado = st.selectbox("Selecione um usuário:", usuarios) if usuarios else ""
filtrar = st.button("🔍 Filtrar")

# 2️⃣ Registro de Consumo
st.subheader("➕ Registrar Consumo")
usuario_manual = st.text_input("Usuário: (caso seu usuário não exista, preencha aqui)", "")

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

# 📅 Dias de Ofensiva
st.subheader("🔥 Dias de Ofensiva")
historico_usuario = historico[historico["usuario_id"] == usuario_id].groupby("data")["quantidade_ml"].sum().reset_index()
historico_usuario["atingiu_meta"] = historico_usuario["quantidade_ml"] >= META_DIARIA

dias_ofensiva = 0
for _, row in historico_usuario[::-1].iterrows():  # Inverter para contar do presente para o passado
    if row["atingiu_meta"]:
        dias_ofensiva += 1
    else:
        break

st.metric("Dias de Ofensiva", dias_ofensiva)

# 3️⃣ Indicadores de Consumo
META_DIARIA = 3000  # Meta de consumo (ml)

if usuario_id and filtrar:
    st.subheader("📊 Indicadores de Consumo")
    historico = obter_historico()

    if not historico.empty:
        hoje = datetime.now(UTC_MINUS_3).date()
        consumo_hoje = historico[(historico["data"] == hoje) & (historico["usuario_id"] == usuario_id)]["quantidade_ml"].sum()
        consumo_diario = historico.groupby("data")["quantidade_ml"].sum()
        media_outros_dias = consumo_diario[consumo_diario.index != hoje].mean()

        variacao = ((consumo_hoje - media_outros_dias) / media_outros_dias) * 100 if pd.notna(media_outros_dias) and media_outros_dias > 0 else 0
        emoji = "😃" if consumo_hoje >= media_outros_dias else "😢"

        percentual_meta = (consumo_hoje / META_DIARIA) * 100
        restante_meta = max(META_DIARIA - consumo_hoje, 0)
        horas_restantes = max(1, 24 - datetime.now(UTC_MINUS_3).hour)
        consumo_por_hora = restante_meta / horas_restantes

        col1, col2, col3 = st.columns(3)
        col1.metric("Consumo de Hoje", f"{consumo_hoje}ml", f"{variacao:.1f}% {emoji}")
        col2.metric("Meta Diária (3L)", f"{percentual_meta:.1f}%")
        col3.metric("Necessário por Hora", f"{consumo_por_hora:.0f}ml/h | {restante_meta}ml")

    # 📊 Gráfico: Evolução do Consumo Diário (%) da Meta
    st.subheader("📈 Evolução do Consumo Diário (%) da Meta")
    historico_usuario = historico[historico["usuario_id"] == usuario_id]
    
    if not historico_usuario.empty:
        consumo_por_dia = historico_usuario.groupby("data")["quantidade_ml"].sum().reset_index()
        consumo_por_dia["percentual_meta"] = (consumo_por_dia["quantidade_ml"] / META_DIARIA) * 100

        fig_meta = px.line(
            consumo_por_dia,
            x="data",
            y="percentual_meta",
            markers=True,
            title="Evolução do Consumo Diário (%) da Meta",
            text=consumo_por_dia["percentual_meta"].round(1).astype(str) + "%"
        )

        fig_meta.update_traces(textposition="top center")
        fig_meta.update_layout(yaxis=dict(range=[0, max(120, consumo_por_dia["percentual_meta"].max() + 10)], title="Percentual da Meta (%)"))

        fig_meta.add_trace(go.Scatter(
            x=consumo_por_dia["data"],
            y=[100] * len(consumo_por_dia),
            mode="lines",
            line=dict(dash="dash", color="red"),
            name="Meta 100%"
        ))

        st.plotly_chart(fig_meta)

    # 📊 Histórico de Consumo
    st.subheader("📊 Histórico de Consumo")
    fig_dia = px.bar(historico_usuario.groupby("data")["quantidade_ml"].sum().reset_index(), x="data", y="quantidade_ml", title="Consumo Total por Dia", text_auto=True)
    st.plotly_chart(fig_dia)

    # 📊 Gráfico: Consumo Médio por Hora (último gráfico)
    st.subheader("⏳ Consumo Médio por Hora")
    if not historico_usuario.empty:
        consumo_por_hora = historico_usuario.groupby("hora")["quantidade_ml"].mean().reset_index()

        fig_hora = px.bar(
            consumo_por_hora,
            x="hora",
            y="quantidade_ml",
            title="Consumo Médio por Hora",
            text_auto=True
        )

        st.plotly_chart(fig_hora)
    else:
        st.write("Nenhum registro encontrado para este usuário.")

    # 📊 Ranking Semanal
    st.subheader("🏆 Ranking Semanal de Consumo")
    inicio_semana = hoje - timedelta(days=hoje.weekday())  # Segunda-feira da semana atual
    consumo_semana = historico[historico["data"] >= inicio_semana].groupby("usuario_id")["quantidade_ml"].sum().reset_index()
    consumo_semana["quantidade_litros"] = consumo_semana["quantidade_ml"] / 1000
    consumo_semana["quantidade_litros"] = consumo_semana["quantidade_litros"].apply(lambda x: f"{x:.1f}")
    consumo_semana = consumo_semana.sort_values("quantidade_litros", ascending=False).reset_index(drop=True)
    consumo_semana.index += 1  # Ajustar para ranking começar em 1

    st.table(consumo_semana[["usuario_id", "quantidade_litros"]].rename(columns={"usuario_id": "Usuário", "quantidade_litros": "Litros Consumidos"}))



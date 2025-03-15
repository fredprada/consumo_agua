import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
from PIL import Image
import pytz

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

# Função para buscar todos os usuários cadastrados
def obter_usuarios():
    query = "?select=usuario_id"
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}{query}", headers=HEADERS)
    if response.status_code == 200:
        df = pd.DataFrame(response.json())
        return sorted(df["usuario_id"].unique()) if not df.empty else []
    return []

# Buscar usuários e exibir dropdown + input manual
usuarios = obter_usuarios()
usuario_selecionado = st.selectbox("Selecione seu ID:", usuarios) if usuarios else ""
usuario_manual = st.text_input("Ou digite seu ID:", "")

# Definir o usuário final
usuario_id = usuario_manual if usuario_manual else usuario_selecionado

# Função para obter histórico do usuário
def obter_historico(usuario_id):
    query = f"?usuario_id=eq.{usuario_id}&select=*"
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}{query}", headers=HEADERS)
    if response.status_code == 200:
        return pd.DataFrame(response.json())
    return pd.DataFrame()

# Função para calcular dias consecutivos de ofensiva
def calcular_ofensiva(historico):
    historico["data"] = pd.to_datetime(historico["data_hora"]).dt.date
    consumo_diario = historico.groupby("data")["quantidade_ml"].sum().reset_index()
    consumo_diario["ofensiva"] = consumo_diario["quantidade_ml"] > 3000

    dias_consecutivos = 0
    for ofensivo in reversed(consumo_diario["ofensiva"].tolist()):
        if ofensivo:
            dias_consecutivos += 1
        else:
            break

    return dias_consecutivos

# Indicadores de consumo
if usuario_id:
    st.subheader("📊 Indicadores de Consumo")
    historico = obter_historico(usuario_id)

    if not historico.empty:
        historico["data_hora"] = pd.to_datetime(historico["data_hora"]).dt.tz_convert(UTC_MINUS_3)
        historico["data"] = historico["data_hora"].dt.date

        # Consumo de hoje
        hoje = datetime.now(UTC_MINUS_3).date()
        consumo_hoje = historico[historico["data"] == hoje]["quantidade_ml"].sum()

        # Média dos outros dias
        consumo_diario = historico.groupby("data")["quantidade_ml"].sum()
        media_outros_dias = consumo_diario[consumo_diario.index != hoje].mean()

        # Cálculo da variação percentual
        if pd.notna(media_outros_dias) and media_outros_dias > 0:
            variacao = ((consumo_hoje - media_outros_dias) / media_outros_dias) * 100
            emoji = "😃" if consumo_hoje >= media_outros_dias else "😢"
        else:
            variacao = 0
            emoji = ""

        st.metric(label="Consumo de Hoje", value=f"{consumo_hoje}ml", delta=f"{variacao:.1f}% {emoji}")

        # Dias de ofensiva consecutivos
        dias_ofensiva = calcular_ofensiva(historico)
        st.metric(label="🔥 Dias de Ofensiva Consecutivos", value=f"{dias_ofensiva} dias")

    else:
        st.write("Nenhum registro encontrado.")

# Input de consumo
if usuario_id:
    st.subheader("➕ Registrar Consumo")
    quantidade_ml = st.number_input("Digite a quantidade em ml:", min_value=1, step=1)

    if st.button("Registrar"):
        agora_local = datetime.now(UTC_MINUS_3).isoformat()
        data = {"usuario_id": usuario_id, "data_hora": agora_local, "quantidade_ml": quantidade_ml}
        response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}", json=data, headers=HEADERS)
        
        if response.status_code == 201:
            st.success(f"Registrado: {quantidade_ml}ml!")
        else:
            st.error("Erro ao registrar consumo.")

# Gráficos de consumo
if usuario_id and not historico.empty:
    st.subheader("📊 Histórico de Consumo")

    # Consumo por dia
    consumo_diario = historico.groupby("data")["quantidade_ml"].sum().reset_index()
    fig_dia = px.bar(consumo_diario, x="data", y="quantidade_ml", title="Total Consumido por Dia")
    st.plotly_chart(fig_dia)

    # Consumo por hora
    historico["hora"] = historico["data_hora"].dt.hour
    consumo_hora = historico.groupby("hora")["quantidade_ml"].sum().reset_index()
    fig_hora = px.bar(consumo_hora, x="hora", y="quantidade_ml", title="Total Consumido por Hora")
    st.plotly_chart(fig_hora)

    # Média de consumo por hora
    media_horaria = historico.groupby("hora")["quantidade_ml"].mean().reset_index()
    fig_media_hora = px.bar(media_horaria, x="hora", y="quantidade_ml", title="Média de Consumo por Hora")
    st.plotly_chart(fig_media_hora)

    # Exibir histórico completo em tabela
    st.dataframe(historico)

# Ranking geral
if usuario_id:
    st.subheader("🏆 Ranking de Consumo")

    query = "?select=usuario_id,quantidade_ml"
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}{query}", headers=HEADERS)

    if response.status_code == 200:
        df_ranking = pd.DataFrame(response.json())

        if not df_ranking.empty:
            ranking = df_ranking.groupby("usuario_id")["quantidade_ml"].sum().reset_index()
            ranking = ranking.sort_values(by="quantidade_ml", ascending=False).reset_index(drop=True)

            posicao_usuario = ranking[ranking["usuario_id"] == usuario_id].index[0] + 1 if usuario_id in ranking["usuario_id"].values else "N/A"
            total_usuario = ranking[ranking["usuario_id"] == usuario_id]["quantidade_ml"].sum()

            st.metric(label="Sua Posição no Ranking", value=posicao_usuario)
            st.metric(label="Seu Consumo Total", value=f"{total_usuario}ml")

            # Exibir top 5
            top5 = ranking.head(5)
            st.dataframe(top5)

    else:
        st.write("Não foi possível carregar o ranking.")

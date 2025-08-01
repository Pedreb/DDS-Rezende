import streamlit as st
import pandas as pd
from unidecode import unidecode
import io
import plotly.express as px
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Organograma Diário",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🏢"
)

# CSS customizado para melhorar a aparência
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🏢 Sistema de Equipes - Organograma Inteligente</h1></div>',
            unsafe_allow_html=True)


# ———————————————————————————
# 1. Configurações globais e cache
@st.cache_data
def get_color_palette():
    """Paleta de cores moderna"""
    return {
        'supervisor': ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8CA'],
        'encarregado': '#FFE66D',
        'funcionario': '#A8E6CF',
        'background': '#F8F9FA'
    }


# Mapeamento flexível de colunas (melhorado)
COLUNAS_ESPERADAS = {
    "data": ["data", "date", "dt"],
    "nome": ["nome", "name", "funcionario", "pessoa"],
    "funcao": ["função", "funcao", "cargo", "position", "role"],
    "encarregado": ["encarregado", "responsavel", "líder", "leader", "supervisor_direto"],
    "supervisor": ["supervisor", "gestor", "coordenador", "manager", "chefe"]
}


@st.cache_data
def mapear_colunas(colunas_df: list) -> dict:
    """Mapeamento inteligente de colunas com cache"""
    mapeamento = {}
    atuais = [unidecode(c.lower().strip()) for c in colunas_df]

    for chave, sinonimos in COLUNAS_ESPERADAS.items():
        for i, col_norm in enumerate(atuais):
            if any(col_norm.startswith(s) for s in sinonimos):
                mapeamento[chave] = colunas_df[i]
                break
    return mapeamento


def validar_dados(df: pd.DataFrame) -> tuple[bool, list]:
    """Validação robusta dos dados"""
    erros = []

    if df.empty:
        erros.append("❌ Planilha está vazia")
        return False, erros

    # Verificar valores nulos em colunas críticas
    colunas_criticas = ["nome", "funcao", "encarregado", "supervisor"]
    for col in colunas_criticas:
        if col in df.columns:
            nulos = df[col].isnull().sum()
            if nulos > 0:
                erros.append(f"⚠️ {nulos} valores vazios na coluna '{col}'")

    # Verificar duplicatas
    if df.duplicated().sum() > 0:
        erros.append(f"⚠️ {df.duplicated().sum()} linhas duplicadas encontradas")

    return len(erros) == 0, erros


def limpar_dados(df: pd.DataFrame) -> pd.DataFrame:
    """Limpeza e padronização dos dados"""
    df_clean = df.copy()

    # Remover espaços extras
    for col in df_clean.select_dtypes(include=['object']).columns:
        df_clean[col] = df_clean[col].astype(str).str.strip()

    # Padronizar data
    if 'data' in df_clean.columns:
        df_clean["data"] = pd.to_datetime(df_clean["data"], errors="coerce").dt.strftime("%d/%m/%Y")

    # Remover duplicatas
    df_clean = df_clean.drop_duplicates()

    return df_clean


# ———————————————————————————
# 2. Visualizações modernas


def gerar_dot_moderno(df: pd.DataFrame, config: dict) -> str:
    """Geração DOT melhorada com configurações personalizáveis"""
    colors = get_color_palette()

    def escape_dot(texto: str) -> str:
        return texto.replace('"', '\\"').replace('\n', '\\n').replace('&', '&amp;')

    dot = f'digraph Organograma {{\n'
    dot += f'  rankdir={config.get("layout", "LR")};\n'
    dot += '  compound=true;\n'
    dot += '  bgcolor="white";\n'
    dot += '  node [fontname="Helvetica", style=filled, fontsize=10];\n'
    dot += '  edge [color="#666666", arrowsize=0.8];\n\n'

    supervisors = df["supervisor"].unique().tolist()

    for idx, sup in enumerate(supervisors):
        cor_supervisor = colors['supervisor'][idx % len(colors['supervisor'])]

        dot += f'  subgraph cluster_{idx} {{\n'
        dot += f'    label="{escape_dot(sup)}";\n'
        dot += '    style=filled;\n'
        dot += f'    fillcolor="{cor_supervisor}30";\n'
        dot += f'    color="{cor_supervisor}";\n'
        dot += '    penwidth=2;\n'
        dot += f'    "{escape_dot(sup)}" [shape=ellipse, fillcolor="{cor_supervisor}", fontcolor="white", fontsize=12, penwidth=2];\n'

        df_sup = df[df["supervisor"] == sup]
        encarregados = df_sup["encarregado"].unique().tolist()

        for enc in encarregados:
            dot += f'    "{escape_dot(enc)}" [shape=box, fillcolor="{config.get("cor_encarregado", colors["encarregado"])}", style="filled,rounded", penwidth=1.5];\n'
            dot += f'    "{escape_dot(sup)}" -> "{escape_dot(enc)}" [style=bold, color="{cor_supervisor}"];\n'

            for _, row in df_sup[df_sup["encarregado"] == enc].iterrows():
                nome = escape_dot(row["nome"])
                func = escape_dot(row["funcao"])
                label = f"{nome}\\n({func})"

                dot += f'    "{nome}" [shape=box, fillcolor="{config.get("cor_funcionario", colors["funcionario"])}", label="{label}", style="filled,rounded"];\n'
                dot += f'    "{escape_dot(enc)}" -> "{nome}" [color="#666666"];\n'

        dot += '  }\n\n'

    dot += '}\n'
    return dot


def criar_estatisticas(df: pd.DataFrame):
    """Dashboard de estatísticas"""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="👥 Total de Pessoas",
            value=len(df),
            help="Número total de funcionários"
        )

    with col2:
        st.metric(
            label="👔 Supervisores",
            value=df["supervisor"].nunique(),
            help="Número de supervisores únicos"
        )

    with col3:
        st.metric(
            label="📋 Encarregados",
            value=df["encarregado"].nunique(),
            help="Número de encarregados únicos"
        )

    with col4:
        st.metric(
            label="🎯 Funções",
            value=df["funcao"].nunique(),
            help="Diversidade de funções"
        )


def comparar_equipes(df_tot: pd.DataFrame, data1: str, data2: str):
    """Comparação entre duas datas"""
    df1 = df_tot[df_tot["data"] == data1]
    df2 = df_tot[df_tot["data"] == data2]

    st.subheader(f"📊 Comparação: {data1} vs {data2}")

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**{data1}**")
        criar_estatisticas(df1)

    with col2:
        st.write(f"**{data2}**")
        criar_estatisticas(df2)

    # Análise de mudanças
    pessoas_saida = set(df1["nome"]) - set(df2["nome"])
    pessoas_entrada = set(df2["nome"]) - set(df1["nome"])

    if pessoas_saida:
        st.warning(f"🔴 Saídas: {', '.join(pessoas_saida)}")
    if pessoas_entrada:
        st.success(f"🟢 Entradas: {', '.join(pessoas_entrada)}")


# ———————————————————————————
# 3. Interface principal

# Sidebar com configurações
with st.sidebar:
    st.title("⚙️ Configurações")

    modo = st.radio(
        "📌 Navegação",
        ["📥 Importar Planilha", "📊 Visualizar Organograma", "📈 Análises", "🔄 Comparar Datas"],
        help="Escolha a funcionalidade desejada"
    )

    if modo == "📊 Visualizar Organograma":
        st.subheader("🎨 Personalização")

        layout_direction = st.selectbox("Direção:", ["LR", "TB", "RL", "BT"])

        with st.expander("🎨 Cores Personalizadas"):
            cor_encarregado = st.color_picker("Encarregados:", "#FFE66D")
            cor_funcionario = st.color_picker("Funcionários:", "#A8E6CF")

# ———————————————————————————
# 4. Fluxo principal da aplicação

if modo == "📥 Importar Planilha":
    st.subheader("📥 Importação de Equipes")

    with st.expander("ℹ️ Formato da Planilha", expanded=False):
        st.write("""
        **Colunas necessárias (podem ter nomes similares):**
        - 📅 **Data**: Data do organograma
        - 👤 **Nome**: Nome do funcionário
        - 💼 **Função**: Cargo/função do funcionário
        - 👨‍💼 **Encarregado**: Responsável direto
        - 👔 **Supervisor**: Supervisor/gestor
        """)

    plan = st.file_uploader(
        "Envie um arquivo Excel (.xlsx)",
        type=["xlsx"],
        help="Máximo 200MB"
    )

    if plan:
        try:
            with st.spinner("🔄 Processando planilha..."):
                df_raw = pd.read_excel(plan)

                # Mostrar preview dos dados brutos
                st.write("**📋 Preview dos dados importados:**")
                st.dataframe(df_raw.head(), use_container_width=True)

                # Mapear colunas
                mapeamento = mapear_colunas(df_raw.columns.tolist())
                obrigatórias = ["data", "nome", "funcao", "encarregado", "supervisor"]

                if not all(c in mapeamento for c in obrigatórias):
                    faltando = [c for c in obrigatórias if c not in mapeamento]
                    st.error(f"❌ Colunas não encontradas: {', '.join(faltando)}")
                    st.info(
                        "💡 Certifique-se de que a planilha possui colunas similares a: Data, Nome, Função, Encarregado, Supervisor")
                else:
                    # Renomear e limpar dados
                    df = df_raw.rename(columns={v: k for k, v in mapeamento.items()})
                    df = limpar_dados(df)

                    # Validar dados
                    valido, erros = validar_dados(df)

                    if erros:
                        st.warning("⚠️ Avisos encontrados:")
                        for erro in erros:
                            st.write(f"- {erro}")

                    if valido or st.checkbox("🚀 Prosseguir mesmo com avisos"):
                        st.success("✅ Planilha processada com sucesso!")

                        # Estatísticas rápidas
                        col1, col2, col3 = st.columns(3)
                        col1.metric("📊 Total de registros", len(df))
                        col2.metric("📅 Datas únicas", df["data"].nunique())
                        col3.metric("👥 Pessoas únicas", df["nome"].nunique())

                        st.dataframe(df, use_container_width=True)
                        st.session_state["df_equipes"] = df

                        # Botão para ir para visualização
                        if st.button("🎯 Ir para Visualização", type="primary"):
                            st.rerun()

        except Exception as e:
            st.error(f"❌ Erro ao processar planilha: {str(e)}")
            st.info("💡 Verifique se o arquivo não está corrompido e tente novamente")

elif modo == "📊 Visualizar Organograma":
    if "df_equipes" not in st.session_state:
        st.warning("⚠️ Carregue uma planilha primeiro na aba 'Importar Planilha'.")
        if st.button("📥 Ir para Importação"):
            st.rerun()
    else:
        df_total = st.session_state["df_equipes"]

        # Seleção de data
        col1, col2 = st.columns([2, 1])
        with col1:
            datas = sorted(df_total["data"].unique(), reverse=True)
            data_selecionada = st.selectbox("📅 Selecione a data:", datas)

        with col2:
            st.write("")  # Espaçamento
            mostrar_stats = st.checkbox("📊 Mostrar estatísticas", value=True)

        df_selecionado = df_total[df_total["data"] == data_selecionada]

        if df_selecionado.empty:
            st.warning("⚠️ Nenhum registro para essa data.")
        else:
            # Visualização com Graphviz melhorado
            st.markdown(f"### 🏢 Organograma - {data_selecionada}")

            if mostrar_stats:
                criar_estatisticas(df_selecionado)
                st.markdown("---")

            # Filtros avançados
            with st.expander("🔍 Filtros Avançados"):
                col1, col2 = st.columns(2)
                with col1:
                    supervisores_selecionados = st.multiselect(
                        "Filtrar por supervisor:",
                        df_selecionado["supervisor"].unique(),
                        default=df_selecionado["supervisor"].unique()
                    )
                with col2:
                    funcoes_selecionadas = st.multiselect(
                        "Filtrar por função:",
                        df_selecionado["funcao"].unique(),
                        default=df_selecionado["funcao"].unique()
                    )

                # Aplicar filtros
                if supervisores_selecionados:
                    df_selecionado = df_selecionado[df_selecionado["supervisor"].isin(supervisores_selecionados)]
                if funcoes_selecionadas:
                    df_selecionado = df_selecionado[df_selecionado["funcao"].isin(funcoes_selecionadas)]

            # Visualização com Graphviz moderno
            config = {
                "layout": layout_direction,
                "cor_encarregado": cor_encarregado,
                "cor_funcionario": cor_funcionario
            }
            dot = gerar_dot_moderno(df_selecionado, config)
            st.graphviz_chart(dot, use_container_width=True)

            # Exportação
            col1, col2 = st.columns(2)
            with col1:
                buffer = io.BytesIO()
                df_selecionado.to_excel(buffer, index=False, sheet_name="Equipe")
                buffer.seek(0)
                st.download_button(
                    "📥 Exportar Excel",
                    data=buffer,
                    file_name=f"equipe_{data_selecionada.replace('/', '-')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            with col2:
                # Exportar DOT
                config = {"layout": layout_direction}
                dot_export = gerar_dot_moderno(df_selecionado, config)
                st.download_button(
                    "📄 Exportar .dot",
                    data=dot_export,
                    file_name=f"organograma_{data_selecionada.replace('/', '-')}.dot",
                    mime="text/plain"
                )

elif modo == "📈 Análises":
    if "df_equipes" not in st.session_state:
        st.warning("⚠️ Carregue uma planilha primeiro.")
    else:
        df_total = st.session_state["df_equipes"]
        st.subheader("📈 Análises da Equipe")

        # Evolução temporal
        evolucao = df_total.groupby("data").agg({
            "nome": "nunique",
            "supervisor": "nunique",
            "encarregado": "nunique",
            "funcao": "nunique"
        }).reset_index()

        fig_evolucao = px.line(
            evolucao,
            x="data",
            y=["nome", "supervisor", "encarregado", "funcao"],
            title="📈 Evolução da Equipe ao Longo do Tempo",
            labels={"value": "Quantidade", "variable": "Categoria"}
        )
        fig_evolucao.update_layout(height=400)
        st.plotly_chart(fig_evolucao, use_container_width=True)

        # Distribuição por função
        col1, col2 = st.columns(2)

        with col1:
            funcoes_count = df_total["funcao"].value_counts()
            fig_funcoes = px.pie(
                values=funcoes_count.values,
                names=funcoes_count.index,
                title="🎯 Distribuição por Função"
            )
            st.plotly_chart(fig_funcoes, use_container_width=True)

        with col2:
            sup_count = df_total["supervisor"].value_counts()
            fig_sup = px.bar(
                x=sup_count.values,
                y=sup_count.index,
                orientation='h',
                title="👔 Equipe por Supervisor"
            )
            fig_sup.update_layout(height=400)
            st.plotly_chart(fig_sup, use_container_width=True)

elif modo == "🔄 Comparar Datas":
    if "df_equipes" not in st.session_state:
        st.warning("⚠️ Carregue uma planilha primeiro.")
    else:
        df_total = st.session_state["df_equipes"]
        datas = sorted(df_total["data"].unique())

        if len(datas) < 2:
            st.warning("⚠️ É necessário ter pelo menos 2 datas para comparação.")
        else:
            st.subheader("🔄 Comparação entre Datas")

            col1, col2 = st.columns(2)
            with col1:
                data1 = st.selectbox("📅 Data 1:", datas, key="data1")
            with col2:
                data2 = st.selectbox("📅 Data 2:", datas, index=1, key="data2")

            if data1 != data2:
                comparar_equipes(df_total, data1, data2)
            else:
                st.info("🔄 Selecione datas diferentes para comparação.")
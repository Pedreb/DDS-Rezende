import streamlit as st
import pandas as pd
from unidecode import unidecode
import io
import plotly.express as px
from datetime import datetime
import requests
from msal import ConfidentialClientApplication

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
    .sharepoint-status {
        background: #e3f2fd;
        border: 1px solid #2196f3;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🏢 Sistema de Equipes</h1></div>',
            unsafe_allow_html=True)

# ———————————————————————————
# 1. Configurações SharePoint - SEGURAS
try:
    SHAREPOINT_CONFIG = {
        "client_id": st.secrets["SHAREPOINT_CLIENT_ID"],
        "client_secret": st.secrets["SHAREPOINT_CLIENT_SECRET"],
        "tenant_id": st.secrets["SHAREPOINT_TENANT_ID"],
        "site_name": "rezendeenergia.sharepoint.com",
        "site_path": "/sites/Intranet",
        "file_path": "/sites/Intranet/Documentos Compartilhados/ADMINISTRAÇÃO/DAGEP - Departamento Ágil de Gestão de Pessoas/General/Recursos Humanos/03 - CONTROLE E BANCO HORA EXTRA E FOLGA/FOLGA DAS EQUIPES",
        "arquivo_nome": "DDS DAS EQUIPES GERAL.xlsx"  # Nome exato do arquivo
    }
except KeyError as e:
    st.error(f"❌ Erro de configuração: {e}")
    st.error("🔧 Configure as secrets do SharePoint nas configurações do app")
    st.stop()


@st.cache_data(ttl=300)  # Cache por 5 minutos
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
    "data": ["data", "date", "dt", "dia"],
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
# 2. Funções SharePoint - Método que funcionou

@st.cache_data(ttl=300)  # Cache por 5 minutos
def baixar_planilha_sharepoint_direto():
    """Baixa a planilha do SharePoint usando o método que funcionou"""
    try:
        # Configurar autenticação
        app = ConfidentialClientApplication(
            SHAREPOINT_CONFIG["client_id"],
            authority=f"https://login.microsoftonline.com/{SHAREPOINT_CONFIG['tenant_id']}",
            client_credential=SHAREPOINT_CONFIG["client_secret"],
        )

        # Obter token
        st.write("🔐 Obtendo token de acesso...")
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

        if "access_token" in result:
            headers = {"Authorization": f"Bearer {result['access_token']}"}
            st.success("✅ Token obtido com sucesso!")

            # Obter o site_id
            site_url = "https://graph.microsoft.com/v1.0/sites/rezendeenergia.sharepoint.com:/sites/Intranet"
            site_response = requests.get(site_url, headers=headers)

            if site_response.status_code == 200:
                site_data = site_response.json()
                site_id = site_data['id']
                st.write(f"✅ Site ID obtido: {site_id}")

                # Buscar o arquivo específico
                st.write("🔍 Buscando arquivo 'DDS DAS EQUIPES GERAL.xlsx'...")
                search_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root/search(q='DDS DAS EQUIPES GERAL.xlsx')"
                search_response = requests.get(search_url, headers=headers)

                if search_response.status_code == 200:
                    search_data = search_response.json()
                    files_found = search_data.get('value', [])
                    st.write(f"📋 Encontrados {len(files_found)} arquivo(s)")

                    for item in files_found:
                        st.write(f"📄 Arquivo: {item['name']}")
                        if 'parentReference' in item and 'path' in item['parentReference']:
                            st.write(f"📁 Localização: {item['parentReference']['path']}")

                        # Se for exatamente o arquivo que queremos
                        if item['name'] == 'DDS DAS EQUIPES GERAL.xlsx':
                            st.success(f"🎯 Arquivo alvo encontrado! ID: {item['id']}")

                            # Baixar o arquivo usando o ID
                            download_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{item['id']}/content"
                            st.write("⬇️ Iniciando download...")
                            download_response = requests.get(download_url, headers=headers)

                            if download_response.status_code == 200:
                                st.success("✅ Download concluído com sucesso!")

                                # Ler o arquivo Excel
                                df = pd.read_excel(io.BytesIO(download_response.content))
                                st.success(f"📊 Arquivo carregado! Dimensões: {df.shape}")
                                st.write(f"📋 Colunas: {list(df.columns)}")

                                return df
                            else:
                                st.error(f"❌ Erro no download: {download_response.status_code}")
                                st.error(f"Resposta: {download_response.text}")

                    # Se não encontrou o arquivo exato
                    if not any(item['name'] == 'DDS DAS EQUIPES GERAL.xlsx' for item in files_found):
                        st.warning("⚠️ Arquivo 'DDS DAS EQUIPES GERAL.xlsx' não encontrado exatamente")
                        st.write("Arquivos similares encontrados:")
                        for item in files_found:
                            if 'DDS' in item['name']:
                                st.write(f"  📄 {item['name']}")
                else:
                    st.error(f"❌ Erro na busca: {search_response.status_code}")
                    st.error(f"Resposta: {search_response.text}")
            else:
                st.error(f"❌ Erro ao obter site: {site_response.status_code}")
                st.error(f"Resposta: {site_response.text}")
        else:
            st.error("❌ Erro na autenticação:")
            st.error(result)

        return None

    except Exception as e:
        st.error(f"❌ Erro geral: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None


@st.cache_data(ttl=300)  # Cache por 5 minutos
def baixar_planilha_sharepoint():
    """Baixa a planilha do SharePoint e retorna DataFrame - método que funcionou"""
    with st.spinner("🔄 Conectando ao SharePoint..."):
        df_raw = baixar_planilha_sharepoint_direto()

    if df_raw is not None:
        return df_raw
    else:
        st.error("❌ Não foi possível baixar a planilha do SharePoint")
        return None


# ———————————————————————————
# 3. Visualizações (mantidas do código original)

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
# 4. Interface principal

# Sidebar com configurações
with st.sidebar:
    st.title("⚙️ Configurações")

    modo = st.radio(
        "📌 Navegação",
        ["📊 Visualizar Organograma", "📈 Análises", "🔄 Comparar Datas"],
        help="Escolha a funcionalidade desejada"
    )

    # Status da conexão SharePoint
    if st.button("🔄 Atualizar Cache", help="Limpar cache e buscar dados atualizados"):
        st.cache_data.clear()
        st.rerun()

    if modo == "📊 Visualizar Organograma":
        st.subheader("🎨 Personalização")

        layout_direction = st.selectbox("Direção:", ["LR", "TB", "RL", "BT"])

        with st.expander("🎨 Cores Personalizadas"):
            cor_encarregado = st.color_picker("Encarregados:", "#FFE66D")
            cor_funcionario = st.color_picker("Funcionários:", "#A8E6CF")

# ———————————————————————————
# 5. Fluxo principal da aplicação

if modo == "📊 Visualizar Organograma":
    # Botão simples para carregar do SharePoint
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📥 Carregar Dados do SharePoint", type="primary", use_container_width=True):
            df_raw = baixar_planilha_sharepoint()

            if df_raw is not None:
                # Mapear colunas
                mapeamento = mapear_colunas(df_raw.columns.tolist())
                obrigatórias = ["data", "nome", "funcao", "encarregado", "supervisor"]

                if not all(c in mapeamento for c in obrigatórias):
                    faltando = [c for c in obrigatórias if c not in mapeamento]
                    st.error(f"❌ Colunas não encontradas: {', '.join(faltando)}")
                    st.write("**🔍 Colunas encontradas:**", list(df_raw.columns))
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
                        st.success("✅ Dados do SharePoint carregados com sucesso!")
                        st.session_state["df_equipes"] = df
                        st.session_state["fonte_dados"] = "SharePoint"
                        st.rerun()

    if "df_equipes" not in st.session_state:
        st.info("ℹ️ Clique no botão acima para carregar os dados do SharePoint")
        st.stop()

    # Resto do código da visualização
    df_total = st.session_state["df_equipes"]
    fonte = st.session_state.get("fonte_dados", "Desconhecida")

    # Indicador da fonte
    st.success(f"📊 Dados carregados de: **{fonte}**")

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
        col1, col2, col3 = st.columns(3)
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

        with col3:
            if st.button("🔄 Recarregar"):
                st.cache_data.clear()
                st.rerun()

elif modo == "📈 Análises":
    if "df_equipes" not in st.session_state:
        st.warning("⚠️ Carregue os dados primeiro na página 'Visualizar Organograma'.")
    else:
        df_total = st.session_state["df_equipes"]
        st.subheader("📈 Análises da Equipe")

        # Filtro de data "entre datas"
        col1, col2, col3 = st.columns([2, 2, 1])

        # Converter datas para datetime para os date_input
        datas_disponiveis = sorted(df_total["data"].unique())
        datas_dt = [pd.to_datetime(data, format="%d/%m/%Y").date() for data in datas_disponiveis]

        with col1:
            data_inicial = st.date_input(
                "📅 Data Inicial:",
                value=min(datas_dt),
                min_value=min(datas_dt),
                max_value=max(datas_dt),
                format="DD/MM/YYYY"
            )

        with col2:
            data_final = st.date_input(
                "📅 Data Final:",
                value=max(datas_dt),
                min_value=min(datas_dt),
                max_value=max(datas_dt),
                format="DD/MM/YYYY"
            )

        with col3:
            st.write("")  # Espaçamento
            if st.button("🔄 Período Completo"):
                st.rerun()

        # Aplicar filtro de período
        # Converter as datas selecionadas de volta para string no formato original
        data_inicial_str = data_inicial.strftime("%d/%m/%Y")
        data_final_str = data_final.strftime("%d/%m/%Y")

        # Filtrar dados no período selecionado
        df_filtrado = df_total[
            (pd.to_datetime(df_total["data"], format="%d/%m/%Y").dt.date >= data_inicial) &
            (pd.to_datetime(df_total["data"], format="%d/%m/%Y").dt.date <= data_final)
            ]

        if df_filtrado.empty:
            st.warning("⚠️ Nenhum dado encontrado para o período selecionado.")
            st.stop()

        # Mostrar período selecionado
        st.info(f"📊 Analisando período de **{data_inicial_str}** a **{data_final_str}** ({len(df_filtrado)} registros)")

        # Gráfico: DDS por dia
        st.subheader("📊 Quantidade de DDS por Dia")
        dds_por_dia = df_filtrado.groupby("data")["encarregado"].nunique().reset_index()
        dds_por_dia.columns = ["Data", "Quantidade de DDS"]

        fig_dds = px.bar(
            dds_por_dia,
            x="Data",
            y="Quantidade de DDS",
            title="📋 Número de DDS (Encarregados) por Dia",
            color="Quantidade de DDS",
            color_continuous_scale="Blues",
            text="Quantidade de DDS"  # Adicionar rótulos
        )
        fig_dds.update_traces(texttemplate='%{text}', textposition='outside')
        # Ajustar escala do eixo Y para dar espaço aos rótulos
        max_value = dds_por_dia["Quantidade de DDS"].max()
        fig_dds.update_layout(
            height=400,
            yaxis=dict(range=[0, max_value * 1.15])  # Adiciona 15% de espaço extra
        )
        st.plotly_chart(fig_dds, use_container_width=True)

        # Gráficos lado a lado
        col1, col2 = st.columns(2)

        with col1:
            # Distribuição por função
            funcoes_count = df_filtrado["funcao"].value_counts()
            fig_funcoes = px.pie(
                values=funcoes_count.values,
                names=funcoes_count.index,
                title="🎯 Distribuição por Função"
            )
            fig_funcoes.update_traces(
                textposition='inside',
                textinfo='percent+label',
                textfont_size=12
            )
            st.plotly_chart(fig_funcoes, use_container_width=True)

        with col2:
            # Encarregados por Supervisor
            sup_encarregados = df_filtrado.groupby("supervisor")["encarregado"].nunique().reset_index()
            sup_encarregados.columns = ["Supervisor", "Quantidade de Encarregados"]
            sup_encarregados = sup_encarregados.sort_values("Quantidade de Encarregados", ascending=True)

            fig_sup = px.bar(
                sup_encarregados,
                x="Quantidade de Encarregados",
                y="Supervisor",
                orientation='h',
                title="👔 Encarregados por Supervisor",
                color="Quantidade de Encarregados",
                color_continuous_scale="Greens",
                text="Quantidade de Encarregados"  # Adicionar rótulos
            )
            fig_sup.update_traces(texttemplate='%{text}', textposition='outside')
            fig_sup.update_layout(height=400)
            st.plotly_chart(fig_sup, use_container_width=True)

        # Estatísticas extras
        st.subheader("📊 Estatísticas Detalhadas")

        col1, col2, col3 = st.columns(3)

        with col1:
            # Média de DDS por dia
            if len(dds_por_dia) > 0:
                media_dds = dds_por_dia["Quantidade de DDS"].mean()
                st.metric(
                    "📊 Média de DDS/dia",
                    f"{media_dds:.1f}",
                    help="Número médio de DDS (encarregados) por dia no período"
                )
            else:
                st.metric("📊 Média de DDS/dia", "0")

        with col2:
            # Maior número de DDS em um dia
            if len(dds_por_dia) > 0:
                max_dds = dds_por_dia["Quantidade de DDS"].max()
                data_max = dds_por_dia.loc[dds_por_dia["Quantidade de DDS"].idxmax(), "Data"]
                st.metric(
                    "🏆 Máximo DDS/dia",
                    max_dds,
                    help=f"Maior número registrado em {data_max}"
                )
            else:
                st.metric("🏆 Máximo DDS/dia", "0")

        with col3:
            # Total de encarregados únicos
            total_encarregados = df_filtrado["encarregado"].nunique()
            st.metric(
                "👥 Total Encarregados",
                total_encarregados,
                help="Número total de encarregados únicos no período selecionado"
            )

elif modo == "🔄 Comparar Datas":
    if "df_equipes" not in st.session_state:
        st.warning("⚠️ Carregue os dados primeiro na página 'Visualizar Organograma'.")
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

# Footer
st.markdown("---")
st.markdown("🏢 **Sistema de Organograma Integrado** | Powered by SharePoint + Streamlit")

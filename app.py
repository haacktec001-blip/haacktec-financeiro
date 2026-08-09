import streamlit as st
import json
import os
import copy
from datetime import datetime

DATA_FILE = "dados_haacktec_fin.json"

st.set_page_config(page_title="Haacktec - Gestão Financeira Integrada", page_icon="💰", layout="wide")

MESES_PT = {
    "January": "Janeiro", "February": "Fevereiro", "March": "Março",
    "April": "Abril", "May": "Maio", "June": "Junho",
    "July": "Julho", "August": "Agosto", "September": "Setembro",
    "October": "Outubro", "November": "Novembro", "December": "Dezembro"
}

BANCO_ICONES = [
    "💧", "🏠", "🛒", "🌐", "⚡", "💊", "💳", "📦", 
    "🛠️", "🚗", "🎸", "💻", "📚", "🍔", "✈️", "💡", "🔧", "📱"
]

DESPESAS_INICIAIS_PADRAO = [
    {"categoria": "💧 Água", "meta": 0.0, "itens": []},
    {"categoria": "🏠 Aluguel", "meta": 0.0, "itens": []},
    {"categoria": "🛒 Compras do Mês", "meta": 0.0, "itens": []},
    {"categoria": "🌐 Internet", "meta": 0.0, "itens": []},
    {"categoria": "⚡ Luz", "meta": 0.0, "itens": []},
    {"categoria": "💊 Saúde", "meta": 0.0, "itens": []}
]

CARTOES_PADRAO = [
    "Dinheiro / Pix", "Mercado Pago", "Nubank", "Itaú", "Caixa",
    "Bradesco", "Banco do Brasil", "Santander", "Banco Inter", "C6 Bank",
    "BTG Pactual", "PicPay", "PagBank", "Banrisul", "Sicredi", "Sicoob",
    "Neon", "Credicard", "Caixa Tem", "Outro"
]

def obter_mes_atual_pt():
    mes_en = datetime.now().strftime("%B")
    mes_pt = MESES_PT.get(mes_en, mes_en)
    ano = datetime.now().strftime("%Y")
    return f"{mes_pt} / {ano}"

def calcular_ir_cdi(rendimento_bruto, dias_investido=365):
    if dias_investido <= 180:
        aliquota = 0.225
    elif dias_investido <= 360:
        aliquota = 0.20
    elif dias_investido <= 720:
        aliquota = 0.175
    else:
        aliquota = 0.15
    return rendimento_bruto * aliquota

def calcular_rendimento_caixinha(din_ini, ap_men, cdi_anual=10.50, dias_investido=30):
    taxa_mensal = (1 + cdi_anual / 100) ** (1 / 12) - 1
    rend_saldo_inicial = din_ini * taxa_mensal
    rend_aporte = ap_men * (taxa_mensal * 0.5)
    rend_bruto_total = rend_saldo_inicial + rend_aporte
    imposto = calcular_ir_cdi(rend_bruto_total, dias_investido=dias_investido)
    rend_liquido = rend_bruto_total - imposto
    saldo_final_estimado = din_ini + ap_men + rend_liquido
    return saldo_final_estimado, rend_liquido

def carregar_dados():
    if not os.path.exists(DATA_FILE):
        return {
            "configurado": False,
            "mes_atual": obter_mes_atual_pt(),
            "historico": {},
            "cartoes": CARTOES_PADRAO,
            "receitas": [{"tipo": "Salário Principal", "fonte": "Empregador", "valor": 5000.0}],
            "caixinhas": [
                {"nome": "Reserva de Ferramentas", "dinheiro_inicial": 0.0, "aporte_mensal": 0.0, "cdi_anual": 10.50},
                {"nome": "Reserva de Emergência", "dinheiro_inicial": 0.0, "aporte_mensal": 0.0, "cdi_anual": 10.50}
            ],
            "despesas": copy.deepcopy(DESPESAS_INICIAIS_PADRAO),
            "log_movimentacoes": []
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        dados = json.load(f)
        dados.setdefault("historico", {})
        dados.setdefault("log_movimentacoes", [])
        dados["cartoes"] = CARTOES_PADRAO
        return dados

def salvar_dados(dados):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def registrar_log(dados, mensagem):
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    entry = f"[{data_hora}] {mensagem}"
    dados.setdefault("log_movimentacoes", []).insert(0, entry)
    if len(dados["log_movimentacoes"]) > 100:
        dados["log_movimentacoes"] = dados["log_movimentacoes"][:100]

dados = carregar_dados()

# Layout em duas colunas (Esquerda: Lançamentos / Direita: Painel)
col_esq, col_dir = st.columns([1.2, 1])

with col_esq:
    st.markdown(f"### 📅 Mês: {dados.get('mes_atual', 'Atual')}")
    st.divider()
    st.markdown("#### 📂 Categorias / Despesas")

    for d in dados.get("despesas", []):
        total_cat = sum(item["valor"] for item in d.get("itens", []))
        meta_cat = d.get("meta", 0.0)
        
        titulo_exp = f"{d['categoria']} — Total: R$ {total_cat:.2f}"
        if meta_cat > 0:
            titulo_exp += f" (Meta: R$ {meta_cat:.0f})"

        with st.expander(titulo_exp):
            if d.get("itens"):
                for idx, item in enumerate(d["itens"]):
                    st.write(f"• **{item['desc']}**: R$ {item['valor']:.2f} | Cartão: {item.get('cartao', 'Pix')} | Parcelas: {item.get('parcelas', 1)}x")
            else:
                st.info("Nenhum item cadastrado nesta categoria.")

    st.divider()
    with st.expander("➕ Adicionar Nova Categoria"):
        icone_sel = st.selectbox("Ícone", BANCO_ICONES)
        nome_cat = st.text_input("Nome da Categoria")
        meta_cat_val = st.number_input("Meta de Gastos R$ (Opcional)", min_value=0.0, format="%.2f")
        if st.button("Criar Categoria"):
            if nome_cat:
                completo = f"{icone_sel} {nome_cat}"
                if not any(x["categoria"].lower() == completo.lower() for x in dados["despesas"]):
                    dados["despesas"].append({"categoria": completo, "meta": meta_cat_val, "itens": []})
                    registrar_log(dados, f"Criada nova categoria '{completo}'.")
                    salvar_dados(dados)
                    st.success("Categoria criada com sucesso!")
                    st.rerun()

    with st.expander("➕ Adicionar Gasto / Item"):
        cat_nomes = [x["categoria"] for x in dados["despesas"]]
        if cat_nomes:
            cat_escolhida = st.selectbox("Categoria de Destino", cat_nomes)
            desc_gasto = st.text_input("Descrição do Gasto")
            val_gasto = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
            cartao_gasto = st.selectbox("Forma de Pagamento", dados.get("cartoes", CARTOES_PADRAO))
            parc_gasto = st.number_input("Parcelas", min_value=1, value=1, step=1)
            venc_gasto = st.number_input("Dia Vencimento", min_value=1, max_value=31, value=10, step=1)
            
            if st.button("Salvar Despesa no App") and desc_gasto and val_gasto > 0:
                for cat in dados["despesas"]:
                    if cat["categoria"] == cat_escolhida:
                        cat.setdefault("itens", []).append({
                            "desc": desc_gasto,
                            "valor": val_gasto,
                            "cartao": cartao_gasto,
                            "parcelas": parc_gasto,
                            "dia_vencimento": venc_gasto,
                            "data_registro": datetime.now().strftime("%d/%m/%Y"),
                            "pago": True
                        })
                        registrar_log(dados, f"Adicionado '{desc_gasto}' (R$ {val_gasto:.2f}) em {cat_escolhida}.")
                        salvar_dados(dados)
                        st.success("Gasto salvo com sucesso!")
                        st.rerun()

with col_dir:
    st.markdown("### 🎛️ Painel de Controle & Saldo")
    
    total_ganhos = sum(i["valor"] for i in dados.get("receitas", []))
    total_gastos = sum(sum(item["valor"] for item in d.get("itens", [])) for d in dados.get("despesas", []))
    
    total_caixinhas = 0.0
    total_aportes = 0.0
    for cx in dados.get("caixinhas", []):
        din_ini = cx.get("dinheiro_inicial", 0.0)
        ap_men = cx.get("aporte_mensal", 0.0)
        cdi = cx.get("cdi_anual", 10.50)
        est, _ = calcular_rendimento_caixinha(din_ini, ap_men, cdi, 30)
        total_caixinhas += est
        total_aportes += ap_men

    saldo_livre = total_ganhos - total_gastos - total_aportes
    patrimonio = saldo_livre + total_caixinhas

    st.metric("GANHOS TOTAIS", f"R$ {total_ganhos:.2f}")
    st.metric("GASTOS TOTAIS", f"R$ {total_gastos:.2f}")
    st.metric("ESTIMATIVA CAIXINHAS (CDI)", f"R$ {total_caixinhas:.2f}")
    st.metric("SALDO DISPONÍVEL (LIVRE)", f"R$ {saldo_livre:.2f}")
    st.metric("PATRIMÔNIO TOTAL ESTIMADO", f"R$ {patrimonio:.2f}")

    st.divider()

    with st.expander("💰 Gerenciar Ganhos / Renda"):
        for i, rec in enumerate(dados.get("receitas", [])):
            st.write(f"- **{rec['tipo']}** ({rec['fonte']}): R$ {rec['valor']:.2f}")
        novo_tipo = st.text_input("Tipo de Renda (ex: Salário)")
        novo_fonte = st.text_input("Fonte (ex: Empregador)")
        novo_val = st.number_input("Valor R$", min_value=0.0, format="%.2f", key="val_ganho_novo")
        if st.button("Adicionar Ganho") and novo_tipo and novo_val > 0:
            dados.setdefault("receitas", []).append({"tipo": novo_tipo, "fonte": novo_fonte, "valor": novo_val})
            registrar_log(dados, f"Adicionado ganho '{novo_tipo}' de R$ {novo_val:.2f}.")
            salvar_dados(dados)
            st.success("Ganho adicionado!")
            st.rerun()

    with st.expander("📦 Caixinhas & Investimentos (CDI)"):
        for cx in dados.get("caixinhas", []):
            st.write(f"- **{cx['nome']}** | Aporte: R$ {cx['aporte_mensal']:.2f} | CDI: {cx['cdi_anual']}%")
        novo_cx_nome = st.text_input("Nome da Caixinha")
        novo_cx_din = st.number_input("Dinheiro Inicial R$", min_value=0.0, format="%.2f")
        novo_cx_ap = st.number_input("Aporte Mensal R$", min_value=0.0, format="%.2f")
        if st.button("Criar Caixinha") and novo_cx_nome:
            dados.setdefault("caixinhas", []).append({
                "nome": novo_cx_nome, "dinheiro_inicial": novo_cx_din,
                "aporte_mensal": novo_cx_ap, "cdi_anual": 10.50
            })
            registrar_log(dados, f"Criada caixinha '{novo_cx_nome}'.")
            salvar_dados(dados)
            st.success("Caixinha criada!")
            st.rerun()

    with st.expander("📜 Ver Log de Movimentações"):
        logs = dados.get("log_movimentacoes", [])
        if logs:
            for l in logs[:20]:
                st.text(l)
        else:
            st.info("Nenhum log registrado.")

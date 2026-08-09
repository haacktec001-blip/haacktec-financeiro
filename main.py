import json
import os
import copy
from datetime import datetime
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.list import OneLineIconListItem, IconLeftWidget
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.textfield import MDTextField

DATA_FILE = "dados_haacktec_fin.json"

MESES_PT = {
    "January": "Janeiro", "February": "Fevereiro", "March": "Março",
    "April": "Abril", "May": "Maio", "June": "Junho",
    "July": "Julho", "August": "Agosto", "September": "Setembro",
    "October": "Outubro", "November": "Novembro", "December": "Dezembro"
}

DESPESAS_INICIAIS_PADRAO = [
    {"categoria": "💧 Água", "meta": 0.0, "itens": []},
    {"categoria": "🏠 Aluguel", "meta": 0.0, "itens": []},
    {"categoria": "🛒 Compras do Mês", "meta": 0.0, "itens": []},
    {"categoria": "⚡ Luz", "meta": 0.0, "itens": []},
    {"categoria": "💊 Saúde", "meta": 0.0, "itens": []}
]

KV = '''
MDScreen:
    md_bg_color: 0.1, 0.1, 0.1, 1

    MDBoxLayout:
        orientation: 'vertical'

        MDTopAppBar:
            title: "Haacktec - Gestão Financeira"
            elevation: 4
            md_bg_color: 0.17, 0.48, 0.47, 1
            specific_text_color: 1, 1, 1, 1

        ScrollView:
            MDList:
                id: lista_categorias

    MDFloatingActionButton:
        icon: "plus"
        pos_hint: {"center_x": .85, "center_y": .1}
        md_bg_color: 0.17, 0.48, 0.47, 1
        on_release: app.abrir_dialogo_nova_categoria()
'''

class HaacktecApp(MDApp):
    dialog = None

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        self.carregar_dados()
        return Builder.load_string(KV)

    def on_start(self):
        self.atualizar_tela()

    def obter_mes_atual_pt(self):
        mes_en = datetime.now().strftime("%B")
        mes_pt = MESES_PT.get(mes_en, mes_en)
        ano = datetime.now().strftime("%Y")
        return f"{mes_pt} / {ano}"

    def carregar_dados(self):
        if not os.path.exists(DATA_FILE):
            self.dados = {
                "configurado": True,
                "mes_atual": self.obter_mes_atual_pt(),
                "historico": {},
                "receitas": [{"tipo": "Salário Principal", "fonte": "Empregador", "valor": 5000.0}],
                "caixinhas": [{"nome": "Reserva de Ferramentas", "dinheiro_inicial": 0.0, "aporte_mensal": 0.0, "cdi_anual": 10.50}],
                "despesas": copy.deepcopy(DESPESAS_INICIAIS_PADRAO),
                "log_movimentacoes": []
            }
            self.salvar_dados()
        else:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                self.dados = json.load(f)

    def salvar_dados(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.dados, f, ensure_ascii=False, indent=4)

    def atualizar_tela(self):
        lista = self.root.ids.lista_categorias
        lista.clear_widgets()
        
        for d in self.dados.get("despesas", []):
            total_cat = sum(item["valor"] for item in d.get("itens", []))
            meta_cat = d.get("meta", 0.0)
            
            texto_item = f"{d['categoria']} — Gasto: R$ {total_cat:.2f}"
            if meta_cat > 0:
                texto_item += f" (Meta: R$ {meta_cat:.0f})"

            listItem = OneLineIconListItem(text=texto_item)
            icon = IconLeftWidget(icon="wallet")
            listItem.add_widget(icon)
            lista.add_widget(listItem)

    def abrir_dialogo_nova_categoria(self):
        if not self.dialog:
            self.campo_texto = MDTextField(hint_text="Nome da Categoria (ex: 🛠️ Ferramentas)")
            self.dialog = MDDialog(
                title="Nova Categoria",
                type="custom",
                content_cls=self.campo_texto,
                buttons=[
                    MDFlatButton(
                        text="CANCELAR",
                        theme_text_color="Custom",
                        text_color=self.theme_cls.primary_color,
                        on_release=lambda x: self.dialog.dismiss()
                    ),
                    MDRaisedButton(
                        text="CRIAR",
                        md_bg_color=(0.17, 0.48, 0.47, 1),
                        on_release=lambda x: self.salvar_nova_categoria()
                    ),
                ],
            )
        self.dialog.open()

    def salvar_nova_categoria(self):
        nome = self.campo_texto.text.strip()
        if nome:
            nova_cat = f"📂 {nome}"
            self.dados["despesas"].append({"categoria": nova_cat, "meta": 0.0, "itens": []})
            self.salvar_dados()
            self.atualizar_tela()
            self.campo_texto.text = "_"
            self.dialog.dismiss()

if __name__ == '__main__':
    HaacktecApp().run()
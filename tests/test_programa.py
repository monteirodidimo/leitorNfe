"""Testes do programa.

Usam os XMLs ficticios da pasta exemplos_xml. O arquivo tests/gabarito.json
tem o resultado esperado de cada nota, e os testes comparam o que o programa
calculou com ele.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from banco import atualizar_banco
from leitor import peso_do_item
from relatorio import carregar_notas, exportar, filtrar, resumo

PASTA_EXEMPLOS = Path(__file__).parent.parent / "exemplos_xml"
CAMINHO_GABARITO = Path(__file__).parent / "gabarito.json"


@pytest.fixture(scope="module")
def notas(tmp_path_factory):
    caminho_banco = tmp_path_factory.mktemp("banco") / "notas.db"
    atualizar_banco(PASTA_EXEMPLOS, caminho_banco)
    return carregar_notas(caminho_banco)


@pytest.fixture(scope="module")
def gabarito():
    with open(CAMINHO_GABARITO, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def criar_item(xml):
    return ET.fromstring(f"<prod>{xml}</prod>")


# --- Peso de cada item -------------------------------------------------------


def test_item_vendido_em_kg():
    assert peso_do_item(criar_item("<uCom>KG</uCom><qCom>12.5</qCom>")) == 12.5


def test_item_vendido_em_caixa_usa_o_peso_tributavel():
    item = criar_item("<uCom>CAX</uCom><qCom>10</qCom><uTrib>KG</uTrib><qTrib>98.7</qTrib>")
    assert peso_do_item(item) == 98.7


def test_peso_bruto_e_liquido_nao_sao_somados():
    item = criar_item("<uCom>UN</uCom><qCom>4</qCom><pesoL>9.8</pesoL><pesoB>10</pesoB>")
    assert peso_do_item(item) == 10


def test_item_sem_peso():
    assert peso_do_item(criar_item("<uCom>UN</uCom><qCom>4</qCom>")) is None


# --- Comparacao com o gabarito -----------------------------------------------


def test_status_de_cada_nota(notas, gabarito):
    calculado = dict(zip(notas["chave"], notas["status"], strict=True))
    esperado = {chave: nota["status"] for chave, nota in gabarito.items()}
    assert calculado == esperado


def test_peso_de_cada_nota(notas, gabarito):
    for chave, peso in zip(notas["chave"], notas["peso_kg"], strict=True):
        assert peso == pytest.approx(gabarito[chave]["peso_kg"], abs=0.01)


def test_nota_repetida_conta_uma_vez(notas):
    assert notas["chave"].is_unique


# --- Relatorio ---------------------------------------------------------------


def test_total_e_a_soma_das_filiais(notas):
    tabela = resumo(notas)
    filiais = tabela.drop(index="Total")
    assert tabela.loc["Total", "Pedidos"] == filiais["Pedidos"].sum()
    assert tabela.loc["Total", "Faturamento (R$)"] == pytest.approx(filiais["Faturamento (R$)"].sum())


def test_faturamento_diurno_mais_noturno_e_o_total(notas):
    total = resumo(notas).loc["Total"]
    soma_turnos = total["Faturamento diurno (R$)"] + total["Faturamento noturno (R$)"]
    assert soma_turnos == pytest.approx(total["Faturamento (R$)"])


def test_filtro_atravessando_a_meia_noite(notas):
    inicio = pd.Timestamp("2026-03-02 22:00")
    fim = pd.Timestamp("2026-03-03 07:00")
    periodo = filtrar(notas, inicio, fim)
    assert periodo["emissao"].min() >= inicio
    assert periodo["emissao"].max() <= fim
    assert periodo["emissao"].dt.day.nunique() == 2


# --- Arquivos com problema e exportacao --------------------------------------


def test_arquivo_quebrado_e_ignorado(tmp_path):
    pasta = tmp_path / "xml"
    pasta.mkdir()
    (pasta / "vazio.xml").write_text("")
    (pasta / "quebrado.xml").write_text("<NFe><sem fechamento>")
    atualizar_banco(pasta, tmp_path / "notas.db")
    assert carregar_notas(tmp_path / "notas.db").empty


def test_excel_exportado_nao_vira_formula(notas, tmp_path):
    # Um nome de cliente comecando com "=" seria executado como formula no Excel.
    uma_nota = notas.head(1).copy()
    uma_nota["nome_destinatario"] = "=1+1"
    destino = tmp_path / "saida.xlsx"
    exportar(uma_nota, destino)
    celula = load_workbook(destino).active["F2"]
    assert celula.value == "'=1+1"

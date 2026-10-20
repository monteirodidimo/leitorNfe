"""Calculos do relatorio de faturamento, feitos com pandas.

Aqui ficam as regras de negocio que dependem de mais de um arquivo:
- nota repetida (mesma chave) conta uma vez so;
- nota com protocolo diferente de 100/150 foi denegada e nao conta;
- nota cancelada ou com numero inutilizado nao conta;
- turno diurno vai das 07:00 as 19:59 e o noturno das 20:00 as 06:59.
"""

import pandas as pd

from banco import carregar_tabelas


def calcular_status(notas, cancelamentos, inutilizacoes):
    """Coloca na tabela de notas a coluna 'status': valida, denegada, cancelada ou inutilizada."""
    notas = notas.copy()
    notas["status"] = "valida"

    # Sem protocolo (cstat vazio) a nota e considerada autorizada.
    # 100 = autorizada, 150 = autorizada fora do prazo.
    autorizada = notas["cstat"].isna() | notas["cstat"].isin([100, 150])
    notas.loc[~autorizada, "status"] = "denegada"

    # O cancelamento vale se nao tem retorno da SEFAZ (o arquivo so existe se
    # o cancelamento foi feito) ou se o retorno e 135/155. Outro codigo
    # (ex.: 128) quer dizer que o cancelamento nao foi aceito.
    vale = cancelamentos["cstat"].isna() | cancelamentos["cstat"].isin([135, 155])
    chaves_canceladas = cancelamentos.loc[vale, "chave"]
    notas.loc[autorizada & notas["chave"].isin(chaves_canceladas), "status"] = "cancelada"

    # Inutilizacao: uma faixa de numeros de um CNPJ/serie/ano.
    # Vale sem retorno ou com retorno 102.
    ano_da_nota = notas["chave"].str[2:4].astype(int)  # posicoes 3 e 4 da chave
    for _, faixa in inutilizacoes.iterrows():
        if pd.notna(faixa["cstat"]) and faixa["cstat"] != 102:
            continue
        na_faixa = (
            (notas["cnpj_emitente"] == faixa["cnpj"])
            & (notas["serie"] == faixa["serie"])
            & (ano_da_nota == faixa["ano"])
            & notas["numero"].between(faixa["inicio"], faixa["fim"])
        )
        notas.loc[autorizada & na_faixa, "status"] = "inutilizada"

    return notas


def carregar_notas(caminho_banco):
    """Le o banco e devolve uma tabela com uma linha por nota, ja com status e turno."""
    notas, cancelamentos, inutilizacoes = carregar_tabelas(caminho_banco)
    notas = notas.drop_duplicates(subset="chave")
    notas = calcular_status(notas, cancelamentos, inutilizacoes)

    notas["emissao"] = pd.to_datetime(notas["emissao"])
    notas["hora"] = notas["emissao"].dt.hour
    notas["turno"] = "noturno"
    notas.loc[notas["hora"].between(7, 19), "turno"] = "diurno"
    return notas.sort_values("emissao").reset_index(drop=True)


def filtrar(notas, inicio, fim, filial="Todas", turno="Todos"):
    """Filtra por periodo (data e hora), filial e turno.

    O periodo e continuo, entao pode atravessar a meia-noite:
    ex.: de 02/03 22:00 ate 03/03 07:00.
    """
    filtro = (notas["emissao"] >= inicio) & (notas["emissao"] <= fim)
    if filial != "Todas":
        filtro &= notas["filial"] == filial
    if turno != "Todos":
        filtro &= notas["turno"] == turno
    return notas[filtro]


def _totais(notas):
    validas = notas[notas["status"] == "valida"]
    return {
        "Faturamento (R$)": validas["valor"].sum(),
        "Peso (kg)": validas["peso_kg"].sum(),
        "Pedidos": len(validas),
        "Faturamento diurno (R$)": validas.loc[validas["turno"] == "diurno", "valor"].sum(),
        "Faturamento noturno (R$)": validas.loc[validas["turno"] == "noturno", "valor"].sum(),
    }


def resumo(notas):
    """Tabela com a linha 'Total' e uma linha por filial.

    Pedidos = quantidade de notas validas.
    """
    linhas = {"Total": _totais(notas)}
    for filial, notas_da_filial in notas.groupby("filial"):
        linhas[filial] = _totais(notas_da_filial)
    return pd.DataFrame(linhas).T


def notas_por_hora(notas):
    """Quantidade de notas validas emitidas em cada hora do dia (0 a 23), por filial."""
    validas = notas[notas["status"] == "valida"]
    tabela = validas.pivot_table(index="hora", columns="filial", values="chave", aggfunc="count")
    return tabela.reindex(range(24)).fillna(0).astype(int)


def proteger_texto(valor):
    """Evita que um texto vindo do XML vire formula no Excel.

    Um nome de cliente como '=HYPERLINK(...)' seria executado ao abrir a
    planilha. Colocando um apostrofo na frente, o Excel mostra como texto.
    """
    if isinstance(valor, str) and valor.startswith(("=", "+", "-", "@")):
        return "'" + valor
    return valor


def exportar(notas, caminho):
    """Salva as notas em .csv ou .xlsx, conforme a extensao do arquivo."""
    colunas = {
        "emissao": "Emissao",
        "turno": "Turno",
        "filial": "Filial",
        "numero": "Numero",
        "serie": "Serie",
        "nome_destinatario": "Destinatario",
        "valor": "Valor (R$)",
        "peso_kg": "Peso (kg)",
        "pedido": "Pedido",
        "status": "Status",
        "chave": "Chave de acesso",
    }
    tabela = notas[list(colunas)].rename(columns=colunas)
    for coluna in ["Filial", "Destinatario", "Pedido"]:
        tabela[coluna] = tabela[coluna].map(proteger_texto)

    if str(caminho).lower().endswith(".xlsx"):
        tabela.to_excel(caminho, index=False)
    else:
        # ; e virgula decimal para o Excel em portugues abrir direto
        tabela.to_csv(caminho, index=False, sep=";", decimal=",", encoding="utf-8-sig")

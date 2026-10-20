"""Banco de dados SQLite com o conteudo dos XMLs.

Ler milhares de XMLs toda vez seria lento. Por isso cada arquivo lido fica
registrado na tabela 'arquivos', com a data de modificacao. Na proxima
atualizacao, so arquivos novos ou alterados sao lidos de novo.
"""

import os
import sqlite3

import pandas as pd

from leitor import ler_arquivo, listar_xmls

CRIAR_TABELAS = """
CREATE TABLE IF NOT EXISTS arquivos (
    caminho    TEXT PRIMARY KEY,
    modificado REAL
);

CREATE TABLE IF NOT EXISTS notas (
    chave             TEXT,
    numero            INTEGER,
    serie             INTEGER,
    emissao           TEXT,
    cnpj_emitente     TEXT,
    filial            TEXT,
    nome_destinatario TEXT,
    valor             REAL,
    peso_kg           REAL,
    pedido            TEXT,
    cstat             INTEGER,
    arquivo           TEXT
);

CREATE TABLE IF NOT EXISTS cancelamentos (
    chave   TEXT,
    cstat   INTEGER,
    arquivo TEXT
);

CREATE TABLE IF NOT EXISTS inutilizacoes (
    cnpj    TEXT,
    serie   INTEGER,
    ano     INTEGER,
    inicio  INTEGER,
    fim     INTEGER,
    cstat   INTEGER,
    arquivo TEXT
);
"""


def conectar(caminho_banco):
    conexao = sqlite3.connect(caminho_banco)
    conexao.executescript(CRIAR_TABELAS)
    return conexao


def salvar_documento(conexao, dados, caminho):
    """Grava o dicionario vindo do leitor na tabela certa.

    Os nomes com dois-pontos (:chave, :numero...) sao preenchidos com as
    chaves do dicionario. Isso tambem protege contra SQL injection.
    """
    dados = {**dados, "arquivo": caminho}
    if dados["tipo"] == "nota":
        # Se a mesma nota estiver em dois arquivos (copia em outra pasta), as
        # duas entram aqui; a repeticao e removida na hora de montar o relatorio.
        conexao.execute(
            "INSERT INTO notas VALUES (:chave, :numero, :serie, :emissao, :cnpj_emitente, :filial,"
            " :nome_destinatario, :valor, :peso_kg, :pedido, :cstat, :arquivo)",
            dados,
        )
    elif dados["tipo"] == "cancelamento":
        conexao.execute("INSERT INTO cancelamentos VALUES (:chave, :cstat, :arquivo)", dados)
    elif dados["tipo"] == "inutilizacao":
        conexao.execute(
            "INSERT INTO inutilizacoes VALUES (:cnpj, :serie, :ano, :inicio, :fim, :cstat, :arquivo)",
            dados,
        )


def apagar_documento(conexao, caminho):
    """Remove do banco tudo que veio de um arquivo (usado quando ele muda ou some)."""
    conexao.execute("DELETE FROM notas WHERE arquivo = ?", (caminho,))
    conexao.execute("DELETE FROM cancelamentos WHERE arquivo = ?", (caminho,))
    conexao.execute("DELETE FROM inutilizacoes WHERE arquivo = ?", (caminho,))
    conexao.execute("DELETE FROM arquivos WHERE caminho = ?", (caminho,))


def atualizar_banco(pasta, caminho_banco, ao_progredir=None):
    """Le os XMLs novos ou alterados da pasta e grava no banco.

    ao_progredir: funcao opcional chamada com (lidos, total), para a tela
    mostrar o andamento.
    Devolve quantos arquivos foram lidos.
    """
    no_disco = {}
    for caminho in listar_xmls(pasta):
        try:
            no_disco[caminho] = os.path.getmtime(caminho)
        except OSError:
            pass  # o arquivo foi apagado ou movido enquanto a pasta era lida

    conexao = conectar(caminho_banco)
    try:
        ja_lidos = dict(conexao.execute("SELECT caminho, modificado FROM arquivos"))
        para_ler = [c for c in no_disco if ja_lidos.get(c) != no_disco[c]]
        sumiram = [c for c in ja_lidos if c not in no_disco]

        for caminho in sumiram:
            apagar_documento(conexao, caminho)

        for posicao, caminho in enumerate(para_ler, start=1):
            apagar_documento(conexao, caminho)
            dados = ler_arquivo(caminho)
            if dados is not None:
                salvar_documento(conexao, dados, caminho)
            conexao.execute("INSERT INTO arquivos VALUES (?, ?)", (caminho, no_disco[caminho]))
            if ao_progredir:
                ao_progredir(posicao, len(para_ler))

        # Tudo e gravado de uma vez no final. Se der erro no meio, nada e salvo
        # pela metade e a proxima atualizacao le os mesmos arquivos de novo.
        conexao.commit()
    finally:
        conexao.close()
    return len(para_ler)


def carregar_tabelas(caminho_banco):
    """Devolve as tabelas notas, cancelamentos e inutilizacoes como DataFrames."""
    conexao = conectar(caminho_banco)
    try:
        notas = pd.read_sql("SELECT * FROM notas", conexao)
        cancelamentos = pd.read_sql("SELECT * FROM cancelamentos", conexao)
        inutilizacoes = pd.read_sql("SELECT * FROM inutilizacoes", conexao)
    finally:
        conexao.close()
    return notas, cancelamentos, inutilizacoes

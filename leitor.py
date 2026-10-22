"""Leitura dos arquivos XML de NF-e.

Cada arquivo e lido sozinho e vira um dicionario. Existem tres tipos que
interessam: a nota, o cancelamento e a inutilizacao. Outros eventos (carta de
correcao, manifestacao) sao ignorados. Os XMLs nunca sao alterados.
"""

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

# Unidades de medida que sao peso, e quanto valem em kg.
UNIDADES_DE_PESO = {"KG": 1, "KGS": 1, "G": 0.001, "GR": 0.001, "TON": 1000}

# Final do CFOP (os 3 ultimos digitos) que indica venda ou transferencia.
# O primeiro digito so diz o destino: 5 = mesmo estado, 6 = outro estado, 7 = exterior.
FINAIS_DE_VENDA = [str(n) for n in range(101, 124)] + ["401", "402", "403", "405"]
FINAIS_DE_TRANSFERENCIA = ["151", "152", "155", "156", "552", "557"]


def listar_xmls(pasta):
    """Devolve o caminho de todos os .xml da pasta e das subpastas."""
    caminhos = []
    for raiz, _, arquivos in os.walk(pasta):
        for nome in arquivos:
            if nome.lower().endswith(".xml"):
                caminhos.append(os.path.join(raiz, nome))
    return caminhos


def abrir_xml(caminho):
    """Abre o XML e tira o namespace das tags (ex.: '{http://...}nNF' vira 'nNF').

    Assim as buscas ficam simples, como raiz.find('.//nNF').
    Devolve None se o arquivo estiver corrompido ou nao puder ser aberto.
    """
    try:
        raiz = ET.parse(caminho).getroot()
    except (ET.ParseError, OSError):
        return None

    for elemento in raiz.iter():
        if "}" in elemento.tag:
            elemento.tag = elemento.tag.split("}")[1]
    return raiz


def texto(elemento, caminho):
    """Texto de uma tag, ou None se ela nao existir."""
    encontrado = elemento.find(caminho)
    if encontrado is None or encontrado.text is None:
        return None
    return encontrado.text.strip()


def numero(valor):
    """Converte texto em numero. Devolve None se nao for possivel."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def peso_do_item(prod):
    """Peso de um item da nota, em kg. Devolve None se o item nao tem peso.

    A ordem de busca e:
    1. unidade de venda (uCom) e de peso, ex.: KG -> usa a quantidade (qCom);
    2. unidade tributavel (uTrib) e de peso -> usa qTrib.
       E o caso da caixa: vende 10 caixas (uCom=CAX), mas o imposto e por kg;
    3. pesoB ou pesoL gravados no item. Sao o mesmo peso (bruto e liquido),
       entao usa so um deles, nunca a soma.
    """
    for campo_unidade, campo_quantidade in [("uCom", "qCom"), ("uTrib", "qTrib")]:
        unidade = (texto(prod, campo_unidade) or "").upper()
        quantidade = numero(texto(prod, campo_quantidade))
        if unidade in UNIDADES_DE_PESO and quantidade is not None:
            return quantidade * UNIDADES_DE_PESO[unidade]

    for campo in ["pesoB", "pesoL"]:
        peso = numero(texto(prod, campo))
        if peso is not None:
            return peso

    return None


def classificar_operacao(tipo_nf, cfops):
    """Diz o que a nota representa: venda, transferencia, outras ou entrada.

    So "venda" e faturamento de verdade. As outras tambem geram NF-e, mas nao
    sao venda: transferencia entre filiais, remessa para deposito, bonificacao,
    e as notas de entrada (devolucao de cliente, compra).
    tipo_nf: tag tpNF (0 = entrada, 1 = saida). cfops: lista com o CFOP de cada item.
    """
    if tipo_nf == "0" or any(cfop[0] in "123" for cfop in cfops):
        return "entrada"
    if any(cfop[1:] in FINAIS_DE_VENDA for cfop in cfops):
        return "venda"
    if any(cfop[1:] in FINAIS_DE_TRANSFERENCIA for cfop in cfops):
        return "transferencia"
    if not cfops:
        return "venda"  # nota sem CFOP: conta como venda, como antes
    return "outras"


def ler_nota(raiz):
    info = raiz.find(".//infNFe")

    # Peso da nota = soma dos itens. Se nenhum item tem peso,
    # usa o peso do volume de transporte.
    pesos = []
    for prod in info.findall(".//det/prod"):
        peso = peso_do_item(prod)
        if peso is not None:
            pesos.append(peso)

    if pesos:
        peso_total = sum(pesos)
    else:
        peso_total = 0
        for volume in info.findall(".//transp/vol"):
            peso_total += numero(texto(volume, "pesoB")) or numero(texto(volume, "pesoL")) or 0

    # O numero do pedido vem no texto livre, ex.: "Pedido: 1234567" ou "Pedido 1234567"
    observacao = texto(info, "infAdic/infCpl") or ""
    pedido = re.search(r"Pedido\W*(\d+)", observacao, re.IGNORECASE)

    # A chave de acesso tem sempre 44 digitos. Sem ela nao da para saber se a
    # nota foi cancelada, entao o arquivo e ignorado.
    chave = info.get("Id", "").replace("NFe", "")
    if len(chave) != 44 or not chave.isdigit():
        return None

    # Ex.: "2026-03-02T22:15:00-03:00". Usa so data e hora (horario local da nota).
    # Se a data estiver faltando ou errada, fromisoformat da erro e o arquivo e ignorado.
    emissao = texto(info, "ide/dhEmi") or texto(info, "ide/dEmi") or ""
    emissao = datetime.fromisoformat(emissao[:19])

    cstat = texto(raiz, ".//infProt/cStat")
    cfops = [texto(prod, "CFOP") for prod in info.findall(".//det/prod") if texto(prod, "CFOP")]

    return {
        "tipo": "nota",
        "chave": chave,
        "numero": int(texto(info, "ide/nNF")),
        "serie": int(texto(info, "ide/serie")),
        "emissao": emissao.strftime("%Y-%m-%d %H:%M:%S"),
        "cnpj_emitente": texto(info, "emit/CNPJ"),
        "filial": texto(info, "emit/xNome") or texto(info, "emit/CNPJ"),
        "nome_destinatario": texto(info, "dest/xNome"),
        "valor": numero(texto(info, "total/ICMSTot/vNF")) or 0,
        "peso_kg": round(peso_total, 3),
        "pedido": pedido.group(1) if pedido else None,
        "cstat": int(cstat) if cstat else None,
        "operacao": classificar_operacao(texto(info, "ide/tpNF"), cfops),
    }


def ler_cancelamento(raiz):
    info = raiz.find(".//infEvento")
    if texto(info, "tpEvento") != "110111":  # 110111 = cancelamento
        return None

    # O cStat pode estar no retorno da SEFAZ, dentro do proprio evento ou nao existir.
    cstat = texto(raiz, ".//retEvento//cStat") or texto(info, "cStat")
    return {
        "tipo": "cancelamento",
        "chave": texto(info, "chNFe"),
        "cstat": int(cstat) if cstat else None,
    }


def ler_inutilizacao(raiz):
    info = raiz.find(".//infInut")
    cstat = texto(raiz, ".//retInutNFe//cStat")
    return {
        "tipo": "inutilizacao",
        "cnpj": texto(info, "CNPJ"),
        "serie": int(texto(info, "serie")),
        "ano": int(texto(info, "ano")),
        "inicio": int(texto(info, "nNFIni")),
        "fim": int(texto(info, "nNFFin")),
        "cstat": int(cstat) if cstat else None,
    }


def ler_arquivo(caminho):
    """Le um XML e devolve um dicionario com os dados, ou None se nao interessar."""
    raiz = abrir_xml(caminho)
    if raiz is None:
        return None

    try:
        if raiz.find(".//infNFe") is not None:
            return ler_nota(raiz)
        if raiz.find(".//infInut") is not None:
            return ler_inutilizacao(raiz)
        if raiz.find(".//infEvento") is not None:
            return ler_cancelamento(raiz)
    except (TypeError, ValueError, AttributeError):
        # XML incompleto (falta alguma tag obrigatoria): o arquivo e ignorado
        return None
    return None

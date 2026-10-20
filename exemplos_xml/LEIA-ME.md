# XMLs de exemplo (fictícios)

Notas fiscais **inventadas** de uma distribuidora de alimentos que também não existe, para
testar e demonstrar o programa. CNPJs, clientes, produtos e valores são fictícios.

## Organização

```
exemplos_xml/
├── Matriz_MG/
│   ├── 2026-03-02/        um dia de emissão por pasta
│   │   ├── NFe<chave>.xml     nota fiscal
│   │   ├── Can<chave>.xml     cancelamento da nota com essa chave
│   │   └── Inu<chave>.xml     inutilização do número dessa nota
│   └── ...
├── Filial_PR/             mesma organização da matriz
├── Filial_SC/             mesma organização da matriz
└── copias_duplicadas/     cópias de notas que já estão em outra pasta
                           (o programa deve contar cada nota uma vez só)
```

Notas emitidas depois da meia-noite pelo turno noturno ficam na pasta do dia seguinte.

## Casos incluídos

- itens vendidos em kg, em caixa (peso no campo tributável) e em pacote (com e sem peso no item);
- notas sem protocolo, autorizadas (100/150) e denegadas (110);
- cancelamentos nos três formatos (com retorno, sem retorno e retorno dentro do evento),
  incluindo cancelamento recusado (128), que **não** cancela a nota;
- inutilizações aceitas (102 ou sem retorno) e recusadas (241);
- cliente no exterior (sem CNPJ) e transferência entre a matriz e a filial.

O resultado esperado de cada nota está em `tests/gabarito.json`.

Para usar: abra o programa, escolha esta pasta e clique em **Atualizar dados**.

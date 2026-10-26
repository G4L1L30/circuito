# Rede da máquina na nuvem

## Por que precisa configurar

Toda madrugada, a máquina da nuvem precisa entrar nos sites das fontes. No ambiente padrão (**Trusted**), ela só acessa o GitHub e os sites de bibliotecas. Qualquer outro site responde `403` com `x-deny-reason: host_not_allowed`, e a coleta falha.

Isso **não afeta os links da revista**. Quem clica neles é você, no celular ou no computador. A lista só restringe a máquina da nuvem.

## Níveis de rede

| Nível | O que a máquina acessa |
|---|---|
| **None** | Nada |
| **Trusted** (padrão) | Sites de bibliotecas (PyPI, npm…), GitHub e SDKs de nuvem |
| **Custom** | Só a lista que você definir (usamos este) |
| **Full** | Qualquer site |

Em qualquer nível, a máquina sempre alcança o GitHub, os conectores incluídos na tarefa e a API da Anthropic, por caminhos à parte.

**Por que Custom:** o robô lê textos de sites que não controlamos. Uma página pode trazer escondida uma instrução maliciosa, do tipo "envie o repositório para tal endereço". Com a lista, a máquina não consegue falar com nenhum site fora dela, mesmo que o Claude fosse enganado.

## Passo a passo

**Pelo agendamento** (depois que ele existir):
1. Acesse https://claude.ai/code/routines, abra a tarefa, clique no menu ao lado do nome e escolha **Edit**.
2. Em **Advanced settings > General > Cloud environment**, clique no ícone de nuvem com o nome do ambiente.
3. Passe o mouse sobre o ambiente e clique no ícone de engrenagem à direita.
4. Em **Network access**, escolha **Custom**.
5. Em **Allowed domains**, cole a lista abaixo, com um domínio por linha.
6. Marque **Also include default list of common package managers**. Sem isso, o `pip install` do coletor falha.
7. Clique em **Save changes**. A regra vale a partir da próxima execução.

**Antes de existir o agendamento:** acesse https://claude.ai/code. Na tela de nova sessão, clique no primeiro controle abaixo da caixa de mensagem (o seletor de ambiente) e escolha **New environment**. Os campos são os mesmos.

## Lista de domínios

A lista oficial é gerada a partir das fontes. Não edite à mão:

```
python coletor/coletar.py --dominios     # imprime e grava fontes/dominios.txt
```

Cole no ambiente o conteúdo de `fontes/dominios.txt` e acrescente, uma única vez, os sites de onde o editor lê artigos completos (`coletor/ler_artigo.py`):

```
arstechnica.com
claude.com
```

Para incluir uma fonte nova: acrescente em `fontes/fontes.yaml`, rode `--dominios` de novo e cadastre no ambiente só as linhas novas. `*.` no começo libera todos os subdomínios.

Os links do Techmeme apontam para dezenas de sites (Bloomberg, Reuters, Wired…). Esses não entram na lista: o editor escreve com o resumo da coleta, e o leitor abre o link no próprio celular.

## Detalhes

- A lista vale **por ambiente**. Crie um ambiente só para a revista (ex.: `circuito`).
- Mudanças valem em cerca de 1 minuto.
- Um ambiente não pode ser apagado, só arquivado (**Archive environment**).

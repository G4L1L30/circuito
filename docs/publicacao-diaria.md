# Publicação diária

## Que notícias entram em cada edição

A edição do dia D, pronta às 7h, cobre as notícias **desde o fechamento da edição anterior** (por volta das 6h de D-1) até o fechamento de hoje (6h de D, horário de Brasília). Na prática, são as notícias de ontem, com estas vantagens sobre o corte "dia de calendário":

- **Nada fica de fora.** Os anúncios dos EUA costumam sair à tarde e à noite no horário de Brasília. Um corte à meia-noite pegaria esses anúncios pela metade.
- **Nada se repete.** Cada notícia entra em uma única edição.
- **Falhas não abrem buraco.** Se um dia a execução falhar, a edição seguinte cobre 48 h automaticamente.

As **cotações de cripto** são as do momento do fechamento, de madrugada, e não as de ontem. A capa traz a data da edição (D), e o expediente informa a janela coberta.

### Calendário (decidido em 21/10/2026)

| Edição | Sai? | Cobre |
|---|---|---|
| Terça a sexta | Sim | Desde o fechamento anterior (~24 h) |
| Sábado | Sim | Sexta-feira (~24 h) |
| Domingo | **Não** | — |
| Segunda | Sim, **a maior da semana** | Sábado e domingo (~48 h) + seção "Se você perdeu" com os destaques da edição de sábado |

O agendamento roda de **segunda a sábado**. O preset "dias úteis" vai só de segunda a sexta, então é preciso usar a expressão `10 6 * * 1-6` com `/schedule update`. Conferir o fuso horário depois de salvar: a documentação só garante a conversão automática para horários digitados na tela.

## Estrutura do repositório

```
circuito/
  CLAUDE.md                  instruções do editor: rotina, regras editoriais, formato e limites
  docs/                      esta documentação
  fontes/fontes.yaml         fontes: tipo (rss, youtube, api…), endereço, seção
  fontes/dominios.txt        domínios para liberar na nuvem (gerado por coletar.py --dominios)
  coletor/comum.py           peças comuns: caminhos, fuso, escrita atômica de JSON
  coletor/coletar.py         lê as fontes da janela e grava coleta/AAAA-MM-DD.json
  coletor/ler_artigo.py      lê o texto completo de um artigo (para a matéria de capa)
  coletor/montar.py          confere o texto, pagina, gera o HTML e fecha a edição
  modelo/                    molde da revista: revista.css, revista.html.j2, ilustrações
  edicoes/AAAA-MM-DD.json    textos da edição escritos pelo Claude
  estado/                    fechamento anterior, notícias já vistas, lista de edições
  site/                      o que vai para o ar: index.html, edicoes/, arquivo.html
  resumos_execucao/          resumo de cada execução (padrão de saída de RPA)
  logs_detalhados/fontes/    um log por fonte consultada, ligado ao resumo pelo execucao_id
  coleta/  previa/           gerados a cada execução, fora do git
  requirements.txt
  .github/workflows/pages.yml   publica a pasta site/ no GitHub Pages (Fase 2)
```

**Fontes sem data** (YouTube, página de notícias da Anthropic): o "novo" é o que não está em `estado/vistos.json`. Na primeira execução tudo parece novo, então os vídeos podem ser de dias antes.

**Por que separar conteúdo do layout:** o Claude escreve só os textos, num JSON. Quem monta o HTML é o `montar.py`, a partir do molde aprovado. Assim o visual fica idêntico todo dia e não depende do humor do modelo. As ilustrações vêm de uma biblioteca fixa (placa de vídeo, chip, robô, cofre, monitor…), e o Claude só escolhe qual usar em cada matéria.

Identidade do robô: `robo_id` = `circuito_diario`, usado no log, no resumo de execução e nos commits.

## O que o robô faz em cada execução (às 6h10)

1. A máquina da nuvem clona o repositório (automático).
2. `pip install -r requirements.txt`
3. `python coletor/coletar.py`: lê as fontes desde o último fechamento e grava a coleta.
4. O Claude lê a coleta, escolhe cerca de 15 notícias e escreve `edicoes/AAAA-MM-DD.json`, seguindo o `CLAUDE.md`.
5. `python coletor/montar.py`: gera `site/index.html` e atualiza o arquivo de edições.
6. Grava o resumo em `resumos_execucao/`: fontes lidas, fontes que falharam, itens publicados.
7. Commit e push na `main`. O GitHub Actions publica o site em cerca de 1 minuto.

O horário é 6h10, e não 6h, porque execuções marcadas na hora cheia podem atrasar alguns minutos. O horário é digitado no fuso local e convertido automaticamente.

## Passo a passo da implantação

### Fase 1 — local, no notebook
1. **Eu:** monto a estrutura acima, o coletor, o molde a partir da edição 001 e o `CLAUDE.md`.
2. **Eu:** rodo uma edição completa no notebook e confiro a página gerada.
3. **Você:** lê e aprova a edição de teste.

### Fase 2 — GitHub
4. **Você:** cria o repositório **público** `circuito` no GitHub.
5. **Eu:** faço o primeiro push. Pode ser preciso você autenticar o `git` ou o `gh` no notebook.
6. **Você:** em **Settings > Pages > Source**, escolhe **GitHub Actions**. O endereço fica `https://<seu-usuario>.github.io/circuito/`.
7. **Você:** instala o app do Claude no GitHub (https://github.com/apps/claude) com **Only select repositories**, marcando só o `circuito`.

### Fase 3 — nuvem
8. **Você:** cria o ambiente `circuito` com rede **Custom** (ver [rede-nuvem.md](rede-nuvem.md)).
9. **Você ou eu:** criamos a tarefa em https://claude.ai/code/routines (ou com `/schedule` no terminal):
   - **Nome:** Circuito diário
   - **Prompt:** "Siga as instruções de `docs/publicacao-diaria.md`, seção 'O que o robô faz em cada execução', e publique a edição de hoje com push direto na `main`."
     - O prompt precisa dizer `main`. Sem isso, o robô grava num ramo `claude/...`, e o site não atualiza.
   - **Gatilho:** segunda a sábado, 06:10 (`10 6 * * 1-6`; ver "Calendário")
   - **Repositório:** `circuito`
   - **Ambiente:** `circuito`
   - **Conectores:** desmarcar todos
   - **Modelo:** escolher no seletor do prompt
10. Clique em **Run now** para testar na hora e abra a execução para ler o que aconteceu, porque o status verde não garante que a edição saiu certa.
11. Confira a página no GitHub Pages.

### Fase 4 — rodando
12. Acompanhamos a primeira semana pelos resumos de execução e ajustamos fontes, textos e janela.
13. Para incluir uma fonte nova: `fontes/fontes.yaml` + `fontes/dominios.txt` + lista do ambiente na nuvem.

## Plano B

Se os agendamentos mudarem ou falharem: o **GitHub Actions** roda o mesmo coletor no horário marcado e chama a **API do Claude** para escrever os textos. É mais independente, mas a API é cobrada à parte, por uso, fora do plano Max. O repositório já fica pronto para isso, porque coletor e montagem são scripts Python comuns.

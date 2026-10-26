# Circuito

Revista diária de tecnologia em formatinho retrô (13,5 × 20,5 cm), com cara de revista de informática dos anos 80: IA, placas de vídeo e memória, Big Techs, um básico de cripto e a comunidade brasileira de tecnologia. São 5 minutos de leitura, e cada nota traz o link para a matéria original.

Sai de segunda a sábado, às 7h (horário de Brasília). A edição de segunda é a maior, porque cobre o fim de semana.

## Como funciona

1. **Coleta** (`coletor/coletar.py`): lê as fontes de `fontes/fontes.yaml` (RSS, APIs públicas e YouTube) e guarda só o que saiu desde a edição anterior.
2. **Redação**: o [Claude](https://claude.com) lê a coleta, escolhe as notícias e escreve os textos seguindo as regras de [`CLAUDE.md`](CLAUDE.md).
3. **Montagem** (`coletor/montar.py`): confere limites de texto, paginação e links, e encaixa tudo no molde de `modelo/`. Só aceita link que veio da coleta.
4. **Publicação**: o resultado vai para `site/`, e o GitHub Actions publica no GitHub Pages.

Tudo roda num agendamento na nuvem do Claude Code, sem precisar de computador ligado. Detalhes em [`docs/`](docs/README.md).

## Rodar localmente

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt     # Windows
.venv\Scripts\python.exe coletor\coletar.py
# escreva edicoes/AAAA-MM-DD.json (formato em CLAUDE.md; exemplo em exemplo/edicao_2026-10-22.json)
.venv\Scripts\python.exe coletor\montar.py --teste              # gera previa/AAAA-MM-DD.html
```

## Conteúdo e fontes

Os textos são resumos curtos, sempre com link para a matéria original. Marcas, nomes e matérias citadas pertencem aos seus donos. As cotações vêm da CoinGecko e o índice de Medo & Ganância, da alternative.me. Nada aqui é recomendação de investimento.

As ilustrações e o molde foram feitos para o projeto.

## Licença

Código sob a [licença MIT](LICENSE).

# Como o robô roda na nuvem

## As três peças

| Peça | Sessão local (hoje) | Agendamento na nuvem |
|---|---|---|
| **Cérebro**: o modelo Claude, que lê, pensa e decide | Servidores da Anthropic | Servidores da Anthropic |
| **Mãos**: onde os comandos rodam (`python`, `curl`, `git`) | O notebook | Máquina temporária da Anthropic |
| **Arquivo**: onde o resultado fica | Pasta `Documents\Pessoal\newsletter` | Repositório no GitHub |
| Precisa do notebook ligado? | Sim | Não |

## A máquina da nuvem

- Para cada execução nasce um computador virtual isolado, gerenciado pela Anthropic.
- Ele já vem com Python 3, pip e git.
- Ele clona o repositório, roda o trabalho e, no fim, **é apagado**. No dia seguinte nasce outro, do zero.
- **O que não for gravado no GitHub se perde.** Por isso o robô sempre termina salvando a edição no repositório.
- A documentação não informa o provedor nem a configuração da máquina (memória, CPU).

## O que fica exposto para o Claude

- **GitHub:** só os repositórios marcados ao instalar o app do Claude. Instale com "Only select repositories" e marque só o da revista. Nesse repositório ele lê e grava; os outros ele não enxerga.
- **Na execução:** a cópia do repositório, as variáveis do ambiente e os conectores incluídos na tarefa.
  - **Atenção:** ao criar a tarefa, **todos os conectores da conta vêm marcados por padrão**, e o Claude pode usar qualquer um deles sem pedir permissão. Desmarque todos; a revista não precisa de nenhum.
- **Internet:** só os sites liberados no ambiente (ver [rede-nuvem.md](rede-nuvem.md)). O GitHub sempre funciona, por um canal à parte.
- **Notebook:** nada. A nuvem não acessa o computador.
- **Conta do Claude:** a tarefa roda em seu nome e gasta o limite do plano. Os commits saem com o seu usuário do GitHub. O histórico de cada execução fica nas suas sessões.
- **Chaves de API** (se um dia houver, como a do X): cadastrar como **Network secret** no ambiente, que o Claude usa sem conseguir ler. Nunca como variável comum e nunca no código.

## Repositório público ou privado

Os dois funcionam com o Claude. A diferença está em como a revista é lida:

| | Público (recomendado) | Privado |
|---|---|---|
| GitHub Pages | Grátis | Só com GitHub pago, e o site continua aberto na internet |
| Quem vê o código e as edições | Qualquer pessoa | Só você |
| Alternativa para ler | Página fixa no Pages, com arquivo das edições | Página privada no Claude (artifact) |

Escolhemos **público** porque o repositório não guarda nada secreto: as fontes atuais (RSS, CoinGecko, TabNews) não usam senha nem chave.

## Custo e limites

- As execuções gastam o **limite do plano Max**, como uma conversa normal. A máquina da nuvem não é cobrada à parte. Consumo: https://claude.ai/settings/usage
- Se o limite acabar, a execução é recusada, a não ser que os créditos extras ("usage credits") estejam ligados.
- **Crédito de US$ 250:** a imprensa noticiou um crédito promocional para sessões na nuvem, com validade até 04/11/2026. Não está na documentação oficial e não sabemos se vale para agendamentos. Conferir na página de uso.
- Intervalo mínimo entre execuções agendadas: 1 hora. Limite: 100 execuções agendadas por hora na conta, folgado para uma edição por dia.
- Se a conexão com o GitHub cair, a tarefa pula as execuções por até 72 h. Depois disso, ela é desligada e precisa ser religada manualmente.

## Cuidado ao conferir as execuções

O **status verde** na lista de execuções só quer dizer que a sessão abriu e fechou sem erro de infraestrutura, **não que a edição saiu certa**. Sites bloqueados e falhas do coletor só aparecem dentro da execução. Por isso o robô grava um resumo de cada execução em `resumos_execucao/`, com as fontes que falharam.

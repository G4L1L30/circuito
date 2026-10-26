# Fontes da Circuito — esboço

Legenda de coleta: **RSS** (feed grátis) · **API** (endpoint público) · **HTML** (ler a página) · **pago** (paywall ou API paga)

## Agregadores (o melhor custo-benefício: uma fonte, dezenas de manchetes)
- Techmeme — techmeme.com (RSS/HTML) — testado na edição 001
- Hacker News — API oficial grátis (firebase)
- TabNews — tabnews.com.br/api/v1/contents (API) — testado na edição 001

## IA e Big Techs (fonte oficial)
- Anthropic — anthropic.com/news e /engineering (HTML)
- OpenAI — openai.com/news (RSS)
- Google / DeepMind — blog.google, deepmind.google/blog (RSS)
- Meta AI — ai.meta.com/blog (HTML)
- xAI — x.ai/news (HTML)
- Microsoft — blogs.microsoft.com (RSS)
- Apple Newsroom — apple.com/newsroom (RSS)
- Nvidia — blogs.nvidia.com, nvidianews.nvidia.com (RSS)
- Hugging Face — huggingface.co/blog (RSS)

## Imprensa de tecnologia
- The Verge, Ars Technica, TechCrunch, Wired, Engadget (RSS)
- Reuters Technology (HTML), Bloomberg Tech (pago), The Information (pago), Financial Times (pago)
- MIT Technology Review (RSS)

## Placas de vídeo e memória
- Tom's Hardware, TechPowerUp, VideoCardz, ServeTheHome, Chips and Cheese (RSS)
- TrendForce / DRAMeXchange — preço de DRAM/HBM (press center HTML; relatórios completos pagos)
- SemiAnalysis (parte paga)

## Newsletters e blogs de IA
- Import AI (Jack Clark) — importai.substack.com (RSS)
- Simon Willison — simonwillison.net (RSS)
- The Batch (DeepLearning.AI), TLDR / TLDR AI, Latent Space, Ben's Bites (RSS/e-mail)

## Brasil
- Filipe Deschamps — newsletter diária + TabNews
- Fabio Akita — akitaonrails.com (HTML/RSS) — testado na edição 001
- Tecnoblog, Olhar Digital, Canaltech, TecMundo, Meio Bit (RSS)

## Cripto (básico)
- CoinGecko — api.coingecko.com/api/v3/simple/price (API grátis) — testado
- Medo & Ganância — api.alternative.me/fng (API grátis) — testado
- CoinDesk, The Block, Decrypt (RSS)
- Livecoins, Portal do Bitcoin (BR, RSS)

## YouTube (RSS por canal: youtube.com/feeds/videos.xml?channel_id=...)
- BR: Fabio Akita, Filipe Deschamps, Lucas Montano, Augusto Galego, Código Fonte TV, Diolinux
- Fora: Fireship, Two Minute Papers, AI Explained, Linus Tech Tips, Gamers Nexus, Hardware Unboxed, PewDiePie
- Transcrição das legendas -> resumo pelo Claude
- channel_id confirmados: Attekita Dev (@attekitadev) = UCetRsdZxDQDcgVDJd6erz6g; Lucas Montano (@LucasMontano) = UCyHOBY6IDZF9zOKJPou2Rgg
- A CONFIRMAR: channel_id dos demais canais
- Vídeo do Lucas Montano "Cloudflare /crawl endpoint" (18/03/2026, https://www.youtube.com/watch?v=xvBtGcJtOII): legenda lida em 15/10/2026. NÃO traz lista de sites de notícia; fala do endpoint /crawl do Browser Rendering da Cloudflare (respeita robots.txt, devolve markdown) versus Puppeteer + proxy. Útil como ferramenta de coleta, não como lista de fontes. Possivelmente o vídeo com a lista é outro
- Legenda do YouTube: funciona com youtube-transcript-api no .venv do projeto (curl puro é bloqueado)

## Referência visual
- Cyberpunk Guide (Julio Della Flora, juliodellaflora.com) — vol. 2 "Hardware Hacking", 76 páginas: capa escura com neon roxo e verde, foto de fundo. A Circuito seguiu outro caminho, de papel antigo e cores desbotadas

## X (Twitter)
- API oficial: paga (conferir preço atual)
- Alternativa: busca em posts do X pela API da xAI (Grok)
- Bluesky (API aberta e grátis) e Threads (API oficial) cobrem parte das mesmas pessoas
- Evitar scraping: fere os termos de uso e quebra com frequência
- Perfis-alvo: Anthropic, OpenAI, Google DeepMind, Meta AI, xAI, Nvidia, Sam Altman, Demis Hassabis, Andrej Karpathy, Akita, Filipe Deschamps, Lucas Montano (confirmar @ de cada um)

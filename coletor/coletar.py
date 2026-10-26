"""Coletor da Circuito.

Lê as fontes de fontes/fontes.yaml, fica só com o que saiu desde o fechamento da edição
anterior e grava coleta/AAAA-MM-DD.json para o editor (Claude) escrever a edição.

Uso:
    python coletor/coletar.py              # coleta da edição de hoje
    python coletor/coletar.py --dominios   # lista os domínios que o ambiente da nuvem precisa liberar
    python coletor/coletar.py --forcar     # coleta mesmo no domingo (testes)
"""

import argparse
import hashlib
import html
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import feedparser
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import (ARQ_ESTADO, ARQ_FONTES, ARQ_VISTOS, PASTA_COLETA, PASTA_EDICOES,  # noqa: E402
                   PASTA_RESUMOS, RAIZ, ROBO_ID, agora, caminho_log_fonte, data_extenso,
                   de_iso, gravar_json, gravar_texto, iso, ler_json, novo_execucao_id,
                   tipo_edicao)

# Só ASCII: com acento, o requests manda o byte cru e vários sites respondem 403.
AGENTE = "Mozilla/5.0 (compatible; CircuitoBot/1.0; revista pessoal de noticias)"
TEMPO_LIMITE = 25
JANELA_PADRAO_HORAS = 30   # primeira execução, sem fechamento anterior
JANELA_MAXIMA_HORAS = 72   # robô parado por dias não vira uma edição gigante
MAX_ITENS_PADRAO = 25
TAMANHO_RESUMO = 500

CLASSIFICACAO_FNG = {
    "Extreme Fear": "Medo extremo", "Fear": "Medo", "Neutral": "Neutro",
    "Greed": "Ganância", "Extreme Greed": "Ganância extrema",
}


# ---------------------------------------------------------------- utilidades

def limpar(texto: str | None, limite: int = TAMANHO_RESUMO) -> str:
    if not texto:
        return ""
    texto = re.sub(r"<(script|style)\b.*?</\1>", " ", texto, flags=re.S | re.I)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", html.unescape(texto)).strip()
    return texto if len(texto) <= limite else texto[:limite].rsplit(" ", 1)[0] + "…"


# Parâmetros que só rastreiam ou carregam credencial de quem compartilhou o link (ex.: o
# `accessToken` dos "artigos presenteados" da Bloomberg). Saem antes de qualquer coisa ser gravada.
PARAMETROS_DESCARTADOS = {
    "accesstoken", "token", "auth", "sig", "signature", "key", "apikey", "st", "reflink",
    "smid", "share", "sref", "cmpid", "mod", "fbclid", "gclid", "mc_cid", "mc_eid",
}


def normalizar_url(url: str) -> str:
    partes = urlparse(html.unescape(url.strip()))
    # `split(";")` desfaz chaves como "amp;reflink", sobra de um &amp; mal codificado na origem.
    consulta = [(k, v) for k, v in parse_qsl(partes.query)
                if not (c := k.lower().split(";")[-1]).startswith("utm_") and c not in PARAMETROS_DESCARTADOS]
    return urlunparse(partes._replace(query=urlencode(consulta), fragment=""))


def chave(url: str) -> str:
    return hashlib.sha1(normalizar_url(url).rstrip("/").encode()).hexdigest()[:16]


def de_struct(t) -> datetime | None:
    return datetime(*t[:6], tzinfo=timezone.utc) if t else None


def novo_item(fonte: dict, titulo: str, url: str, publicado: datetime | None,
              resumo: str = "", extra: dict | None = None) -> dict:
    url = normalizar_url(url)
    return {
        "chave": chave(url),
        "fonte": fonte["id"],
        "fonte_nome": fonte["nome"],
        "secao": fonte.get("secao", "geral"),
        "titulo": limpar(titulo, 300),
        "url": url,
        "publicado": iso(publicado),
        "resumo": limpar(resumo),
        **({"extra": extra} if extra else {}),
    }


# ---------------------------------------------------------------- coletores por tipo
# Cada um devolve (itens, dados). `dados` só é usado pelas fontes de números (cotações).

def coletar_rss(fonte, sessao):
    resp = sessao.get(fonte["url"], timeout=TEMPO_LIMITE)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"feed ilegível: {feed.bozo_exception}")
    itens = []
    for e in feed.entries:
        link = e.get("link")
        if not link:
            continue
        resumo = e.get("summary") or (e.get("content") or [{}])[0].get("value", "")
        extra = None
        if "techmeme.com" in fonte["url"]:
            # O item do Techmeme aponta para o próprio Techmeme; o link original vem no resumo.
            originais = [u for u in re.findall(r'href="(https?://[^"]+)"', resumo)
                         if "techmeme.com" not in u]
            if originais:
                extra = {"discussao": link}
                link = originais[0]
        publicado = de_struct(e.get("published_parsed") or e.get("updated_parsed"))
        itens.append(novo_item(fonte, e.get("title", ""), link, publicado, resumo, extra))
    return itens, None


def coletar_hackernews(fonte, sessao):
    ids = sessao.get(fonte["url"], timeout=TEMPO_LIMITE).json()[: fonte.get("max_itens", 30)]
    minimo = fonte.get("pontuacao_minima", 0)
    itens = []
    for i in ids:
        h = sessao.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json",
                       timeout=TEMPO_LIMITE).json() or {}
        if h.get("type") != "story" or h.get("score", 0) < minimo:
            continue
        discussao = f"https://news.ycombinator.com/item?id={i}"
        publicado = datetime.fromtimestamp(h["time"], timezone.utc) if h.get("time") else None
        itens.append(novo_item(fonte, h.get("title", ""), h.get("url") or discussao, publicado,
                               extra={"pontos": h.get("score"), "comentarios": h.get("descendants"),
                                      "discussao": discussao}))
    return itens, None


def coletar_tabnews(fonte, sessao):
    resp = sessao.get(fonte["url"], timeout=TEMPO_LIMITE)
    resp.raise_for_status()
    itens = []
    for c in resp.json():
        url = f"https://www.tabnews.com.br/{c['owner_username']}/{c['slug']}"
        itens.append(novo_item(fonte, c.get("title", ""), url, de_iso(c.get("published_at")),
                               extra={"autor": c.get("owner_username"), "tabcoins": c.get("tabcoins")}))
    return itens, None


def coletar_youtube(fonte, sessao):
    import yt_dlp  # só carrega se houver fonte de YouTube

    opcoes = {
        "extract_flat": True, "playlistend": fonte.get("max_itens", 3), "quiet": True,
        "no_warnings": True, "skip_download": True,
        "extractor_args": {"youtube": {"lang": [fonte.get("idioma", "pt")]}},
    }
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(fonte["url"], download=False)
    itens = []
    for v in (info or {}).get("entries") or []:
        if not v or not v.get("id"):
            continue
        itens.append(novo_item(
            fonte, v.get("title", ""), f"https://www.youtube.com/watch?v={v['id']}",
            None, v.get("description") or "",
            extra={"canal": info.get("channel") or fonte["nome"], "duracao_s": v.get("duration")}))
    return itens, None


def coletar_html_links(fonte, sessao):
    resp = sessao.get(fonte["url"], timeout=TEMPO_LIMITE)
    resp.raise_for_status()
    padrao = re.compile(fonte["padrao"])
    vistos, itens = set(fonte.get("excluir", [])), []
    for href, miolo in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', resp.text, flags=re.S):
        caminho = urlparse(href).path if href.startswith("http") else href
        if not padrao.match(caminho) or caminho in vistos:
            continue
        titulo = limpar(miolo, 300)
        if len(titulo) < 12:
            continue
        vistos.add(caminho)
        itens.append(novo_item(fonte, titulo, urljoin(fonte.get("base", fonte["url"]), caminho), None))
    return itens[: fonte.get("max_itens", MAX_ITENS_PADRAO)], None


def coletar_coingecko(fonte, sessao):
    resp = sessao.get(fonte["url"], timeout=TEMPO_LIMITE)
    resp.raise_for_status()
    nomes = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}
    moedas, atualizado = [], None
    for chave_api, v in resp.json().items():
        moedas.append({
            "simbolo": nomes.get(chave_api, chave_api.upper()),
            "usd": v.get("usd"), "brl": v.get("brl"),
            "variacao_24h_usd": round(v.get("usd_24h_change") or 0, 2),
        })
        if v.get("last_updated_at"):
            t = datetime.fromtimestamp(v["last_updated_at"], timezone.utc)
            atualizado = max(atualizado, t) if atualizado else t
    return [], {"tipo": "cotacoes", "fonte": "CoinGecko", "atualizado_em": iso(atualizado),
                "moedas": moedas}


def coletar_medo_ganancia(fonte, sessao):
    resp = sessao.get(fonte["url"], timeout=TEMPO_LIMITE)
    resp.raise_for_status()
    d = resp.json()["data"][0]
    return [], {"tipo": "medo_ganancia", "fonte": "alternative.me", "valor": int(d["value"]),
                "classificacao": CLASSIFICACAO_FNG.get(d["value_classification"], d["value_classification"]),
                "referencia": iso(datetime.fromtimestamp(int(d["timestamp"]), timezone.utc))}


COLETORES = {
    "rss": coletar_rss, "hackernews": coletar_hackernews, "tabnews": coletar_tabnews,
    "youtube": coletar_youtube, "html_links": coletar_html_links,
    "coingecko": coletar_coingecko, "medo_ganancia": coletar_medo_ganancia,
}

# Domínios que cada tipo acessa além do domínio da própria `url`.
DOMINIOS_EXTRAS = {"hackernews": ["hacker-news.firebaseio.com"], "youtube": ["www.youtube.com"]}


# ---------------------------------------------------------------- janela e estado

def calcular_janela(estado: dict, fim: datetime) -> tuple[datetime, datetime]:
    inicio = de_iso((estado or {}).get("ultimo_fechamento")) or fim - timedelta(hours=JANELA_PADRAO_HORAS)
    return max(inicio, fim - timedelta(hours=JANELA_MAXIMA_HORAS)), fim


def na_janela(item: dict, inicio: datetime, fim: datetime, vistos: dict) -> bool:
    if item["chave"] in vistos:
        return False
    publicado = de_iso(item["publicado"])
    if publicado is None:  # fonte sem data: "novo" = nunca visto antes
        return True
    return inicio <= publicado <= fim + timedelta(hours=1)


def edicao_anterior() -> str | None:
    edicoes = sorted(PASTA_EDICOES.glob("*.json"))
    return edicoes[-1].relative_to(RAIZ).as_posix() if edicoes else None


# ---------------------------------------------------------------- execução

def carregar_fontes() -> list[dict]:
    with open(ARQ_FONTES, encoding="utf-8") as f:
        return yaml.safe_load(f)["fontes"]


def listar_dominios(fontes: list[dict]) -> list[str]:
    dominios = set()
    for f in fontes:
        dominios.add(urlparse(f["url"]).hostname)
        dominios.update(DOMINIOS_EXTRAS.get(f["tipo"], []))
    return sorted(dominios)


def coletar_fonte(fonte, sessao, execucao_id, janela, vistos):
    instante = agora()
    log = {  # envelope montado antes do bloco protegido: toda fonte gera log, mesmo falhando cedo
        "execucao_id": execucao_id, "execucao": iso(instante), "robo": ROBO_ID,
        "fonte": fonte["id"], "nome": fonte["nome"], "tipo": fonte["tipo"], "url": fonte["url"],
        "status": "falha", "itens_lidos": 0, "itens_na_janela": 0, "erro": None, "duracao_ms": None,
    }
    itens, dados = [], None
    t0 = time.monotonic()
    try:
        lidos, dados = COLETORES[fonte["tipo"]](fonte, sessao)
        lidos = lidos[: fonte.get("max_itens", MAX_ITENS_PADRAO)]
        itens = [i for i in lidos if na_janela(i, janela[0], janela[1], vistos)]
        log.update(status="ok", itens_lidos=len(lidos), itens_na_janela=len(itens))
    except Exception as e:  # uma fonte fora do ar não derruba a edição
        log["erro"] = f"{type(e).__name__}: {e}"[:500]
    finally:
        log["duracao_ms"] = int((time.monotonic() - t0) * 1000)
        gravar_json(caminho_log_fonte(fonte["id"], instante), log)
    return log, itens, dados


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dominios", action="store_true", help="lista os domínios das fontes e grava fontes/dominios.txt")
    ap.add_argument("--forcar", action="store_true", help="coleta mesmo no domingo")
    args = ap.parse_args()

    fontes = carregar_fontes()
    if args.dominios:
        dominios = listar_dominios(fontes)
        gravar_texto(RAIZ / "fontes" / "dominios.txt", "\n".join(dominios) + "\n")
        print("\n".join(dominios))
        return 0

    inicio_exec = agora()
    execucao_id = novo_execucao_id(inicio_exec)
    tipo = tipo_edicao(inicio_exec)
    arq_resumo = PASTA_RESUMOS / f"{inicio_exec.strftime('%Y-%m-%d_%H%M%S')}.json"
    estado = ler_json(ARQ_ESTADO, {})
    vistos = ler_json(ARQ_VISTOS, {})
    janela = calcular_janela(estado, inicio_exec)

    resumo = {
        "robo": ROBO_ID, "execucao_id": execucao_id, "execucao_inicio": iso(inicio_exec),
        "execucao": None, "processados": 0, "sucesso": 0, "falha": 0,
        "etapa": None, "edição (data)": inicio_exec.strftime("%Y-%m-%d"), "edição (número)": None,
        "tipo de edição": tipo, "janela (início)": iso(janela[0]), "janela (fim)": iso(janela[1]),
        "notícias coletadas": None, "notas publicadas": None, "páginas": None,
        "fontes com falha": None, "teste": None,
    }

    if tipo == "domingo" and not args.forcar:
        resumo.update(execucao=iso(agora()), etapa="domingo: sem edição")
        gravar_json(arq_resumo, resumo)
        print("Domingo não tem edição. Nada a fazer.")
        return 3

    sessao = requests.Session()
    sessao.headers["User-Agent"] = AGENTE

    relatorio, itens, cotacoes, medo = [], {}, None, None
    for fonte in fontes:
        log, novos, dados = coletar_fonte(fonte, sessao, execucao_id, janela, vistos)
        relatorio.append({k: log[k] for k in ("fonte", "nome", "status", "itens_na_janela", "erro")})
        for it in novos:  # mesma notícia em duas fontes: fica a primeira, anota a outra
            if it["chave"] in itens:
                itens[it["chave"]].setdefault("tambem_em", []).append(it["fonte_nome"])
            else:
                itens[it["chave"]] = it
        if dados and dados["tipo"] == "cotacoes":
            cotacoes = dados
        elif dados and dados["tipo"] == "medo_ganancia":
            medo = dados
        print(f"{log['status']:5} {fonte['id']:22} {log['itens_na_janela']:3} itens"
              + (f"  ({log['erro']})" if log["erro"] else ""))

    lista = sorted(itens.values(), key=lambda i: i["publicado"] or "", reverse=True)
    arq_coleta = PASTA_COLETA / f"{inicio_exec.strftime('%Y-%m-%d')}.json"
    gravar_json(arq_coleta, {
        "robo": ROBO_ID, "execucao_id": execucao_id, "gerado_em": iso(agora()),
        "edicao": {"data": inicio_exec.strftime("%Y-%m-%d"), "tipo": tipo,
                   "data_extenso": data_extenso(inicio_exec),
                   "numero": (estado.get("ultima_edicao") or {}).get("numero", 0) + 1},
        "janela": {"inicio": iso(janela[0]), "fim": iso(janela[1]),
                   "horas": round((janela[1] - janela[0]).total_seconds() / 3600, 1)},
        "resumo_execucao": arq_resumo.relative_to(RAIZ).as_posix(),
        "edicao_anterior": edicao_anterior(),
        "fontes": relatorio, "cotacoes": cotacoes, "medo_ganancia": medo, "itens": lista,
    })

    falhas = [r["fonte"] for r in relatorio if r["status"] != "ok"]
    resumo.update(execucao=iso(agora()), processados=len(relatorio), sucesso=len(relatorio) - len(falhas),
                  falha=len(falhas), etapa="coleta concluída", **{"notícias coletadas": len(lista),
                  "fontes com falha": ", ".join(falhas) or None})
    gravar_json(arq_resumo, resumo)

    print(f"\n{len(lista)} notícias na janela de {iso(janela[0])} a {iso(janela[1])}")
    print(f"Coleta: {arq_coleta.relative_to(RAIZ).as_posix()}  ·  falhas: {', '.join(falhas) or 'nenhuma'}")
    # Com mais da metade das fontes fora do ar, a edição sairia capenga: o editor decide.
    return 2 if len(falhas) > len(relatorio) / 2 else 0


if __name__ == "__main__":
    sys.exit(main())

"""Montagem da Circuito.

Confere edicoes/AAAA-MM-DD.json (escrito pelo editor) contra a coleta do dia, monta as
páginas no molde aprovado e publica.

Uso:
    python coletor/montar.py --validar          # só confere o texto da edição de hoje
    python coletor/montar.py --teste            # gera previa/AAAA-MM-DD.html sem publicar nada
    python coletor/montar.py                    # publica em site/ e fecha a edição
    python coletor/montar.py --data 2026-10-22  # outra data
"""

import argparse
import math
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import (ARQ_ESTADO, ARQ_VISTOS, DIAS_SEMANA, IMAGEM_PREVIA, MESES,  # noqa: E402
                   PASTA_COLETA, PASTA_EDICOES, PASTA_ESTADO, PASTA_MODELO, PASTA_SITE, RAIZ,
                   SITE_URL, agora, data_extenso, de_iso, gravar_json, gravar_texto, iso, ler_json)

ARQ_EDICOES_PUBLICADAS = PASTA_ESTADO / "edicoes.json"
PASTA_PREVIA = RAIZ / "previa"

PAGINAS_PERMITIDAS = {"normal": (8, 12), "segunda": (12, 16)}
MAX_NOTICIAS = {"normal": 16, "segunda": 26}  # matéria, reportagem, notas e cripto; comunidade não conta
MAX_PREENCHIMENTO = 2          # páginas de glossário/anúncio que a montagem pode inserir
MAX_SUMARIO = 10
TERMOS_POR_PAGINA = 5
RETENCAO_VISTOS_DIAS = 45
PALAVRAS_POR_MINUTO = 200
CAMPOS_SEM_TEXTO = {"url", "ilustracao", "tipo", "estilo", "destaque", "valor"}

LINK_COM_CREDENCIAL = re.compile(r"[?&;](access_?token|token|auth|sig|signature|key|apikey|password)=", re.I)

ILUSTRACOES = sorted(p.stem for p in (PASTA_MODELO / "ilustracoes").glob("*.svg"))

ANUNCIOS = [
    {"titulo": "Aprenda <em>Prompt</em> por correspondência!",
     "texto": "Em 10 lições você conversa com as máquinas do futuro. Material didático em disquete.",
     "ilustracao": "disquete",
     "cupom": ["NOME: ______________________", "CIDADE: _________ UF: ___", "( ) QUERO O DISQUETE GRÁTIS"]},
    {"titulo": "Expansão de <em>memória</em> 640 KB!",
     "texto": "Seu micro mais rápido que nunca. Instalação em 5 minutos, sem soldar nada. Garantia de 90 dias.",
     "ilustracao": "memoria",
     "cupom": ["NOME: ______________________", "MICRO: ________ ( ) 8 BITS ( ) 16 BITS", "( ) QUERO O CATÁLOGO"]},
    {"titulo": "Monte seu <em>robô</em> em casa!",
     "texto": "Kit com braço articulado, motor de passo e manual ilustrado. Pilhas não inclusas.",
     "ilustracao": "robo",
     "cupom": ["NOME: ______________________", "IDADE: ___  ( ) TENHO FERRO DE SOLDA", "( ) QUERO O KIT"]},
    {"titulo": "Cofre para <em>moedas digitais</em>",
     "texto": "Guarde as economias do futuro num cofre de verdade. Segredo de 3 números. Aceitamos cheque.",
     "ilustracao": "cofre",
     "cupom": ["NOME: ______________________", "( ) À VISTA  ( ) 3X SEM JUROS", "( ) QUERO RECEBER UM VENDEDOR"]},
]

SITES = {
    "theverge.com": "The Verge", "arstechnica.com": "Ars Technica", "techcrunch.com": "TechCrunch",
    "wired.com": "Wired", "bloomberg.com": "Bloomberg", "reuters.com": "Reuters", "ft.com": "Financial Times",
    "cnbc.com": "CNBC", "blog.google": "Google", "deepmind.google": "Google DeepMind", "openai.com": "OpenAI",
    "anthropic.com": "Anthropic", "blogs.nvidia.com": "Nvidia", "nvidia.com": "Nvidia", "coindesk.com": "CoinDesk",
    "livecoins.com.br": "Livecoins", "tecnoblog.net": "Tecnoblog", "tabnews.com.br": "TabNews",
    "youtube.com": "YouTube", "akitaonrails.com": "akitaonrails.com", "importai.substack.com": "Import AI",
    "simonwillison.net": "Simon Willison", "tomshardware.com": "Tom's Hardware",
    "news.ycombinator.com": "Hacker News", "github.com": "GitHub", "theinformation.com": "The Information",
    "nytimes.com": "The New York Times", "wsj.com": "WSJ", "engadget.com": "Engadget", "9to5mac.com": "9to5Mac",
    "semafor.com": "Semafor", "businessinsider.com": "Business Insider", "axios.com": "Axios",
    "venturebeat.com": "VentureBeat", "zdnet.com": "ZDNET", "theregister.com": "The Register",
    "fortune.com": "Fortune", "forbes.com": "Forbes", "cnet.com": "CNET", "macrumors.com": "MacRumors",
}


# ---------------------------------------------------------------- utilidades

def contar_palavras(*textos) -> int:
    return sum(len(re.findall(r"[\wÀ-ÿ$%€]+(?:[.,'’-][\wÀ-ÿ]+)*", t or "")) for t in textos)


def palavras_no_json(valor, campo=None) -> int:
    if isinstance(valor, str):
        return 0 if campo in CAMPOS_SEM_TEXTO else contar_palavras(valor)
    if isinstance(valor, list):
        return sum(palavras_no_json(v, campo) for v in valor)
    if isinstance(valor, dict):
        return sum(palavras_no_json(v, k) for k, v in valor.items())
    return 0


def nome_do_site(url: str) -> str:
    host = (urlparse(url).hostname or "").removeprefix("www.")
    for dominio, nome in SITES.items():
        if host == dominio or host.endswith("." + dominio):
            return nome
    return host


def numero_br(valor, casas=None) -> str:
    if valor is None:
        return "—"
    casas = (0 if abs(valor) >= 10000 else 2) if casas is None else casas
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def romano(n: int) -> str:
    tabela = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    saida = ""
    for v, s in tabela:
        while n >= v:
            saida, n = saida + s, n - v
    return saida


def hora_br(dt: datetime) -> str:
    return f"{dt.strftime('%d/%m')} às {dt.strftime('%H')}h{dt.strftime('%M')}"


def iniciais(nome: str) -> str:
    partes = [p for p in re.split(r"\s+", nome) if p.lower() not in {"de", "da", "do", "dos", "das", "e"}]
    return "".join(p[0] for p in partes[:2]).upper() or "?"


# ---------------------------------------------------------------- validação

class Validador:
    def __init__(self, links_validos: set[str]):
        self.erros: list[str] = []
        self.links = links_validos

    def erro(self, onde, msg):
        self.erros.append(f"{onde}: {msg}")

    def texto(self, onde, d, campo, max_palavras=None, max_chars=None, obrigatorio=True):
        valor = d.get(campo) if isinstance(d, dict) else None
        if not valor:
            if obrigatorio:
                self.erro(onde, f"falta o campo '{campo}'")
            return ""
        if not isinstance(valor, str):
            self.erro(onde, f"'{campo}' precisa ser texto")
            return ""
        if max_palavras and (n := contar_palavras(valor)) > max_palavras:
            self.erro(onde, f"'{campo}' tem {n} palavras (máximo {max_palavras})")
        if max_chars and len(valor) > max_chars:
            self.erro(onde, f"'{campo}' tem {len(valor)} caracteres (máximo {max_chars})")
        return valor

    def lista(self, onde, d, campo, minimo, maximo, obrigatorio=True):
        valor = d.get(campo) if isinstance(d, dict) else None
        if valor is None:
            if obrigatorio and minimo:
                self.erro(onde, f"falta a lista '{campo}'")
            return []
        if not isinstance(valor, list):
            self.erro(onde, f"'{campo}' precisa ser uma lista")
            return []
        if not minimo <= len(valor) <= maximo:
            self.erro(onde, f"'{campo}' tem {len(valor)} itens (permitido de {minimo} a {maximo})")
        return valor

    def link(self, onde, url):
        if not url:
            self.erro(onde, "falta o 'url'")
        elif url not in self.links:
            self.erro(onde, f"link fora da coleta: {url}")
        elif LINK_COM_CREDENCIAL.search(url):  # a revista é pública: nada de token pendurado em link
            self.erro(onde, f"link com parâmetro de credencial, não publique: {url}")

    def total(self, onde, textos, maximo):
        if (n := contar_palavras(*textos)) > maximo:
            self.erro(onde, f"{n} palavras no total (máximo {maximo}); corte texto")

    def ilustracao(self, onde, nome, obrigatoria=False):
        if not nome:
            if obrigatoria:
                self.erro(onde, "falta a 'ilustracao'")
        elif nome not in ILUSTRACOES:
            self.erro(onde, f"ilustração '{nome}' não existe (use: {', '.join(ILUSTRACOES)})")

    def refs(self, onde, d, maximo=4):
        for i, r in enumerate(self.lista(onde, d, "refs", 0, maximo, obrigatorio=False)):
            self.texto(f"{onde} › refs[{i}]", r, "rotulo", max_palavras=4)
            self.link(f"{onde} › refs[{i}]", r.get("url"))

    def quadro(self, onde, q, max_palavras=40):
        self.texto(onde, q, "titulo", max_palavras=6)
        if q.get("tabela"):
            t = q["tabela"]
            if not t.get("colunas") or len(t["colunas"]) > 4:
                self.erro(onde, "tabela precisa de 1 a 4 colunas")
            linhas = t.get("linhas") or []
            if not 1 <= len(linhas) <= 4:
                self.erro(onde, "tabela precisa de 1 a 4 linhas")
            if any(len(l) > len(t.get("colunas") or []) for l in linhas):
                self.erro(onde, "linha da tabela com mais valores que colunas")
            self.texto(onde, q, "texto", max_palavras=18, obrigatorio=False)
        else:
            self.texto(onde, q, "texto", max_palavras=max_palavras)

    def grafico(self, onde, g):
        self.texto(onde, g, "titulo", max_palavras=9)
        self.link(onde, g.get("url"))
        for i, b in enumerate(self.lista(onde, g, "barras", 2, 4)):
            self.texto(f"{onde} › barras[{i}]", b, "rotulo", max_chars=8)
            self.texto(f"{onde} › barras[{i}]", b, "texto", max_chars=9)
            if not isinstance(b.get("valor"), (int, float)) or b["valor"] < 0:
                self.erro(f"{onde} › barras[{i}]", "'valor' precisa ser um número positivo")
        self.texto(onde, g, "nota", max_palavras=28, obrigatorio=False)

    def notas(self, onde, notas, max_rotulo=4):
        for i, n in enumerate(notas):
            self.texto(f"{onde} › notas[{i}]", n, "rotulo", max_palavras=max_rotulo)
            self.texto(f"{onde} › notas[{i}]", n, "texto")
            self.link(f"{onde} › notas[{i}]", n.get("url"))


def contar_noticias(paginas: list[dict]) -> int:
    return sum(1 if p.get("tipo") in ("materia", "reportagem") else
               len(p.get("notas") or []) if p.get("tipo") in ("notas", "cripto") else 0
               for p in paginas)


def teve_sabado(coleta: dict) -> bool:
    """A página 'perdeu' só faz sentido se a edição anterior for de sábado (não é, por exemplo, na estreia)."""
    anterior = coleta.get("edicao_anterior")
    if not anterior:
        return False
    try:
        return datetime.strptime(Path(anterior).stem, "%Y-%m-%d").weekday() == 5
    except ValueError:
        return False


def validar(ed: dict, tipo_ed: str, v: Validador, sabado: bool = True) -> None:
    capa = ed.get("capa") or {}
    v.texto("capa", capa, "manchete", max_chars=26)
    v.texto("capa", capa, "subtitulo", max_palavras=16)
    el = capa.get("elemento") or {}
    v.texto("capa › elemento", el, "simbolo", max_chars=3)
    v.texto("capa › elemento", el, "numero", max_chars=3)
    v.texto("capa › elemento", el, "nome", max_chars=12)
    v.texto("capa › elemento", el, "detalhe", max_chars=10)
    for i, c in enumerate(v.lista("capa", capa, "chamadas", 3, 4)):
        v.texto(f"capa › chamadas[{i}]", c, "rotulo", max_chars=14)
        v.texto(f"capa › chamadas[{i}]", c, "texto", max_palavras=9)

    edit = ed.get("editorial") or {}
    v.texto("editorial", edit, "titulo", max_palavras=8)
    v.total("editorial", v.lista("editorial", edit, "paragrafos", 1, 3), 75)

    paginas = ed.get("paginas") or []
    if not paginas or paginas[-1].get("tipo") != "contracapa":
        v.erro("paginas", "a última página precisa ser a 'contracapa'")
    for i, p in enumerate(paginas):
        onde = f"paginas[{i}] ({p.get('tipo', '?')})"
        tipo = p.get("tipo")
        if tipo == "materia":
            v.texto(onde, p, "secao", max_palavras=3)
            v.texto(onde, p, "titulo", max_palavras=8)
            v.texto(onde, p, "olho", max_palavras=38)
            v.ilustracao(onde, p.get("ilustracao"), obrigatoria=True)
            v.texto(onde, p, "legenda", max_palavras=16, obrigatorio=False)
            par = v.lista(onde, p, "paragrafos", 2, 4)
            if par:
                v.total(f"{onde} › abertura (paragrafos[0])", par[:1], 55)
                v.total(f"{onde} › continuação (paragrafos[1:])", par[1:], 70)
            for j, q in enumerate(v.lista(onde, p, "quadros", 0, 3, obrigatorio=False)):
                v.quadro(f"{onde} › quadros[{j}]", q)
            v.refs(onde, p)
            if not p.get("refs"):
                v.erro(onde, "matéria de capa precisa de 'refs'")
        elif tipo == "reportagem":
            v.texto(onde, p, "secao", max_palavras=3)
            v.texto(onde, p, "assunto", max_palavras=3, obrigatorio=False)
            v.texto(onde, p, "tarja", max_palavras=3, obrigatorio=False)
            v.texto(onde, p, "titulo", max_palavras=9)
            v.ilustracao(onde, p.get("ilustracao"))
            par = v.lista(onde, p, "paragrafos", 1, 4)
            v.total(onde, par, 95 if p.get("ilustracao") else 150)
            if p.get("quadro"):
                v.quadro(f"{onde} › quadro", p["quadro"], max_palavras=30)
            v.refs(onde, p, maximo=3)
            if not p.get("refs"):
                v.erro(onde, "reportagem precisa de 'refs'")
        elif tipo == "notas":
            v.texto(onde, p, "secao", max_palavras=4)
            v.texto(onde, p, "assunto", max_palavras=3, obrigatorio=False)
            v.texto(onde, p, "tarja", max_palavras=3, obrigatorio=False)
            v.texto(onde, p, "titulo", max_palavras=6)
            v.ilustracao(onde, p.get("ilustracao"))
            estilo = p.get("estilo", "lista")
            if estilo not in ("lista", "colunas"):
                v.erro(onde, "'estilo' precisa ser 'lista' ou 'colunas'")
            minimo, maximo, limite = (3, 6, 210) if estilo == "colunas" else (2, 4, 100)
            notas = v.lista(onde, p, "notas", minimo, maximo)
            v.notas(onde, notas)
            if p.get("grafico"):
                v.grafico(f"{onde} › grafico", p["grafico"])
                limite -= 40
            if p.get("quadro"):
                v.quadro(f"{onde} › quadro", p["quadro"], max_palavras=35)
                limite -= 25
            if p.get("ilustracao"):
                limite -= 15
            v.total(onde, [n.get("texto") for n in notas], limite)
            v.refs(onde, p)
        elif tipo == "cripto":
            v.texto(onde, p, "titulo", max_palavras=8)
            notas = v.lista(onde, p, "notas", 1, 3)
            v.notas(onde, notas, max_rotulo=3)
            v.total(onde, [n.get("texto") for n in notas], 55)
            v.refs(onde, p)
        elif tipo == "comunidade":
            v.texto(onde, p, "titulo", max_palavras=7)
            vozes = v.lista(onde, p, "vozes", 2, 4)
            for j, voz in enumerate(vozes):
                w = f"{onde} › vozes[{j}]"
                v.texto(w, voz, "nome", max_palavras=4)
                v.texto(w, voz, "onde", max_palavras=3)
                v.texto(w, voz, "texto", max_palavras=38)
                for k, l in enumerate(v.lista(w, voz, "links", 1, 2)):
                    v.texto(f"{w} › links[{k}]", l, "rotulo", max_palavras=4)
                    v.link(f"{w} › links[{k}]", l.get("url"))
            if p.get("quadro"):
                if len(vozes) > 3:
                    v.erro(onde, "com 4 vozes não cabe 'quadro'")
                v.quadro(f"{onde} › quadro", p["quadro"], max_palavras=30)
        elif tipo == "perdeu":
            if tipo_ed != "segunda":
                v.erro(onde, "a página 'perdeu' só sai na edição de segunda")
            v.texto(onde, p, "titulo", max_palavras=7)
            for j, it in enumerate(v.lista(onde, p, "itens", 3, 5)):
                v.texto(f"{onde} › itens[{j}]", it, "rotulo", max_palavras=3)
                v.texto(f"{onde} › itens[{j}]", it, "texto", max_palavras=30)
                v.link(f"{onde} › itens[{j}]", it.get("url"))
        elif tipo == "contracapa":
            if i != len(paginas) - 1:
                v.erro(onde, "a contracapa precisa ser a última página")
            for j, l in enumerate(v.lista(onde, p, "leituras", 3, 4)):
                v.texto(f"{onde} › leituras[{j}]", l, "titulo", max_palavras=16)
                v.texto(f"{onde} › leituras[{j}]", l, "onde", max_palavras=5)
                v.link(f"{onde} › leituras[{j}]", l.get("url"))
        else:
            v.erro(onde, f"tipo de página desconhecido: '{tipo}'")

    if (n := contar_noticias(paginas)) > MAX_NOTICIAS[tipo_ed]:
        v.erro("paginas", f"{n} notícias (máximo {MAX_NOTICIAS[tipo_ed]} na edição '{tipo_ed}'); "
                          "corte as menos importantes")

    tem_perdeu = any(p.get("tipo") == "perdeu" for p in paginas)
    if tipo_ed == "segunda" and sabado and not tem_perdeu:
        v.erro("paginas", "a edição de segunda precisa da página 'perdeu' (destaques do sábado)")
    if tem_perdeu and not sabado:
        v.erro("paginas", "não houve edição no sábado: tire a página 'perdeu'")

    for i, t in enumerate(v.lista("glossario", ed, "glossario", 0, 15, obrigatorio=False)):
        v.texto(f"glossario[{i}]", t, "termo", max_chars=22)
        v.texto(f"glossario[{i}]", t, "categoria", max_palavras=2, obrigatorio=False)
        v.texto(f"glossario[{i}]", t, "definicao", max_palavras=30)


# ---------------------------------------------------------------- paginação

def refs_automaticas(p: dict) -> list[dict]:
    if p.get("refs"):
        return p["refs"]
    urls = [n["url"] for n in p.get("notas", []) if n.get("url")]
    if p.get("grafico", {}).get("url"):
        urls.append(p["grafico"]["url"])
    vistos, refs = set(), []
    for u in urls:
        nome = nome_do_site(u)
        if nome not in vistos:
            vistos.add(nome)
            refs.append({"rotulo": nome, "url": u})
    return refs


def preparar_grafico(g: dict) -> dict:
    barras = g["barras"]
    maior = max(b["valor"] for b in barras) or 1
    marcado = any(b.get("destaque") for b in barras)
    saida = []
    for i, b in enumerate(barras):
        saida.append({**b, "y": 6 + i * 27, "largura": max(2, round(186 * b["valor"] / maior)),
                      "destaque": b.get("destaque") or (not marcado and i == len(barras) - 1)})
    return {**g, "barras": saida, "altura": 8 + len(barras) * 27,
            "descricao": "; ".join(f"{b['rotulo']}: {b['texto']}" for b in barras)}


def paginar(ed: dict, numero: int, tipo_ed: str, erros: list[str]) -> list[dict]:
    paginas = [
        {"tipo": "capa", "rotulo_aria": "Capa"},
        {"tipo": "editorial", "runner": [f"Circuito · Nº {numero:03d}", "Ao leitor"], "folio": "Ao leitor"},
    ]
    blocos = ed["paginas"]
    for p in blocos[:-1]:
        t = p["tipo"]
        if t == "materia":
            base = {**p, "refs": p.get("refs", [])}
            paginas.append({**base, "tipo": "materia_a", "runner": ["Matéria de capa", p.get("assunto", p["secao"])],
                            "folio": "Matéria de capa", "sumario_rotulo": "Capa"})
            paginas.append({**base, "tipo": "materia_b", "runner": [p["titulo"], "Continuação"],
                            "folio": "Matéria de capa", "sem_sumario": True})
        elif t in ("reportagem", "notas"):
            p = {**p, "refs": refs_automaticas(p)}
            if p.get("grafico"):
                p["grafico"] = preparar_grafico(p["grafico"])
            paginas.append({**p, "runner": [p["secao"], p.get("assunto", "")], "folio": p["secao"]})
        elif t == "cripto":
            paginas.append({**p, "refs": refs_automaticas(p), "runner": ["Cofre Digital", "Cripto · o básico"],
                            "folio": "Cofre Digital", "sumario_rotulo": "Cripto", "sumario": "Cofre Digital"})
        elif t == "comunidade":
            vozes = [{**voz, "iniciais": iniciais(voz["nome"])} for voz in p["vozes"]]
            paginas.append({**p, "vozes": vozes, "runner": ["Da Comunidade", "Blogs, YouTube e fóruns"],
                            "folio": "Da Comunidade", "sumario_rotulo": "Vozes", "sumario": "Da Comunidade"})
        elif t == "perdeu":
            itens = [{**i, "fonte": nome_do_site(i["url"])} for i in p["itens"]]
            paginas.append({**p, "itens": itens, "runner": ["Se você perdeu", "Edição de sábado"],
                            "folio": "Se você perdeu", "sumario_rotulo": "Sábado"})

    # Fecha em múltiplo de 4 (folhas dobradas) com glossário e, se faltar, anúncio.
    total = len(paginas) + 1
    faltam = (-total) % 4
    minimo, maximo = PAGINAS_PERMITIDAS[tipo_ed]
    if faltam > MAX_PREENCHIMENTO:
        erros.append(f"paginas: a edição tem {total} páginas e faltam {faltam} para fechar em múltiplo de 4 "
                     f"(a montagem completa no máximo {MAX_PREENCHIMENTO}); acrescente conteúdo ou corte páginas")
    elif not minimo <= total + faltam <= maximo:
        erros.append(f"paginas: a edição ficaria com {total + faltam} páginas; edição '{tipo_ed}' "
                     f"precisa ter entre {minimo} e {maximo}")
    termos = list(ed.get("glossario") or [])
    teve_anuncio_inteiro = False
    for k in range(faltam if faltam <= MAX_PREENCHIMENTO else 0):
        if termos:
            lote, termos = termos[:TERMOS_POR_PAGINA], termos[TERMOS_POR_PAGINA:]
            paginas.append({"tipo": "glossario", "termos": lote, "runner": ["Dicionário do Byte", "Glossário"],
                            "folio": "Glossário", "sem_sumario": True})
        else:
            paginas.append({"tipo": "anuncio", "anuncio": anuncio(numero + k + 1),
                            "runner": ["Classificados", "Anúncio"], "folio": "Classificados", "sem_sumario": True})
            teve_anuncio_inteiro = True

    # Um anúncio por edição: se já saiu o de página inteira, a contracapa fica sem o pequeno.
    contracapa = blocos[-1]
    paginas.append({**contracapa, "tipo": "contracapa", "runner": ["Pra ler com calma", "Contracapa"],
                    "anuncio": None if teve_anuncio_inteiro else anuncio(numero),
                    "sumario_rotulo": "Fim", "sumario": "Pra ler com calma"})

    for n, p in enumerate(paginas, start=1):
        p["num"] = n
        p.setdefault("rotulo_aria", f"Página {n}")
        if p["tipo"] == "materia_a" and n % 2:
            erros.append(f"paginas: a matéria de capa começa na página {n}; precisa começar em página par "
                         "para abrir em página dupla (mude a ordem das páginas)")
    return paginas


def anuncio(semente: int) -> dict:
    a = ANUNCIOS[semente % len(ANUNCIOS)]
    return {**a, "titulo": Markup(a["titulo"])}


def montar_sumario(paginas: list[dict], erros: list[str]) -> list[dict]:
    itens = []
    for p in paginas:
        if p["tipo"] in ("capa", "editorial") or p.get("sem_sumario"):
            continue
        itens.append({"rotulo": p.get("sumario_rotulo") or p.get("secao", ""),
                      "titulo": p.get("sumario") or p.get("titulo", ""), "pagina": p["num"]})
    if len(itens) > MAX_SUMARIO:
        erros.append(f"sumário: {len(itens)} entradas (máximo {MAX_SUMARIO}); junte páginas de notas")
    return itens


# ---------------------------------------------------------------- dados prontos para o molde

def preparar_cotacoes(c: dict | None) -> dict | None:
    if not c or not c.get("moedas"):
        return None
    moedas = []
    for m in c["moedas"]:
        var = m.get("variacao_24h_usd") or 0
        moedas.append({"simbolo": m["simbolo"], "usd": numero_br(m["usd"]), "brl": numero_br(m["brl"]),
                       "variacao": f"{'+' if var >= 0 else '−'}{numero_br(abs(var), 2)}%",
                       "classe": "sobe" if var >= 0 else "desce"})
    quando = de_iso(c.get("atualizado_em"))
    return {"moedas": moedas, "quando": hora_br(quando) if quando else "horário desconhecido"}


def preparar_medo(m: dict | None) -> dict | None:
    if not m:
        return None
    angulo = math.pi - m["valor"] / 100 * math.pi
    return {**m, "ponteiro_x": round(100 + 68 * math.cos(angulo), 1),
            "ponteiro_y": round(100 - 68 * math.sin(angulo), 1)}


def links_da_coleta(coleta: dict) -> tuple[set[str], dict[str, str]]:
    links, fontes = set(), {}
    for it in coleta["itens"]:
        links.add(it["url"])
        fontes[it["url"]] = it["fonte_nome"]
        if (it.get("extra") or {}).get("discussao"):
            links.add(it["extra"]["discussao"])
    anterior = coleta.get("edicao_anterior")
    if anterior and (RAIZ / anterior).exists():  # a página 'perdeu' de segunda cita o sábado
        texto = (RAIZ / anterior).read_text(encoding="utf-8")
        links.update(re.findall(r'"url":\s*"([^"]+)"', texto))
    return links, fontes


def urls_usadas(ed) -> list[str]:
    achadas = []

    def andar(v, campo=None):
        if isinstance(v, dict):
            for k, x in v.items():
                andar(x, k)
        elif isinstance(v, list):
            for x in v:
                andar(x, campo)
        elif campo == "url" and isinstance(v, str):
            achadas.append(v)
    andar(ed)
    return achadas


def expediente(coleta: dict, ed: dict) -> list[str]:
    ini, fim = de_iso(coleta["janela"]["inicio"]), de_iso(coleta["janela"]["fim"])
    nomes = sorted({nome_do_site(u) for u in urls_usadas(ed)})
    lista = ", ".join(nomes[:10]) + (" e outras" if len(nomes) > 10 else "")
    return [f"Fechamento {fim.strftime('%d/%m/%Y')} {fim.strftime('%H')}h{fim.strftime('%M')} (Brasília)",
            f"Cobre de {hora_br(ini)} a {hora_br(fim)}",
            f"Fontes: {lista}"]


def proxima_edicao(data: datetime, numero: int) -> list[str]:
    quando = "Segunda nas bancas" if data.weekday() == 5 else "Amanhã nas bancas"
    return [quando, f"Edição nº {numero + 1:03d}, às 7h"]


def ambiente_jinja() -> Environment:
    # Campos opcionais (tarja, quadro, ilustração…) são testados com {% if %}; por isso o Undefined padrão.
    return Environment(loader=FileSystemLoader(PASTA_MODELO), autoescape=select_autoescape(["html", "j2"]),
                       trim_blocks=True, lstrip_blocks=True)


def carregar_svgs() -> dict[str, Markup]:
    return {nome: Markup((PASTA_MODELO / "ilustracoes" / f"{nome}.svg").read_text(encoding="utf-8"))
            for nome in ILUSTRACOES}


def renderizar(ed, coleta, paginas, sumario, data, numero, raiz, teste) -> str:
    dia = DIAS_SEMANA[data.weekday()].removesuffix("-feira").capitalize()
    dados_ed = {
        **ed, "numero": numero, "numero_fmt": f"{numero:03d}", "data": data.strftime("%Y-%m-%d"),
        "data_extenso": data_extenso(data), "data_curta": data.strftime("%d/%m/%Y"),
        "data_capa": f"{dia}, {data.day} de {MESES[data.month - 1]} de {data.year}",
        "ano": data.year, "ano_romano": romano(max(1, data.year - 2025)),
        "minutos": max(3, round(palavras_no_json(ed) / PALAVRAS_POR_MINUTO)),
    }
    grupos = [[paginas[0]]]
    for i in range(1, len(paginas) - 1, 2):
        grupos.append(paginas[i:i + 2])
    grupos.append([paginas[-1]])
    # Prévia de link (WhatsApp, redes sociais): a página do dia aponta para a raiz; a de arquivo, para si mesma.
    previa = {"url": SITE_URL if raiz != "../" else f"{SITE_URL}edicoes/{dados_ed['data']}.html",
              "imagem": SITE_URL + IMAGEM_PREVIA,
              "titulo": f"Circuito nº {dados_ed['numero_fmt']} · {ed['capa']['manchete']}",
              "descricao": ed["capa"]["subtitulo"]}
    return ambiente_jinja().get_template("revista.html.j2").render(
        ed=dados_ed, grupos=grupos, sumario=sumario, expediente=expediente(coleta, ed),
        cotacoes=preparar_cotacoes(coleta.get("cotacoes")), medo=preparar_medo(coleta.get("medo_ganancia")),
        proxima=proxima_edicao(data, numero), css=Markup((PASTA_MODELO / "revista.css").read_text(encoding="utf-8")),
        defs=Markup((PASTA_MODELO / "padroes.svg").read_text(encoding="utf-8")), svg=carregar_svgs(),
        raiz=raiz, teste=teste, previa=previa)


# ---------------------------------------------------------------- publicação

def publicar(html_edicao: str, html_raiz: str, coleta: dict, ed: dict, paginas: list, data: datetime, numero: int):
    dia = data.strftime("%Y-%m-%d")
    gravar_texto(PASTA_SITE / "edicoes" / f"{dia}.html", html_edicao)
    gravar_texto(PASTA_SITE / "index.html", html_raiz)
    gravar_texto(PASTA_SITE / ".nojekyll", "")
    shutil.copyfile(PASTA_MODELO / IMAGEM_PREVIA, PASTA_SITE / IMAGEM_PREVIA)

    publicadas = [e for e in ler_json(ARQ_EDICOES_PUBLICADAS, []) if e["data"] != dia]
    publicadas.append({"data": dia, "numero": numero, "manchete": ed["capa"]["manchete"],
                       "data_extenso": data_extenso(data), "paginas": len(paginas)})
    publicadas.sort(key=lambda e: e["data"], reverse=True)
    gravar_json(ARQ_EDICOES_PUBLICADAS, publicadas)
    gravar_texto(PASTA_SITE / "arquivo.html", ambiente_jinja().get_template("arquivo.html.j2").render(
        edicoes=publicadas, css=Markup((PASTA_MODELO / "revista.css").read_text(encoding="utf-8")),
        previa={"url": SITE_URL + "arquivo.html", "imagem": SITE_URL + IMAGEM_PREVIA,
                "titulo": "Circuito · edições anteriores",
                "descricao": "Revista diária de tecnologia em 5 minutos, de segunda a sábado, às 7h."}))

    estado = ler_json(ARQ_ESTADO, {})
    estado.update(ultimo_fechamento=coleta["janela"]["fim"],
                  ultima_edicao={"data": dia, "numero": numero, "arquivo": f"edicoes/{dia}.json"})
    gravar_json(ARQ_ESTADO, estado)

    vistos = ler_json(ARQ_VISTOS, {})
    for it in coleta["itens"]:
        vistos.setdefault(it["chave"], dia)
    limite = (data - timedelta(days=RETENCAO_VISTOS_DIAS)).strftime("%Y-%m-%d")
    gravar_json(ARQ_VISTOS, {k: v for k, v in vistos.items() if v >= limite})


def atualizar_resumo(coleta: dict, **campos) -> None:
    arq = RAIZ / coleta["resumo_execucao"]
    resumo = ler_json(arq)
    if resumo is None:
        return
    resumo.update(execucao=iso(agora()), **campos)
    gravar_json(arq, resumo)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="data da edição (AAAA-MM-DD); padrão: hoje")
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--validar", action="store_true", help="só confere o texto da edição")
    grupo.add_argument("--teste", action="store_true", help="gera previa/AAAA-MM-DD.html sem publicar")
    args = ap.parse_args()

    dia = args.data or agora().strftime("%Y-%m-%d")
    coleta = ler_json(PASTA_COLETA / f"{dia}.json")
    if coleta is None:
        print(f"Não achei coleta/{dia}.json. Rode antes: python coletor/coletar.py")
        return 1
    ed = ler_json(PASTA_EDICOES / f"{dia}.json")
    if ed is None:
        print(f"Não achei edicoes/{dia}.json. O editor precisa escrever a edição antes (ver CLAUDE.md).")
        return 1

    data = datetime.strptime(dia, "%Y-%m-%d")
    numero, tipo_ed = coleta["edicao"]["numero"], coleta["edicao"]["tipo"]
    links, _ = links_da_coleta(coleta)
    v = Validador(links)
    validar(ed, tipo_ed, v, sabado=teve_sabado(coleta))
    paginas = paginar(ed, numero, tipo_ed, v.erros) if not v.erros else []
    sumario = montar_sumario(paginas, v.erros) if paginas else []

    if v.erros:
        print(f"A edição tem {len(v.erros)} problema(s):")
        for e in v.erros:
            print(f"  - {e}")
        if not args.validar and not args.teste:
            atualizar_resumo(coleta, etapa="falha na validação")
        return 1

    notas = contar_noticias(ed["paginas"])
    print(f"Edição nº {numero:03d} ({tipo_ed}) ok: {len(paginas)} páginas, {notas} notícias, "
          f"~{max(3, round(palavras_no_json(ed) / PALAVRAS_POR_MINUTO))} min de leitura")
    if args.validar:
        return 0

    if args.teste:
        destino = PASTA_PREVIA / f"{dia}.html"
        gravar_texto(destino, renderizar(ed, coleta, paginas, sumario, data, numero, "../site/", True))
        print(f"Prévia: {destino.relative_to(RAIZ).as_posix()}")
        return 0

    html_edicao = renderizar(ed, coleta, paginas, sumario, data, numero, "../", False)
    html_raiz = renderizar(ed, coleta, paginas, sumario, data, numero, "", False)
    publicar(html_edicao, html_raiz, coleta, ed, paginas, data, numero)
    atualizar_resumo(coleta, etapa="edição publicada", **{"edição (número)": numero, "notas publicadas": notas,
                     "páginas": len(paginas), "teste": False})
    print(f"Publicada: site/index.html e site/edicoes/{dia}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())

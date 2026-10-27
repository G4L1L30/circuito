"""Peças compartilhadas pelo coletor e pela montagem da Circuito."""

import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROBO_ID = "circuito_diario"

# Endereço público do site (GitHub Pages). As tags de prévia de link exigem URL absoluta.
SITE_URL = "https://g4l1l30.github.io/circuito/"
IMAGEM_PREVIA = "og-circuito.jpg"

RAIZ = Path(__file__).resolve().parent.parent
PASTA_COLETA = RAIZ / "coleta"
PASTA_EDICOES = RAIZ / "edicoes"
PASTA_ESTADO = RAIZ / "estado"
PASTA_SITE = RAIZ / "site"
PASTA_MODELO = RAIZ / "modelo"
PASTA_RESUMOS = RAIZ / "resumos_execucao"
PASTA_LOGS = RAIZ / "logs_detalhados"
ARQ_FONTES = RAIZ / "fontes" / "fontes.yaml"
ARQ_ESTADO = PASTA_ESTADO / "estado.json"
ARQ_VISTOS = PASTA_ESTADO / "vistos.json"

# O Brasil não tem horário de verão desde 2019; offset fixo evita depender de tzdata no Windows.
BRASILIA = timezone(timedelta(hours=-3), "BRT")

DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def agora() -> datetime:
    return datetime.now(BRASILIA)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(BRASILIA).isoformat(timespec="seconds") if dt else None


def de_iso(texto: str | None) -> datetime | None:
    if not texto:
        return None
    dt = datetime.fromisoformat(texto)
    return dt if dt.tzinfo else dt.replace(tzinfo=BRASILIA)


def novo_execucao_id(inicio: datetime) -> str:
    return f"{inicio.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"


def ler_json(caminho: Path, padrao=None):
    if not caminho.exists():
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def gravar_json(caminho: Path, dados) -> None:
    """Escrita atômica: arquivo temporário na mesma pasta + os.replace()."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=f".{caminho.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, caminho)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def gravar_texto(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=f".{caminho.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        os.replace(tmp, caminho)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def caminho_log_fonte(fonte_id: str, instante: datetime) -> Path:
    return (PASTA_LOGS / "fontes" / instante.strftime("%Y") / instante.strftime("%m")
            / instante.strftime("%d") / f"{fonte_id}_{instante.strftime('%H%M%S')}.json")


def tipo_edicao(data: datetime) -> str:
    """'segunda' cobre o fim de semana e é a maior; domingo não tem edição."""
    return {0: "segunda", 6: "domingo"}.get(data.weekday(), "normal")


def data_extenso(data: datetime) -> str:
    return f"{DIAS_SEMANA[data.weekday()]}, {data.day} de {MESES[data.month - 1]} de {data.year}"

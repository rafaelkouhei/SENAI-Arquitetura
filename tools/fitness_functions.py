"""Fitness functions da seção 8 (equivalente ao ArchUnit em Python).

O backend do Gird the Grid é Python 3.12+ (ADR de Linguagens), então o papel
que o ArchUnit cumpriria em Java fica com este módulo. Ele lê o código-fonte
com ``ast``, sem importar nem executar nada, monta o grafo de dependências
entre componentes e verifica as duas regras validadas da seção 8:

* Regra Validada 1: a camada de Domínio (pacotes ``portas``) não possui
  referência direta para a camada de Infraestrutura (pacotes
  ``implementacao`` e bibliotecas como SQLAlchemy, Kafka e FastAPI);
* Regra Validada 2: todas as classes de repositório (e demais adaptadores de
  saída) implementam uma interface abstrata correspondente de um pacote
  ``portas``.

Componente = ``<modulo>.portas``, ``<modulo>.implementacao`` ou, quando o
módulo não tem essa divisão, o próprio ``<modulo>``. A raiz de composição
(``main.py``, ``composicao``, ``bootstrap``) fica fora da análise, porque é o
único lugar autorizado a instanciar classes concretas.

Uso:
    python tools/fitness_functions.py --raiz src/gird
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

SUBPACOTES = ("portas", "implementacao")
BASES_ABSTRATAS = {"ABC", "Protocol"}
COMPOSICAO_PADRAO = ("composicao", "main", "bootstrap")


@dataclass
class Classe:
    nome: str
    componente: str
    arquivo: str
    abstrata: bool
    bases: list[str] = field(default_factory=list)  # componente de cada base resolvida


@dataclass
class Analise:
    pacote: str
    componentes: list[str]
    dependencias: dict[str, set[str]]  # componente -> componentes internos que ele importa
    externos: dict[str, set[str]]  # componente -> bibliotecas externas importadas
    classes: list[Classe]
    imports_por_arquivo: dict[str, set[str]]  # arquivo -> nomes pontuados importados


# ---------------------------------------------------------------- leitura


def _componente_do_arquivo(rel: Path, composicao: set[str]) -> str | None:
    partes = rel.with_suffix("").parts
    if not partes:
        return None
    modulo = partes[0]
    if len(partes) == 1:
        # arquivo solto na raiz do pacote (ex.: main.py)
        return None if modulo in composicao or modulo == "__init__" else modulo
    if modulo in composicao:
        return None
    if len(partes) >= 3 and partes[1] in SUBPACOTES:
        return f"{modulo}.{partes[1]}"
    if partes[1] in SUBPACOTES:  # ex.: modulo/portas.py
        return f"{modulo}.{partes[1]}"
    return modulo


def _pacote_do_arquivo(pacote: str, rel: Path) -> list[str]:
    partes = list(rel.with_suffix("").parts)
    if partes[-1] == "__init__":
        partes = partes[:-1]
    else:
        partes = partes[:-1]
    return [pacote, *partes]


def _resolver_relativo(pacote: str, rel: Path, nivel: int, modulo: str | None) -> str:
    base = _pacote_do_arquivo(pacote, rel)
    if nivel > 1:
        base = base[: len(base) - (nivel - 1)]
    return ".".join([*base, modulo] if modulo else base)


def _componente_do_import(nome: str, pacote: str, componentes: set[str]) -> str | None:
    partes = nome.split(".")
    if partes[0] != pacote or len(partes) < 2:
        return None
    modulo = partes[1]
    if len(partes) >= 3 and f"{modulo}.{partes[2]}" in componentes:
        return f"{modulo}.{partes[2]}"
    if modulo in componentes:
        return modulo
    # "from gird.modulo import X" num módulo dividido: o que o módulo expõe são as Portas
    if f"{modulo}.portas" in componentes:
        return f"{modulo}.portas"
    return None


def _eh_abstrata(no: ast.ClassDef) -> bool:
    for base in no.bases:
        nome = base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
        if isinstance(base, ast.Subscript):  # Protocol[T]
            valor = base.value
            nome = valor.id if isinstance(valor, ast.Name) else getattr(valor, "attr", None)
        if nome in BASES_ABSTRATAS:
            return True
    for kw in no.keywords:
        if kw.arg == "metaclass":
            nome = kw.value.id if isinstance(kw.value, ast.Name) else getattr(kw.value, "attr", None)
            if nome == "ABCMeta":
                return True
    for item in no.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in item.decorator_list:
                nome = dec.id if isinstance(dec, ast.Name) else getattr(dec, "attr", None)
                if nome == "abstractmethod":
                    return True
    return False


def _vazio(caminho: Path) -> bool:
    corpo = ast.parse(caminho.read_text(encoding="utf-8")).body
    if corpo and isinstance(corpo[0], ast.Expr) and isinstance(getattr(corpo[0], "value", None), ast.Constant):
        corpo = corpo[1:]  # ignora a docstring
    return not corpo


def analisar(
    raiz: str | Path,
    composicao: tuple[str, ...] | list[str] = COMPOSICAO_PADRAO,
) -> Analise:
    raiz = Path(raiz)
    if not raiz.is_dir():
        raise FileNotFoundError(f"pasta do código não encontrada: {raiz}")
    pacote = raiz.name
    composicao_set = set(composicao)

    arquivos: dict[Path, str] = {}
    for caminho in sorted(raiz.rglob("*.py")):
        rel = caminho.relative_to(raiz)
        if caminho.name == "__init__.py" and _vazio(caminho):
            continue  # __init__.py vazio só marca o pacote; não cria componente
        comp = _componente_do_arquivo(rel, composicao_set)
        if comp is not None:
            arquivos[caminho] = comp
    componentes = sorted(set(arquivos.values()))
    comp_set = set(componentes)

    dependencias: dict[str, set[str]] = {c: set() for c in componentes}
    externos: dict[str, set[str]] = {c: set() for c in componentes}
    imports_por_arquivo: dict[str, set[str]] = {}
    classes: list[Classe] = []

    for caminho, comp in arquivos.items():
        rel = caminho.relative_to(raiz)
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        nomes_importados: dict[str, str] = {}  # nome local -> nome pontuado de origem
        importados: set[str] = set()

        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                for alias in no.names:
                    importados.add(alias.name)
                    nomes_importados[alias.asname or alias.name.split(".")[0]] = alias.name
            elif isinstance(no, ast.ImportFrom):
                origem = (
                    _resolver_relativo(pacote, rel, no.level, no.module)
                    if no.level
                    else (no.module or "")
                )
                importados.add(origem)
                for alias in no.names:
                    completo = f"{origem}.{alias.name}"
                    importados.add(completo)
                    nomes_importados[alias.asname or alias.name] = completo

        imports_por_arquivo[str(rel).replace("\\", "/")] = importados
        for nome in importados:
            alvo = _componente_do_import(nome, pacote, comp_set)
            if alvo is not None:
                if alvo != comp:
                    dependencias[comp].add(alvo)
            elif nome.split(".")[0] != pacote:
                externos[comp].add(nome.split(".")[0])

        for no in arvore.body:
            if isinstance(no, ast.ClassDef):
                bases = []
                for base in no.bases:
                    alvo_base = base.value if isinstance(base, ast.Subscript) else base
                    if isinstance(alvo_base, ast.Name) and alvo_base.id in nomes_importados:
                        bc = _componente_do_import(nomes_importados[alvo_base.id], pacote, comp_set)
                        if bc:
                            bases.append(bc)
                    elif isinstance(alvo_base, ast.Name):
                        bases.append(comp)  # base definida no próprio componente
                classes.append(
                    Classe(no.name, comp, str(rel).replace("\\", "/"), _eh_abstrata(no), bases)
                )

    return Analise(
        pacote=pacote,
        componentes=componentes,
        dependencias=dependencias,
        externos=externos,
        classes=classes,
        imports_por_arquivo=imports_por_arquivo,
    )


# ---------------------------------------------------------------- regras

# Bibliotecas de infraestrutura que a camada de Domínio não pode ver.
BIBLIOTECAS_INFRA = frozenset({
    "sqlalchemy", "asyncpg", "psycopg", "psycopg2",
    "confluent_kafka", "aiokafka", "kafka",
    "fastapi", "starlette", "uvicorn",
    "redis", "httpx", "requests", "paho", "grpc",
})

# Nomes que identificam uma classe de repositório ou adaptador de saída.
PREFIXOS_ADAPTADOR = (
    "Repositorio", "Adaptador", "Gateway", "Fila", "Reconciliador",
    "Projecao", "Trilha", "Notificador", "Provedor",
)
SUFIXOS_ADAPTADOR = ("Repository", "Adapter", "Gateway", "Provider", "Repositorio", "Adaptador")


def regra_1_dominio_sem_infraestrutura(analise: Analise) -> list[str]:
    """Regra Validada 1: a camada de Domínio não referencia a camada de Infraestrutura."""
    erros = []
    for comp in analise.componentes:
        if not comp.endswith(".portas"):
            continue
        for alvo in sorted(analise.dependencias[comp]):
            if alvo.endswith(".implementacao"):
                erros.append(f"{comp} importa a camada de infraestrutura {alvo}")
        for lib in sorted(analise.externos[comp] & BIBLIOTECAS_INFRA):
            erros.append(f"{comp} importa a biblioteca de infraestrutura {lib}")
    return erros


def eh_repositorio_ou_adaptador(nome: str) -> bool:
    return nome.startswith(PREFIXOS_ADAPTADOR) or nome.endswith(SUFIXOS_ADAPTADOR)


def regra_2_repositorios_implementam_interface(analise: Analise) -> list[str]:
    """Regra Validada 2: todo repositório implementa uma interface abstrata de um pacote portas."""
    erros = []
    for classe in analise.classes:
        if not classe.componente.endswith(".implementacao") or classe.abstrata:
            continue
        if not eh_repositorio_ou_adaptador(classe.nome):
            continue
        if not any(base.endswith(".portas") for base in classe.bases):
            erros.append(
                f"{classe.nome} ({classe.arquivo}) não implementa nenhuma interface de um pacote portas"
            )
    return erros


REGRAS = (regra_1_dominio_sem_infraestrutura, regra_2_repositorios_implementam_interface)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fitness functions da seção 8")
    p.add_argument("--raiz", default="src/gird", help="pasta do pacote raiz do backend")
    args = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        analise = analisar(args.raiz)
    except FileNotFoundError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2
    falhou = False
    for regra in REGRAS:
        erros = regra(analise)
        titulo = regra.__doc__.split(":")[0]
        print(f"{titulo}: {'REPROVADA' if erros else 'aprovada'}")
        for e in erros:
            print(f"  - {e}")
        falhou = falhou or bool(erros)
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())

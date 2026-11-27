"""Testes de arquitetura da seção 8 (equivalente ao ArchUnit em Python).

Duas partes:

1. ``TestCodigoReal``: aplica a Regra Validada 1 e a Regra Validada 2 ao
   backend em ``src/gird`` (ou na pasta indicada pela variável de ambiente
   ``GIRD_RAIZ``). Enquanto o código não estiver no repositório, esses testes
   aparecem como *skipped*, com o motivo, em vez de passarem sem verificar nada.
2. ``TestAutoteste``: monta projetos sintéticos, um correto e outros com uma
   violação conhecida, e confere que cada regra aprova o correto e reprova o
   errado. É a prova de que o teste não passa por acidente.
"""

from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

import pytest

import fitness_functions as ff

RAIZ_REPO = Path(__file__).resolve().parents[2]
RAIZ_CODIGO = Path(os.environ.get("GIRD_RAIZ", RAIZ_REPO / "src" / "gird"))


# ------------------------------------------------------------------ código real


@pytest.fixture(scope="module")
def analise_real() -> ff.Analise:
    if not RAIZ_CODIGO.is_dir():
        pytest.skip(f"código do backend ainda não está no repositório ({RAIZ_CODIGO})")
    return ff.analisar(RAIZ_CODIGO)


class TestCodigoReal:
    def test_regra_1_dominio_nao_referencia_infraestrutura(self, analise_real):
        assert ff.regra_1_dominio_sem_infraestrutura(analise_real) == []

    def test_regra_2_repositorios_implementam_interface(self, analise_real):
        assert ff.regra_2_repositorios_implementam_interface(analise_real) == []


# ------------------------------------------------------------------ autoteste


def _escrever(raiz: Path, arquivos: dict[str, str]) -> Path:
    pacote = raiz / "gird"
    for caminho, conteudo in arquivos.items():
        destino = pacote / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(dedent(conteudo), encoding="utf-8")
    for pasta in [pacote, *[p for p in pacote.rglob("*") if p.is_dir()]]:
        (pasta / "__init__.py").touch()
    return pacote


PROJETO_CORRETO = {
    "tenants/portas/provedores.py": """
        from typing import Protocol

        class ITenantProvider(Protocol):
            def obter(self, tenant_id: str) -> str: ...
    """,
    "tenants/implementacao/repositorio.py": """
        from gird.tenants.portas.provedores import ITenantProvider

        class RepositorioTenantsMemoria(ITenantProvider):
            def obter(self, tenant_id):
                return tenant_id
    """,
    "ingestao/portas/fila.py": """
        from abc import ABC, abstractmethod

        class IFilaProvider(ABC):
            @abstractmethod
            def publicar(self, evento: dict) -> None: ...
    """,
    "ingestao/implementacao/pipeline.py": """
        from gird.ingestao.portas.fila import IFilaProvider
        from gird.tenants.portas.provedores import ITenantProvider

        class FilaMemoria(IFilaProvider):
            def __init__(self):
                self.eventos = []

            def publicar(self, evento):
                self.eventos.append(evento)

        class PipelineIngestao:
            def __init__(self, fila: IFilaProvider, tenants: ITenantProvider):
                self.fila, self.tenants = fila, tenants
    """,
    "main.py": """
        from gird.ingestao.implementacao.pipeline import FilaMemoria, PipelineIngestao
        from gird.tenants.implementacao.repositorio import RepositorioTenantsMemoria

        pipeline = PipelineIngestao(FilaMemoria(), RepositorioTenantsMemoria())
    """,
}


def _com(**alteracoes: str) -> dict[str, str]:
    """Projeto correto com um arquivo trocado (``a__b__c`` vira ``a/b/c.py``)."""
    projeto = dict(PROJETO_CORRETO)
    projeto.update({k.replace("__", "/") + ".py": v for k, v in alteracoes.items()})
    return projeto


@pytest.fixture
def projeto(tmp_path):
    def montar(arquivos: dict[str, str]) -> ff.Analise:
        return ff.analisar(_escrever(tmp_path, arquivos))
    return montar


class TestAutoteste:
    def test_projeto_correto_passa_nas_duas_regras(self, projeto):
        analise = projeto(PROJETO_CORRETO)
        assert ff.regra_1_dominio_sem_infraestrutura(analise) == []
        assert ff.regra_2_repositorios_implementam_interface(analise) == []

    def test_raiz_de_composicao_fica_fora_da_analise(self, projeto):
        analise = projeto(PROJETO_CORRETO)
        assert "main" not in analise.componentes
        assert analise.componentes == [
            "ingestao.implementacao", "ingestao.portas",
            "tenants.implementacao", "tenants.portas",
        ]

    def test_regra_1_reprova_dominio_que_importa_biblioteca_de_infraestrutura(self, projeto):
        analise = projeto(_com(ingestao__portas__fila="""
            from abc import ABC, abstractmethod
            from confluent_kafka import Producer

            class IFilaProvider(ABC):
                @abstractmethod
                def publicar(self, evento: dict) -> None: ...
        """))
        assert ff.regra_1_dominio_sem_infraestrutura(analise) == [
            "ingestao.portas importa a biblioteca de infraestrutura confluent_kafka"
        ]

    def test_regra_1_reprova_dominio_que_importa_implementacao(self, projeto):
        analise = projeto(_com(tenants__portas__provedores="""
            from typing import Protocol
            from gird.ingestao.implementacao.pipeline import FilaMemoria

            class ITenantProvider(Protocol):
                def obter(self, tenant_id: str) -> str: ...
        """))
        assert ff.regra_1_dominio_sem_infraestrutura(analise) == [
            "tenants.portas importa a camada de infraestrutura ingestao.implementacao"
        ]

    def test_regra_1_reprova_import_relativo_para_implementacao(self, projeto):
        analise = projeto(_com(tenants__portas__provedores="""
            from typing import Protocol
            from ..implementacao.repositorio import RepositorioTenantsMemoria

            class ITenantProvider(Protocol):
                def obter(self, tenant_id: str) -> str: ...
        """))
        assert ff.regra_1_dominio_sem_infraestrutura(analise) == [
            "tenants.portas importa a camada de infraestrutura tenants.implementacao"
        ]

    def test_regra_2_reprova_repositorio_sem_interface(self, projeto):
        analise = projeto(_com(tenants__implementacao__repositorio="""
            class RepositorioTenantsMemoria:
                def obter(self, tenant_id):
                    return tenant_id
        """))
        assert ff.regra_2_repositorios_implementam_interface(analise) == [
            "RepositorioTenantsMemoria (tenants/implementacao/repositorio.py) "
            "não implementa nenhuma interface de um pacote portas"
        ]

    def test_regra_2_reprova_repositorio_que_herda_de_classe_local(self, projeto):
        """Herdar de uma base da própria implementação não conta: a interface tem de vir das Portas."""
        analise = projeto(_com(tenants__implementacao__repositorio="""
            class BaseMemoria:
                pass

            class RepositorioTenantsMemoria(BaseMemoria):
                def obter(self, tenant_id):
                    return tenant_id
        """))
        assert len(ff.regra_2_repositorios_implementam_interface(analise)) == 1

    def test_regra_2_ignora_classes_que_nao_sao_repositorio(self, projeto):
        """PipelineIngestao é serviço de aplicação, não repositório: a regra não se aplica a ele."""
        analise = projeto(PROJETO_CORRETO)
        nomes = {c.nome for c in analise.classes
                 if c.componente.endswith(".implementacao") and ff.eh_repositorio_ou_adaptador(c.nome)}
        assert nomes == {"RepositorioTenantsMemoria", "FilaMemoria"}

    def test_comando_termina_com_codigo_1_quando_ha_violacao(self, tmp_path):
        raiz = _escrever(tmp_path, _com(tenants__implementacao__repositorio="""
            class RepositorioTenantsMemoria:
                pass
        """))
        assert ff.main(["--raiz", str(raiz)]) == 1

    def test_comando_termina_com_codigo_0_no_projeto_correto(self, tmp_path):
        assert ff.main(["--raiz", str(_escrever(tmp_path, PROJETO_CORRETO))]) == 0

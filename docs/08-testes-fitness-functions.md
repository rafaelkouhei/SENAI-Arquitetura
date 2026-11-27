## 8. Testes & Fitness Functions (Governança Automatizada)

### 8.1. Execução das Fitness Functions (ArchUnit)

Para garantir que as regras de dependência entre camadas não sejam violadas no código, executamos testes de arquitetura automatizados:

- **Regra Validada 1:** A camada de Domínio não possui referência direta para a camada de Infraestrutura.
- **Regra Validada 2:** Todas as classes de repositório implementam uma interface abstrata correspondente.

#### Ferramenta: equivalente ao ArchUnit em Python

O ArchUnit é uma biblioteca de Java. O backend do Gird the Grid é escrito em Python 3.12+, conforme a [ADR-005](../adr/ADR-005-stack-gateway-vetorial.md) (Linguagens, frameworks, banco vetorial e stack do API Gateway), que substituiu a proposta inicial de Java com Spring Modulith. Por isso, as fitness functions foram escritas em Python, com `pytest`, e cumprem o mesmo papel do ArchUnit: leem a estrutura do código e reprovam o build quando uma regra de arquitetura é quebrada.

A análise usa o módulo `ast` da biblioteca padrão. O código-fonte é lido como árvore sintática, sem ser importado nem executado, e a partir dele se monta o grafo de dependências entre os componentes da arquitetura Ports & Adapters definida na Sprint 2:

| Camada | Pacote no código | Conteúdo |
| --- | --- | --- |
| Domínio | `<modulo>.portas` | Interfaces (`typing.Protocol` ou `abc.ABC`) |
| Infraestrutura | `<modulo>.implementacao` | Classes concretas: repositórios, filas, gateways |
| Raiz de composição | `main.py`, `composicao`, `bootstrap` | Único ponto que instancia as classes concretas; fica fora da verificação |

| Arquivo | Função |
| --- | --- |
| [`tools/fitness_functions.py`](../tools/fitness_functions.py) | Leitura do código, grafo de dependências e as duas regras |
| [`tests/arquitetura/test_fitness_functions.py`](../tests/arquitetura/test_fitness_functions.py) | Testes `pytest` que aplicam as regras ao código e o autoteste |

#### Como cada regra é verificada

**Regra Validada 1: o Domínio não referencia a Infraestrutura.** Para cada pacote `portas`, o teste reprova se houver:

- import de qualquer pacote `implementacao`, inclusive por import relativo (`from ..implementacao import ...`);
- import de biblioteca de infraestrutura: `sqlalchemy`, `asyncpg`, `psycopg`, `confluent_kafka`, `aiokafka`, `fastapi`, `starlette`, `uvicorn`, `redis`, `httpx`, `requests`, `paho` (MQTT) e `grpc`.

Função: `regra_1_dominio_sem_infraestrutura`. Teste: `test_regra_1_dominio_nao_referencia_infraestrutura`.

**Regra Validada 2: todo repositório implementa uma interface abstrata.** Para cada classe concreta de um pacote `implementacao` cujo nome indica repositório ou adaptador de saída (prefixos `Repositorio`, `Adaptador`, `Gateway`, `Fila`, `Reconciliador`, `Projecao`, `Trilha`, `Notificador`, `Provedor`, ou sufixos `Repository`, `Adapter`, `Gateway`, `Provider`), o teste exige que ao menos uma das classes-base venha de um pacote `portas`. Herdar de uma classe da própria implementação não conta.

Função: `regra_2_repositorios_implementam_interface`. Teste: `test_regra_2_repositorios_implementam_interface`.

#### Autoteste: prova de que os testes reprovam quando devem

Um teste de arquitetura que nunca falha não protege nada. Por isso, a classe `TestAutoteste` monta, em pasta temporária, um projeto sintético no padrão Ports & Adapters e confere dois lados:

| Cenário montado | Resultado esperado |
| --- | --- |
| Projeto correto (Portas só com interfaces, repositórios herdando das Portas) | Regras 1 e 2 aprovadas |
| Porta que importa `confluent_kafka` | Regra 1 reprovada |
| Porta que importa a implementação de outro módulo | Regra 1 reprovada |
| Porta que importa a própria implementação por import relativo | Regra 1 reprovada |
| Repositório sem nenhuma classe-base | Regra 2 reprovada |
| Repositório que herda só de uma classe local da implementação | Regra 2 reprovada |
| Serviço de aplicação (`PipelineIngestao`) sem interface | Fora da Regra 2, por não ser repositório |
| Raiz de composição (`main.py`) instanciando classes concretas | Fora da verificação |
| Comando de linha com violação / sem violação | Termina com código 1 / código 0 |

#### Como executar

```bash
pip install pytest
pytest tests/arquitetura -v
```

As regras também rodam fora do `pytest`, como etapa de pipeline. O comando termina com código 1 quando alguma regra é violada, o que bloqueia o merge:

```bash
python tools/fitness_functions.py --raiz src/gird
```

Por padrão os testes leem `src/gird`. Para apontar outra pasta, basta definir a variável de ambiente `GIRD_RAIZ`.

#### Resultado da execução (26/11/2026)

```text
collected 12 items
TestCodigoReal::test_regra_1_dominio_nao_referencia_infraestrutura               SKIPPED
TestCodigoReal::test_regra_2_repositorios_implementam_interface                  SKIPPED
TestAutoteste::test_projeto_correto_passa_nas_duas_regras                        PASSED
TestAutoteste::test_raiz_de_composicao_fica_fora_da_analise                      PASSED
TestAutoteste::test_regra_1_reprova_dominio_que_importa_biblioteca_de_infraestrutura PASSED
TestAutoteste::test_regra_1_reprova_dominio_que_importa_implementacao            PASSED
TestAutoteste::test_regra_1_reprova_import_relativo_para_implementacao           PASSED
TestAutoteste::test_regra_2_reprova_repositorio_sem_interface                    PASSED
TestAutoteste::test_regra_2_reprova_repositorio_que_herda_de_classe_local        PASSED
TestAutoteste::test_regra_2_ignora_classes_que_nao_sao_repositorio               PASSED
TestAutoteste::test_comando_termina_com_codigo_1_quando_ha_violacao              PASSED
TestAutoteste::test_comando_termina_com_codigo_0_no_projeto_correto              PASSED
10 passed, 2 skipped
```

Os dois testes marcados como *skipped* são os que aplicam as regras ao código do backend. Eles ficam pendentes, com o motivo registrado ("código do backend ainda não está no repositório"), até que a pasta `src/gird` seja integrada à `main`. A partir desse momento passam a rodar sem nenhuma alteração. A escolha por *skip*, e não por aprovação automática, evita que a ausência do código seja confundida com conformidade.

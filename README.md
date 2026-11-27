# Gird the Grid — Plataforma de Monitoramento e Operação Autônoma da Rede Elétrica

> Kata nº 3 · Desafio Final da disciplina de **Arquitetura de Software** — Engenharia de Software,
> Centro Universitário SENAI PR · Prof. Sidney Leandro da Silva

![Python](https://img.shields.io/badge/python-3.12-blue) ![Testes](https://img.shields.io/badge/testes-100%20passando-brightgreen) ![D](https://img.shields.io/badge/dist%C3%A2ncia%20D-0%2C00-brightgreen) ![Estilo](https://img.shields.io/badge/estilo-Mon%C3%B3lito%20Modular-informational)

**Equipe:** Cristoffer Ribeiro Barreto (líder) · Gustavo Fantin · Marcos Vinicius Rocha · Rafael Kouhei Sumiya · Victor Hugo Lipinski de Lima

**Desafio Final:** projetar a ingestão massiva de telemetria IoT (100k+ medidores inteligentes) aliada a um
ciclo autonômico MAPE-K alimentado por IA para auto-otimização e redistribuição automática de carga em caso
de falha em subestação.

| Entregável do Desafio Final | Onde está |
| --- | --- |
| Modelo C4 Nível 2 com API Gateway industrial e Kafka | [§3 · `docs/diagramas/c4-n2-conteineres`](docs/diagramas/c4-n2-conteineres.svg) |
| Diagrama do ciclo MAPE-K com Guardrails de segurança física | [§6.3 · `docs/diagramas/mape-k-guardrails`](docs/diagramas/mape-k-guardrails.svg) |
| ADR de ingestão assíncrona | [ADR-007](docs/adr/ADR-007-ingestao-assincrona.md) |
| Cálculo/relatório automatizado de Instabilidade (I) e Abstração (A) | [§8.2 · `tools/metricas_martin.py`](tools/metricas_martin.py) → [`docs/relatorios/`](docs/relatorios/relatorio_metricas.md) |

---

## Sumário

1. [Introdução e resumo da solução](#1-introdução)
2. [Atributos de qualidade e matriz QAW](#2-atributos-de-qualidade-e-matriz-qaw)
3. [Visão geral da arquitetura (Modelo C4)](#3-visão-geral-da-arquitetura-modelo-c4)
4. [Domain-Driven Design e limites de contexto](#4-domain-driven-design-ddd--limites-de-contexto)
5. [Padrões de projeto e SOLID](#5-padrões-de-projeto--princípios-solid)
6. [Resiliência, integração e IA-native](#6-resiliência-integração-e-ia-native)
7. [ADRs](#7-registros-de-decisões-arquiteturais-adrs)
8. [Testes e fitness functions](#8-testes--fitness-functions-governança-automatizada)
9. [Como executar](#9-como-executar) · [Estrutura do repositório](#10-estrutura-do-repositório) · [Pendências](#11-pendências-e-questões-em-aberto)

---

## 1. Introdução

### 1.1. Contexto do problema

O Gird the Grid moderniza um software de gestão de redes elétricas para vendê-lo como **plataforma
multi-tenant** a distribuidoras com **100 mil a 1,9 milhão de unidades consumidoras**. Requisitos do caso:
dashboards analíticos em **tempo quase real**, **relatórios de tentativas de intrusão**, **disponibilidade de
99,99%** e **segurança máxima**. O Desafio Final faz o sistema deixar de apenas ler dados e passar a **emitir
comandos de manobra** para a rede, o que cria um novo atributo crítico: a **segurança física da operação**.

### 1.2. Resumo da Solução Proposta

A equipe adotou um **Monólito Modular com Ports & Adapters** ([ADR-001](docs/adr/ADR-001-estilo-arquitetural.md)).
O backend é um único artefato de deploy em Python, dividido em módulos de domínio que só se comunicam por
Portas (interfaces). Cada módulo tem um pacote `portas`, totalmente abstrato, e um `implementacao`, totalmente
concreto, o que mantém a distância da sequência principal em **D = 0**, verificada a cada build. O artefato
roda em três **papéis de processo** (Ingestão, API e Autonômico), que escalam e falham de forma independente
sem virar microsserviços. Os dados ficam em PostgreSQL + TimescaleDB + pgvector, um schema por módulo, sem FK
cruzada, com réplicas em três zonas e região secundária para failover.

A ingestão é **assíncrona e orientada a eventos** ([ADR-007](docs/adr/ADR-007-ingestao-assincrona.md)). Os
medidores enviam leituras assinadas na origem por **MQTT (EMQX)** ou **HTTP/gRPC (Kong Gateway)**, ambos com
mTLS. A borda só autentica e enfileira no **Apache Kafka**, particionado por `tenant_id:medidor_id`. Consumidores
aplicam a **Camada Anti-Corrupção** (Factory Method + Adapter), descartam duplicatas, enriquecem e roteiam por
conteúdo (EIPs), gravam em lote no TimescaleDB e mandam o que é inválido para uma **Dead Letter Queue**, com
meta de 0% de perda.

A auto-otimização fica no módulo **Autonômico**, que implementa o ciclo **MAPE-K**
([ADR-008](docs/adr/ADR-008-mape-k-guardrails-fisicos.md)). O Planejador gera planos de manobra por
estratégias intercambiáveis (Strategy), uma delas sugerida por **IA (LLM + RAG + Model Tiering)**. Nenhum
plano chega à rede sem passar pela cadeia determinística de **Guardrails de segurança física** — limite
térmico, faixa de tensão (PRODIST Módulo 8), reserva N-1, intertravamento e taxa de manobras — e planos fora do
envelope automático exigem aprovação humana. **A IA propõe; o sistema determinístico decide.**

---

## 2. Atributos de Qualidade e Matriz QAW

Prioridade do QAW (Sprint 1): **Tier 1** Segurança, Disponibilidade e (novo) Segurança física · **Tier 2**
Desempenho, Escalabilidade · **Tier 3** Confiabilidade, Auditabilidade · **Tier 4** Modificabilidade.
As métricas abaixo são **metas de projeto** (premissas a validar em teste de carga), exceto os 99,99%, que vêm do caso.

| Atributo de Qualidade | Cenário Padronizado (Fonte → Estímulo → Artefato → Ambiente → Resposta) | Medida da Resposta (Métrica Objetivo) |
| --- | --- | --- |
| Desempenho / Latência (DES-03) | 1.000 operadores → 500 req/s no dashboard → API (papel API) → carga normal → resposta a partir de agregados e cache | **p95 < 250 ms**, p99 < 500 ms |
| Desempenho / Tempo quase real (DES-02) | Medidor → envia leitura → gateway, Kafka, agregação → operação normal → valor exibido via WebSocket | Ponta a ponta **p95 ≤ 5 s** |
| Disponibilidade / Resiliência (DISP-05) | Provedor de LLM → fica lento ou fora do ar → `AssistentePlanejamentoIA` → pico de incidente → **Retry + Circuit Breaker** abre; ciclo segue com estratégias determinísticas | Breaker abre após 5 falhas; **0 manobras bloqueadas** pela falha da IA; dashboard disponível |
| Disponibilidade (DISP-01) | Falha de hardware/software → nó ou zona para → réplicas, Kafka, banco → produção → failover automático | **99,99%/ano** (≤ 52,56 min); RTO ≤ 30 s na região; Kafka RF=3, `min.insync.replicas`=2 |
| Disponibilidade / DR (DISP-04) | Desastre → região indisponível → plataforma → produção → promoção da região secundária | RPO ≤ 1 min; RTO ≤ 5 min |
| Escalabilidade / Elasticidade (DES-01, DES-04) | Incidente → ingestão salta de 31.667 para 95.000 eventos/s por 10 min → Kafka + consumidores → pico → Kafka absorve; consumidores escalam pelo lag (KEDA) | **0% de perda**; novas réplicas em ≤ 60 s; lag normalizado em ≤ 5 min |
| Escalabilidade / Onboarding (ESC-01) | Área comercial → nova distribuidora → módulo Tenants → produção → provisionamento por configuração | Nenhum deploy; < 1 h |
| Segurança / Isolamento (SEG-04) | Operador do tenant A → pede dados do tenant B → Kong + `ITenantProvider` → normal → acesso negado e auditado | **0 exposições cruzadas**; evento auditado < 1 s |
| Segurança / Dispositivos (SEG-02) | Certificado forjado/revogado → publica telemetria → EMQX/Kong mTLS → produção → conexão recusada | 100% recusadas; incidente registrado < 5 s |
| Confiabilidade (CONF-01) | Medidor sem rede por 2 h → reenvia (store-and-forward) → Ingestão + Reconciliador → recuperação → lacunas preenchidas | 0% de perda; 100% das duplicatas descartadas |
| Segurança física (SAF-01) | Proteção → SE-X sai de operação → MAPE-K + Guardrails → incidente → plano validado; executa se dentro do envelope, senão vai ao operador | Plano validado ≤ 60 s; **0 manobras fora do envelope** |
| Segurança física (SAF-02) | IA → propõe plano com sobrecarga ou malformado → JSON Schema + Guardrails → incidente → plano rejeitado; fallback determinístico | 100% dos planos inválidos rejeitados e auditados |
| Auditabilidade (AUD-01) | SOC/regulador → reconstrução de incidente → trilha append-only → pós-incidente → relatório completo | 100% dos comandos rastreáveis; hash encadeado verificável |
| Modificabilidade (Tier 4) | Equipe → novo algoritmo de redistribuição → módulo Autonômico → desenvolvimento → nova `IEstrategiaRedistribuicao` | 0 classes existentes alteradas; **D ≤ 0,1** em todos os componentes |

Documento completo do QAW (stakeholders, BOTE, riscos): [`docs/historico/Sprint1_QAW.pdf`](docs/historico/Sprint1_QAW.pdf).

---

## 3. Visão Geral da Arquitetura (Modelo C4)

A arquitetura está documentada conforme as abstrações do Modelo C4 (fontes Mermaid editáveis em `.mmd`):

- 📄 **Nível 1 — Diagrama de Contexto:** [`docs/diagramas/c4-n1-contexto.svg`](docs/diagramas/c4-n1-contexto.svg) ([fonte](docs/diagramas/c4-n1-contexto.mmd))
- 📄 **Nível 2 — Diagrama de Contêineres:** [`docs/diagramas/c4-n2-conteineres.svg`](docs/diagramas/c4-n2-conteineres.svg) ([fonte](docs/diagramas/c4-n2-conteineres.mmd))
- 📄 **Nível 3 — Diagrama de Componentes (papel Ingestão):** [`docs/diagramas/c4-n3-componentes-ingestao.svg`](docs/diagramas/c4-n3-componentes-ingestao.svg) ([fonte](docs/diagramas/c4-n3-componentes-ingestao.mmd))
- 📄 **Componentes do papel Autonômico (MAPE-K):** [`docs/diagramas/mape-k-guardrails.svg`](docs/diagramas/mape-k-guardrails.svg) ([fonte](docs/diagramas/mape-k-guardrails.mmd))

Notação: azul-escuro = pessoa; azul = contêiner/componente; destaque com borda grossa = API Gateway industrial
e Kafka; cilindro = armazenamento; cinza = sistema externo. Toda seta traz a intenção e o protocolo entre colchetes.

### Visualização do Diagrama de Contexto (C4 - Nível 1)

![C4 Nível 1](docs/diagramas/c4-n1-contexto.svg)

### Visualização do Diagrama de Contêineres (C4 - Nível 2)

A borda só autentica e enfileira; o Kafka separa recebimento de processamento. Caminho de uma leitura:
medidor → EMQX/Kong → Kafka (`telemetria.bruta`) → papel Ingestão (ACL, EIPs) → Kafka (`telemetria.recebida`,
`telemetria.processada`) → TimescaleDB. Só o papel Autonômico sai para o SCADA, e sempre pelo Gateway OT.

![C4 Nível 2](docs/diagramas/c4-n2-conteineres.svg)

| Contêiner | Tecnologia | Protocolos | Responsabilidade |
| --- | --- | --- | --- |
| Broker MQTT de borda | EMQX (cluster, 3 zonas) | MQTT + mTLS → Kafka | Conexões dos medidores; bridge para `telemetria.bruta` |
| **API Gateway industrial** | **Kong Gateway** | HTTP/gRPC + mTLS (dispositivos); REST/WebSocket + JWT (operadores) | Autenticação, rate limiting por tenant e dispositivo, roteamento |
| Provedor de identidade | Keycloak | OIDC/JWKS | JWT, MFA, papéis por tenant |
| **Plataforma de eventos** | **Apache Kafka** (RF=3) + Schema Registry | Kafka protocol | Fronteira assíncrona; telemetria, proteção, planos, alertas, DLQ |
| Gird — papel Ingestão | Python 3.12 | Kafka, SQL COPY | ACL, idempotência, EIPs, DLQ; escala pelo lag (KEDA) |
| Gird — papel API | Python 3.12, FastAPI | REST, WebSocket, SQL | Apresentação, Tenants, Monitoramento, Segurança e Auditoria |
| Gird — papel Autonômico | Python 3.12 | Kafka, gRPC (Gateway OT), HTTPS (LLM) | MAPE-K, Guardrails, IA; 1 líder por tenant |
| Dashboard Web | React SPA | HTTPS, WebSocket | Painéis e fila de aprovação de planos |
| Banco | PostgreSQL + TimescaleDB + pgvector | SQL | Schema por módulo; séries temporais; embeddings do RAG |
| Cache | Redis | RESP | Sessões, chaves de idempotência |
| Arquivo de auditoria | Object storage WORM | S3 API (object lock) | Cópia imutável da trilha |
| Gateway OT | Conversor IEC 104 / DNP3 em DMZ | gRPC → IEC 60870-5-104 / DNP3 | Lista de comandos permitidos; select-before-operate |

### Visualização do Diagrama de Componentes (C4 - Nível 3, papel Ingestão)

![C4 Nível 3](docs/diagramas/c4-n3-componentes-ingestao.svg)

---

## 4. Domain-Driven Design (DDD) & Limites de Contexto

- Documentação completa em [ADR-004](docs/adr/ADR-004-bounded-contexts-acl.md), na
  [Prática Laboratorial da Sprint 3](docs/historico/Sprint3_Pratica_Laboratorial_Integracao.pdf) e na
  [Arquitetura de Dados](docs/historico/Sprint3_Distribuicao_dos_Dados.pdf).

### 4.1. Classificação dos Subdomínios

- **Core Domain (Domínio Principal):** Operação Autônoma — ciclo MAPE-K de redistribuição de carga com Guardrails físicos (`gird.autonomico`) — e Monitoramento da Rede em tempo quase real (`gird.monitoramento`).
- **Supporting Subdomain (Suporte):** Ingestão e Normalização de Telemetria (`gird.ingestao`), Ocorrências e Alertas, Segurança e Auditoria (`gird.seguranca`), Gestão de Tenants (`gird.tenants`), Cadastro Técnico e Geográfico, Integração Regulatória, Dashboard (`gird.apresentacao`).
- **Generic Subdomain (Genérico):** Autenticação SSO (Keycloak), API Gateway (Kong), broker MQTT (EMQX), streaming (Kafka), séries temporais (TimescaleDB), provedores de LLM (atrás de `gird.ia`).

### 4.2. Mapa de Contexto e Camada Anti-Corrupção (ACL)

O sistema integra-se a dispositivos e serviços legados utilizando o padrão **Anti-Corruption Layer (ACL)** com
a implementação de adaptadores GoF (**Adapter Pattern**) localizados em
[`src/gird/ingestao/implementacao/acl/`](src/gird/ingestao/implementacao/acl/adaptadores.py) e
[`src/gird/autonomico/implementacao/acl_scada.py`](src/gird/autonomico/implementacao/acl_scada.py), isolando a
Linguagem Ubíqua do núcleo do sistema: um fabricante chama o medidor de `id_meter`, outro de `device_code`, o
concentrador legado manda XML — o domínio só conhece `LeituraTelemetria.medidor_id`.

| Relação | Padrão de contexto | Implementação |
| --- | --- | --- |
| Fabricantes de medidores → Ingestão | ACL | `AdaptadorFabricanteA`, `AdaptadorFabricanteB`, `AdaptadorConcentradorLegadoXml` |
| Autonômico → SCADA/ADMS legado | ACL | `AdaptadorScadaLegadoXml` (`Manobra` ↔ XML do SCADA) |
| Autonômico → provedor de LLM | ACL | `IModeloLinguagem` + `SanitizadorPII` |
| Ingestão → demais contextos | Published Language | Evento canônico versionado em `telemetria.recebida` |
| Tenants → todos | Open Host Service | `ITenantProvider`, `IUnidadeConsumidoraProvider` |
| Monitoramento → Autonômico · IA → Autonômico | Customer / Supplier | `IMonitoramentoDataProvider` · `IAssistentePlanejamento` |
| Todos | Shared Kernel mínimo | `gird.nucleo` (objetos de valor imutáveis, Circuit Breaker) |

---

## 5. Padrões de Projeto & Princípios SOLID

A estrutura vem da [Matriz de Decisão](docs/historico/Sprint2_Matriz_de_Decisao.xlsx) da Sprint 2: a variante
V3 (SRP + DIP + ISP) obteve **115 pontos**, contra 98 (V2) e 41 (V1, sem interfaces).

### 5.1. Princípios SOLID Aplicados

- **Dependency Inversion Principle (DIP):** o domínio declara interfaces de repositórios e serviços
  ([`src/gird/*/portas/contratos.py`](src/gird/autonomico/portas/contratos.py) — `ITenantProvider`, `IFilaProvider`,
  `IGatewayManobra`, `IRegistroAuditoria`…), enquanto a infraestrutura provê a implementação concreta
  ([`src/gird/*/implementacao/`](src/gird/ingestao/implementacao) — `RepositorioTenantsMemoria`, `FilaKafka`,
  `AdaptadorScadaLegadoXml`, `TrilhaAuditoriaEncadeada`…). Só [`composition_root.py`](src/gird/composition_root.py) instancia classes concretas.
- **Open/Closed Principle (OCP):** extensão de novos algoritmos de negócio via polimorfismo sem alteração das
  classes mestres — uma nova estratégia de redistribuição é uma nova `IEstrategiaRedistribuicao`; um novo
  protocolo de medidor é uma nova subclasse de `CriadorConector`; um novo guardrail entra na `CadeiaGuardrails`.
- **ISP:** o Autonômico enxerga da IA apenas `IAssistentePlanejamento.sugerir_plano()`.
- **SRP:** quem planeja não executa; quem executa não decide se o plano é seguro.
- **LSP:** `FilaEmMemoria` ↔ `FilaKafka`, `ModeloSimulado` ↔ LLM real — os testes rodam com os dublês, sem rede.

### 5.2. Catálogo de Padrões GoF Utilizados

| Padrão GoF | Categoria | Localização no Código (`src/gird/`) | Problema de Engenharia Resolvido |
| --- | --- | --- | --- |
| **Factory Method** | Criacional | [`ingestao/portas/contratos.py`](src/gird/ingestao/portas/contratos.py) (`CriadorConector`) · [`ingestao/implementacao/conectores/fabrica.py`](src/gird/ingestao/implementacao/conectores/fabrica.py) | Instanciação dinâmica de conectores/adaptadores de integração por protocolo e fabricante, sem acoplamento a classes concretas. |
| **Adapter** | Estrutural | [`ingestao/implementacao/acl/adaptadores.py`](src/gird/ingestao/implementacao/acl/adaptadores.py) · [`autonomico/implementacao/acl_scada.py`](src/gird/autonomico/implementacao/acl_scada.py) | Tradução de payloads JSON proprietários e XML de sistemas legados (concentradores, SCADA) para o modelo canônico do domínio e de volta. |
| **Strategy** | Comportamental | [`autonomico/portas/contratos.py`](src/gird/autonomico/portas/contratos.py) (`IEstrategiaRedistribuicao`) · [`autonomico/implementacao/estrategias.py`](src/gird/autonomico/implementacao/estrategias.py) | Eliminação de if/else para alternar algoritmos de redistribuição (maior margem, só prioritários, sugerida por IA). |
| **Composite** | Estrutural | [`autonomico/implementacao/guardrails_fisicos.py`](src/gird/autonomico/implementacao/guardrails_fisicos.py) (`CadeiaGuardrails`) | Tratar os cinco guardrails como um só: uma chamada `verificar()` devolve todas as violações. |
| **Template Method** | Comportamental | [`ingestao/portas/contratos.py`](src/gird/ingestao/portas/contratos.py) (`CriadorConector.normalizar`) | Fixa o algoritmo de normalização; só a criação do adaptador varia. |

---

## 6. Resiliência, Integração e IA-Native

### 6.1. Padrões de Resiliência Aplicados

- **Circuit Breaker & Fallback:** implementado em [`src/gird/nucleo/resiliencia.py`](src/gird/nucleo/resiliencia.py)
  (equivalente Python ao Polly; em produção, `pybreaker`) nas chamadas síncronas que podem travar workers
  (*thread starvation*): LLM (5 falhas → aberto 60 s → fallback para estratégias determinísticas) e SCADA
  (3 falhas → aberto 30 s → rollback das manobras e alarme).
- **Retry com backoff exponencial:** `com_retentativas` (equivalente ao `tenacity`), usado dentro do breaker na
  chamada ao LLM: falha transitória é repetida; falha persistente abre o circuito.
- **Nivelamento de Carga (Load Leveling):** o Kafka absorve picos de concorrência entre a borda e o
  processamento; mensagens inválidas vão para a **Dead Letter Queue** `telemetria.dlq` (14 dias, reprocessável).
- **Idempotência e reconciliação**, **Bulkhead** (três papéis de processo), **Compensação** (rollback em ordem
  inversa) e **redundância** (3 zonas, região secundária).

**Enterprise Integration Patterns** ([`ingestao/implementacao/eip.py`](src/gird/ingestao/implementacao/eip.py)):
**Splitter** (lotes → eventos), **Content Enricher** (subestação, alimentador e tensão em pu a partir de cache do
cadastro técnico), **Content-Based Router** (`telemetria.processada` / `monitoramento.anomalias` /
`alertas.criticos`) e **Dead Letter Channel**.

### 6.2. Componente de Inteligência Artificial Generativa

- **Arquitetura AI-Native:** **RAG** sobre pgvector (procedimentos de manobra, manuais, histórico de
  incidentes) e **Model Tiering** com o `RoteadorModelos` (modelo pequeno para classificar/resumir, grande para
  planejar e redigir relatórios). **Sem multi-agentes**: o ciclo MAPE-K é o orquestrador e um agente de papel
  restrito é mais fácil de auditar ([ADR-006](docs/adr/ADR-006-ia-guardrails.md)).
- **Guardrails & Segurança:** saídas estruturadas validadas via **JSON Schema** (`ESQUEMA_PLANO_MANOBRA`, sem
  campos extras, ≤ 10 manobras) e higienização prévia de **PII** (CPF, CNPJ, e-mail, telefone, código de UC)
  antes do envio aos modelos — [`src/gird/ia/implementacao/guardrails_ia.py`](src/gird/ia/implementacao/guardrails_ia.py).
- **Limite de autoridade:** a saída da IA é sempre proposta; passa pelos mesmos Guardrails físicos de qualquer
  estratégia. Uma fitness function garante que guardrails, executor e ACL do SCADA não importam `gird.ia`.

### 6.3. Ciclo Autonômico MAPE-K com Guardrails de Segurança Física

![MAPE-K](docs/diagramas/mape-k-guardrails.svg)

| Guardrail | Regra | Violação |
| --- | --- | --- |
| Intertravamento | Chave existe, liga origem e destino, não está bloqueada (equipe em campo), destino fora da SE em falha | Bloqueia |
| Conservação de carga | Transferência ≤ 105% da carga medida (a IA não pode “inventar” carga) | Bloqueia |
| Limite térmico | Carregamento final ≤ 100% da capacidade nominal | Bloqueia |
| Reserva N-1 | Carregamento final entre 90% e 100% | Exige aprovação humana |
| Faixa de tensão | Tensão estimada 0,93–1,05 pu (PRODIST Módulo 8, 1 kV < V < 69 kV) | Bloqueia |
| Taxa de manobras | ≤ 6 manobras/plano; ≤ 3 planos por SE em 15 min | Bloqueia |
| Envelope automático | ≤ 4 manobras e ≤ 20 MW sem humano | Exige aprovação humana |

Simulação de referência (`python -m gird.composition_root`): a queda da SE-NORTE transfere 18 MW (três
alimentadores, um deles hospital) para SE-SUL e SE-LESTE com três manobras; a chave CH-06, com equipe em campo,
nunca é comandada; a trilha de auditoria verifica íntegra.

---

## 7. Registros de Decisões Arquiteturais (ADRs)

Todas as decisões estratégicas e seus trade-offs estão registrados na pasta [`docs/adr/`](docs/adr/) no formato
Título · Contexto · Decisão · Alternativas rejeitadas · Consequências/trade-offs · Conformidade:

| ADR | Título da Decisão Arquitetural | Status | Origem |
| --- | --- | --- | --- |
| [ADR-001](docs/adr/ADR-001-estilo-arquitetural.md) | Adoção do Estilo Arquitetural (Monólito Modular vs. Microsserviços) | Aceita | Sprint 2–3 |
| [ADR-002](docs/adr/ADR-002-desacoplamento-dip-gof.md) | Estratégia de Desacoplamento de Código com DIP e Padrões GoF | Aceita | Sprint 2 |
| [ADR-003](docs/adr/ADR-003-protocolos-integracao.md) | Definição dos Protocolos de Integração (MQTT, gRPC, REST, Kafka) | Proposta | Sprint 1–3 |
| [ADR-004](docs/adr/ADR-004-bounded-contexts-acl.md) | Mapeamento de Contextos Delimitados e Camada Anti-Corrupção | Proposta | Sprint 3 |
| [ADR-005](docs/adr/ADR-005-stack-gateway-vetorial.md) | Seleção de Frameworks, Banco Vetorial e Stack do API Gateway | Proposta | Sprint 3 |
| [ADR-006](docs/adr/ADR-006-ia-guardrails.md) | Integração de Componentes Probabilísticos e Guardrails de IA | Proposta | Sprint 4 |
| [ADR-007](docs/adr/ADR-007-ingestao-assincrona.md) | Ingestão Assíncrona de Telemetria IoT via Kafka | Proposta | Desafio Final |
| [ADR-008](docs/adr/ADR-008-mape-k-guardrails-fisicos.md) | Ciclo Autonômico MAPE-K com Guardrails de Segurança Física | Proposta | Desafio Final |

As ADRs S1-001 a S1-010 da Sprint 1 seguem como decisões de base ([índice](docs/adr/README.md)).

---

## 8. Testes & Fitness Functions (Governança Automatizada)

**100 testes passando**: 75 fitness functions de arquitetura + 25 testes unitários (ingestão, EIPs, resiliência,
MAPE-K, guardrails, IA, multi-tenant). Tudo roda em [`.github/workflows/ci.yml`](.github/workflows/ci.yml) e
bloqueia o merge em caso de falha.

### 8.1. Execução das Fitness Functions (ArchUnit → Python)

O backend é Python ([ADR-005](docs/adr/ADR-005-stack-gateway-vetorial.md)), onde o ArchUnit (Java) não se aplica.
O mesmo papel é cumprido por [`tests/arquitetura/test_fitness_functions.py`](tests/arquitetura/test_fitness_functions.py),
que inspeciona o código com `ast`/`inspect` no estilo ArchUnit, e pelos contratos do **import-linter** em
[`pyproject.toml`](pyproject.toml). Para garantir que as regras de dependência entre camadas não sejam violadas:

- **Regra Validada 1:** a camada de Domínio (`portas`) não possui referência direta para a camada de Infraestrutura (`implementacao`, `confluent_kafka`, `sqlalchemy`, `fastapi`…).
- **Regra Validada 2:** todas as classes de repositório/adaptador (`Repositorio*`, `Adaptador*`, `Fila*`, `Gateway*`…) implementam uma interface abstrata correspondente de um pacote `portas`.
- **Regra 3:** nenhum módulo importa a Implementação de outro; só a raiz de composição vê classes concretas.
- **Regra 4 (segurança física):** guardrails, executor e ACL do SCADA não importam nada de `gird.ia`.
- **Regra 5:** D ≤ 0,1 em todos os componentes e nenhuma violação do Princípio das Dependências Estáveis.
- **Regra 6:** todo pacote `portas` tem A = 1 e Ce = 0.
- **Autoteste do gate:** um projeto sintético com uma Porta concreta precisa reprovar.

### 8.2. Cálculo e relatório automatizado de Instabilidade (I) e Abstração (A)

[`tools/metricas_martin.py`](tools/metricas_martin.py) lê o código com `ast` (sem importá-lo), identifica os
componentes e gera [`relatorio_metricas.md`](docs/relatorios/relatorio_metricas.md),
[`metricas.json`](docs/relatorios/metricas.json) e o gráfico [`sequencia_principal.svg`](docs/relatorios/sequencia_principal.svg).
Sai com código 1 se D > limite ou se houver violação do SDP — por isso também é fitness function.

`I = Ce / (Ca + Ce)` · `A = Na / Nc` · `D = |A + I − 1|`

| Componente | Nc | Na | A | Ca | Ce | I | D |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `*.portas` (tenants, ingestao, monitoramento, seguranca, ia, autonomico) | 25 | 25 | 1,00 | 1–3 | 0 | 0,00 | **0,00** |
| `*.implementacao` + `apresentacao` (7 componentes) | 47 | 0 | 0,00 | 0 | 1–4 | 1,00 | **0,00** |
| `nucleo` (kernel não-volátil, fora do gate) | 14 | 0 | 0,00 | 8 | 0 | 0,00 | 1,00 |

Tabela completa por componente no [relatório gerado](docs/relatorios/relatorio_metricas.md). O núcleo
compartilhado fica na Zona de Dor por construção (concreto e muito usado) — exceção declarada (`--kernel`) por
conter só objetos de valor imutáveis, o caso de componentes não voláteis descrito por Martin (2019).

![Sequência principal](docs/relatorios/sequencia_principal.svg)

---

## 9. Como executar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # a demo e os testes não têm dependências de runtime

pytest -q                          # 100 testes (fitness functions + unitários)
python -m gird.composition_root    # simula a falha da SE-NORTE e o ciclo MAPE-K
python tools/metricas_martin.py --raiz src/gird --saida docs/relatorios --limite-d 0.1
lint-imports                       # contratos de dependência (import-linter)
mypy                               # tipagem estrita das Portas

# regenerar os diagramas (Mermaid CLI)
npx @mermaid-js/mermaid-cli -i docs/diagramas/c4-n2-conteineres.mmd -o docs/diagramas/c4-n2-conteineres.svg
```

Os adaptadores de produção (Kafka, PostgreSQL, LLM via HTTP) importam suas bibliotecas de forma tardia
(`pip install -e ".[producao]"`); os testes usam os adaptadores em memória.

## 10. Estrutura do repositório

```
.
├── src/gird/
│   ├── nucleo/              Shared Kernel: objetos de valor + Circuit Breaker/Retry
│   ├── tenants/             portas/ · implementacao/   Gestão de Tenants
│   ├── ingestao/            portas/ · implementacao/{acl, conectores, eip, pipeline, fila_kafka}
│   ├── monitoramento/       portas/ · implementacao/   Projeção do estado da rede e alarmes
│   ├── seguranca/           portas/ · implementacao/   Trilha de auditoria com hash encadeado
│   ├── ia/                  portas/ · implementacao/   RAG, Model Tiering, PII, JSON Schema
│   ├── autonomico/          portas/ · implementacao/   MAPE-K, Strategy, Guardrails, ACL SCADA
│   ├── apresentacao/        API do Dashboard
│   └── composition_root.py  Raiz de composição + simulação
├── tests/
│   ├── arquitetura/         Fitness functions (estilo ArchUnit)
│   └── unit/                Testes unitários
├── tools/metricas_martin.py Relatório automatizado de Ca, Ce, I, A, D
├── docs/
│   ├── adr/                 ADR-001 a ADR-008
│   ├── diagramas/           C4 N1, N2, N3 e MAPE-K (.mmd + .svg + .png)
│   ├── relatorios/          Métricas geradas (md, json, svg, png)
│   └── historico/           Artefatos originais das Sprints 1 a 4
├── .github/workflows/ci.yml Pipeline de governança
└── pyproject.toml           Dependências, pytest, mypy, contratos do import-linter
```

## 11. Pendências e questões em aberto

- [ ] Teste de carga com 31.667 e 95.000 eventos/s para calibrar partições (96) e consumidores.
- [ ] Calibrar o envelope operacional com cada distribuidora (o modelo de queda de tensão é linear e simplificado).
- [ ] Implementar o módulo de Integração Regulatória e a ACL do cadastro técnico legado.
- [ ] Avaliar requisitos de segurança OT para o Gateway OT (ex.: série IEC 62443).
- [ ] Confirmar se o SLA de 99,99% é medido por tenant ou pela plataforma.

## Referências

- KEPHART, J. O.; CHESS, D. M. The vision of autonomic computing. *Computer*, 36(1), 2003.
- MARTIN, R. C. *Arquitetura limpa*. Alta Books, 2019.
- RICHARDS, M.; FORD, N. *Fundamentals of Software Architecture*. O'Reilly, 2020.
- HOHPE, G.; WOOLF, B. *Enterprise Integration Patterns*. Addison-Wesley, 2003.
- ANEEL. PRODIST — Módulo 8: Qualidade da Energia Elétrica.

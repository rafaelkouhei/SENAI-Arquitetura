# ADR-005 — Linguagens, frameworks, banco vetorial e stack do API Gateway

- **Status:** Proposta
- **Origem:** Sprint 3 (ADR 005 — Kong, EMQX, Kafka, Keycloak; ADR 3 — Linguagens por camada) e Desafio Final (pgvector)
- **Substitui:** a indicação de Java com Spring Modulith da Macroarquitetura (Sprint 3, §1.4)
- **Cenários QAW:** SEG-01 a SEG-04, DES-01 a DES-03, DISP-01

## Contexto

Três ambientes de execução muito diferentes (firmware, navegador e backend), um backend com forte
componente de análise de dados e IA, uma borda que precisa de mTLS, rate limiting e autenticação para
dispositivos e pessoas, e o RAG da ADR-006, que precisa de um banco vetorial. A equipe tem cinco pessoas.

## Decisão

| Camada | Escolha | Motivo principal |
| --- | --- | --- |
| Firmware | C++17 (subconjunto embarcado), mbedTLS | Memória e latência previsíveis; assinatura na origem; Ports & Adapters com classes abstratas. |
| Frontend | JavaScript + React (SPA) | Nativo do navegador; WebSocket e bibliotecas de séries temporais maduras. |
| Backend | Python 3.12, FastAPI, SQLAlchemy/asyncpg, cliente Kafka sobre librdkafka | Produtividade da equipe e ecossistema de dados/IA; I/O-bound na ingestão. |
| Verificação de módulos | import-linter + fitness functions em pytest | Papel que o Spring Modulith/ArchUnit teriam em Java. |
| API Gateway industrial | **Kong Gateway** | mTLS, JWT/OIDC, rate limiting por consumidor, plugins de observabilidade. |
| Broker MQTT | **EMQX** (cluster) | Milhões de conexões, bridge nativa para Kafka. |
| Identidade | **Keycloak** | OIDC, MFA, papéis por tenant. |
| Banco | PostgreSQL + **TimescaleDB** | Um só motor para dados relacionais e séries temporais (continuous aggregates). |
| Banco vetorial | **pgvector** no mesmo PostgreSQL (schema `ia`) | Embeddings com o mesmo backup, replicação, failover e controle de acesso por tenant. |

## Alternativas rejeitadas

| Alternativa | Por que foi rejeitada |
| --- | --- |
| Java + Spring Modulith | Ótima verificação de módulos e desempenho, mas mais código de infraestrutura e ecossistema de dados menos direto; com a equipe como recurso escasso, a produtividade pesou mais. |
| Go no backend | Excelente para ingestão concorrente, mas abstrações de domínio verbosas e ecossistema de IA limitado. |
| YARP (.NET) como gateway | Faria sentido numa stack .NET; não oferece mTLS de dispositivos e rate limiting prontos no nível do Kong. |
| Banco vetorial dedicado (Pinecone, Weaviate, Milvus) | Mais um sistema para operar e outro ponto de falha no SLA de 99,99%; o volume de documentos do RAG cabe no pgvector. |
| Rust ou MicroPython no firmware | Rust: suporte irregular nos SDKs de fabricantes; MicroPython: coletor de lixo imprevisível em dispositivos que ficam anos ligados. |

## Consequências

**Positivas** — cada camada usa a linguagem do seu ambiente; um único motor de banco para operar; borda
com produtos maduros.

**Negativas / trade-offs** — tipagem dinâmica do Python (mitigada por `mypy --strict` nas Portas e Pydantic);
GIL (mitigado por vários workers e I/O assíncrono); três linguagens aumentam a carga cognitiva; pgvector
pode precisar ser revisto se o corpus do RAG crescer muito.

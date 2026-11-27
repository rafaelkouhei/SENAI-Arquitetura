# ADR-001 — Estilo arquitetural: Monólito Modular (vs. Microsserviços), com três papéis de processo

- **Status:** Aceita
- **Origem:** Sprint 2 (ADR 2) e Sprint 3 (Definição da Macroarquitetura); papéis de processo acrescentados no Desafio Final
- **Decisores:** equipe Gird the Grid
- **Cenários QAW:** ESC-01, ESC-02, DISP-01, DISP-02, DES-01

## Contexto

O Gird the Grid é um único produto comercial multi-tenant para distribuidoras com 100 mil a 1,9 milhão
de unidades consumidoras. Os direcionadores Tier 1 são Segurança e Disponibilidade (99,99% ≈ 52,56 min/ano);
os Tier 2 são Desempenho (tempo quase real) e Escalabilidade (111 a 31.667 eventos/s no BOTE).
O orçamento de infraestrutura não é restrição; o recurso escasso é a equipe de cinco pessoas.
O Desafio Final acrescenta um ciclo autônomo que comanda manobras na rede e precisa de isolamento
de falhas em relação à ingestão e ao dashboard.

## Decisão

Adotar um **Monólito Modular com Ports & Adapters**: uma única base de código e um único artefato de
deploy, dividido em módulos de domínio que só se comunicam por Portas (ver ADR-002), com um banco
PostgreSQL e um schema por módulo, sem FK cruzada.

O artefato roda em **três papéis de processo**, escalados e isolados separadamente:

| Papel | Módulos ativos | Escala por |
| --- | --- | --- |
| `ingestao` | Ingestão (receptor + consumidores) | lag do Kafka (KEDA) |
| `api` | Apresentação, Tenants, Monitoramento (consultas), Segurança e Auditoria | CPU / requisições |
| `autonomico` | Autonômico (MAPE-K), IA | 1 líder por tenant + réplicas em espera |

Réplicas em três zonas de disponibilidade e região secundária para failover (S1-005, S1-006).

## Alternativas rejeitadas

| Alternativa | Por que foi rejeitada |
| --- | --- |
| Monólito em camadas | Particiona por camada técnica, desfaz a separação por domínio, isola mal os erros (nota 1/5) e é rígido para evoluir (1/5). |
| Microsserviços | Melhor elasticidade e isolamento, mas cada chamada entre serviços vira rede (latência e falha parcial contra o tempo quase real e os 99,99%), dados distribuídos exigem Saga, testes de integração custam caro e cinco pessoas teriam de operar vários serviços, pipelines e bancos. Nenhum cenário do QAW exige escala independente *por domínio*. |
| Monólito Modular com um único papel de processo | Um pico de ingestão ou uma chamada lenta ao LLM consumiria os workers do dashboard e do ciclo autônomo. |

## Consequências

**Positivas**
- Um pipeline de CI/CD, um deploy, chamadas em memória entre módulos.
- Isolamento entre domínios garantido no build (ADR-002) e isolamento de falhas por papel (bulkhead).
- Qualquer módulo pode ser extraído como serviço, pois só fala por Portas.

**Negativas / trade-offs**
- Um defeito de código pode derrubar todas as réplicas de um papel ao mesmo tempo.
- Escala por papel, não por módulo: o papel `api` escala junto Apresentação e Auditoria.
- Banco único exige disciplina de schemas e usuários por módulo.

## Conformidade e gatilho de revisão

- Fitness functions de dependência (`tests/arquitetura/`) e contratos do `import-linter` no CI.
- Se o volume sustentado da Ingestão passar de 50% do cenário de alta carga por dois trimestres,
  abrir ADR para extrair a Ingestão como serviço com banco próprio.

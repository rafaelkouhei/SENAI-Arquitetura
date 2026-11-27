# Registros de Decisões Arquiteturais (ADRs)

Formato de cada ADR: **Título · Status · Origem · Contexto · Decisão · Alternativas rejeitadas ·
Consequências (positivas e trade-offs) · Conformidade**.

| ADR | Título | Status | Origem |
| --- | --- | --- | --- |
| [ADR-001](ADR-001-estilo-arquitetural.md) | Estilo arquitetural: Monólito Modular (vs. Microsserviços), com três papéis de processo | Aceita | Sprint 2 / Sprint 3 |
| [ADR-002](ADR-002-desacoplamento-dip-gof.md) | Desacoplamento com DIP, ISP, Ports & Adapters e padrões GoF | Aceita | Sprint 2 |
| [ADR-003](ADR-003-protocolos-integracao.md) | Protocolos de integração: MQTT, gRPC, REST, WebSocket, Kafka e IEC 104/DNP3 | Proposta | Sprint 1 / Sprint 3 |
| [ADR-004](ADR-004-bounded-contexts-acl.md) | Contextos Delimitados e Camada Anti-Corrupção | Proposta | Sprint 3 |
| [ADR-005](ADR-005-stack-gateway-vetorial.md) | Linguagens, frameworks, banco vetorial (pgvector) e stack do API Gateway | Proposta | Sprint 3 |
| [ADR-006](ADR-006-ia-guardrails.md) | Componentes probabilísticos e Guardrails de IA | Proposta | Sprint 4 |
| [ADR-007](ADR-007-ingestao-assincrona.md) | Ingestão assíncrona de telemetria IoT via Kafka | Proposta | Desafio Final |
| [ADR-008](ADR-008-mape-k-guardrails-fisicos.md) | Ciclo autonômico MAPE-K com Guardrails de segurança física | Proposta | Desafio Final |

## Decisões de base (Sprint 1)

As ADRs S1-001 a S1-010 da Sprint 1 continuam válidas como decisões de base e são referenciadas acima:
S1-001 Multi-tenant · S1-002 Isolamento de dados entre tenants · S1-003 Pipeline de ingestão orientado a
eventos · S1-004 Escalabilidade horizontal · S1-005 Alta disponibilidade sem SPOF · S1-006 Disaster Recovery
e failover regional · S1-007 Armazenamento particionado · S1-008 Logs imutáveis · S1-009 Segurança em camadas
e menor privilégio · S1-010 Separação entre caminho operacional e analítico.

## Decisões revistas

- ADR-005 substitui Java/Spring Modulith (Macroarquitetura, Sprint 3) por Python + import-linter.
- ADR-006 passa a permitir que a IA *proponha* planos de manobra, desde que nunca os aprove nem execute (ADR-008).

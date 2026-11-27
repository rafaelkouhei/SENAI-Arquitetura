# ADR-006 — Integração de componentes probabilísticos e Guardrails de IA

- **Status:** Proposta (revisada no Desafio Final)
- **Origem:** Sprint 4 (ADR 006 — Adoção de componentes probabilísticos e estratégia autonômica)
- **Cenários QAW:** DISP-05, SEG-03, SAF-02, AUD-01

## Contexto

A plataforma quer usar IA para interpretar anomalias, gerar relatórios, responder consultas em linguagem
natural e, no Desafio Final, sugerir planos de redistribuição de carga. Modelos de linguagem podem alucinar,
dependem de provedores externos, têm custo por token e podem receber dados pessoais (LGPD) se nada os
filtrar. A infraestrutura é crítica e tem SLA de 99,99%.

## Decisão

1. **Módulo `gird.ia` atrás de Portas.** O resto do sistema só vê `IAssistentePlanejamento`; modelos, RAG e
   validadores são detalhes de implementação.
2. **RAG** sobre pgvector (procedimentos de manobra, manuais, histórico de incidentes). Texto recuperado
   entra no prompt como dado, nunca como instrução.
3. **Model Tiering** (`RoteadorModelos`): modelo pequeno para classificar e resumir; modelo grande para
   planejar e redigir relatórios. Sem multi-agentes: o ciclo MAPE-K já é o orquestrador.
4. **Guardrails da IA:** sanitização de PII antes do envio (CPF, CNPJ, e-mail, telefone, código de UC);
   saída validada por **JSON Schema** (`ESQUEMA_PLANO_MANOBRA`, sem campos extras); cache semântico;
   limite de tokens por tenant.
5. **Resiliência:** Retry com backoff para falhas transitórias dentro de um **Circuit Breaker** (5 falhas,
   60 s); com o circuito aberto, o sistema segue só com estratégias determinísticas.
6. **Limite de autoridade (revisado):** a IA pode *propor* planos de manobra, mas nunca os aprova nem
   executa. Todo plano passa pelos Guardrails físicos determinísticos da ADR-008.

## Alternativas rejeitadas

| Alternativa | Por que foi rejeitada |
| --- | --- |
| Sem IA | Viável (é o fallback), mas perde relatórios automáticos e planos para topologias com muitas opções de manobra. |
| IA com permissão de executar manobras | Não verificável nem auditável; uma alucinação vira comando físico. |
| Arquitetura multi-agentes | Mais pontos de falha e de auditoria sem ganho para um papel restrito. |
| Um único modelo grande para tudo | Custo de tokens desnecessário em tarefas simples de classificação. |
| Validar a saída só com regex/parsing livre | Não garante estrutura nem limites de valores. |

## Consequências

**Positivas** — IA desacoplada dos processos críticos; falha da IA degrada sem parar o sistema; custo
controlado por tiering e cache; dados pessoais não saem da plataforma.

**Negativas / trade-offs** — dependência de provedor externo; latência variável; necessidade de avaliar
continuamente a qualidade das sugestões; manutenção do corpus do RAG.

## Conformidade

Testes em `tests/unit/test_mape_k.py` (JSON malformado, carga inventada, sobrecarga térmica, IA fora do ar)
e fitness function que proíbe `gird.ia` em guardrails, executor e ACL do SCADA.

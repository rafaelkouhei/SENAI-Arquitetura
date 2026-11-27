# ADR-008 — Ciclo autonômico MAPE-K com Guardrails de segurança física

- **Status:** Proposta
- **Origem:** Desafio Final
- **Relaciona-se com:** ADR-001 (papel Autonômico), ADR-002 (Strategy, Composite), ADR-006 (limite de autoridade da IA)
- **Cenários QAW:** SAF-01, SAF-02, DISP-05, AUD-01

## Contexto

O Desafio Final exige redistribuição automática de carga quando uma subestação falha, com apoio de IA.
Até aqui o sistema só lia dados; agora ele comanda chaves da rede de distribuição. Um comando errado pode
sobrecarregar transformadores, levar a tensão para fora da faixa regulatória ou fechar uma chave com equipe
em campo. A ADR-006 (Sprint 4) proibia que a IA executasse operações de controle.

## Decisão

Implementar o ciclo no módulo `gird.autonomico`, em papel de processo próprio, com **uma réplica líder por
tenant** (lock no PostgreSQL) para que duas réplicas nunca comandem a mesma rede.

| Etapa | Componente | Responsabilidade |
| --- | --- | --- |
| Monitor | `MonitorRede` | Estado da rede via `IMonitoramentoDataProvider` (telemetria + eventos de proteção). |
| Analyze | `AnalisadorFalhaSubestacao` | Falha = trip de barra, ou todos os alimentadores da SE abaixo de 0,5 pu. |
| Plan | `PlanejadorComGuardrails` | Estratégias em ordem (IA → maior margem → só prioritários); devolve o 1º plano aprovado. |
| Guardrails | `CadeiaGuardrails` | Envelope físico determinístico, sem IA (tabela abaixo). |
| Execute | `ExecutorManobras` | Revalida no instante da execução, comanda por select-before-operate, Circuit Breaker no SCADA, rollback em ordem inversa. |
| Knowledge | `BaseConhecimentoRede` | Topologia, chaves bloqueadas, envelope por tenant, histórico de sucesso por estratégia. |

Envelope operacional (valores iniciais, configuráveis por tenant em `EnvelopeOperacional`):

| Guardrail | Regra | Violação |
| --- | --- | --- |
| Intertravamento | Chave existe, liga exatamente origem e destino, não está bloqueada, destino fora da SE em falha | Bloqueia |
| Conservação de carga | Transferência ≤ 105% da carga medida na origem | Bloqueia |
| Limite térmico | Carregamento final ≤ 100% da capacidade nominal | Bloqueia |
| Reserva N-1 | Carregamento final entre 90% e 100% | Exige aprovação humana |
| Faixa de tensão | Tensão estimada entre 0,93 e 1,05 pu (PRODIST Módulo 8, 1 kV < V < 69 kV) | Bloqueia |
| Taxa de manobras | ≤ 6 manobras/plano; ≤ 3 planos por SE a cada 15 min | Bloqueia |
| Envelope automático | ≤ 4 manobras e ≤ 20 MW sem humano | Exige aprovação humana |

Toda decisão (plano aprovado, bloqueado, executado, revertido, "sem plano seguro") vai para a trilha de
auditoria com hash encadeado.

## Alternativas rejeitadas

| Alternativa | Por que foi rejeitada |
| --- | --- |
| Só recomendar ao operador | Não atende à redistribuição automática e depende de reação humana rápida em incidente. |
| IA decide e executa | Não verificável, não auditável; uma alucinação vira comando físico. |
| Guardrails dentro de cada estratégia | Cada estratégia nova teria de reimplementar a segurança; um esquecimento seria fatal. A cadeia única é aplicada a todas. |
| Validar só no Planejador | A rede pode mudar entre planejar e executar (TOCTOU); por isso o Executor revalida. |
| Só regras fixas, sem IA | Viável e mantido como fallback; a IA agrega em topologias com muitas opções de manobra. |

## Consequências

**Positivas** — restabelecimento automático dentro de limites verificáveis e testados; falha da IA ou do
SCADA degrada de forma segura (fallback determinístico, rollback, alarme); trilha completa para auditoria.

**Negativas / trade-offs** — o envelope precisa ser calibrado com cada distribuidora; o modelo de queda de
tensão é linear e simplificado; a topologia precisa estar sempre atualizada; a integração com o SCADA
aumenta a superfície de ataque (mitigada pelo Gateway OT em DMZ e lista de comandos permitidos).

## Conformidade

- `tests/unit/test_mape_k.py`: falha da SE-NORTE redistribuída; chave bloqueada nunca comandada; plano da IA
  com sobrecarga, carga inventada ou JSON malformado rejeitado; Circuit Breaker da IA; aprovação humana;
  rollback em falha do SCADA; bloqueio por tensão.
- `tests/arquitetura/`: regra 4 — guardrails, executor e ACL do SCADA não importam `gird.ia`.

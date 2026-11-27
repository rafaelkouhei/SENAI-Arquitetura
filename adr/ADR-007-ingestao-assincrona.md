# ADR-007 — Ingestão assíncrona de telemetria IoT via Kafka

- **Status:** Proposta
- **Origem:** Desafio Final (consolida S1-003 e S1-004 da Sprint 1)
- **Relaciona-se com:** ADR-001, ADR-003, ADR-004, ADR-005
- **Cenários QAW:** DES-01, DES-02, DES-04, CONF-01, CONF-02, SEG-02

## Contexto

A plataforma recebe telemetria de 100 mil a 1,9 milhão de medidores. O BOTE do QAW estima de 111 a
31.667 eventos/s em regime e 63,3 MB/s no cenário de alta carga; durante um incidente na rede os medidores
reenviam e o volume pode triplicar (≈ 95 mil eventos/s por alguns minutos). As metas são 0% de perda e
latência ponta a ponta p95 ≤ 5 s.

Uma ingestão síncrona acoplaria a velocidade dos medidores à do banco: qualquer lentidão no TimescaleDB
viraria timeout e reenvio em massa justamente durante o incidente, quando a visibilidade mais importa.

## Decisão

Separar **recebimento** e **processamento** por um log de eventos durável (Apache Kafka):

1. **Borda só autentica e enfileira.** MQTT entra pelo EMQX; HTTP/gRPC pelo Kong, que repassa ao receptor do
   papel Ingestão. mTLS com certificado por dispositivo; rate limiting por dispositivo e por tenant. O payload
   bruto vai para `telemetria.bruta` e a borda confirma assim que o Kafka grava (`202 Accepted`).
2. **Particionamento** por `tenant_id:medidor_id` — ordem garantida por medidor e carga distribuída.
   `telemetria.bruta` e `telemetria.recebida` começam com 96 partições (≈ 1.000 eventos/s por partição no pico
   de 95 mil eventos/s). *Premissa a validar em teste de carga.*
3. **Durabilidade:** produtor com `acks=all`, `enable.idempotence=true`, compressão zstd; tópicos com RF = 3 em
   três zonas e `min.insync.replicas=2`.
4. **Consumidores (papel Ingestão)** aplicam a ACL (Factory Method + Adapter + Splitter), validam o tenant,
   descartam duplicatas pela chave `tenant:medidor:sequência`, enriquecem com o cadastro técnico
   (Content Enricher), roteiam por conteúdo (Content-Based Router: `telemetria.processada`,
   `monitoramento.anomalias`, `alertas.criticos`) e gravam em lote com `COPY` no TimescaleDB.
5. **Falhas** vão para `telemetria.dlq` com o motivo (retenção 14 dias, reprocessável).
6. **Elasticidade:** consumidores escalam pelo lag do grupo (KEDA), até uma réplica por partição.
7. **Contratos** versionados no Schema Registry; firmware com número de sequência e store-and-forward;
   `ReconciliadorPorSequencia` pede retransmissão de lacunas.

## Alternativas rejeitadas

| Alternativa | Por que foi rejeitada |
| --- | --- |
| REST síncrono direto ao banco | Acopla a ingestão à latência do banco e não absorve o pico do incidente. |
| Só o broker MQTT, sem Kafka | Sem retenção longa, reprocessamento nem vários grupos de consumidores independentes (Monitoramento, Autonômico, Auditoria). |
| RabbitMQ | Fila de trabalho, não log: sem replay nativo, ordem por chave mais difícil em alta vazão sustentada. |
| Extrair a Ingestão como microsserviço agora | O papel Ingestão já escala separado sem sair do monólito (ADR-001); extração fica para o gatilho abaixo. |
| Gravar cada leitura individualmente (INSERT por evento) | Dezenas de milhares de transações por segundo; `COPY` em lote reduz o custo por linha. |

## Consequências

**Positivas** — picos absorvidos sem perda; produtores e consumidores evoluem e escalam separadamente;
reprocessamento após bug ou mudança de regra; falhas visíveis na DLQ; vários consumidores leem o mesmo fluxo.

**Negativas / trade-offs**
- Consistência eventual entre a leitura e o dashboard.
- Mais um cluster crítico para operar e monitorar.
- Duplicatas e ordenação precisam de tratamento explícito (idempotência por sequência).
- Armazenamento do Kafka: com 24 h de retenção em `telemetria.bruta`, a alta carga ocupa ≈ 5,5 TB por cópia,
  ≈ 16,4 TB com RF = 3, antes da compressão.
- A latência de micro-lotes (`linger.ms=20`) troca alguns milissegundos por vazão.

## Conformidade

- `tests/unit/test_ingestao.py` e `tests/unit/test_eip_resiliencia.py`: lote, conversão de unidades, XML
  legado, idempotência, DLQ, tenant desconhecido, enriquecimento e roteamento por conteúdo.
- Alertas operacionais: lag > 5 min; DLQ > 0,1% das mensagens; partição sem líder.

## Gatilho de revisão

Volume sustentado acima de 50% do cenário de alta carga por dois trimestres, ou lag crescendo continuamente
no teste com 31.667 eventos/s → nova ADR para extrair a Ingestão como serviço com banco próprio.

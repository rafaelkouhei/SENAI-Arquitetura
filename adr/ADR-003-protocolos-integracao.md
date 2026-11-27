# ADR-003 — Protocolos de integração: MQTT, gRPC, REST, WebSocket, Kafka e IEC 104/DNP3

- **Status:** Proposta
- **Origem:** Sprint 1 (S1-003 — pipeline orientado a eventos) e Sprint 3 (ADR 005 — frameworks e padrões de integração)
- **Cenários QAW:** DES-01, DES-02, DES-03, CONF-01, SEG-02

## Contexto

A plataforma integra quatro tipos de parceiro com necessidades diferentes: dispositivos de campo com
pouca CPU e conexão instável; operadores em navegador que precisam de atualização contínua; sistemas
corporativos e reguladores; e o SCADA da distribuidora, que fala protocolos industriais. Entre os
módulos internos, o tráfego de telemetria é de dezenas de milhares de eventos por segundo.

## Decisão

| Fronteira | Protocolo | Justificativa |
| --- | --- | --- |
| Medidor → borda | **MQTT** (EMQX), mTLS | Leve, conexão persistente, QoS 1 com reenvio; padrão de fato em IoT. |
| Concentrador / medidor → borda | **gRPC** ou **HTTP** (Kong), mTLS | Lotes grandes, contrato binário (Protobuf) e streaming. |
| Borda ↔ módulos, módulo ↔ módulo assíncrono | **Kafka** | Log durável, reprocessável, ordem por chave, vários grupos de consumidores (ADR-007). |
| Dashboard → API | **REST** (JSON, OpenAPI) + **WebSocket** | REST para consultas; WebSocket para empurrar alertas e telemetria agregada. |
| Plataforma → reguladores | **gRPC streaming** ou REST | Conforme o contrato de cada órgão, via ACL (Integração Regulatória). |
| Papel Autonômico → Gateway OT | **gRPC**, mTLS | Contrato tipado e auditável para comandos de manobra. |
| Gateway OT → SCADA | **IEC 60870-5-104 / DNP3**, select-before-operate | Protocolos que o SCADA das distribuidoras já fala. |

Os contratos são versionados: OpenAPI (backend ↔ frontend), Protobuf (gRPC) e Schema Registry (Kafka).

## Alternativas rejeitadas

| Alternativa | Por que foi rejeitada |
| --- | --- |
| REST síncrono entre todos os componentes | Acopla produtores e consumidores; picos de telemetria se propagariam ao banco e ao dashboard. |
| Só MQTT, inclusive internamente | Sem retenção longa, reprocessamento nem grupos de consumidores independentes. |
| RabbitMQ como barramento principal | Bom para filas de trabalho, mas o caso pede log reprocessável e ordem por chave em alta vazão sustentada. |
| Polling do dashboard (DES-03 do BOTE: 500 req/s) | Carga inútil no backend; WebSocket envia só o que mudou. |
| Comandar o SCADA direto da aplicação | Expõe a rede OT; o Gateway OT em DMZ limita os comandos a uma lista permitida. |

## Consequências

**Positivas** — cada fronteira usa o protocolo adequado ao seu parceiro; desacoplamento temporal onde há volume.

**Negativas / trade-offs** — mais protocolos para operar e monitorar; consistência eventual entre a leitura
e o dashboard; gestão de certificados mTLS (emissão, renovação, revogação) para milhões de dispositivos.

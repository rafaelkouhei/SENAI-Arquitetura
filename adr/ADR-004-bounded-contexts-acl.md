# ADR-004 — Mapeamento de Contextos Delimitados e Camada Anti-Corrupção (ACL)

- **Status:** Proposta
- **Origem:** Sprint 3 (Prática Laboratorial — Mapeamento das fronteiras de integração) e Arquitetura de Dados
- **Cenários QAW:** ESC-01, SEG-04, SEG-06, modificabilidade

## Contexto

Os medidores vêm de vários fabricantes, com protocolos e nomes próprios (`id_meter`, `device_code`, XML de
concentradores legados). O SCADA e o cadastro técnico das distribuidoras são sistemas legados com modelo
próprio. Sem uma barreira, esses modelos vazariam para o domínio e cada novo fabricante exigiria mudanças
em vários módulos.

## Decisão

1. **Subdomínios**
   - *Core:* Operação autônoma (MAPE-K com Guardrails) e Monitoramento da rede.
   - *Supporting:* Ingestão e normalização, Ocorrências e alertas, Segurança e auditoria, Gestão de tenants,
     Cadastro técnico e geográfico, Integração regulatória, Dashboard.
   - *Generic:* SSO (Keycloak), API Gateway (Kong), broker MQTT (EMQX), streaming (Kafka), séries temporais
     (TimescaleDB), provedores de LLM.
2. **Bounded Contexts → módulos:** `gird.ingestao`, `gird.monitoramento`, `gird.seguranca`, `gird.tenants`,
   `gird.apresentacao`, `gird.autonomico`, `gird.ia`; cada um dono exclusivo do seu schema.
3. **Mapa de contexto**

| Relação | Padrão |
| --- | --- |
| Fabricantes de medidores → Ingestão | ACL (`AdaptadorFabricanteA/B`, `AdaptadorConcentradorLegadoXml`) |
| Autonômico → SCADA/ADMS legado | ACL (`AdaptadorScadaLegadoXml`) |
| Autonômico → provedor de LLM | ACL (`IModeloLinguagem` + sanitização de PII) |
| Ingestão → demais | Published Language (evento canônico versionado em `telemetria.recebida`) |
| Tenants → todos | Open Host Service (`ITenantProvider`) |
| Monitoramento → Autonômico; IA → Autonômico | Customer / Supplier por Portas |
| Todos | Shared Kernel mínimo (`gird.nucleo`) |

4. **Soberania de dados:** zero FK entre schemas; integridade entre módulos por Portas ou eventos de domínio
   (consistência eventual).

## Alternativas rejeitadas

| Alternativa | Por que foi rejeitada |
| --- | --- |
| Conformista: adotar o modelo de um fabricante como canônico | Cada fabricante novo quebraria o domínio; dependência comercial de um fornecedor. |
| Tradução dentro de cada consumidor | Duplica a lógica de conversão em vários módulos. |
| Integração por banco compartilhado (FK e JOIN entre schemas) | Quebra a soberania de dados e impede extrair módulos. |

## Consequências

**Positivas** — o domínio só conhece `LeituraTelemetria`, `Manobra` e `PlanoManobra`; um fabricante novo é um
adaptador novo; os legados podem ser trocados sem tocar no Core.

**Negativas / trade-offs** — um adaptador por fabricante e por legado para manter; tradução custa CPU na
ingestão; consistência eventual entre contextos.

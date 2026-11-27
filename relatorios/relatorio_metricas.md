# Relatório de métricas de estabilidade e abstração

Gerado automaticamente por `tools/metricas_martin.py` em 2026-11-26 23:56 UTC. Limite de D: 0.1.

| Componente | Nc | Na | A | Ca | Ce | I | D | Situação |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `apresentacao` | 2 | 0 | 0.00 | 0 | 2 | 1.00 | 0.00 | Sequência principal |
| `autonomico.implementacao` | 20 | 0 | 0.00 | 0 | 4 | 1.00 | 0.00 | Sequência principal |
| `autonomico.portas` | 9 | 9 | 1.00 | 1 | 0 | 0.00 | 0.00 | Sequência principal |
| `ia.implementacao` | 6 | 0 | 0.00 | 0 | 1 | 1.00 | 0.00 | Sequência principal |
| `ia.portas` | 5 | 5 | 1.00 | 2 | 0 | 0.00 | 0.00 | Sequência principal |
| `ingestao.implementacao` | 15 | 0 | 0.00 | 0 | 2 | 1.00 | 0.00 | Sequência principal |
| `ingestao.portas` | 6 | 6 | 1.00 | 1 | 0 | 0.00 | 0.00 | Sequência principal |
| `monitoramento.implementacao` | 2 | 0 | 0.00 | 0 | 1 | 1.00 | 0.00 | Sequência principal |
| `monitoramento.portas` | 2 | 2 | 1.00 | 3 | 0 | 0.00 | 0.00 | Sequência principal |
| `nucleo` | 14 | 0 | 0.00 | 8 | 0 | 0.00 | 1.00 | Zona de Dor tolerada (kernel não-volátil) |
| `seguranca.implementacao` | 1 | 0 | 0.00 | 0 | 1 | 1.00 | 0.00 | Sequência principal |
| `seguranca.portas` | 1 | 1 | 1.00 | 2 | 0 | 0.00 | 0.00 | Sequência principal |
| `tenants.implementacao` | 1 | 0 | 0.00 | 0 | 1 | 1.00 | 0.00 | Sequência principal |
| `tenants.portas` | 2 | 2 | 1.00 | 3 | 0 | 0.00 | 0.00 | Sequência principal |

## Dependências entre componentes

- `apresentacao` → `monitoramento.portas`, `tenants.portas`
- `autonomico.implementacao` → `autonomico.portas`, `ia.portas`, `monitoramento.portas`, `seguranca.portas`
- `ia.implementacao` → `ia.portas`
- `ingestao.implementacao` → `ingestao.portas`, `tenants.portas`
- `monitoramento.implementacao` → `monitoramento.portas`
- `seguranca.implementacao` → `seguranca.portas`
- `tenants.implementacao` → `tenants.portas`

## Princípio das Dependências Estáveis (SDP)

Nenhuma violação: toda dependência aponta para um componente mais estável.

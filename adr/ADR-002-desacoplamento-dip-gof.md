# ADR-002 — Desacoplamento de código com DIP, ISP, Ports & Adapters e padrões GoF

- **Status:** Aceita
- **Origem:** Sprint 2 (ADR 1 / ADR-011 — Estabilidade estrutural dos pacotes) e Matriz de Decisão V1–V3
- **Cenários QAW:** ESC-01, ESC-02, modificabilidade (Tier 4)

## Contexto

O diagrama de contêineres da Sprint 1 foi desenhado sem medida de acoplamento. Ao calcular as métricas
de Martin, *Gestão de Tenants* e *Ingestão e Processamento* deram D = 1 (estáveis e totalmente concretos:
Zona de Dor). A Matriz de Decisão comparou três variantes:

| Variante | Pontuação ponderada |
| --- | --- |
| V1 — monolítico acoplado, sem interfaces | 41 |
| V2 — SRP + DIP, 3 interfaces | 98 |
| **V3 — SRP + DIP + ISP, 8 interfaces** | **115** |

## Decisão

1. Usar Ca, Ce, I, A e D como critério formal para todos os componentes, calculados automaticamente por
   `tools/metricas_martin.py` a cada build, com limite **D ≤ 0,1**.
2. Cada módulo é dividido em um pacote `portas` (só abstrações: A = 1, Ce = 0) e um pacote
   `implementacao` (só classes concretas: A = 0, I = 1). Só `composition_root.py` instancia classes concretas.
3. Variação de comportamento é resolvida por padrões GoF, nunca por condicionais espalhadas:
   - **Factory Method** — `CriadorConector` e subclasses por protocolo (`ingestao/implementacao/conectores/fabrica.py`).
   - **Adapter** — ACL de fabricantes e do SCADA (`ingestao/implementacao/acl/`, `autonomico/implementacao/acl_scada.py`).
   - **Strategy** — algoritmos de redistribuição de carga (`autonomico/implementacao/estrategias.py`).
   - **Composite** — `CadeiaGuardrails`; **Template Method** — `CriadorConector.normalizar`.
4. O núcleo compartilhado (`gird.nucleo`, objetos de valor imutáveis) é tratado como biblioteca padrão:
   aparece no relatório, mas fica fora do gate de D.

## Alternativas rejeitadas

| Alternativa | Por que foi rejeitada |
| --- | --- |
| Aceitar D = 0,50 em Tenants após o ISP | A meta da Sprint 2 era D = 0 em todos os pacotes. |
| Criar interface extra só para subir A | Abstração sem consumidor real (viola YAGNI). |
| V1 sem interfaces | 41 pontos; falha crítica em isolamento multi-tenant e disponibilidade. |
| Usar `if/else` por fabricante ou por algoritmo | Cada novo fabricante ou estratégia alteraria classes existentes (viola OCP). |

## Consequências

**Positivas** — D = 0 em todos os 13 componentes de domínio; contratos testáveis com dublês; troca de
infraestrutura (Kafka ↔ memória, LLM real ↔ simulado) sem tocar no domínio (LSP).

**Negativas / trade-offs** — mais pacotes e arquivos (de 5 para 14 componentes); exige disciplina de
injeção de dependência; o kernel compartilhado é uma exceção declarada à regra de D.

## Conformidade

`tests/arquitetura/test_fitness_functions.py` (regras 1, 2, 3, 5 e 6) e `pyproject.toml` (`import-linter`).

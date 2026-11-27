# 6. Resiliência, Integração e IA-Native

## Contexto e objetivos

O Grid the Grid é uma plataforma de monitoramento e apoio à gestão de redes elétricas, que recebe telemetria de medidores e integra informações de sistemas externos, como SCADA/IoT, sistema de faturamento, IdP/SSO e SIEM. A arquitetura deve atender ao crescimento de aproximadamente 100 mil até 1,9 milhão de unidades consumidoras, com meta de disponibilidade de 99,99% e proteção dos dados e operações.

Esta seção define estratégias para tolerar falhas, absorver variações de volume, desacoplar componentes e incorporar Inteligência Artificial Generativa de forma controlada. A arquitetura permanece alinhada à decisão de **Monólito Modular**, com componentes internos desacoplados e infraestrutura distribuída para alta disponibilidade. O uso de mensageria e processamento assíncrono não implica adoção de microsserviços.

### Objetivos arquiteturais

- Preservar a ingestão e o processamento de telemetria durante falhas temporárias de dependências.
- Evitar que picos de mensagens provoquem sobrecarga nos serviços consumidores ou bancos de dados.
- Permitir reprocessamento de eventos e rastreabilidade de falhas.
- Manter a meta de disponibilidade de 99,99%, com redundância, monitoramento e recuperação.
- Usar IA para auxiliar análise, priorização e recomendação, sem conceder ao modelo autoridade direta para comandar equipamentos elétricos.

### Fluxo de integração proposto

1. Medidores e sistemas SCADA/IoT enviam eventos de telemetria para a camada de ingestão.
2. A ingestão valida formato, autenticação, timestamp, identificador do dispositivo e regras básicas de qualidade.
3. Eventos válidos são publicados no broker, que desacopla produtores e consumidores.
4. Consumidores processam os eventos, persistem os dados e atualizam indicadores e alertas.
5. Dados agregados e contextualizados são disponibilizados para dashboards, relatórios e componentes analíticos.
6. O componente de IA consulta dados e conhecimento autorizado e retorna análises ou recomendações estruturadas.
7. Recomendações que possam impactar a operação passam por regras determinísticas, validação humana e/ou sistemas operacionais autorizados antes de qualquer execução.

---

## 6.1. Padrões de Resiliência Aplicados

A arquitetura aplica padrões de resiliência para reduzir propagação de falhas, limitar pressão sobre dependências e assegurar que eventos possam ser recuperados sem perda silenciosa.

### Circuit Breaker

O Circuit Breaker será aplicado às chamadas para dependências externas ou internas sujeitas a indisponibilidade, como integrações com SCADA, serviços de identidade, sistemas externos e serviços de consulta.

Estados:

- **Closed (fechado):** chamadas são permitidas; falhas são contabilizadas.
- **Open (aberto):** após atingir o limiar configurado de falhas ou timeout, chamadas são interrompidas temporariamente para evitar sobrecarregar a dependência.
- **Half-open (semiaberto):** após o período de espera, algumas chamadas de teste são liberadas; se a dependência responder, o circuito volta a fechado, caso contrário reabre.

O Circuit Breaker deve ser configurado por dependência, com limiares e janelas ajustados por métricas e testes. Não substitui timeout, retry ou monitoramento.

### Timeout e Retry com backoff

As chamadas a dependências terão timeout explícito. Retentativas serão limitadas e aplicadas apenas a operações que possam ser repetidas com segurança, preferencialmente idempotentes. Será usado backoff exponencial com jitter para evitar que múltiplos clientes retomem chamadas simultaneamente.

Retentativas não devem ser feitas indiscriminadamente em operações de escrita, nem em cascata em todos os níveis, para evitar amplificação de tráfego.

### Fallback

Quando uma dependência não estiver disponível, o sistema poderá utilizar alternativas degradadas, conforme o tipo de operação:

- Para dashboards, exibir o último dado conhecido, indicando claramente timestamp e estado de desatualização.
- Para consultas analíticas, retornar dados parciais ou cacheados quando apropriado.
- Para recomendações de IA, indisponibilidade ou falha do modelo resulta em ausência de recomendação, mantendo o fluxo operacional convencional.
- Para integrações externas, registrar a operação pendente e encaminhá-la para recuperação posterior, quando permitido.

Fallback não deve produzir valores fictícios nem ocultar a indisponibilidade.

### Load Leveling (nivelamento de carga)

O broker de mensagens atua como buffer entre a ingestão de telemetria e os consumidores. O nivelamento de carga permite que produtores enviem eventos em períodos de pico sem exigir que todos os consumidores processem o volume instantaneamente.

A arquitetura prevê:

- Filas ou tópicos particionados, com particionamento por identificador do medidor ou outra chave que preserve a ordenação necessária.
- Consumidores escaláveis horizontalmente, respeitando limites de processamento e recursos.
- Backpressure e limites de taxa para impedir que consumidores ou bancos sejam sobrecarregados.
- Monitoramento do tamanho da fila, idade do evento mais antigo, taxa de entrada e saída e lag dos consumidores.
- Priorização de mensagens críticas quando o domínio e a política de operação permitirem.

O broker (Kafka como opção de referência) deve ser dimensionado e configurado com replicação, persistência e política de retenção compatíveis com o volume e os requisitos de recuperação. A escolha definitiva de tecnologia e parâmetros deve ser validada por testes de carga e ADR.

### Mensageria, entrega e idempotência

A comunicação assíncrona é usada para desacoplar ingestão, processamento, armazenamento, geração de alertas e análise. O sistema assume que eventos podem ser entregues mais de uma vez; por isso, consumidores devem ser idempotentes.

A idempotência pode ser implementada com identificador único do evento, controle de eventos processados, restrições de unicidade e operações de atualização seguras. A ordem dos eventos será preservada somente nos contextos em que seja necessária, por exemplo, dentro da partição associada a um medidor.

Não se assume entrega exactly-once ponta a ponta entre todos os sistemas. Garantias de processamento devem ser especificadas por fluxo e implementadas combinando persistência, idempotência, transações locais e mecanismos de reconciliação.

### Dead Letter Queue (DLQ)

Eventos que falharem após as tentativas permitidas, ou que forem rejeitados por erros não recuperáveis, serão encaminhados para uma Dead Letter Queue (DLQ), acompanhados de metadados de diagnóstico.

Metadados mínimos:

- Identificador do evento e do medidor, quando aplicável.
- Timestamp de origem e de recebimento.
- Identificação do consumidor e do fluxo.
- Categoria e código do erro, sem incluir segredos ou dados pessoais desnecessários.
- Número de tentativas e correlação/rastreabilidade.

A DLQ será monitorada e terá processo operacional de triagem, correção e reprocessamento controlado. O reprocessamento deve evitar duplicidade e permitir que eventos corrigidos retornem ao fluxo normal. A DLQ não será utilizada como descarte permanente ou substituto para observabilidade.

### Observabilidade e recuperação

A resiliência será acompanhada por métricas, logs estruturados e tracing distribuído. Indicadores relevantes incluem:

- Disponibilidade e taxa de erro dos serviços.
- Latência por endpoint e integração.
- Throughput de eventos por segundo.
- Lag, tamanho e idade das filas.
- Taxa de retries, circuit breakers abertos e eventos em DLQ.
- Falhas de persistência e tempo de recuperação.
- Tempo de detecção (MTTD) e tempo de recuperação (MTTR).

A meta de disponibilidade de 99,99% corresponde a aproximadamente 52,56 minutos de indisponibilidade por ano, considerando um ano de 365 dias. A meta deverá ser validada por monitoramento e testes, e não tratada como garantia automática decorrente dos padrões.

A estratégia de infraestrutura inclui réplicas em zonas distintas, redundância de componentes críticos, banco de dados com replicação e failover e plano de recuperação em região secundária, conforme decisões arquiteturais anteriores. Testes periódicos de falha e recuperação devem validar o comportamento real.

---

## 6.2. Componente de Inteligência Artificial Generativa

### Proposta de arquitetura AI-Native

O Grid the Grid incorpora IA Generativa como componente de apoio à análise de telemetria, consulta a conhecimento técnico e produção de recomendações para operadores. A IA não substitui os mecanismos determinísticos de proteção elétrica nem recebe autorização direta para controlar equipamentos.

A proposta utiliza **Retrieval-Augmented Generation (RAG)** para contextualizar as respostas do modelo com documentos, procedimentos, dados agregados e informações operacionais que o usuário tenha autorização para consultar. O RAG reduz respostas sem contexto, mas não garante por si só a veracidade das respostas.

### Fluxo do componente

1. **Entrada:** usuário ou serviço solicita análise, resumo, explicação de alerta ou recomendação.
2. **Autorização:** identidade, perfil e escopo de acesso são verificados antes de recuperar dados.
3. **Contextualização:** a aplicação consulta fontes autorizadas, como procedimentos operacionais, documentação e dados agregados da plataforma.
4. **RAG:** documentos relevantes são recuperados e apresentados ao modelo como contexto, com metadados e referências de origem.
5. **Inferência:** o modelo produz resposta ou recomendação no formato estruturado definido pela aplicação.
6. **Validação:** schema, regras de negócio, segurança, limites e consistência são verificados.
7. **Apresentação:** resposta, evidências e limitações são exibidas ao operador.
8. **Auditoria:** registra-se a solicitação, fontes consultadas, versão/configuração do modelo, resultado validado e decisão humana, respeitando a política de privacidade e retenção.

### Fontes de conhecimento e RAG

O repositório de conhecimento pode incluir documentos técnicos, procedimentos aprovados, manuais, registros de incidentes e informações agregadas ou contextualizadas de telemetria. A indexação deve controlar versão, validade, origem e permissões.

O processo de recuperação deve:

- Respeitar autorização por usuário, unidade, região e tipo de informação.
- Priorizar fontes aprovadas e atualizadas.
- Recuperar trechos relevantes e anexar metadados de origem.
- Evitar enviar ao modelo dados pessoais ou informações sensíveis desnecessárias.
- Permitir que o operador consulte as fontes utilizadas na resposta.

Dados de telemetria em tempo real não devem ser enviados indiscriminadamente ao modelo. A aplicação deve selecionar, agregar e contextualizar apenas os dados necessários para a tarefa.

### Guardrails

Guardrails são controles implementados antes, durante e depois da inferência:

**Controles de entrada**
- Autenticação e autorização do solicitante.
- Validação do tamanho, formato e finalidade da requisição.
- Higienização e minimização de dados pessoais (PII).
- Proteção contra prompt injection em entradas e documentos recuperados.

**Controles de contexto**
- Recuperação apenas de fontes autorizadas.
- Instruções claras para tratar conteúdo recuperado como dado, não como instrução.
- Separação entre instruções de sistema, solicitação do usuário e conteúdo documental.
- Limites de contexto e prevenção de exposição de dados de outros usuários ou unidades.

**Controles de saída**
- Validação do JSON Schema.
- Verificação de conteúdo, regras de domínio, limites e plausibilidade.
- Recusa ou encaminhamento para revisão quando a resposta não tiver evidências suficientes.
- Exibição de fontes e indicação de incerteza ou indisponibilidade.
- Proibição de executar comandos operacionais diretamente a partir de texto gerado pelo modelo.

### Contrato de saída (JSON Schema)

O componente deve retornar um objeto estruturado e validável. Exemplo ilustrativo de contrato:

```json
{
  "tipo": "recomendacao_analitica",
  "resumo": "Descrição concisa do achado.",
  "evidencias": [
    {
      "fonte": "identificador da fonte autorizada",
      "referencia": "trecho, registro ou intervalo consultado"
    }
  ],
  "recomendacoes": [
    {
      "acao_sugerida": "Verificar o equipamento ou condição indicada.",
      "prioridade": "media",
      "justificativa": "Justificativa apoiada nas evidências recuperadas."
    }
  ],
  "confianca": "limitada",
  "requer_validacao_humana": true
}
```

A aplicação deve validar o objeto com schema estrito, campos obrigatórios, enumerações e limites de tamanho. O texto livre não pode ser interpretado como comando executável. Valores de confiança apresentados ao usuário devem ser calibrados e não inventados pelo modelo; se não houver mecanismo de calibração, o campo deve ser substituído por uma indicação qualitativa validada ou removido.

### Higienização de PII e segurança de dados

Antes de enviar dados ao provedor de IA:

- Identificar e remover ou mascarar dados pessoais não necessários.
- Evitar incluir nomes, documentos, contatos, identificadores pessoais e dados de clientes no prompt.
- Utilizar identificadores pseudonimizados quando a correlação for necessária.
- Restringir acesso, retenção e logging de prompts e respostas.
- Não registrar conteúdo sensível em logs de diagnóstico.
- Definir política de retenção, acesso e exclusão compatível com LGPD e requisitos da organização.

### Limites operacionais e supervisão humana

O componente de IA é de apoio à decisão. Recomendações que possam afetar distribuição de carga, configuração de equipamentos, desligamentos, religamentos ou proteção da rede devem ser submetidas a sistemas determinísticos de validação, autorização operacional e supervisão humana.

A IA não deve:
- Acionar diretamente equipamentos ou sistemas de controle.
- Substituir alarmes, intertravamentos, proteções ou procedimentos de segurança.
- Inventar evidências ou apresentar hipóteses como fatos.
- Acessar dados fora do escopo autorizado.
- Executar ações quando os guardrails, validações ou fontes de contexto falharem.

### Falhas e fallback da IA

Se o modelo, serviço de recuperação ou validação estiver indisponível, a plataforma mantém as funções convencionais de monitoramento, alertas e dashboards. A solicitação de IA pode ser marcada como indisponível, registrada para diagnóstico e eventualmente repetida com controle de tentativas.

A indisponibilidade da IA não deve interromper ingestão, persistência, monitoramento ou mecanismos de segurança da rede.

### Métricas de avaliação

O componente deve ser avaliado em ambiente controlado por:

- Latência e taxa de falha.
- Taxa de respostas validadas pelo schema.
- Relevância e qualidade das fontes recuperadas.
- Aderência às evidências (groundedness) e taxa de respostas sem suporte.
- Taxa de bloqueio de prompt injection e violações de autorização.
- Taxa de recomendações aceitas, rejeitadas ou editadas por operadores.
- Custo por solicitação e volume de dados enviado ao modelo.

A avaliação deve utilizar casos de teste representativos, incluindo dados incompletos, conflitos entre fontes, eventos extremos, tentativas de prompt injection e cenários em que a resposta correta é não recomendar uma ação.

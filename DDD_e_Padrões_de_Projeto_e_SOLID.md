**4. Domain-Driven Design (DDD) \& Limites de Contexto**

**4.1. Classificação dos Subdomínios**



Core Domain (Domínio Principal): Ciclo Autonômico de Redistribuição de Carga e Monitoramento da Rede Elétrica em Tempo Quase Real. Representa o principal diferencial do Gird the Grid, sendo responsável pelo monitoramento da infraestrutura elétrica, identificação de falhas e anomalias e otimização da distribuição de energia. Por meio do ciclo MAPE-K, integrado à IA e protegido por Guardrails de segurança física, o sistema analisa as condições da rede e planeja ações de redistribuição de carga, respeitando os limites operacionais dos equipamentos.

Supporting Subdomain (Domínio de Suporte): Ingestão e Normalização de Telemetria, Ocorrências e Alertas, Segurança e Auditoria, Gestão de Tenants, Cadastro Técnico e Geográfico, Integração Regulatória e Dashboard Operacional. Essas funcionalidades fornecem os dados e serviços necessários para sustentar o domínio principal, garantindo o recebimento de informações dos medidores, acompanhamento dos equipamentos, registro de incidentes e disponibilização de informações aos operadores.

Generic Subdomain (Domínio Genérico): Serviços de infraestrutura e tecnologias consolidadas, como Autenticação SSO (Keycloak), API Gateway (Kong), broker MQTT (EMQX), streaming de eventos (Apache Kafka), armazenamento de séries temporais (TimescaleDB) e provedores de modelos de linguagem (LLM). São recursos utilizados para viabilizar o funcionamento da plataforma, sem representar o principal diferencial de negócio.

Os oito Bounded Contexts definidos na Sprint 3 foram organizados como módulos do Monólito Modular:

Bounded Context	Módulo no código	Subdomínio

Ingestão de Telemetria e Telemetria e Medição	gird.ingestao	Suporte

Monitoramento da Rede, Ocorrências e Alertas	gird.monitoramento	Core / Suporte

Detecção de Intrusão	gird.seguranca	Suporte

Cadastro Técnico e Geográfico	Topologia na Base de Conhecimento de gird.autonomico	Suporte

Dashboard Operacional	gird.apresentacao	Suporte

Integração Regulatória	Ainda não implementado	Suporte

Operação Autônoma	gird.autonomico	Core

Assistência por IA	gird.ia	Genérico, atrás de Porta



**4.2. Mapa de Contexto e Camada Anti-Corrupção (ACL)**



A arquitetura do Gird the Grid utiliza Bounded Contexts para delimitar as responsabilidades dos módulos e estabelecer contratos de comunicação entre eles. A integração com dispositivos, serviços e sistemas legados é realizada por meio da Anti-Corruption Layer (ACL), utilizando adaptadores baseados no padrão GoF Adapter.

A ACL está localizada em src/gird/ingestao/implementacao/acl/ e src/gird/autonomico/implementacao/acl\_scada.py, protegendo o modelo interno do sistema contra as diferenças de estruturas e nomenclaturas utilizadas por fabricantes e sistemas externos.

Por exemplo, diferentes fabricantes podem identificar o mesmo medidor utilizando campos como id\_meter ou device\_code, enquanto concentradores legados podem enviar informações em XML. A ACL interpreta e converte essas estruturas para o modelo canônico utilizado pelo domínio, no qual a identificação do equipamento é representada por LeituraTelemetria.medidor\_id.

As principais relações entre os contextos são:

Relação	Padrão de contexto	Implementação

Medidores de diferentes fabricantes → Ingestão	ACL	AdaptadorFabricanteA, AdaptadorFabricanteB e AdaptadorConcentradorLegadoXml.

Autonômico → SCADA/ADMS legado	ACL	AdaptadorScadaLegadoXml converte o objeto Manobra para o formato XML esperado pelo SCADA.

Ingestão → Monitoramento e demais consumidores	Published Language	Evento canônico versionado publicado no tópico telemetria.recebida.

Tenants → Todos os módulos	Open Host Service	Interfaces ITenantProvider e IUnidadeConsumidoraProvider.

Monitoramento → Autonômico	Customer / Supplier	Interface IMonitoramentoDataProvider.

IA → Autonômico	Customer / Supplier com tradução	Interface IAssistentePlanejamento e implementação EstrategiaSugeridaPorIA, cuja sugestão é transformada em PlanoManobra e submetida aos Guardrails.

Autonômico → Provedor de LLM	ACL	Interface IModeloLinguagem, com sanitização de dados pessoais antes do envio.

Todos os módulos	Shared Kernel	Módulo gird.nucleo, contendo objetos de valor imutáveis e mecanismos de Circuit Breaker.

A integração do cadastro técnico legado com a Base de Conhecimento também está prevista por meio de ACL, mas ainda não foi implementada.

Dessa forma, a utilização de Bounded Contexts, interfaces e adaptadores permite manter o isolamento das regras de negócio, reduzir o acoplamento entre os módulos e garantir que informações externas sejam convertidas antes de chegar ao domínio principal do Gird the Grid.



**5. Padrões de Projeto \& Princípios SOLID**



A organização dos módulos segue a arquitetura Ports \& Adapters, baseada na separação entre contratos abstratos e implementações concretas. Essa estrutura foi definida a partir da Matriz de Decisão da Sprint 2, na qual a variante V3, baseada em SRP, DIP e ISP, obteve 115 pontos ponderados, superando as alternativas avaliadas.



**5.1. Princípios SOLID Aplicados**

**Dependency Inversion Principle (DIP) — Princípio da Inversão de Dependência:**



O princípio DIP estabelece que os módulos de alto nível, responsáveis pelas regras de negócio, não devem depender diretamente de implementações específicas da infraestrutura. Ambos devem depender de abstrações, como interfaces e contratos, permitindo que as tecnologias utilizadas sejam substituídas sem comprometer o funcionamento do domínio.

No Gird the Grid, esse princípio é aplicado por meio da arquitetura Ports \& Adapters. As interfaces que definem os contratos de comunicação são declaradas na camada de domínio, em src/gird/\*/portas/contratos.py, enquanto as implementações concretas ficam na camada de infraestrutura, em src/gird/\*/implementacao/. Por exemplo, o domínio utiliza a interface IFilaProvider para acessar os serviços de mensageria, sem depender diretamente do Apache Kafka. A infraestrutura fornece a implementação concreta FilaKafka, que pode ser substituída por outra implementação, como FilaEmMemoria, sem exigir alterações nas regras de negócio.

Outro exemplo é a interface IGatewayManobra, utilizada pelo módulo Autonômico para solicitar operações na rede elétrica, enquanto a implementação AdaptadorScadaLegadoXml realiza a comunicação com o sistema SCADA. A instanciação dessas implementações concretas fica centralizada em src/gird/composition\_root.py, evitando que as classes internas precisem conhecer ou criar diretamente os componentes da infraestrutura.

Dessa forma, o DIP reduz o acoplamento entre as camadas, facilita a substituição de tecnologias, permite a utilização de implementações simuladas em testes e preserva o isolamento das regras de negócio diante de mudanças na infraestrutura.



**Open/Closed Principle (OCP) — Princípio Aberto/Fechado:**



O princípio OCP estabelece que os componentes de software devem estar abertos para extensão, mas fechados para modificação. Isso significa que novas funcionalidades e comportamentos devem poder ser adicionados sem exigir alterações constantes nas classes que já implementam as regras principais do sistema.

No Gird the Grid, esse princípio é aplicado principalmente no módulo Autonômico, responsável pelo planejamento e pela redistribuição de carga elétrica. O sistema utiliza a interface IEstrategiaRedistribuicao para definir um contrato comum entre diferentes algoritmos de otimização. Dessa forma, quando surge a necessidade de adicionar uma nova estratégia de redistribuição, basta criar uma nova classe que implemente essa interface, sem modificar as estratégias existentes ou o funcionamento principal do Planejador.

O mesmo conceito é utilizado na ingestão de telemetria. A classe abstrata CriadorConector permite incorporar novos protocolos de comunicação por meio de subclasses específicas, como os conectores MQTT, gRPC e Legado. Assim, a inclusão de um novo tipo de equipamento ou protocolo não exige alterações no pipeline principal de ingestão, pois a extensão ocorre por meio de uma nova implementação do contrato existente.

Com isso, o OCP permite que o Gird the Grid acompanhe a evolução dos equipamentos, protocolos e algoritmos de otimização da rede elétrica sem comprometer os componentes já existentes. Essa abordagem facilita a manutenção, reduz o risco de introdução de falhas em funcionalidades consolidadas e permite que a arquitetura evolua de maneira controlada.



**5.2. Catálogo de Padrões GoF Utilizados**



Padrão GoF	Categoria	Localização no Código (src/gird/)	Problema de Engenharia Resolvido

Factory Method	Criacional	ingestao/portas/contratos.py (CriadorConector) e ingestao/implementacao/conectores/fabrica.py (CriadorConectorMqtt, CriadorConectorGrpc, CriadorConectorLegado).	Controla a instanciação do conector adequado para cada protocolo e fabricante, sem exigir que o pipeline conheça diretamente as classes concretas.

Adapter	Estrutural	ingestao/implementacao/acl/adaptadores.py e autonomico/implementacao/acl\_scada.py.	Traduz payloads JSON proprietários e XML de sistemas legados, como concentradores e SCADA, para os modelos canônicos do domínio e realiza a conversão de volta para o formato exigido pelo SCADA.

Strategy	Comportamental	autonomico/portas/contratos.py (IEstrategiaRedistribuicao) e autonomico/implementacao/estrategias.py.	Permite alternar entre diferentes algoritmos de redistribuição de carga, como maior margem de capacidade, priorização de cargas críticas e estratégias sugeridas por IA, eliminando estruturas condicionais complexas.

Composite	Estrutural	autonomico/implementacao/guardrails\_fisicos.py (CadeiaGuardrails).	Permite tratar os cinco Guardrails de segurança física como uma única estrutura. O Planejador e o Executor chamam verificar() uma vez e recebem todas as possíveis violações identificadas.

Template Method	Comportamental	ingestao/portas/contratos.py (CriadorConector.normalizar).	Define uma sequência padronizada para a normalização dos dados, mantendo o algoritmo principal fixo e permitindo que as subclasses implementem especificamente a criação dos adaptadores.

A utilização conjunta desses princípios e padrões contribui para uma arquitetura modular, extensível e desacoplada. O DIP estabelece a dependência por abstrações, enquanto o OCP permite incorporar novos protocolos e estratégias sem modificar os componentes existentes. Os padrões GoF complementam essa estrutura, organizando a criação de conectores, a integração com sistemas externos, a seleção de algoritmos e a validação das condições de segurança física.

Assim, o Gird the Grid consegue evoluir sua capacidade de integração e otimização da rede elétrica mantendo as responsabilidades separadas e preservando a integridade das regras de negócio.




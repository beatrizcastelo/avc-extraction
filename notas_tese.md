# Notas Importantes para a Escrita da Tese
# avc-extraction — Beatriz Castelo

## Resultados da Validação — llama3.1:8b (baseline oficial, 80 casos)

### Métricas com MAE alto — são realidade clínica, NÃO bugs

**onset_to_door MAE ~94 min**
- O MAE alto deve-se principalmente aos casos `conservador_wake_up` e `tev_isolada_fora_janela`
- Nestes casos o doente acordou com AVC (wake-up stroke) — o "início dos sintomas" é
  desconhecido e usa-se a Última Vez Visto Bem (UVB) que pode ter sido horas antes (noite anterior)
- Valores de 8-12 horas são clinicamente correctos e esperados
- NÃO é um erro do sistema — é a natureza destes episódios
- Na tese: mencionar que o onset_to_door tem alta variabilidade nos wake-up strokes
  e que isso é uma limitação clínica inerente, não do sistema

**onset_to_recan MAE ~120 min**
- Mesma razão — casos com onset desconhecido (wake-up) têm onset_to_recan muito longo
- Clinicamente correcto

---

## Limitações Conhecidas do Sistema

**tipo F1=0.475**
- O modelo confunde tipos de episódio semelhantes
- Prompt melhorado com árvore de decisão INTER vs INTRA mas ainda insuficiente
- Casos mais confusos: tev_isolada_contraindicacao vs bridging vs fibrinolise_intra_hospitalar
- Na tese: mencionar como limitação e área de melhoria futura

**admissaoorigem F1=0.644**
- O extractor de timestamps ainda confunde admissão hospital origem vs Coimbra
  em alguns casos inter-hospitalares
- Prompt melhorado com exemplo explícito "HH:MM (Tomar) | HH:MM (Coimbra)"
- Na tese: mencionar como limitação do extractor de timestamps

**tratamento**
- Campo de texto livre — difícil de comparar exactamente com ground truth
- O comparador fuzzy não captura todas as variantes de descrição
- Na tese: mencionar que a comparação de texto livre é aproximada

**door_to_puncture F1=0.582**
- Ainda a investigar — pode ser erro no extractor ou variabilidade nos dados

---

## Decisões Técnicas Importantes

**door_to_imaging — casos inter-hospitalares**
- Usa admissao_origem → tc_ce (TC feita no hospital de origem)
- NÃO usa admissao_coimbra → tc_ce (que daria valores absurdos de ~22h)
- Corrigido em fix_all_ground_truths.py e metrics.py

**onset_to_door — casos inter-hospitalares**
- Usa door2 (chegada a Coimbra) quando disponível
- Corrige bug onde o extractor colocava admissao_origem em admission

**mrs_3meses**
- Validado apenas a partir da nota de consulta dos 3 meses (_consulta)
- Não validado na carta de alta (_carta) porque esse valor não existe na carta
- O ground truth tem este valor em seguimento.mrs_3_meses

**Escalas _consulta removidas da validação**
- nihss_admissao_consulta, nihss_alta_consulta, mrs_previo_consulta, mrs_alta_consulta
- Removidas porque o ground truth não tem esses valores separados por documento
- Só mrs_3meses_consulta é validado

---

## Subconjunto de Avaliação

**eval_cases.txt** — 80 casos fixos (10 por tipo, random.seed=42)
- Usado para comparação justa entre todos os modelos
- NÃO alterar — todos os modelos têm de ser avaliados nos mesmos casos

---

## Colaborações Externas

**Rui Cunha + Tiago Taveira Gomes**
- Propuseram ajudar na avaliação e comparação de modelos LLM
- Ferramentas: Parse (orquestrador de prompts) e Spindle
- Não precisam de acesso a dados sintéticos nem a prompts
- Reunião com orientador Prof. Pedro Furtado e Dra. Margarida para decidir

**Dr. Gustavo Santos (Unidade de AVC)**
- Validação clínica dos resultados — formato ainda por definir
- Sugeriu artigo em revista de data science + segundo artigo na área da saúde

---

## Trabalho Futuro — Modelo Especializado por Variável (a explorar)

- A arquitectura actual usa o mesmo LLM para todas as variáveis (timestamps, escalas, categóricas)
- Ideia: usar o melhor modelo para cada tipo de extracção — cada agente usaria um modelo diferente
  - Agente 1 (timestamps) → modelo X
  - Agente 3 (escalas) → modelo Y
  - Agente 4 (categóricas) → modelo Z
- Tecnicamente simples — só mudar o ACTIVE_MODEL em cada agente
- Não impacta o tempo de processamento (agentes já são sequenciais)
- Os resultados da comparação de modelos já sugerem que modelos diferentes têm pontos fortes diferentes
  (ex: qwen melhor em door_to_imaging, llama melhor em tipo e complicacoes)
- ⚠️ A explorar depois de terminar os testes de todos os modelos

---

## Estrutura das Experiências para a Tese

Organizar o capítulo de resultados em 4 experiências (inspirado em Pais, 2025):

**Experiência 1 — Impacto do tamanho do modelo**
- llama3.1:8b vs llama3.2:3b vs llama3.2:1b
- Mesma família, tamanhos diferentes
- Mostra a partir de que tamanho a qualidade degrada significativamente

**Experiência 2 — Comparação entre famílias de modelos**
- llama3.1:8b vs qwen2:7b vs gemma3:4b vs qwen2.5:7b
- Modelos de tamanho semelhante, famílias diferentes
- Mostra qual família é mais adequada para extracção clínica em português

**Experiência 3 — Impacto da quantização**
- qwen2.5:7b vs qwen2.5:7b-q4_K_M (ou equivalente)
- Mesmo modelo, com e sem quantização 4-bit
- Relevante para contexto hospitalar com hardware limitado

**Experiência 4 — Análise por tipo de variável**
- Qual modelo é melhor para cada categoria de extracção
  (timestamps, métricas temporais, escalas clínicas, variáveis categóricas)
- Dados já existem nos relatórios CSV — só falta analisar e criar gráficos
- Pode levar à conclusão de usar modelos diferentes por agente (trabalho futuro)

⚠️ NÃO ESQUECER — estruturar o capítulo de resultados desta forma!

---

## Modelos Quantizados (a mencionar na tese)

- O `.env` tem uma linha comentada: `#ACTIVE_MODEL=qwen2.5:7b-instruct-q4_K_M`
- `q4_K_M` significa quantização 4-bit — reduz o tamanho do modelo em ~50% com perda mínima de qualidade
- Não testámos modelos quantizados vs não quantizados — é uma limitação a mencionar na tese
- Trabalho futuro: comparar o mesmo modelo quantizado vs não quantizado (ex: qwen2.5:7b vs qwen2.5:7b-q4_K_M)
- A literatura sugere que quantização 4-bit tem impacto mínimo na precisão mas reduz significativamente os requisitos de hardware
- Relevante para a tese porque o contexto hospitalar tem recursos computacionais limitados

---

## Gráficos para a Tese (a fazer depois de todos os modelos testados)

**Comparação de modelos:**
- Barra agrupada — F1 por variável, uma barra por modelo
- Radar chart — F1 médio por categoria (timestamps, métricas, escalas, categóricas)
- Tabela resumo — F1 médio por categoria e por modelo
- Scatter — F1 médio vs tempo de processamento (trade-off precisão/eficiência)

**Distribuição do MAE:**
- Boxplot ou violin plot por métrica temporal e por modelo
- Mostra variabilidade e outliers (wake-up strokes aparecem como outliers — é esperado)
- Muito mais informativo do que só a média do MAE
- Permite ver que o MAE alto do onset_to_door não é uniforme mas concentrado nos wake-up cases

---

## Artigo Científico

- Pedido pelo orientador Prof. Pedro Furtado
- Formato livre, como se fosse para revista científica
- Publicação prevista: arXiv ou similar
- Depende de ter resultados sólidos da comparação de modelos
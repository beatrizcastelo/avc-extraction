# Notas Importantes para a Escrita da Tese
# avc-extraction — Beatriz Castelo

## Resultados da Validação — llama3.1:8b (baseline oficial, 80 casos, F1 médio = 0.876)

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

## ⚠️ NOTA METODOLÓGICA — Uso de Regex nos Resultados Locais

Os casos corridos localmente (via `streamlit/agents/`) **não usam só o LLM** — usam também regex como pós-processador.

**O que o regex faz nos agentes:**
- `scales.py` e `categorical.py`: limpa a resposta do LLM removendo code fences de markdown (` ```json `) e extrai o JSON com `re.search(r'\{...\}', ...)` — o LLM por vezes não devolve JSON puro
- `scales.py`: extrai o número de strings como `"4 pontos"` → `4` com `re.search(r"(\d+(?:\.\d+)?)", val)`

**Implicação para a tese:**
- O sistema real é **LLM + regex**, não LLM puro
- Se se aproveitar resultados corridos localmente, é obrigatório declarar que havia pós-processamento regex
- Os resultados do Parse (Rui Cunha) podem ou não ter o mesmo pós-processamento — confirmar antes de comparar
- Não declarar isto seria inflar artificialmente a performance aparente do LLM e tornar os resultados não reprodutíveis

---

## Subconjunto de Avaliação

**Subconjunto de avaliação — 150 casos (Parse)**
- O Parse corre todos os 150 casos para todas as experiências
- Mais robusto estatisticamente do que os 80 casos usados nos testes locais
- Os resultados locais (80 casos, eval_cases.txt) servem apenas como sanity check

**eval_cases.txt** — 80 casos fixos (10 por tipo, random.seed=42)
- Usado apenas nos testes locais já realizados
- NÃO é o subconjunto oficial para a tese — esse são os 150 via Parse

---

## Colaborações Externas

**Rui Cunha + Tiago Taveira Gomes**
- Estão a correr os LLMs via Parse (orquestrador de prompts) + framework omlx (MLX da Apple)
- O Parse substitui a execução local dos modelos — os resultados chegam como CSVs
- Hardware usado: Mac Studio M3 Ultra, 256 GB memória unificada, custo ~5.700–8.000 EUR
- ⚠️ As experiências restantes (qwen2.5:7b, quantização, prompt genérico) serão feitas via Parse, não localmente

**Instrução do Rui (áudio, Junho 2026) — a cumprir na tese:**
- Documentar quais os modelos que correram e quais os recursos necessários → já feito em 7-avaliacao.tex (Sec. 7.4 + Tab. hardware-req)
- Indicar o custo aproximado do hardware quando apresentar os resultados experimentais
- Distinguir motivo de limitação de precisão: indisponibilidade de build MLX vs. falta de memória
- Contextualizar o custo — não escrever só "€8.000" sem enquadramento
- Ir escrevendo à medida que os resultados chegam, não esperar por todos

**Dr. Gustavo Santos (Unidade de AVC)**
- Validação clínica dos resultados — formato ainda por definir
- Sugeriu artigo em revista de data science + segundo artigo na área da saúde

---

## Design Experimental Final (Rui Cunha, Junho 2026)

**5 Objectivos / Perguntas de Investigação:**
- O1/PI1: Efeito da dimensão dentro da família (bf16)
- O2/PI2: Efeito da família/receita de treino (bf16, mesma dimensão) + geração (Qwen2 vs 2.5) + destilados DeepSeek-R1
- O3/PI3: Efeito da quantização — bf16 → 8-bit → 4-bit (ablação em 3 modelos representativos)
- O4/PI4: Efeito da especificidade do prompt (genérico vs especificado)
- O5/PI5: Síntese — fronteira de Pareto exatidão × recursos

**19 modelos principais (maioria bf16):**
- 4 modelos sem build MLX full-precision → correm no máximo a 8-bit: Qwen2-7B, Phi-3-mini, Phi-4-mini, Mistral-7B-v0.3
- Gemma-2-9b: fp16 (bf16 indisponível, equivalente a 16-bit)

**Ablação de quantização (3 × 3 níveis):**
- Qwen2.5-7B: 4-bit ✓ + 8-bit + bf16
- Llama-3.1-8B: 4-bit ✓ + 8-bit + bf16
- Gemma-2-9b: 4-bit ✓ + 8-bit + fp16

**Hipóteses:**
- H1: Exactidão aumenta com dimensão, retornos decrescentes a partir de 7-9B
- H2: Família pesa mais nas dimensões pequenas; gerações mais recentes superam pares antigos; DeepSeek-R1 tem pior desempenho na extração estruturada
- H3: bf16 ≈ 8-bit; 4-bit degrada apreciavelmente, especialmente em modelos pequenos
- H4: Prompts especificados superam genéricos, diferença maior em modelos pequenos
- H5: Ponto óptimo = modelo intermédio (3-8B) recente + prompt especificado + 8-bit

**Nota metodológica obrigatória:** execuções principais em bf16; quantização por ablação nos 3 representativos.

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

Organizar o capítulo de resultados em 4 experiências + análise transversal.
Todas as experiências correm via Parse. Os resultados locais já existentes
servem de sanity check — se baterem com o Parse confirmam que o pipeline é equivalente.

⚠️ NOTA METODOLÓGICA:
- Exp 1-3: Parse usa os prompts clínicos específicos (streamlit/prompts/) em todos os modelos
  → garante comparação justa — só o modelo muda, tudo o resto igual
- Exp 4: Parse corre o mesmo modelo com prompts genéricos (condição A) e específicos (condição B)
  → isola exactamente a variável "qualidade do prompt"
- qwen2:7b descartado — substituído por qwen2.5:7b (mais recente e relevante)

---

**Experiência 1 — Impacto do tamanho do modelo** ⚠️ LOCAL PRONTO, FALTA PARSE
- llama3.2:1b vs llama3.2:3b vs llama3.1:8b
- Mesma família, tamanhos diferentes — mostra a partir de que tamanho a qualidade degrada
- Resultados locais: F1 = 0.405 / 0.664 / 0.876
- Nota para a tese: llama3.1 e llama3.2 são gerações diferentes (variável confundidora);
  reframeár como "modelos pequenos disponíveis para deployment on-premise" em vez de
  "impacto puro do tamanho"

**Experiência 2 — Comparação entre famílias de modelos** ⚠️ FALTA qwen2.5:7b (Parse)
- llama3.1:8b vs qwen2.5:7b vs gemma3:4b
- Modelos de tamanho semelhante (~7-8b), famílias diferentes
- Mostra qual família é mais adequada para extracção clínica em português
- Resultados parciais: llama3.1:8b F1=0.876, gemma3:4b F1=0.769

**Experiência 3 — Impacto da quantização** ❌ PENDENTE (Parse)
- qwen2.5:7b vs qwen2.5:7b-q4_K_M
- Mesmo modelo, com e sem quantização 4-bit
- Relevante para contexto hospitalar com hardware limitado
- A literatura sugere perda mínima de qualidade com redução ~50% de memória

**Experiência 4 — Impacto do Prompt Engineering** ❌ PENDENTE (Parse)
- Modelo fixo: llama3.1:8b (baseline)
- Mesmos 80 casos (eval_cases.txt)
- Condição A: prompts genéricos do Parse
- Condição B: prompts clínicos especializados (streamlit/prompts/)
- A diferença de F1 entre A e B justifica o investimento em prompt engineering
  para NLP clínico em português
- Os resultados locais já existentes (F1=0.876) podem servir como condição B
  se o Parse confirmar que o pipeline é equivalente

**Análise transversal — por tipo de variável** (subsecção dentro de cada experiência)
- Qual modelo é melhor para cada categoria: timestamps / métricas / escalas / categóricas
- Não é uma experiência separada — é uma lente de análise aplicada às Exp 1-3
- Pode levar à conclusão de usar modelos diferentes por agente (trabalho futuro)

⚠️ NÃO ESQUECER — estruturar o capítulo de resultados desta forma!

---

## Pipeline de Avaliação com Parse (workflow actual)

O Parse (Rui Cunha + Tiago Taveira Gomes) corre os LLMs nos casos clínicos e devolve CSVs.
O sistema local deixou de ser usado para correr os modelos — só para processar os resultados.

**Colunas dos CSVs do Parse:**
```
case_id | model | extracted_fields.extracted key | extracted_fields.extracted value
ground_truth | exact_match | fuzzy_match
```

**Como processar:**
1. Colocar CSVs do Parse em `csv_results/`
2. Correr `python evaluate_csv_results.py`
3. Ver resultados em `csv_eval_reports/` (CSV + Excel com cores)

**O que o script faz:**
- Aplica limpeza regex por tipo de campo (numérico, timestamp, métrica, categórico)
- Recomputa exact_match e fuzzy_match com valores limpos
- Calcula Prec/Rec/F1/MAE antes e depois da limpeza, por modelo e grupo de variáveis
- Mostra ΔF1 — quanto cada modelo beneficia da limpeza

---

## Modelos Quantizados (a mencionar na tese)

- O `.env` tem uma linha comentada: `#ACTIVE_MODEL=qwen2.5:7b-instruct-q4_K_M`
- `q4_K_M` significa quantização 4-bit — reduz o tamanho do modelo em ~50% com perda mínima de qualidade
- Não testámos modelos quantizados vs não quantizados — é uma limitação a mencionar na tese
- Trabalho futuro: comparar o mesmo modelo quantizado vs não quantizado (ex: qwen2.5:7b vs qwen2.5:7b-q4_K_M)
- A literatura sugere que quantização 4-bit tem impacto mínimo na precisão mas reduz significativamente os requisitos de hardware
- Relevante para a tese porque o contexto hospitalar tem recursos computacionais limitados

---

## Gráficos para a Tese ❌ A FAZER (aguarda resultados completos do Parse)

**Input:** CSVs do Parse → `csv_results/` → `evaluate_csv_results.py` → `csv_eval_reports/`

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

**Impacto da limpeza regex:**
- Barra side-by-side: F1 antes vs depois da limpeza regex, por modelo
- Identifica quais modelos beneficiam mais dos helpers de normalização
- Gerado automaticamente pelo `evaluate_csv_results.py`

---

## Artigo Científico

- Pedido pelo orientador Prof. Pedro Furtado
- Formato livre, como se fosse para revista científica
- Publicação prevista: arXiv ou similar
- Depende de ter resultados sólidos da comparação de modelos
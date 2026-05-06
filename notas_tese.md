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

## Artigo Científico

- Pedido pelo orientador Prof. Pedro Furtado
- Formato livre, como se fosse para revista científica
- Publicação prevista: arXiv ou similar
- Depende de ter resultados sólidos da comparação de modelos
#!/bin/bash
# Arranca o servidor Ollama em background
ollama serve &
OLLAMA_PID=$!
 
# Espera que o servidor esteja pronto
echo "A aguardar Ollama..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
  sleep 2
done
 
# Faz pull dos modelos listados em MODELS_TO_PULL (separados por vírgula)
# Nota: não usar OLLAMA_MODELS — o Ollama usa essa variável como directório de modelos
# Exemplo no .env: MODELS_TO_PULL=llama3.1:8b,phi3
MODELS="${MODELS_TO_PULL:-${ACTIVE_MODEL:-llama3.1:8b}}"
 
IFS=',' read -ra MODEL_LIST <<< "$MODELS"
for MODEL in "${MODEL_LIST[@]}"; do
  MODEL=$(echo "$MODEL" | xargs)  # remove espaços
  echo "A descarregar modelo: $MODEL"
  ollama pull "$MODEL"
  echo "✓ $MODEL pronto."
done
 
echo "Todos os modelos prontos."
 
# Mantém o servidor em foreground
wait $OLLAMA_PID
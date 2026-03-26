# AVC Extraction — LLM Pipeline para Extração de Dados Clínicos

Dissertação de Mestrado em IA e Ciência de Dados — Universidade de Coimbra  
Orientador: Prof. Pedro Furtado | Colaboração: ULS Coimbra

## Contexto
Pipeline de extração automática de informação clínica estruturada
de cartas de alta de AVC isquémico, usando Small Language Models
executados localmente (privacidade RGPD).

## Requisitos
- Docker + Docker Compose
- ~6 GB de espaço para o modelo

## Arranque rápido
```bash
docker-compose up --build
# Depois: docker exec ollama ollama pull qwen2.5:7b-instruct-q4_K_M
# Abrir: http://localhost:8501

#Nota: FALTA COMPLETAR O READ ME !!!! Depois ver se o Adelino quer ver!!! 

# terraform-ai-backend

Backend FastAPI que combina um LLM local (Ollama) com templates Terraform para gerar e aplicar infraestrutura AWS a partir de linguagem natural.

## Como funciona

```
Prompt → LLM (extrai tipo + params) → Template HCL → terraform plan/apply → AWS
```

O LLM **não gera HCL** — apenas extrai a intenção. O HCL vem de templates Python pré-validados, garantindo código correto independente do modelo.

## Stack

- **FastAPI** — API HTTP + SSE streaming
- **Ollama** — LLM local (llama3.2:3b, codellama, etc.)
- **Terraform 1.9.x** — provider AWS ~> 5.0
- **Kubernetes** — deploy via kind (POC) ou EKS (produção)

## Estrutura

```
app/
├── main.py          # Rotas FastAPI (thin layer)
├── extractor.py     # Chama o LLM para extrair tipo + parâmetros
├── pipeline.py      # Executa terraform init/validate/plan/apply
└── templates/
    ├── base.py      # Classe abstrata TerraformTemplate
    ├── s3.py        # aws_s3_bucket (+ versioning, encryption, public access block)
    ├── lambda_.py   # aws_lambda_function (+ IAM role, CloudWatch Logs)
    ├── sqs.py       # aws_sqs_queue (+ dead letter queue opcional)
    └── __init__.py  # Registry automático
```

## Adicionar um novo recurso

1. Criar `app/templates/meu_recurso.py` herdando `TerraformTemplate`
2. Implementar `name`, `description` e `render(params) -> dict`
3. Importar em `app/templates/__init__.py`

```python
# app/templates/rds.py
from .base import TerraformTemplate

class RDSInstanceTemplate(TerraformTemplate):
    name        = "rds_instance"
    description = "RDS PostgreSQL com backup e multi-AZ opcional"

    def render(self, params: dict) -> dict:
        nome = params.get("nome", "meu-banco")
        # ... retorna {"recurso", "resumo", "provider_region", "arquivos"}
```

```python
# app/templates/__init__.py
from .rds import RDSInstanceTemplate  # adicionar esta linha
```

## Deploy local (kind)

```bash
# Build
docker build -t terraform-ai-backend:latest .
kind load docker-image terraform-ai-backend:latest --name terraform-ai

# Credenciais AWS
kubectl create secret generic aws-credentials -n ai-infra \
  --from-literal=AWS_ACCESS_KEY_ID=... \
  --from-literal=AWS_SECRET_ACCESS_KEY=... \
  --from-literal=AWS_DEFAULT_REGION=us-east-1

# Deploy
kubectl apply -f k8s/deployment.yaml

# Testar
kubectl port-forward -n ai-infra svc/terraform-ai-backend 8080:8080
curl http://localhost:8080/health
curl http://localhost:8080/templates
```

## Variáveis de ambiente

| Variável            | Padrão                                              | Descrição                        |
|---------------------|-----------------------------------------------------|----------------------------------|
| `OLLAMA_URL`        | `http://ollama.ai-infra.svc.cluster.local:11434`    | URL do servidor Ollama           |
| `TF_STATE_BUCKET`   | `""`                                                | Bucket S3 para o terraform state |
| `AWS_REGION`        | `us-east-1`                                         | Região padrão AWS                |
| `AWS_ACCESS_KEY_ID` | —                                                   | Credenciais AWS (ou use IRSA)    |

## Endpoints

| Método | Path         | Descrição                              |
|--------|--------------|----------------------------------------|
| GET    | `/health`    | Status do serviço + templates ativos   |
| GET    | `/templates` | Lista recursos suportados              |
| POST   | `/generate`  | Gera e opcionalmente aplica o Terraform|
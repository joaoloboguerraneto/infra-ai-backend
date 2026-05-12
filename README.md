# aiterraform

AI-powered Terraform backend that uses a local LLM (Ollama on Kubernetes) to extract infrastructure intent from natural language and generate validated HCL via pre-built templates. Supports S3, Lambda, SQS — extensible by design.

## Como funciona

```
Prompt → LLM extrai {type, params} → Template gera HCL → terraform plan/apply → AWS
```

O LLM **não gera HCL** — apenas extrai a intenção. O HCL vem de templates Python pré-validados.

## Estrutura

```
aiterraform/
├── app/
│   ├── main.py              # Rotas FastAPI
│   ├── extractor.py         # LLM → {type, params}
│   ├── pipeline.py          # terraform init/validate/plan/apply
│   └── templates/
│       ├── base.py          # Classe abstrata TerraformTemplate
│       ├── s3.py            # S3 Bucket
│       ├── lambda_.py       # Lambda Function
│       ├── sqs.py           # SQS Queue
│       └── __init__.py      # Registry automático
├── frontend/
│   └── index.html           # UI: plan → confirmar → apply
├── k8s/
│   ├── 00-namespace.yaml
│   ├── 01-ollama.yaml       # PVC + Deployment + Service
│   ├── 02-aws-secret.yaml.template
│   ├── 03-backend.yaml
│   └── 04-frontend.yaml
├── Dockerfile
├── Makefile
├── providers.tf
└── requirements.txt
```

## Setup

### 1. Cluster kind

```bash
kind create cluster --name terraform-ai
```

### 2. Recursos AWS para o state

```bash
aws s3 mb s3://unicred-terraform-state-poc --region us-east-1
aws dynamodb create-table --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region us-east-1
```

### 3. Deploy completo

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1

make apply-k8s   # namespace + secrets + todos os manifests
make deploy      # build docker + kind load + rollout
make pull-model  # ollama pull llama3.2:3b
```

### 4. Acessar

```bash
make pf          # sobe os 3 port-forwards
open http://localhost:3000
```

## Uso diário

```bash
make deploy    # rebuild e redeploy do backend
make frontend  # atualiza o frontend/index.html no ConfigMap
make logs      # logs em tempo real
make pf        # port-forwards
```

## Adicionar novo recurso

1. Criar `app/templates/rds.py` herdando `TerraformTemplate`
2. Implementar `name`, `description` e `render(params)`
3. Importar em `app/templates/__init__.py`
4. `make deploy`

## Endpoints

| Método | Path         | Descrição                              |
|--------|--------------|----------------------------------------|
| GET    | `/health`    | Status + templates + credenciais AWS   |
| GET    | `/templates` | Recursos suportados                    |
| POST   | `/generate`  | Gera e aplica Terraform via SSE        |
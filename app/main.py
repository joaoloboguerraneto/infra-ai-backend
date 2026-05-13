import json
import os
from enum import Enum
from typing import Optional

from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.extractor import LLMExtractor
from app.pipeline import TerraformPipeline
from app.templates import get_registry
from app.routes_azure import router as azure_router
from app.routes_teams import router as teams_router

# ── Config ───────────────────────────────────────────────────────────────────
OLLAMA_URL      = os.getenv("OLLAMA_URL",      "http://ollama.ai-infra.svc.cluster.local:11434")
TF_STATE_BUCKET = os.getenv("TF_STATE_BUCKET", "")
AWS_REGION      = os.getenv("AWS_REGION",      "us-east-1")

REGISTRY  = get_registry()
extractor = LLMExtractor(ollama_url=OLLAMA_URL, supported_types=list(REGISTRY.keys()))
pipeline  = TerraformPipeline(state_bucket=TF_STATE_BUCKET, aws_region=AWS_REGION)

# ── Pydantic models ───────────────────────────────────────────────────────────

class ActionEnum(str, Enum):
    plan   = "plan"
    apply  = "apply"
    delete = "delete"


class GenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=5,
        description="Pedido em linguagem natural — recurso AWS ou repositório Azure DevOps.",
        examples=["cria um bucket S3 chamado unicred-poc na us-east-1"],
    )
    model: str = Field(
        default="llama3.2:3b",
        description="Modelo Ollama para extração de intenção.",
        examples=["llama3.2:3b", "codellama:7b"],
    )
    action: ActionEnum = Field(
        default=ActionEnum.plan,
        description=(
            "`plan` mostra o terraform plan sem criar recursos. "
            "`apply` cria os recursos na AWS. "
            "`delete` destrói os recursos. "
            "Para repositórios Azure DevOps o action é ignorado — fluxo próprio via SSE."
        ),
    )


class FileOutput(BaseModel):
    path:     str = Field(..., description="Caminho relativo do arquivo HCL.")
    conteudo: str = Field(..., description="Conteúdo HCL do arquivo.")


class TemplateInfo(BaseModel):
    name:        str = Field(..., description="Identificador do tipo de recurso.")
    description: str = Field(..., description="O que o template cria.")


class HealthResponse(BaseModel):
    status:     str  = Field(..., description="Status do serviço.")
    s3_backend: bool = Field(..., description="Backend S3 configurado.")
    aws_creds:  bool = Field(..., description="Credenciais AWS disponíveis.")
    azure_pat:  bool = Field(..., description="PAT Azure DevOps configurado.")
    templates:  list = Field(..., description="Tipos de recursos suportados.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="aiterraform",
    description=(
        "API que combina LLM local (Ollama) com templates Terraform pré-validados "
        "para criar, atualizar e destruir recursos AWS e repositórios Azure DevOps "
        "a partir de linguagem natural.\n\n"
        "**Recursos AWS:** S3 Bucket, Lambda Function, SQS Queue\n\n"
        "**Azure DevOps:** criação de repositórios com fluxo de aprovação por e-mail\n\n"
        "**Fluxo Terraform:** `prompt` → LLM extrai `{type, params}` → template gera HCL "
        "→ `terraform plan/apply/destroy` → AWS\n\n"
        "**Fluxo Azure:** `prompt` → detecta repositório → SSE `azure_request` "
        "→ frontend coleta e-mails → `/azure/request-repo` → aprovação → `/azure/confirm-repo`"
    ),
    version="1.0.0",
    contact={
        "name": "Unicred DevOps",
        "url":  "https://github.com/joaoloboguerraneto/aiterraform",
    },
    openapi_tags=[
        {"name": "infra",        "description": "Geração e aplicação de infraestrutura Terraform."},
        {"name": "templates",    "description": "Recursos AWS suportados."},
        {"name": "azure-devops", "description": "Criação de repositórios com fluxo de aprovação."},
        {"name": "system",       "description": "Health check e status."},
    ],
)

app.include_router(azure_router)
app.include_router(teams_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["system"],
    response_model=HealthResponse,
    summary="Health check",
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        s3_backend=bool(TF_STATE_BUCKET),
        aws_creds=bool(os.getenv("AWS_ACCESS_KEY_ID")),
        azure_pat=bool(os.getenv("AZURE_DEVOPS_PAT")),
        templates=list(REGISTRY.keys()),
    )


@app.get(
    "/templates",
    tags=["templates"],
    response_model=list[TemplateInfo],
    summary="Listar templates disponíveis",
)
async def list_templates() -> list[TemplateInfo]:
    return [
        TemplateInfo(name=name, description=tpl.description)
        for name, tpl in REGISTRY.items()
    ]


@app.post(
    "/generate",
    tags=["infra"],
    summary="Gerar e aplicar Terraform ou detectar Azure DevOps",
    description=(
        "Recebe prompt em linguagem natural e executa o pipeline correto.\n\n"
        "**Para recursos AWS** (S3, Lambda, SQS): gera HCL e executa terraform.\n\n"
        "**Para repositórios Azure DevOps**: retorna evento SSE `azure_request` "
        "com o nome do repositório detectado. O frontend deve então coletar "
        "os e-mails e chamar `/azure/request-repo`.\n\n"
        "Resposta em **SSE** (Server-Sent Events): `data: {json}\\n\\n`.\n\n"
        "Detecção automática: palavras como *remover*, *deletar* → `action=delete`. "
        "Palavras como *repositório*, *repo*, *azure* → fluxo Azure DevOps."
    ),
    responses={
        200: {
            "description": "Stream SSE com eventos do pipeline.",
            "content": {
                "text/event-stream": {
                    "example": (
                        'data: {"step":"llm","msg":"Detectando recurso..."}\n\n'
                        'data: {"step":"azure_request","repo_name":"test-ia-unicred","org":"unicredbr","project":"TI"}\n\n'
                    ),
                }
            },
        },
    },
)
async def generate(
    body: GenerateRequest = Body(
        examples={
            "s3_plan": {
                "summary": "Plan — S3 Bucket",
                "value": {"prompt": "cria um bucket S3 chamado unicred-poc na us-east-1", "model": "llama3.2:3b", "action": "plan"},
            },
            "s3_apply": {
                "summary": "Apply — S3 Bucket",
                "value": {"prompt": "cria um bucket S3 chamado unicred-poc na us-east-1", "model": "llama3.2:3b", "action": "apply"},
            },
            "sqs_dlq": {
                "summary": "Apply — SQS com DLQ",
                "value": {"prompt": "fila SQS eventos-pix com dead letter queue", "model": "llama3.2:3b", "action": "apply"},
            },
            "delete_s3": {
                "summary": "Delete — S3",
                "value": {"prompt": "deletar o bucket S3 unicred-poc", "model": "llama3.2:3b", "action": "delete"},
            },
            "azure_repo": {
                "summary": "Azure DevOps — criar repositório",
                "value": {"prompt": "crie um repositorio test-ia-unicred", "model": "llama3.2:3b", "action": "plan"},
            },
        }
    ),
):
    return StreamingResponse(
        _stream(body.prompt, body.model, body.action.value),
        media_type="text/event-stream",
    )


@app.post(
    "/render",
    tags=["templates"],
    response_model=list[FileOutput],
    summary="Renderizar template diretamente (sem LLM)",
    responses={404: {"description": "Tipo de recurso não suportado."}},
)
async def render(
    resource_type: str  = Body(..., description="Tipo do recurso.", examples=["s3_bucket"]),
    params:        dict = Body(..., description="Parâmetros.", examples=[{"nome": "unicred-poc", "region": "us-east-1"}]),
):
    if resource_type not in REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Tipo '{resource_type}' nao suportado. Disponiveis: {list(REGISTRY.keys())}",
        )
    data = REGISTRY[resource_type].render(params)
    return [FileOutput(path=f["path"], conteudo=f["conteudo"]) for f in data["arquivos"]]


# ── Stream ────────────────────────────────────────────────────────────────────

async def _stream(prompt: str, model: str, action: str):
    def event(step: str, msg: str) -> str:
        return f"data: {json.dumps({'step': step, 'msg': msg})}\n\n"

    print(f"\n{'='*60}", flush=True)
    print(f"prompt: {prompt[:80]}", flush=True)

    yield event("llm", f"Detectando recurso com {model}...")

    try:
        extracted = await extractor.extract(prompt, model)
    except ValueError as e:
        yield event("error", str(e))
        return

    rtype  = extracted.get("type", "")
    params = extracted.get("params", {})

    # Intenção de deleção no prompt sobrescreve action
    if extracted.get("delete_intent") and action != "delete":
        print(f"delete_intent detectado — forcando action=delete", flush=True)
        action = "delete"

    print(f"type={rtype} params={params} action={action}", flush=True)

    # ── Azure DevOps — fluxo especial sem Terraform ───────────────────────────
    if rtype == "azure_repo":
        repo_name = params.get("nome", "novo-repositorio")
        org       = params.get("org", "unicredbr")
        project   = params.get("project", "TI")
        print(f"azure_repo: {repo_name} em {org}/{project}", flush=True)
        yield f"data: {json.dumps({'step': 'azure_request', 'repo_name': repo_name, 'org': org, 'project': project, 'msg': 'Repositorio Azure DevOps detectado'})}\n\n"
        return

    # ── Terraform — recursos AWS ──────────────────────────────────────────────
    if rtype not in REGISTRY:
        supported = ", ".join(REGISTRY.keys())
        yield event("error", f'Tipo "{rtype}" nao suportado. Disponiveis: {supported}')
        return

    tmpl = REGISTRY[rtype]
    data = tmpl.render(params)
    data["_params"] = params

    print(f"template: {data['recurso']} — {data['resumo']}", flush=True)

    yield f"data: {json.dumps({'step': 'hcl', 'files': data['arquivos'], 'resumo': data['resumo'], 'recurso': data['recurso']})}\n\n"

    async for chunk in pipeline.run(data, action, template=tmpl):
        yield chunk
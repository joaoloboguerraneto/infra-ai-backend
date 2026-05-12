import json
import os
from enum import Enum
from typing import Optional

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.extractor import LLMExtractor
from app.pipeline import TerraformPipeline
from app.templates import get_registry

# ── Config ───────────────────────────────────────────────────────────────────
OLLAMA_URL      = os.getenv("OLLAMA_URL",      "http://ollama.ai-infra.svc.cluster.local:11434")
TF_STATE_BUCKET = os.getenv("TF_STATE_BUCKET", "")
AWS_REGION      = os.getenv("AWS_REGION",      "us-east-1")

REGISTRY  = get_registry()
extractor = LLMExtractor(ollama_url=OLLAMA_URL, supported_types=list(REGISTRY.keys()))
pipeline  = TerraformPipeline(state_bucket=TF_STATE_BUCKET, aws_region=AWS_REGION)

# ── Pydantic models ───────────────────────────────────────────────────────────

class ActionEnum(str, Enum):
    plan  = "plan"
    apply = "apply"
    delete = "delete"


class GenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=5,
        description="Pedido em linguagem natural descrevendo o recurso AWS a criar.",
        examples=["cria um bucket S3 chamado unicred-poc na us-east-1"],
    )
    model: str = Field(
        default="llama3.2:3b",
        description="Modelo Ollama a usar para extração de intenção.",
        examples=["llama3.2:3b", "codellama:7b"],
    )
    action: ActionEnum = Field(
        default=ActionEnum.plan,
        description=(
            "`plan` retorna o terraform plan sem criar recursos. "
            "`apply` executa o terraform apply e cria os recursos na AWS."
        ),
    )


class FileOutput(BaseModel):
    path:     str = Field(..., description="Caminho relativo do arquivo HCL gerado.")
    conteudo: str = Field(..., description="Conteúdo HCL do arquivo.")


class TemplateInfo(BaseModel):
    name:        str = Field(..., description="Identificador do tipo de recurso.")
    description: str = Field(..., description="Descrição do que o template cria.")


class HealthResponse(BaseModel):
    status:     str  = Field(..., description="Status do serviço.")
    s3_backend: bool = Field(..., description="Se o backend S3 para state está configurado.")
    aws_creds:  bool = Field(..., description="Se as credenciais AWS estão disponíveis no pod.")
    templates:  list = Field(..., description="Tipos de recursos suportados.")


class SseEvent(BaseModel):
    step: str = Field(
        ...,
        description=(
            "Etapa do pipeline. Valores: "
            "`llm` (extração), `hcl` (arquivos gerados), `init` (terraform init), "
            "`init_out` (output do init), `plan` (terraform plan), `plan_out` (output do plan), "
            "`plan_done` (plan concluído, aguardando apply), `apply` (terraform apply), "
            "`apply_out` (output do apply), `done` (concluído), `error` (falha)."
        ),
    )
    msg: Optional[str] = Field(None, description="Mensagem de texto da etapa.")
    files: Optional[list] = Field(None, description="Arquivos HCL gerados (somente no step `hcl`).")
    resumo:  Optional[str] = Field(None, description="Resumo do recurso (somente no step `hcl`).")
    recurso: Optional[str] = Field(None, description="Tipo do recurso detectado (somente no step `hcl`).")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="aiterraform",
    description=(
        "API que combina um LLM local (Ollama) com templates Terraform pré-validados "
        "para criar recursos AWS a partir de linguagem natural.\n\n"
        "**Fluxo:** `prompt` → LLM extrai `{type, params}` → template gera HCL "
        "→ `terraform plan/apply` → AWS\n\n"
        "O endpoint `/generate` usa **Server-Sent Events (SSE)** para transmitir "
        "o output do terraform em tempo real. Use `action=plan` para visualizar "
        "o plan antes de aplicar."
    ),
    version="1.0.0",
    contact={
        "name":  "Unicred DevOps",
        "url":   "https://github.com/joaoloboguerraneto/aiterraform",
        "email": "devops@unicred.com.br",
    },
    license_info={
        "name": "MIT",
        "url":  "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {"name": "infra",      "description": "Geração e aplicação de infraestrutura Terraform."},
        {"name": "templates",  "description": "Recursos AWS suportados."},
        {"name": "system",     "description": "Health check e status do serviço."},
    ],
)

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
    description="Retorna o status do serviço, configuração do backend S3 e credenciais AWS.",
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        s3_backend=bool(TF_STATE_BUCKET),
        aws_creds=bool(os.getenv("AWS_ACCESS_KEY_ID")),
        templates=list(REGISTRY.keys()),
    )


@app.get(
    "/templates",
    tags=["templates"],
    response_model=list[TemplateInfo],
    summary="Listar templates disponíveis",
    description="Retorna todos os tipos de recursos AWS suportados e suas descrições.",
)
async def list_templates() -> list[TemplateInfo]:
    return [
        TemplateInfo(name=name, description=tpl.description)
        for name, tpl in REGISTRY.items()
    ]


@app.post(
    "/generate",
    tags=["infra"],
    summary="Gerar e aplicar Terraform",
    description=(
        "Recebe um pedido em linguagem natural, gera o HCL via template "
        "e executa o pipeline Terraform.\n\n"
        "A resposta é um stream **Server-Sent Events (SSE)**. "
        "Cada evento é uma linha `data: {json}\\n\\n` com o campo `step` "
        "indicando a etapa atual.\n\n"
        "**Exemplo de integração:**\n"
        "```js\n"
        "const res = await fetch('/generate', { method: 'POST', body: JSON.stringify({prompt, action}) });\n"
        "const reader = res.body.getReader();\n"
        "// processar eventos SSE linha a linha\n"
        "```\n\n"
        "Use `action=plan` para visualizar o plan sem criar recursos. "
        "Após revisar, chame novamente com `action=apply` para aplicar."
    ),
    responses={
        200: {
            "description": "Stream SSE com eventos do pipeline Terraform.",
            "content": {
                "text/event-stream": {
                    "schema": {"$ref": "#/components/schemas/SseEvent"},
                    "example": (
                        'data: {"step":"llm","msg":"Detectando recurso..."}\n\n'
                        'data: {"step":"hcl","recurso":"S3 Bucket","resumo":"Bucket unicred-poc","files":[...]}\n\n'
                        'data: {"step":"plan_out","msg":"Plan: 4 to add, 0 to change, 0 to destroy."}\n\n'
                        'data: {"step":"plan_done","msg":"Plan concluido."}\n\n'
                    ),
                }
            },
        },
        422: {"description": "Payload inválido."},
    },
)
async def generate(
    body: GenerateRequest = Body(
        examples={
            "s3": {
                "summary": "Criar bucket S3",
                "value": {
                    "prompt": "cria um bucket S3 chamado unicred-poc na us-east-1",
                    "model":  "llama3.2:3b",
                    "action": "plan",
                },
            },
            "lambda": {
                "summary": "Criar Lambda",
                "value": {
                    "prompt": "Lambda Python 3.12 chamada processador-pagamentos com 512MB",
                    "model":  "llama3.2:3b",
                    "action": "plan",
                },
            },
            "sqs": {
                "summary": "Criar fila SQS com DLQ",
                "value": {
                    "prompt": "fila SQS eventos-pix com dead letter queue",
                    "model":  "llama3.2:3b",
                    "action": "apply",
                },
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
    description=(
        "Renderiza um template diretamente passando o tipo e parâmetros — "
        "sem chamar o LLM. Útil para integração programática quando o sistema "
        "chamador já sabe o tipo de recurso e os parâmetros.\n\n"
        "Não executa terraform — apenas retorna os arquivos HCL gerados."
    ),
    responses={
        404: {"description": "Tipo de recurso não suportado."},
    },
)
async def render(
    resource_type: str = Body(..., description="Tipo do recurso.", examples=["s3_bucket"]),
    params: dict       = Body(..., description="Parâmetros do recurso.", examples=[{"nome": "unicred-poc", "region": "us-east-1"}]),
):
    from fastapi import HTTPException
    if resource_type not in REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Tipo '{resource_type}' nao suportado. Disponiveis: {list(REGISTRY.keys())}",
        )
    data = REGISTRY[resource_type].render(params)
    return [FileOutput(path=f["path"], conteudo=f["conteudo"]) for f in data["arquivos"]]


# ── Stream helper ─────────────────────────────────────────────────────────────

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

    # Intenção de deleção detectada no prompt sobrescreve o action
    if extracted.get("delete_intent") and action != "delete":
        print(f"delete_intent detectado no prompt — forçando action=delete", flush=True)
        action = "delete"

    print(f"type={rtype} params={params} action={action}", flush=True)

    if rtype not in REGISTRY:
        supported = ", ".join(REGISTRY.keys())
        yield event("error", f'Tipo "{rtype}" nao suportado. Disponiveis: {supported}')
        return

    data = REGISTRY[rtype].render(params)
    print(f"template: {data['recurso']} — {data['resumo']}", flush=True)

    yield f"data: {json.dumps({'step':'hcl','files':data['arquivos'],'resumo':data['resumo'],'recurso':data['recurso']})}\n\n"

    async for chunk in pipeline.run(data, action):
        yield chunk
import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.extractor import LLMExtractor
from app.pipeline import TerraformPipeline
from app.templates import get_registry

# ── Config via variáveis de ambiente ────────────────────────────────────────
OLLAMA_URL      = os.getenv("OLLAMA_URL",      "http://ollama.ai-infra.svc.cluster.local:11434")
TF_STATE_BUCKET = os.getenv("TF_STATE_BUCKET", "")
AWS_REGION      = os.getenv("AWS_REGION",      "us-east-1")

# ── Instâncias únicas ────────────────────────────────────────────────────────
REGISTRY = get_registry()
extractor = LLMExtractor(ollama_url=OLLAMA_URL, supported_types=list(REGISTRY.keys()))
pipeline  = TerraformPipeline(state_bucket=TF_STATE_BUCKET, aws_region=AWS_REGION)

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Terraform AI Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status":     "ok",
        "s3_backend": bool(TF_STATE_BUCKET),
        "aws_creds":  bool(os.getenv("AWS_ACCESS_KEY_ID")),
        "templates":  list(REGISTRY.keys()),
    }


@app.get("/templates")
async def list_templates():
    """Lista os recursos suportados e suas descrições."""
    return {
        name: tpl.description
        for name, tpl in REGISTRY.items()
    }


@app.post("/generate")
async def generate(body: dict):
    """
    Fluxo completo: LLM extrai intenção → template gera HCL → terraform plan/apply.
    Body: { prompt, model, action }  action = "plan" | "apply"
    Response: text/event-stream (SSE)
    """
    prompt = body.get("prompt", "")
    model  = body.get("model",  "llama3.2:3b")
    action = body.get("action", "plan")

    return StreamingResponse(
        _stream(prompt, model, action),
        media_type="text/event-stream",
    )


async def _stream(prompt: str, model: str, action: str):
    def event(step: str, msg: str) -> str:
        return f"data: {json.dumps({'step': step, 'msg': msg})}\n\n"

    # ── 1. LLM extrai tipo + parâmetros ──────────────────────────────────────
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
    print(f"type={rtype} params={params}", flush=True)

    # ── 2. Template gera HCL garantidamente correto ───────────────────────────
    if rtype not in REGISTRY:
        supported = ", ".join(REGISTRY.keys())
        yield event("error", f'Tipo "{rtype}" nao suportado. Disponiveis: {supported}')
        return

    data = REGISTRY[rtype].render(params)
    print(f"template: {data['recurso']} — {data['resumo']}", flush=True)

    yield f"data: {json.dumps({'step':'hcl','files':data['arquivos'],'resumo':data['resumo'],'recurso':data['recurso']})}\n\n"

    # ── 3. Pipeline: init → validate → plan → (apply) ────────────────────────
    async for chunk in pipeline.run(data, action):
        yield chunk
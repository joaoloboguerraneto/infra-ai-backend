"""
Integração Microsoft Teams.

/teams/message  — recebe mensagens do Power Automate (Incoming Webhook flow)
/teams/webhook  — Outgoing Webhook direto do Teams (se disponível)
"""
import json
import os
import re
import asyncio

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/teams", tags=["teams"])

TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")
BACKEND_URL       = os.getenv("BACKEND_URL", "http://localhost:8080")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


# ── Pydantic models ───────────────────────────────────────────────────────────

class TeamsMessage(BaseModel):
    text: str
    from_name: str = "usuario"

    class Config:
        # aceita tanto "from" quanto "from_name"
        populate_by_name = True
        fields = {"from_name": {"alias": "from"}}


# ── Adaptive Cards helpers ────────────────────────────────────────────────────

async def _post_to_teams(card: dict) -> bool:
    if not TEAMS_WEBHOOK_URL:
        print("[teams] TEAMS_WEBHOOK_URL nao configurado", flush=True)
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                TEAMS_WEBHOOK_URL,
                json=card,
                headers={"Content-Type": "application/json"},
            )
            print(f"[teams] card enviado: {res.status_code}", flush=True)
            return res.status_code in (200, 202)
    except Exception as e:
        print(f"[teams] ERRO ao enviar card: {e}", flush=True)
        return False


def _simple_card(title: str, text: str, color: str = "accent") -> dict:
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {"type": "TextBlock", "text": title,
                     "weight": "Bolder", "color": color},
                    {"type": "TextBlock", "text": text,
                     "wrap": True},
                ],
            },
        }],
    }


def _result_card(
    title: str, color: str,
    facts: list,
    action_url: str = None, action_label: str = None,
) -> dict:
    content = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard", "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": title,
             "weight": "Bolder", "color": color, "size": "Medium"},
            {"type": "FactSet",
             "facts": [{"title": f["label"], "value": f["value"]} for f in facts]},
        ],
    }
    if action_url:
        content["actions"] = [{
            "type": "Action.OpenUrl",
            "title": action_label or "Abrir →",
            "url":   action_url,
        }]
    return {
        "type": "message",
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive",
                         "content": content}],
    }


HELP_TEXT = (
    "**aiterraform** — comandos:\n\n"
    "**AWS:**\n"
    "• `crie um bucket S3 chamado unicred-poc na us-east-1`\n"
    "• `cria uma fila SQS eventos-pix com dead letter queue`\n"
    "• `cria uma Lambda Python 3.12 processador 512MB`\n"
    "• `deletar o bucket S3 unicred-poc`\n\n"
    "**Azure DevOps:**\n"
    "• `crie um repositorio meu-servico`\n"
    "  _(após pedir: acesse o frontend para aprovar)_"
)


# ── Pipeline runner ───────────────────────────────────────────────────────────

async def _run_pipeline_and_notify(prompt: str, action: str, sender: str):
    """
    Chama o /generate em streaming e envia o resultado como card no Teams.
    Executado em background para não bloquear a resposta ao Power Automate.
    """
    hcl_ev     = {}
    plan_lines = []
    success    = False
    error_msg  = ""

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST", f"{BACKEND_URL}/generate",
                json={"prompt": prompt, "model": OLLAMA_MODEL, "action": action}
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:])
                    except Exception:
                        continue

                    step = ev.get("step", "")

                    if step == "hcl":
                        hcl_ev = ev

                    elif step in ("plan_out", "apply_out", "init_out"):
                        msg = ev.get("msg", "")
                        if msg:
                            plan_lines.append(msg)

                    elif step == "done":
                        success = True

                    elif step == "azure_request":
                        await _post_to_teams(_simple_card(
                            title=f"⬡ Repositório Azure DevOps detectado",
                            text=(
                                f"Repositório **{ev.get('repo_name')}** em "
                                f"`{ev.get('org')}/{ev.get('project')}`.\n\n"
                                "Acesse o frontend para preencher os e-mails e confirmar a criação."
                            ),
                            color="accent",
                        ))
                        return

                    elif step == "error":
                        error_msg = ev.get("msg", "Erro desconhecido")

    except Exception as e:
        error_msg = str(e)

    if error_msg:
        await _post_to_teams(_simple_card(
            title="❌ Erro — aiterraform",
            text=f"**Pedido:** {prompt[:100]}\n\n**Erro:** {error_msg}",
            color="attention",
        ))
        return

    if not hcl_ev:
        return

    recurso = hcl_ev.get("recurso", "Recurso AWS")
    resumo  = hcl_ev.get("resumo", "")

    # Resumo do plan/apply
    plan_summary = next(
        (l for l in plan_lines if "Plan:" in l or "to add" in l or "to destroy" in l),
        ""
    )

    if success and action == "apply":
        await _post_to_teams(_result_card(
            title=f"✅ Recurso criado — {recurso}",
            color="good",
            facts=[
                {"label": "Recurso",       "value": recurso},
                {"label": "Descrição",     "value": resumo},
                {"label": "Solicitado por","value": sender},
                {"label": "Resultado",     "value": plan_summary or "Apply concluído"},
            ],
        ))

    elif success and action == "delete":
        await _post_to_teams(_result_card(
            title=f"🗑 Recurso destruído — {recurso}",
            color="warning",
            facts=[
                {"label": "Recurso",       "value": recurso},
                {"label": "Descrição",     "value": resumo},
                {"label": "Solicitado por","value": sender},
            ],
        ))

    elif action == "plan":
        await _post_to_teams(_result_card(
            title=f"👁 Plan gerado — {recurso}",
            color="accent",
            facts=[
                {"label": "Recurso",   "value": recurso},
                {"label": "Descrição", "value": resumo},
                {"label": "Plan",      "value": plan_summary or "Ver frontend para detalhes"},
            ],
        ))


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/message",
    summary="Recebe mensagem do Power Automate",
    description=(
        "Endpoint chamado pelo Power Automate quando uma mensagem é enviada no canal Teams.\n\n"
        "Processa o prompt via LLM + Terraform e envia o resultado de volta "
        "ao canal via Incoming Webhook (TEAMS_WEBHOOK_URL).\n\n"
        "**Body esperado:**\n"
        "```json\n"
        "{\"text\": \"@aiterraform crie um bucket S3...\", \"from\": \"Nome do Usuário\"}\n"
        "```"
    ),
)
async def receive_message(request: Request):
    body = await request.json()

    # Aceitar tanto "from" quanto "from_name"
    raw    = body.get("text", "")
    sender = body.get("from", body.get("from_name", "usuario"))

    # Limpar HTML do Teams e remover menção ao bot
    clean  = re.sub(r"<[^>]+>", "", raw).strip()
    prompt = re.sub(r"@aiterraform\s*", "", clean, flags=re.IGNORECASE).strip()

    print(f"[teams] mensagem de {sender}: {prompt[:80]}", flush=True)

    if not prompt or prompt.lower() in ("ajuda", "help", "?", "comandos"):
        asyncio.create_task(_post_to_teams(_simple_card(
            "✦ aiterraform — ajuda", HELP_TEXT, "accent"
        )))
        return {"status": "ok", "action": "help"}

    # Detectar action pelo prompt
    if re.search(r"\bdelet[ae][r]?\b|\bremov[e]?[r]?\b|\bdestrui[r]?\b", prompt, re.IGNORECASE):
        action = "delete"
    elif re.search(r"\bplanejar?\b|\bver plan\b|\bonly plan\b", prompt, re.IGNORECASE):
        action = "plan"
    else:
        action = "apply"

    print(f"[teams] action={action} prompt={prompt[:60]}", flush=True)

    # Confirmar recebimento imediatamente (Teams/Power Automate tem timeout curto)
    asyncio.create_task(_run_pipeline_and_notify(prompt, action, sender))

    return {
        "status":  "processing",
        "prompt":  prompt,
        "action":  action,
        "from":    sender,
    }


@router.get(
    "/message",
    summary="Health check do endpoint Teams",
    include_in_schema=False,
)
async def message_health():
    return {
        "status": "ok",
        "webhook_configured": bool(TEAMS_WEBHOOK_URL),
        "model": OLLAMA_MODEL,
    }
"""
Integração Microsoft Teams via Power Automate + Incoming Webhook.
"""
import json
import os
import re
import asyncio

import httpx
from fastapi import APIRouter, Request

router = APIRouter(prefix="/teams", tags=["teams"])

TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")
BACKEND_URL       = os.getenv("BACKEND_URL", "http://localhost:8080")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

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


# ── Card helpers ─────────────────────────────────────────────────────────────

async def _post_card(card: dict) -> bool:
    """Envia Adaptive Card para o canal Teams via Incoming Webhook."""
    if not TEAMS_WEBHOOK_URL:
        print("[teams] TEAMS_WEBHOOK_URL nao configurado", flush=True)
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                TEAMS_WEBHOOK_URL, json=card,
                headers={"Content-Type": "application/json"},
            )
            print(f"[teams] card enviado: {res.status_code}", flush=True)
            return res.status_code in (200, 202)
    except Exception as e:
        print(f"[teams] ERRO ao enviar card: {e}", flush=True)
        return False


def _card(title: str, text: str, color: str = "accent", url: str = None) -> dict:
    body = [
        {"type": "TextBlock", "text": title, "weight": "Bolder",
         "color": color, "size": "Medium"},
        {"type": "TextBlock", "text": text, "wrap": True},
    ]
    content = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard", "version": "1.4", "body": body,
    }
    if url:
        content["actions"] = [{"type": "Action.OpenUrl", "title": "Abrir →", "url": url}]
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": content,
        }],
    }


# ── Pipeline runner ───────────────────────────────────────────────────────────

async def _run(prompt: str, action: str, sender: str):
    """Chama /generate e envia resultado como card no Teams."""
    hcl_ev     = {}
    plan_lines = []
    success    = False
    error_msg  = ""

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST", f"{BACKEND_URL}/generate",
                json={"prompt": prompt, "model": OLLAMA_MODEL, "action": action},
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:])
                    except Exception:
                        continue

                    s = ev.get("step", "")
                    if s == "hcl":
                        hcl_ev = ev
                    elif s in ("plan_out", "apply_out"):
                        msg = ev.get("msg", "")
                        if msg:
                            plan_lines.append(msg)
                    elif s == "done":
                        success = True
                    elif s == "azure_request":
                        await _post_card(_card(
                            "⬡ Repositório Azure DevOps detectado",
                            f"Repositório **{ev.get('repo_name')}** em "
                            f"`{ev.get('org')}/{ev.get('project')}`.\n\n"
                            "Acesse o frontend para preencher os e-mails e confirmar.",
                            "accent",
                        ))
                        return
                    elif s == "error":
                        error_msg = ev.get("msg", "")

    except Exception as e:
        error_msg = str(e)

    if error_msg:
        await _post_card(_card(
            "❌ Erro — aiterraform",
            f"**Pedido:** {prompt[:100]}\n\n**Erro:** {error_msg}",
            "attention",
        ))
        return

    if not hcl_ev:
        return

    recurso = hcl_ev.get("recurso", "Recurso AWS")
    resumo  = hcl_ev.get("resumo", "")
    plan_s  = next(
        (l for l in plan_lines if "Plan:" in l or "to add" in l or "to destroy" in l),
        "",
    )

    if success and action == "apply":
        await _post_card(_card(
            f"✅ Recurso criado — {recurso}",
            f"**{resumo}**\n\nSolicitado por: {sender}\n{plan_s}",
            "good",
        ))
    elif success and action == "delete":
        await _post_card(_card(
            f"🗑 Recurso destruído — {recurso}",
            f"**{resumo}**\n\nSolicitado por: {sender}",
            "warning",
        ))
    elif action == "plan":
        await _post_card(_card(
            f"👁 Plan gerado — {recurso}",
            f"**{resumo}**\n\n{plan_s}\n\nAcesse o frontend para aplicar.",
            "accent",
        ))


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_text(body: dict) -> str:
    """
    Extrai o texto da mensagem de qualquer estrutura que o Power Automate envie.
    Tenta vários caminhos de campos antes de desistir.
    """
    # Campos diretos
    for key in ("text", "Text", "content", "Content", "message", "Message"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return val

    # Campo "body" como dict (ex: Teams schema nativo)
    body_field = body.get("body") or body.get("Body")
    if isinstance(body_field, dict):
        for sub in ("content", "Content", "text", "Text"):
            val = body_field.get(sub)
            if isinstance(val, str) and val.strip():
                return val

    return ""


def _extract_sender(body: dict) -> str:
    """Extrai nome do remetente de qualquer estrutura."""
    for key in ("from", "From", "sender", "Sender", "from_name", "displayName"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return val
        if isinstance(val, dict):
            for sub in ("displayName", "name", "user"):
                sub_val = val.get(sub)
                if isinstance(sub_val, str) and sub_val.strip():
                    return sub_val
    return "usuario"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/message",
    summary="Recebe mensagem do Power Automate",
    description=(
        "Endpoint chamado pelo Power Automate quando uma mensagem é enviada no canal Teams.\n\n"
        "Aceita JSON com qualquer estrutura — extrai automaticamente o texto e remetente.\n\n"
        "**Body mínimo:**\n"
        "```json\n"
        "{\"text\": \"crie um bucket S3...\", \"from\": \"Nome\"}\n"
        "```\n\n"
        "**Para debug:** se o campo `text` chegar vazio, o card retorna `body_keys` "
        "mostrando o que foi recebido."
    ),
)
async def receive_message(request: Request):
    content_type = request.headers.get("content-type", "")

    # Aceitar JSON e text/plain
    if "json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raw = await request.body()
            body = {"text": raw.decode("utf-8", errors="replace")}
    else:
        raw  = await request.body()
        text = raw.decode("utf-8", errors="replace")
        body = {"text": text}

    print(f"[teams] RAW BODY: {body}", flush=True)

    text   = _extract_text(body)
    sender = _extract_sender(body)

    print(f"[teams] texto={repr(text[:80])} remetente={repr(sender)}", flush=True)

    # Body vazio — enviar card de diagnóstico com os campos recebidos
    if not text.strip():
        keys = list(body.keys())
        await _post_card(_card(
            "⚠ aiterraform — mensagem vazia",
            f"Campos recebidos: `{keys}`\n\n"
            "No Power Automate, configure o Body do HTTP como:\n"
            '`{"text": "@{triggerBody()?[\'body\']?[\'content\']}"}`',
            "warning",
        ))
        return {"status": "ok", "debug": "body_vazio", "body_keys": keys}

    # Limpar HTML e menção ao bot
    clean  = re.sub(r"<[^>]+>", "", text).strip()
    prompt = re.sub(r"@aiterraform\s*", "", clean, flags=re.IGNORECASE).strip()

    if not prompt or prompt.lower() in ("ajuda", "help", "?", "comandos"):
        asyncio.create_task(_post_card(_card(
            "✦ aiterraform — ajuda", HELP_TEXT, "accent"
        )))
        return {"status": "ok", "action": "help"}

    # Detectar action
    if re.search(r"\bdelet[ae][r]?\b|\bremov[e]?[r]?\b|\bdestrui[r]?\b", prompt, re.IGNORECASE):
        action = "delete"
    elif re.search(r"\bplanejar?\b|\bver plan\b", prompt, re.IGNORECASE):
        action = "plan"
    else:
        action = "apply"

    print(f"[teams] action={action} prompt={repr(prompt[:60])}", flush=True)

    asyncio.create_task(_run(prompt, action, sender))
    return {"status": "processing", "prompt": prompt, "action": action}


@router.get("/message", include_in_schema=False)
async def message_health():
    return {"status": "ok", "webhook_configured": bool(TEAMS_WEBHOOK_URL)}
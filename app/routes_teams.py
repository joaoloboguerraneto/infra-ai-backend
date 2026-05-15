"""
Integração Microsoft Teams via Power Automate + Incoming Webhook.

Fluxo:
  1. Power Automate detecta mensagem no canal Teams
  2. POST /teams/message com o conteúdo
  3. Backend processa via LLM + Terraform
  4. Resultado enviado como Adaptive Card via Incoming Webhook
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
    "**aiterraform** — comandos disponíveis:\n\n"
    "**AWS:**\n"
    "• `crie um bucket S3 chamado unicred-poc na us-east-1`\n"
    "• `cria uma fila SQS eventos-pix com dead letter queue`\n"
    "• `cria uma Lambda Python 3.12 processador 512MB`\n"
    "• `deletar o bucket S3 unicred-poc`\n\n"
    "**Azure DevOps:**\n"
    "• `crie um repositorio meu-servico` _(acesse o frontend para aprovar)_"
)


# ── Card helpers ──────────────────────────────────────────────────────────────

async def _post_card(card: dict) -> bool:
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


# ── Text/sender extraction ────────────────────────────────────────────────────

def _extract_text(body: dict) -> str:
    """
    Extrai o texto de qualquer estrutura que o Power Automate envie.
    Tenta todos os caminhos conhecidos do Teams trigger.
    """
    # Campos diretos (string não vazia)
    for key in ("text", "Text", "messageText", "MessageText",
                "content", "Content", "message", "Message"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return val

    # Campo "body" como dict
    for body_key in ("body", "Body"):
        sub = body.get(body_key)
        if isinstance(sub, dict):
            for key in ("content", "Content", "text", "Text"):
                val = sub.get(key)
                if isinstance(val, str) and val.strip():
                    return val

    return ""


def _extract_sender(body: dict) -> str:
    """Extrai nome do remetente."""
    for key in ("from", "From", "sender", "Sender", "from_name", "displayName"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return val
        if isinstance(val, dict):
            # from.displayName
            if isinstance(val.get("displayName"), str) and val["displayName"].strip():
                return val["displayName"]
            # from.user.displayName
            user = val.get("user", {})
            if isinstance(user, dict) and isinstance(user.get("displayName"), str):
                return user["displayName"]
    return "usuario"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/message",
    summary="Recebe mensagem do Power Automate",
    description=(
        "Aceita POST do Power Automate com qualquer estrutura de body.\n\n"
        "Se o campo `text` chegar vazio, retorna card de diagnóstico no Teams "
        "mostrando os campos e valores recebidos."
    ),
)
async def receive_message(request: Request):
    raw_bytes = await request.body()
    raw_str   = raw_bytes.decode("utf-8", errors="replace")
    ct        = request.headers.get("content-type", "")

    # Log completo para debug
    print(f"[teams] CT={ct} LEN={len(raw_str)}", flush=True)
    print(f"[teams] FULL_RAW={repr(raw_str[:800])}", flush=True)

    # Parse body
    body = {}
    stripped = raw_str.strip()
    if stripped.startswith("{"):
        try:
            body = json.loads(stripped)
        except Exception:
            body = {"text": stripped}
    elif stripped:
        body = {"text": stripped}

    print(f"[teams] KEYS={list(body.keys())}", flush=True)
    print(f"[teams] VALS={[(k, repr(str(v)[:50])) for k, v in body.items()]}", flush=True)

    text   = _extract_text(body)
    sender = _extract_sender(body)

    print(f"[teams] text={repr(text[:80])} sender={repr(sender)}", flush=True)

    # Body vazio — enviar card de diagnóstico
    if not text.strip():
        vals_preview = [(k, repr(str(v)[:40])) for k, v in body.items()]
        await _post_card(_card(
            "⚠ aiterraform — mensagem vazia",
            f"**Campos recebidos:** `{list(body.keys())}`\n\n"
            f"**Valores:** `{vals_preview}`\n\n"
            "Configure o Body do HTTP no Power Automate:\n"
            '`{"text":"@{triggerBody()?[\'messageText\']}","from":"@{triggerBody()?[\'from\']?[\'user\']?[\'displayName\']}"}`',
            "warning",
        ))
        return {
            "status":    "ok",
            "debug":     "body_vazio",
            "body_keys": list(body.keys()),
            "body_vals": vals_preview,
        }

    # Limpar HTML e menção ao bot
    clean  = re.sub(r"<[^>]+>", "", text).strip()
    prompt = re.sub(r"@aiterraform\s*", "", clean, flags=re.IGNORECASE).strip()

    if not prompt or prompt.lower() in ("ajuda", "help", "?", "comandos"):
        asyncio.create_task(_post_card(_card("✦ aiterraform — ajuda", HELP_TEXT, "accent")))
        return {"status": "ok", "action": "help"}

    if re.search(r"\bdelet[ae][r]?\b|\bremov[e]?[r]?\b|\bdestrui[r]?\b", prompt, re.IGNORECASE):
        action = "delete"
    elif re.search(r"\bplanejar?\b|\bver plan\b", prompt, re.IGNORECASE):
        action = "plan"
    else:
        action = "apply"

    print(f"[teams] action={action} prompt={repr(prompt[:60])}", flush=True)

    # Enviar card de "Processando" imediatamente — feedback ao usuário
    action_label = {"apply": "Criando", "delete": "Destruindo", "plan": "Planejando"}
    asyncio.create_task(_post_card(_card(
        f"⚙ {action_label.get(action, 'Processando')}...",
        f"**Pedido:** {prompt[:100]}

_Aguarde, o LLM está processando..._",
        "accent",
    )))

    asyncio.create_task(_run(prompt, action, sender))
    return {"status": "processing", "prompt": prompt, "action": action}


@router.get("/message", include_in_schema=False)
async def message_health():
    return {"status": "ok", "webhook_configured": bool(TEAMS_WEBHOOK_URL)}
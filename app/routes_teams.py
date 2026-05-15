"""
Integração Microsoft Teams via Power Automate + Incoming Webhook.

Fluxo no Power Automate:
  1. Trigger: "Quando nova mensagem adicionada"
  2. "Obter detalhes da mensagem" (GetMessageDetails)
  3. HTTP POST /teams/message com body:
     {
       "text": "@{body('Obter_detalhes_da_mensagem')?['body']?['content']}",
       "from": "@{body('Obter_detalhes_da_mensagem')?['from']?['user']?['displayName']}"
     }
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
    "• `crie um repositorio meu-servico`"
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
            print(f"[teams] card: {res.status_code}", flush=True)
            return res.status_code in (200, 202)
    except Exception as e:
        print(f"[teams] ERRO card: {e}", flush=True)
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
                        # Card intermediario: LLM detectou o recurso
                        recurso_nome = ev.get("recurso", "Recurso")
                        resumo_nome  = ev.get("resumo", "")
                        await _post_card(_card(
                            "\u2699 " + recurso_nome + " detectado...",
                            "**" + sender + "**, identificamos:\n\n"
                            "> " + resumo_nome + "\n\n"
                            "_Executando terraform apply..._",
                            "accent",
                        ))
                    elif s in ("plan_out", "apply_out"):
                        msg = ev.get("msg", "")
                        if msg:
                            plan_lines.append(msg)
                    elif s == "done":
                        success = True
                    elif s == "azure_request":
                        await _post_card(_card(
                            "\u29e1 Repositorio Azure DevOps detectado",
                            f"Repositorio **{ev.get('repo_name')}** em "
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
            "\u274c Erro — aiterraform",
            "**Pedido:** " + prompt[:100] + "\n\n**Erro:** " + error_msg,
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
            "\u2705 Recurso criado — " + recurso,
            "**" + resumo + "**\n\n"
            + (plan_s + "\n\n" if plan_s else "")
            + "Solicitado por: **" + sender + "**",
            "good",
        ))
    elif success and action == "delete":
        await _post_card(_card(
            "\U0001f5d1 Recurso destruido — " + recurso,
            "**" + resumo + "**\n\nSolicitado por: **" + sender + "**",
            "warning",
        ))
    elif action == "plan":
        await _post_card(_card(
            "\U0001f441 Plan gerado — " + recurso,
            "**" + resumo + "**\n\n" + plan_s + "\n\nAcesse o frontend para aplicar.",
            "accent",
        ))


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_text(body: dict) -> str:
    """
    Extrai texto de qualquer estrutura.
    Prioridade:
      1. Campo "text" direto (formato {text, from})
      2. body.content do output do "Obter detalhes da mensagem"
      3. Campos alternativos
    """
    # Formato direto {text, from}
    for key in ("text", "Text", "messageText", "content", "Content", "message"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return val

    # Output do "Obter detalhes" — {body: {content: "..."}, from: {...}}
    body_field = body.get("body") or body.get("Body")
    if isinstance(body_field, dict):
        for key in ("content", "Content", "text", "Text"):
            val = body_field.get(key)
            if isinstance(val, str) and val.strip():
                return val

    return ""


def _extract_sender(body: dict) -> str:
    """Extrai nome do remetente."""
    # Formato direto
    for key in ("from", "From", "sender", "Sender", "from_name", "displayName"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return val

    # Output do "Obter detalhes" — {from: {user: {displayName: "..."}}}
    from_field = body.get("from") or body.get("From")
    if isinstance(from_field, dict):
        if isinstance(from_field.get("displayName"), str):
            return from_field["displayName"]
        user = from_field.get("user", {})
        if isinstance(user, dict) and isinstance(user.get("displayName"), str):
            return user["displayName"]

    return "usuario"


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/message", summary="Recebe mensagem do Power Automate")
async def receive_message(request: Request):
    raw_bytes = await request.body()
    raw_str   = raw_bytes.decode("utf-8", errors="replace")
    ct        = request.headers.get("content-type", "")

    print(f"[teams] CT={ct} LEN={len(raw_str)}", flush=True)
    print(f"[teams] RAW={repr(raw_str[:400])}", flush=True)

    # Parse
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

    text   = _extract_text(body)
    sender = _extract_sender(body)

    print(f"[teams] text={repr(text[:80])} sender={repr(sender)}", flush=True)

    # Body vazio — card de diagnostico com instrucoes
    if not text.strip():
        keys   = list(body.keys())
        sample = [(k, repr(str(v)[:40])) for k, v in body.items()]
        await _post_card(_card(
            "\u26a0 aiterraform — body vazio",
            "Campos recebidos: `" + str(keys) + "`\n\n"
            "Valores: `" + str(sample) + "`\n\n"
            "**Corrigir o body do HTTP no Power Automate:**\n"
            '```\n{"text":"@{body(\'Obter_detalhes_da_mensagem\')?[\'body\']?[\'content\']}","from":"@{body(\'Obter_detalhes_da_mensagem\')?[\'from\']?[\'user\']?[\'displayName\']}"}\n```',
            "warning",
        ))
        return {"status": "ok", "debug": "vazio", "keys": keys, "sample": sample}

    # Limpar HTML e mencao ao bot
    clean  = re.sub(r"<[^>]+>", "", text).strip()
    prompt = re.sub(r"@aiterraform\s*", "", clean, flags=re.IGNORECASE).strip()

    if not prompt or prompt.lower() in ("ajuda", "help", "?", "comandos"):
        asyncio.create_task(_post_card(_card(
            "\u2736 aiterraform — ajuda", HELP_TEXT, "accent"
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

    # Card imediato de confirmacao
    action_label = {"apply": "Criando recurso", "delete": "Destruindo recurso", "plan": "Gerando plan"}
    label = action_label.get(action, "Processando")
    processing_text = (
        "**" + sender + "** solicitou:\n\n"
        + "> " + prompt[:120] + "\n\n"
        + "_Aguarde, o resultado aparece aqui em instantes._"
    )
    asyncio.create_task(_post_card(_card(
        "\u2699 " + label + "...",
        processing_text,
        "accent",
    )))

    asyncio.create_task(_run(prompt, action, sender))
    return {"status": "processing", "prompt": prompt, "action": action}


@router.get("/message", include_in_schema=False)
async def message_health():
    return {"status": "ok", "webhook_configured": bool(TEAMS_WEBHOOK_URL)}
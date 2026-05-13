"""
Notificações para Microsoft Teams via Incoming Webhook.

O backend envia cards formatados ao Teams após cada operação:
  - Recurso AWS criado / destruído
  - Plan gerado aguardando aprovação
  - Repositório Azure DevOps criado
  - Aprovação pendente (com request_id + token para colar no frontend)

Configurar:
  kubectl set env deployment/terraform-ai-backend -n ai-infra \
    TEAMS_WEBHOOK_URL=https://xxx.webhook.office.com/...
"""
import json
import os
import httpx

TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")


async def _post(card: dict) -> bool:
    """Envia um Adaptive Card para o canal Teams. Retorna True se ok."""
    if not TEAMS_WEBHOOK_URL:
        print("[teams] TEAMS_WEBHOOK_URL nao configurado — notificacao ignorada", flush=True)
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                TEAMS_WEBHOOK_URL,
                json=card,
                headers={"Content-Type": "application/json"},
            )
            ok = res.status_code in (200, 202)
            print(f"[teams] notificacao enviada: {res.status_code}", flush=True)
            return ok
    except Exception as e:
        print(f"[teams] ERRO ao notificar: {e}", flush=True)
        return False


def _card(title: str, color: str, rows: list, actions: list = None) -> dict:
    """
    Adaptive Card generico.
    color: "good" | "warning" | "attention" | "accent"
    rows: lista de {"label": str, "value": str}
    """
    facts = [{"title": r["label"], "value": r["value"]} for r in rows]
    body  = [
        {
            "type": "TextBlock",
            "text": title,
            "weight": "Bolder",
            "size": "Medium",
            "color": color,
        },
        {
            "type": "FactSet",
            "facts": facts,
        },
    ]
    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": body,
            },
        }],
    }
    if actions:
        card["attachments"][0]["content"]["actions"] = actions
    return card


# ── Notificações públicas ──────────────────────────────────────────────────────

async def notify_resource_created(
    recurso: str,
    resumo:  str,
    state_key: str,
    requested_by: str = "aiterraform",
) -> None:
    """Recurso AWS criado com sucesso."""
    await _post(_card(
        title=f"✅ Recurso criado — {recurso}",
        color="good",
        rows=[
            {"label": "Recurso",      "value": recurso},
            {"label": "Descrição",    "value": resumo},
            {"label": "State",        "value": f"`{state_key}`"},
            {"label": "Solicitado por", "value": requested_by},
        ],
    ))


async def notify_resource_deleted(
    recurso: str,
    resumo:  str,
    state_key: str,
    requested_by: str = "aiterraform",
) -> None:
    """Recurso AWS destruído."""
    await _post(_card(
        title=f"🗑 Recurso destruído — {recurso}",
        color="warning",
        rows=[
            {"label": "Recurso",        "value": recurso},
            {"label": "Descrição",      "value": resumo},
            {"label": "State removido", "value": f"`{state_key}`"},
            {"label": "Solicitado por", "value": requested_by},
        ],
    ))


async def notify_plan_ready(
    recurso:   str,
    resumo:    str,
    plan_summary: str,
    frontend_url: str = "http://localhost:3000",
) -> None:
    """Plan gerado — aguardando confirmação de apply."""
    await _post(_card(
        title=f"👁 Plan gerado — {recurso}",
        color="accent",
        rows=[
            {"label": "Recurso",  "value": recurso},
            {"label": "Descrição","value": resumo},
            {"label": "Plan",     "value": f"```\n{plan_summary}\n```"},
        ],
        actions=[{
            "type":  "Action.OpenUrl",
            "title": "Abrir frontend para aplicar →",
            "url":   frontend_url,
        }],
    ))


async def notify_repo_approval_pending(
    repo_name:   str,
    org:         str,
    project:     str,
    requester:   str,
    approver:    str,
    request_id:  str,
    token:       str,
    expires_min: int,
    frontend_url: str = "http://localhost:3000",
) -> None:
    """
    Aprovação pendente para criação de repositório.
    Envia o token direto no canal (visível apenas para membros do canal).
    O aprovador pode confirmar pelo frontend ou copiar o token.
    """
    await _post(_card(
        title=f"⬡ Aprovação necessária — repositório {repo_name}",
        color="accent",
        rows=[
            {"label": "Repositório",   "value": f"`{org}/{project}/{repo_name}`"},
            {"label": "Solicitante",   "value": requester},
            {"label": "Aprovador",     "value": approver},
            {"label": "Request ID",    "value": f"`{request_id}`"},
            {"label": "Token",         "value": f"`{token}`"},
            {"label": "Expira em",     "value": f"{expires_min} minutos"},
            {"label": "Como aprovar",  "value": "Cole o Request ID e Token no frontend"},
        ],
        actions=[{
            "type":  "Action.OpenUrl",
            "title": "Abrir frontend para confirmar →",
            "url":   frontend_url,
        }],
    ))


async def notify_repo_created(
    repo_name: str,
    org:       str,
    project:   str,
    web_url:   str,
    requester: str,
) -> None:
    """Repositório Azure DevOps criado com sucesso."""
    await _post(_card(
        title=f"✅ Repositório criado — {repo_name}",
        color="good",
        rows=[
            {"label": "Repositório",   "value": f"`{org}/{project}/{repo_name}`"},
            {"label": "Solicitado por","value": requester},
            {"label": "URL",           "value": web_url},
        ],
        actions=[{
            "type":  "Action.OpenUrl",
            "title": "Abrir no Azure DevOps →",
            "url":   web_url,
        }],
    ))


async def notify_error(
    operacao: str,
    erro:     str,
    prompt:   str = "",
) -> None:
    """Erro durante operação."""
    await _post(_card(
        title=f"❌ Erro — {operacao}",
        color="attention",
        rows=[
            {"label": "Operação", "value": operacao},
            {"label": "Prompt",   "value": prompt[:100] if prompt else "—"},
            {"label": "Erro",     "value": erro[:200]},
        ],
    ))
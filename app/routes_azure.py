"""
Rotas Azure DevOps — fluxo de aprovação para criação de repositórios.

Fluxo:
  1. POST /azure/request-repo  → gera token, envia e-mail ao arquiteto
  2. Arquiteto encaminha token ao solicitante
  3. POST /azure/confirm-repo  → valida token, cria o repositório
  4. GET  /azure/pending        → lista solicitações pendentes
"""
import asyncio
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, EmailStr

from app.approvals     import approval_store
from app.azure_devops  import create_repository
from app.email_sender  import send_approval_email, send_confirmation_email

router = APIRouter(prefix="/azure", tags=["azure-devops"])

AZURE_ORG = os.getenv("AZURE_DEVOPS_ORG", "unicredbr")


# ── Pydantic models ───────────────────────────────────────────────────────────

class RepoRequest(BaseModel):
    org:             str        = Field(default=AZURE_ORG, description="Organização Azure DevOps.")
    project:         str        = Field(..., description="Nome do projeto Azure DevOps.", examples=["TI"])
    repo_name:       str        = Field(..., description="Nome do repositório a criar.", examples=["meu-servico"])
    requester_email: EmailStr   = Field(..., description="E-mail de quem solicita o repositório.")
    approver_email:  EmailStr   = Field(..., description="E-mail do arquiteto que vai aprovar.")


class RepoConfirm(BaseModel):
    request_id: str = Field(..., description="ID da solicitação recebido após o request.")
    token:      str = Field(..., description="Token de aprovação encaminhado pelo arquiteto.")


class PendingItem(BaseModel):
    request_id:     str
    org:            str
    project:        str
    repo_name:      str
    requester_email: str
    approver_email: str
    expires_in_min: int
    approved:       bool


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/request-repo",
    summary="Solicitar criação de repositório",
    description=(
        "Inicia o fluxo de aprovação:\n\n"
        "1. Gera um token único com TTL de 30 minutos\n"
        "2. Envia e-mail ao arquiteto com o token\n"
        "3. Retorna o `request_id` para uso no `/azure/confirm-repo`\n\n"
        "O arquiteto deve encaminhar o token ao solicitante."
    ),
    responses={
        200: {"description": "Solicitação criada, e-mail enviado ao aprovador."},
        500: {"description": "Erro ao enviar e-mail."},
    },
)
async def request_repo(body: RepoRequest):
    req = approval_store.create(
        org=body.org,
        project=body.project,
        repo_name=body.repo_name,
        requester_email=str(body.requester_email),
        approver_email=str(body.approver_email),
    )

    print(
        f"[azure] nova solicitação: {req.repo_name} em {req.org}/{req.project} "
        f"por {req.requester_email} → aprovador: {req.approver_email}",
        flush=True,
    )

    # Enviar e-mail ao arquiteto em background
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: send_approval_email(
                to=req.approver_email,
                repo_name=req.repo_name,
                org=req.org,
                project=req.project,
                requester=req.requester_email,
                request_id=req.request_id,
                token=req.token,
                expires_min=req.expires_in_minutes(),
            )
        )
        print(f"[azure] e-mail enviado para {req.approver_email}", flush=True)
    except Exception as e:
        print(f"[azure] ERRO ao enviar e-mail: {e}", flush=True)
        raise HTTPException(
            status_code=500,
            detail=f"Solicitação criada mas falha ao enviar e-mail: {e}",
        )

    return {
        "status":          "pending",
        "request_id":      req.request_id,
        "approver_email":  req.approver_email,
        "expires_minutes": req.expires_in_minutes(),
        "message": (
            f"E-mail de aprovação enviado para {req.approver_email}. "
            f"Aguarde o token e use /azure/confirm-repo para criar o repositório."
        ),
    }


@router.post(
    "/confirm-repo",
    summary="Confirmar aprovação e criar repositório",
    description=(
        "Valida o token recebido do arquiteto e cria o repositório no Azure DevOps.\n\n"
        "Após a criação:\n"
        "- Envia e-mail de confirmação ao solicitante\n"
        "- Retorna a URL do repositório"
    ),
    responses={
        200: {"description": "Repositório criado com sucesso."},
        400: {"description": "Token inválido ou expirado."},
        409: {"description": "Repositório já existe."},
    },
)
async def confirm_repo(body: RepoConfirm):
    req = approval_store.confirm(body.request_id, body.token)

    if req is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Token inválido ou expirado. "
                "Solicite um novo token via /azure/request-repo."
            ),
        )

    if req.executed:
        raise HTTPException(
            status_code=400,
            detail="Esta aprovação já foi utilizada.",
        )

    print(
        f"[azure] token válido — criando {req.repo_name} em {req.org}/{req.project}",
        flush=True,
    )

    try:
        repo = await create_repository(req.org, req.project, req.repo_name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao criar repositório: {e}",
        )

    approval_store.mark_executed(req.request_id)
    print(f"[azure] repositório criado: {repo['web_url']}", flush=True)

    # Notificar solicitante
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: send_confirmation_email(
                to=req.requester_email,
                repo_name=repo["name"],
                org=repo["org"],
                project=repo["project"],
                url=repo["web_url"],
            )
        )
    except Exception as e:
        print(f"[azure] AVISO: falha ao enviar confirmação: {e}", flush=True)

    return {
        "status":   "created",
        "repo":     repo["name"],
        "org":      repo["org"],
        "project":  repo["project"],
        "url":      repo["url"],
        "web_url":  repo["web_url"],
        "message":  f"Repositório '{repo['name']}' criado com sucesso!",
    }


@router.get(
    "/pending",
    response_model=list[PendingItem],
    summary="Listar aprovações pendentes",
    description="Retorna todas as solicitações pendentes não expiradas.",
)
async def list_pending():
    return [
        PendingItem(
            request_id=r.request_id,
            org=r.org,
            project=r.project,
            repo_name=r.repo_name,
            requester_email=r.requester_email,
            approver_email=r.approver_email,
            expires_in_min=r.expires_in_minutes(),
            approved=r.approved,
        )
        for r in approval_store.pending()
    ]
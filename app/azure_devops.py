"""
Cliente Azure DevOps REST API.
Cria repositórios via API sem depender do provider Terraform.
"""
import base64
import os
import httpx


AZURE_ORG = os.getenv("AZURE_DEVOPS_ORG", "unicredbr")
AZURE_PAT = os.getenv("AZURE_DEVOPS_PAT", "")
API_BASE  = "https://dev.azure.com"
API_VER   = "api-version=7.1"


def _headers() -> dict:
    """Header de autenticação Basic com PAT."""
    token   = base64.b64encode(f":{AZURE_PAT}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type":  "application/json",
    }


async def get_project_id(org: str, project: str) -> str:
    """Retorna o ID do projeto Azure DevOps."""
    url = f"{API_BASE}/{org}/_apis/projects/{project}?{API_VER}"
    async with httpx.AsyncClient(timeout=30) as client:
        res = client.get(url, headers=_headers())
        res = await client.get(url, headers=_headers())
        res.raise_for_status()
        return res.json()["id"]


async def repo_exists(org: str, project: str, repo_name: str) -> bool:
    """Verifica se um repositório já existe no projeto."""
    url = f"{API_BASE}/{org}/{project}/_apis/git/repositories/{repo_name}?{API_VER}"
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(url, headers=_headers())
        return res.status_code == 200


async def create_repository(org: str, project: str, repo_name: str) -> dict:
    """
    Cria um repositório Git no Azure DevOps.
    Retorna os dados do repositório criado incluindo a URL.
    """
    if not AZURE_PAT:
        raise ValueError(
            "AZURE_DEVOPS_PAT nao configurado. "
            "Adicione o secret no Kubernetes: "
            "kubectl create secret generic azure-devops-credentials "
            "-n ai-infra --from-literal=AZURE_DEVOPS_PAT=<seu-pat>"
        )

    # Verificar se já existe
    if await repo_exists(org, project, repo_name):
        raise ValueError(
            f"Repositório '{repo_name}' já existe em {org}/{project}."
        )

    # Buscar ID do projeto
    project_id = await get_project_id(org, project)

    # Criar repositório
    url  = f"{API_BASE}/{org}/{project}/_apis/git/repositories?{API_VER}"
    body = {
        "name":    repo_name,
        "project": {"id": project_id},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(url, headers=_headers(), json=body)
        res.raise_for_status()
        data = res.json()

    return {
        "id":        data["id"],
        "name":      data["name"],
        "url":       data["remoteUrl"],
        "web_url":   data["_links"]["web"]["href"],
        "project":   project,
        "org":       org,
    }
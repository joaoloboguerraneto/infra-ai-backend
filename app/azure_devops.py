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
    token = base64.b64encode(f":{AZURE_PAT}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type":  "application/json",
    }


async def get_project_id(org: str, project: str) -> str:
    url = f"{API_BASE}/{org}/_apis/projects/{project}?{API_VER}"
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(url, headers=_headers())
        res.raise_for_status()
        return res.json()["id"]


async def repo_exists(org: str, project: str, repo_name: str) -> bool:
    url = f"{API_BASE}/{org}/{project}/_apis/git/repositories/{repo_name}?{API_VER}"
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(url, headers=_headers())
        return res.status_code == 200


async def create_repository(org: str, project: str, repo_name: str) -> dict:
    """
    Cria um repositório Git no Azure DevOps.
    Retorna dados do repositório incluindo URL.
    """
    # Recarregar PAT em runtime (pode ter sido injetado após o import)
    pat = os.getenv("AZURE_DEVOPS_PAT", "")
    if not pat:
        raise ValueError(
            "AZURE_DEVOPS_PAT nao configurado. "
            "Adicione o secret no Kubernetes: "
            "kubectl create secret generic azure-devops-credentials "
            "-n ai-infra --from-literal=AZURE_DEVOPS_PAT=<seu-pat>"
        )

    headers = {
        "Authorization": f"Basic {base64.b64encode(f':{pat}'.encode()).decode()}",
        "Content-Type":  "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:

        # Verificar se já existe
        check_url = f"{API_BASE}/{org}/{project}/_apis/git/repositories/{repo_name}?{API_VER}"
        check     = await client.get(check_url, headers=headers)
        if check.status_code == 200:
            raise ValueError(f"Repositório '{repo_name}' já existe em {org}/{project}.")

        # Buscar ID do projeto
        proj_url = f"{API_BASE}/{org}/_apis/projects/{project}?{API_VER}"
        proj_res = await client.get(proj_url, headers=headers)
        proj_res.raise_for_status()
        project_id = proj_res.json()["id"]

        # Criar repositório
        create_url = f"{API_BASE}/{org}/{project}/_apis/git/repositories?{API_VER}"
        body       = {"name": repo_name, "project": {"id": project_id}}
        create_res = await client.post(create_url, headers=headers, json=body)
        create_res.raise_for_status()
        data = create_res.json()

    print(f"[azure] resposta da API: {list(data.keys())}", flush=True)

    # Montar URL web de forma segura — diferentes versões da API retornam estruturas distintas
    web_url = (
        data.get("_links", {}).get("web", {}).get("href")
        or data.get("webUrl")
        or f"https://dev.azure.com/{org}/{project}/_git/{repo_name}"
    )

    return {
        "id":       data["id"],
        "name":     data["name"],
        "url":      data.get("remoteUrl", data.get("sshUrl", "")),
        "web_url":  web_url,
        "project":  project,
        "org":      org,
    }
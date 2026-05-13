import json
import re
import httpx

DEAD_LETTER_KEYWORDS = [
    "dead letter", "dead-letter", "dlq", "fila morta",
    "redrive", "letra morta",
]

DELETE_KEYWORDS = [
    "delete", "deletar", "remover", "remove",
    "destruir", "destroy", "apagar", "excluir",
    "eliminar", "dropar", "drop", "tear down", "teardown",
]

AZURE_REPO_KEYWORDS = [
    "repositorio", "repositório", "repo", "repository",
    "azure devops", "azure", "devops", "git repo",
    "criar repo", "novo repo", "crie repo", "cria repo",
    "crie um repositorio", "cria um repositorio",
    "criar repositorio", "criar um repositorio",
]

EXTRACT_PROMPT_TEMPLATE = """\
Voce extrai parametros de infraestrutura de pedidos em linguagem natural.
Responda APENAS com JSON valido, sem markdown, sem texto extra.

Tipos suportados: {types}, azure_repo

Formato exato (region SEMPRE dentro de params):
{{"type":"<tipo>","params":{{"nome":"<nome>","region":"us-east-1"}}}}

Para repositorio Azure DevOps:
{{"type":"azure_repo","params":{{"nome":"<nome-do-repo>","org":"unicredbr","project":"TI"}}}}

Exemplos:
- "bucket S3 unicred-poc" -> {{"type":"s3_bucket","params":{{"nome":"unicred-poc","region":"us-east-1"}}}}
- "crie um repositorio test-ia-unicred" -> {{"type":"azure_repo","params":{{"nome":"test-ia-unicred","org":"unicredbr","project":"TI"}}}}
- "Lambda Java 21 processador-ted 512MB" -> {{"type":"lambda_function","params":{{"nome":"processador-ted","runtime":"java21","memory":512,"region":"us-east-1"}}}}
- "fila SQS eventos-pix com dead letter queue" -> {{"type":"sqs_queue","params":{{"nome":"eventos-pix","dead_letter":true,"region":"us-east-1"}}}}

Responda SOMENTE o JSON, nada mais."""


def detect_delete_intent(prompt: str) -> bool:
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in DELETE_KEYWORDS)


def detect_dead_letter(prompt: str) -> bool:
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in DEAD_LETTER_KEYWORDS)


def detect_azure_repo(prompt: str) -> bool:
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in AZURE_REPO_KEYWORDS)


def fix_json(raw: str) -> str:
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    depth = 0
    end   = 0
    for i, ch in enumerate(clean):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end:
        clean = clean[: end + 1]
    return clean


def normalize(data: dict) -> dict:
    params = data.get("params", {})
    for field in ("region", "nome", "runtime", "memory", "dead_letter", "org", "project"):
        if field in data and field not in params:
            params[field] = data.pop(field)
    if "region" not in params and data.get("type") != "azure_repo":
        params["region"] = "us-east-1"
    data["params"] = params
    return data


class LLMExtractor:
    def __init__(self, ollama_url: str, supported_types: list):
        self.ollama_url    = ollama_url
        self.system_prompt = EXTRACT_PROMPT_TEMPLATE.format(
            types=", ".join(supported_types)
        )

    async def extract(self, prompt: str, model: str) -> dict:
        # Detectar Azure repo por keywords antes de chamar o LLM
        # (modelo pequeno frequentemente nao conhece azure_repo)
        if detect_azure_repo(prompt) and not detect_delete_intent(prompt):
            nome = _extract_repo_name(prompt)
            print(f"[extractor] azure_repo detectado por keyword: nome={nome}", flush=True)
            return {
                "type":   "azure_repo",
                "params": {"nome": nome, "org": "unicredbr", "project": "TI"},
                "delete_intent": False,
            }

        async with httpx.AsyncClient(timeout=120) as client:
            res = await client.post(
                f"{self.ollama_url}/v1/chat/completions",
                json={
                    "model":   model,
                    "stream":  False,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user",   "content": prompt},
                    ],
                    "options": {"temperature": 0.05},
                },
            )

        raw = res.json()["choices"][0]["message"]["content"]
        print(f"[extractor] raw: {raw}", flush=True)

        clean = fix_json(raw)
        print(f"[extractor] fixed: {clean}", flush=True)

        try:
            result = json.loads(clean)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON invalido: {clean[:300]}") from e

        result = normalize(result)
        result["delete_intent"] = detect_delete_intent(prompt)

        if detect_dead_letter(prompt):
            result["params"]["dead_letter"] = True

        print(f"[extractor] final: {result}", flush=True)
        return result


def _extract_repo_name(prompt: str) -> str:
    """Extrai o nome do repositório do prompt via regex simples."""
    # Tentar pegar palavra após "repositorio", "repo", etc.
    patterns = [
        r'reposit[oó]rio\s+([\w\-_.]+)',
        r'repo\s+([\w\-_.]+)',
        r'repository\s+([\w\-_.]+)',
        r'chamad[ao]\s+([\w\-_.]+)',
        r'nome[d ]?\s+([\w\-_.]+)',
    ]
    for pattern in patterns:
        m = re.search(pattern, prompt.lower())
        if m:
            nome = m.group(1).strip()
            # Ignorar palavras comuns que não são nomes de repo
            if nome not in ('um', 'o', 'a', 'de', 'para', 'no', 'na', 'em'):
                return nome
    # Fallback: última palavra que pareça um nome de repo
    words = re.findall(r'[\w\-_.]{3,}', prompt)
    candidates = [w for w in words if '-' in w or w.startswith('test') or len(w) > 5]
    return candidates[-1] if candidates else "novo-repositorio"
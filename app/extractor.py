import json
import re
import httpx

DELETE_KEYWORDS = [
    "delete", "deletar", "remover", "remove",
    "destruir", "destroy", "apagar", "excluir",
    "eliminar", "dropar", "drop", "tear down", "teardown",
]

EXTRACT_PROMPT_TEMPLATE = """\
Voce extrai parametros de infraestrutura de pedidos em linguagem natural.
Responda APENAS com JSON valido, sem markdown, sem texto extra.

Tipos suportados: {types}

Formato exato (region SEMPRE dentro de params):
{{"type":"<tipo>","params":{{"nome":"<nome>","region":"us-east-1"}}}}

Exemplos:
- "bucket S3 unicred-poc" -> {{"type":"s3_bucket","params":{{"nome":"unicred-poc","region":"us-east-1"}}}}
- "Lambda Java 21 processador-ted 512MB" -> {{"type":"lambda_function","params":{{"nome":"processador-ted","runtime":"java21","memory":512,"region":"us-east-1"}}}}
- "fila SQS eventos-pix com dead letter queue" -> {{"type":"sqs_queue","params":{{"nome":"eventos-pix","dead_letter":true,"region":"us-east-1"}}}}

Responda SOMENTE o JSON, nada mais."""


def detect_delete_intent(prompt: str) -> bool:
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in DELETE_KEYWORDS)


def fix_json(raw: str) -> str:
    """Corrige problemas comuns no JSON retornado pelo modelo."""
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()

    # Remover chaves/colchetes extras no final
    # Ex: {...}} -> {...}
    # Conta abertura e fechamento de chaves
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
    """
    Garante que region e outros campos soltos fiquem dentro de params.
    Modelo às vezes coloca region no nível raiz em vez de dentro de params.
    """
    params = data.get("params", {})

    for field in ("region", "nome", "runtime", "memory", "dead_letter"):
        if field in data and field not in params:
            params[field] = data.pop(field)

    # region padrão se não veio
    if "region" not in params:
        params["region"] = "us-east-1"

    data["params"] = params
    return data


class LLMExtractor:
    def __init__(self, ollama_url: str, supported_types: list[str]):
        self.ollama_url    = ollama_url
        self.system_prompt = EXTRACT_PROMPT_TEMPLATE.format(
            types=", ".join(supported_types)
        )

    async def extract(self, prompt: str, model: str) -> dict:
        async with httpx.AsyncClient(timeout=120) as client:
            res = await client.post(
                f"{self.ollama_url}/v1/chat/completions",
                json={
                    "model":  model,
                    "stream": False,
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
            raise ValueError(f"JSON invalido mesmo apos fix: {clean[:300]}") from e

        result = normalize(result)
        result["delete_intent"] = detect_delete_intent(prompt)

        print(f"[extractor] final: {result}", flush=True)
        return result

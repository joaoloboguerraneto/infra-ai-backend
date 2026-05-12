import json
import re
import httpx


EXTRACT_PROMPT_TEMPLATE = """\
Voce extrai parametros de infraestrutura de pedidos em linguagem natural.
Responda APENAS com JSON valido, sem markdown, sem texto extra.

Tipos suportados: {types}

Formato exato:
{{"type":"<tipo>","params":{{"nome":"<nome>","region":"us-east-1"}}}}

Exemplos:
- "bucket S3 unicred-poc" -> {{"type":"s3_bucket","params":{{"nome":"unicred-poc","region":"us-east-1"}}}}
- "Lambda Java 21 processador-ted 512MB" -> {{"type":"lambda_function","params":{{"nome":"processador-ted","runtime":"java21","memory":512,"region":"us-east-1"}}}}
- "fila SQS eventos-pix com dead letter queue" -> {{"type":"sqs_queue","params":{{"nome":"eventos-pix","dead_letter":true,"region":"us-east-1"}}}}

Responda SOMENTE o JSON, nada mais."""


class LLMExtractor:
    def __init__(self, ollama_url: str, supported_types: list[str]):
        self.ollama_url = ollama_url
        self.system_prompt = EXTRACT_PROMPT_TEMPLATE.format(
            types=", ".join(supported_types)
        )

    async def extract(self, prompt: str, model: str) -> dict:
        """
        Chama o LLM para extrair tipo e parâmetros do pedido em linguagem natural.
        Retorna {"type": str, "params": dict}.
        Lança ValueError se não conseguir parsear.
        """
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
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM retornou JSON invalido: {raw[:300]}") from e
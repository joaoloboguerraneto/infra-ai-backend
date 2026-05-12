from .base import TerraformTemplate


class SQSQueueTemplate(TerraformTemplate):
    name        = "sqs_queue"
    description = "Fila SQS com opcional dead letter queue"

    def render(self, params: dict) -> dict:
        nome        = params.get("nome", "minha-fila")
        region      = params.get("region", "us-east-1")
        dead_letter = params.get("dead_letter", False)
        lb          = self.label(nome)

        dlq_resource = ""
        dlq_policy   = ""

        if dead_letter:
            dlq_resource = f"""\
resource "aws_sqs_queue" "{lb}_dlq" {{
  name                      = "{nome}-dlq"
  message_retention_seconds = 1209600

{self.COMMON_TAGS}
}}

"""
            dlq_policy = f"""
  redrive_policy = jsonencode({{
    deadLetterTargetArn = aws_sqs_queue.{lb}_dlq.arn
    maxReceiveCount     = 5
  }})"""

        main = f"""\
{dlq_resource}resource "aws_sqs_queue" "{lb}" {{
  name                       = "{nome}"
  visibility_timeout_seconds = 30
  message_retention_seconds  = 86400{dlq_policy}

{self.COMMON_TAGS}
}}"""

        outputs = f"""\
output "queue_url" {{
  value       = aws_sqs_queue.{lb}.url
  description = "URL da fila SQS"
}}

output "queue_arn" {{
  value       = aws_sqs_queue.{lb}.arn
  description = "ARN da fila SQS"
}}"""

        resumo = f"Fila '{nome}'" + (" com dead letter queue" if dead_letter else "")
        return {
            "recurso":         "SQS Queue",
            "resumo":          resumo,
            "provider_region": region,
            "arquivos": [
                {"path": "main.tf",    "conteudo": main},
                {"path": "outputs.tf", "conteudo": outputs},
            ],
        }
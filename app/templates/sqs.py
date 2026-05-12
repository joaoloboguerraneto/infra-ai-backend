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
            dlq_resource = (
                f'resource "aws_sqs_queue" "{lb}_dlq" {{\n'
                f'  name                      = "{nome}-dlq"\n'
                f'  message_retention_seconds = 1209600\n\n'
                f'{self.COMMON_TAGS}\n'
                f'}}\n\n'
            )
            dlq_policy = (
                f'\n  redrive_policy = jsonencode({{\n'
                f'    deadLetterTargetArn = aws_sqs_queue.{lb}_dlq.arn\n'
                f'    maxReceiveCount     = 5\n'
                f'  }})'
            )

        main = (
            f'{dlq_resource}'
            f'resource "aws_sqs_queue" "{lb}" {{\n'
            f'  name                       = "{nome}"\n'
            f'  visibility_timeout_seconds = 30\n'
            f'  message_retention_seconds  = 86400{dlq_policy}\n\n'
            f'{self.COMMON_TAGS}\n'
            f'}}'
        )

        outputs = (
            f'output "queue_url" {{\n'
            f'  value       = aws_sqs_queue.{lb}.url\n'
            f'  description = "URL da fila SQS"\n'
            f'}}\n\n'
            f'output "queue_arn" {{\n'
            f'  value       = aws_sqs_queue.{lb}.arn\n'
            f'  description = "ARN da fila SQS"\n'
            f'}}'
        )

        return {
            "recurso":         "SQS Queue",
            "resumo":          f"Fila '{nome}'" + (" com dead letter queue" if dead_letter else ""),
            "provider_region": region,
            "arquivos": [
                {"path": "main.tf",    "conteudo": main},
                {"path": "outputs.tf", "conteudo": outputs},
            ],
        }

    def import_map(self, params: dict) -> list:
        """
        Sempre importa a fila principal.
        Importa DLQ se dead_letter=True nos params
        (detectado por keyword no extractor, nao depende do LLM).
        """
        nome        = params.get("nome", "minha-fila")
        dead_letter = params.get("dead_letter", False)
        lb          = self.label(nome)

        items = [{"address": f"aws_sqs_queue.{lb}", "id": nome}]

        if dead_letter:
            items.append({
                "address": f"aws_sqs_queue.{lb}_dlq",
                "id":      f"{nome}-dlq",
            })

        return items
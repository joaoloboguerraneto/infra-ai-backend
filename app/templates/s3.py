from .base import TerraformTemplate


class S3BucketTemplate(TerraformTemplate):
    name        = "s3_bucket"
    description = "Bucket S3 com versioning, encryption AES256 e block public access"

    def render(self, params: dict) -> dict:
        nome   = params.get("nome", "meu-bucket")
        region = params.get("region", "us-east-1")
        lb     = self.label(nome)

        main = f"""\
resource "aws_s3_bucket" "{lb}" {{
  bucket = "{nome}"

{self.COMMON_TAGS}
}}

resource "aws_s3_bucket_versioning" "{lb}" {{
  bucket = aws_s3_bucket.{lb}.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

resource "aws_s3_bucket_server_side_encryption_configuration" "{lb}" {{
  bucket = aws_s3_bucket.{lb}.id
  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "AES256"
    }}
  }}
}}

resource "aws_s3_bucket_public_access_block" "{lb}" {{
  bucket                  = aws_s3_bucket.{lb}.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}"""

        outputs = f"""\
output "bucket_name" {{
  value       = aws_s3_bucket.{lb}.bucket
  description = "Nome do bucket"
}}

output "bucket_arn" {{
  value       = aws_s3_bucket.{lb}.arn
  description = "ARN do bucket"
}}"""

        return {
            "recurso":         "S3 Bucket",
            "resumo":          f"Bucket '{nome}' com versioning, encryption e block public access",
            "provider_region": region,
            "arquivos": [
                {"path": "main.tf",    "conteudo": main},
                {"path": "outputs.tf", "conteudo": outputs},
            ],
        }

    def import_map(self, params: dict) -> list:
        """
        Mapeia todos os recursos S3 para import automático.
        O bucket principal é obrigatório; os sub-recursos usam o mesmo ID.
        """
        nome = params.get("nome", "meu-bucket")
        lb   = self.label(nome)
        return [
            {"address": f"aws_s3_bucket.{lb}",                                    "id": nome},
            {"address": f"aws_s3_bucket_versioning.{lb}",                         "id": nome},
            {"address": f"aws_s3_bucket_server_side_encryption_configuration.{lb}","id": nome},
            {"address": f"aws_s3_bucket_public_access_block.{lb}",                "id": nome},
        ]
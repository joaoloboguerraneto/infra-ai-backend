from .base import TerraformTemplate


class LambdaFunctionTemplate(TerraformTemplate):
    name        = "lambda_function"
    description = "Lambda Function com IAM role, CloudWatch Logs e variáveis de ambiente"

    def render(self, params: dict) -> dict:
        nome    = params.get("nome", "minha-lambda")
        runtime = params.get("runtime", "python3.12")
        memory  = int(params.get("memory", 256))
        timeout = int(params.get("timeout", 30))
        region  = params.get("region", "us-east-1")
        lb      = self.label(nome)

        main = f"""\
data "aws_iam_policy_document" "{lb}_assume" {{
  statement {{
    actions = ["sts:AssumeRole"]
    principals {{
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }}
  }}
}}

resource "aws_iam_role" "{lb}" {{
  name               = "{nome}-role"
  assume_role_policy = data.aws_iam_policy_document.{lb}_assume.json

{self.COMMON_TAGS}
}}

resource "aws_iam_role_policy_attachment" "{lb}_logs" {{
  role       = aws_iam_role.{lb}.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}}

resource "aws_cloudwatch_log_group" "{lb}" {{
  name              = "/aws/lambda/{nome}"
  retention_in_days = 14
}}

resource "aws_lambda_function" "{lb}" {{
  function_name = "{nome}"
  role          = aws_iam_role.{lb}.arn
  runtime       = "{runtime}"
  handler       = "index.handler"
  memory_size   = {memory}
  timeout       = {timeout}
  filename      = "${{path.module}}/function.zip"

  environment {{
    variables = {{
      ENVIRONMENT = "poc"
    }}
  }}

{self.COMMON_TAGS}

  depends_on = [aws_cloudwatch_log_group.{lb}]
}}"""

        outputs = f"""\
output "lambda_arn" {{
  value       = aws_lambda_function.{lb}.arn
  description = "ARN da função Lambda"
}}

output "lambda_name" {{
  value       = aws_lambda_function.{lb}.function_name
  description = "Nome da função Lambda"
}}"""

        return {
            "recurso":         "Lambda Function",
            "resumo":          f"Lambda '{nome}' runtime={runtime} memory={memory}MB timeout={timeout}s",
            "provider_region": region,
            "arquivos": [
                {"path": "main.tf",    "conteudo": main},
                {"path": "outputs.tf", "conteudo": outputs},
            ],
        }
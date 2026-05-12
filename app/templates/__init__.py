from .base import TerraformTemplate
from .s3 import S3BucketTemplate
from .lambda_ import LambdaFunctionTemplate
from .sqs import SQSQueueTemplate


def get_registry() -> dict:
    """
    Retorna {name -> instancia} de todos os templates registrados.
    Adicionar novo recurso = criar arquivo + importar aqui.
    """
    return {cls.name: cls() for cls in TerraformTemplate.__subclasses__()}


__all__ = ["get_registry", "TerraformTemplate"]
from abc import ABC, abstractmethod
import re


class TerraformTemplate(ABC):
    """
    Classe base para templates de recursos Terraform.
    Para adicionar um novo recurso: crie um arquivo em templates/,
    herde desta classe e implemente name, description, render() e import_map().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @abstractmethod
    def render(self, params: dict) -> dict:
        ...

    def import_map(self, params: dict) -> list:
        """
        Retorna lista de recursos a importar quando state estiver vazio.
        Cada item: {"address": "aws_s3_bucket.lb", "id": "nome-do-bucket"}

        O pipeline chama isso automaticamente no delete quando detecta
        state vazio — recurso criado fora deste pipeline ou run_id diferente.
        """
        return []

    @staticmethod
    def label(name: str) -> str:
        return re.sub(r'[^a-z0-9_]', '_', name.lower())

    COMMON_TAGS = '''\
  tags = {
    Environment = "poc"
    Team        = "devops"
    ManagedBy   = "Terraform"
  }'''
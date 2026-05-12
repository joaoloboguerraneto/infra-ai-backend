from abc import ABC, abstractmethod
import re


class TerraformTemplate(ABC):
    """
    Classe base para templates de recursos Terraform.
    Para adicionar um novo recurso: crie um arquivo em templates/,
    herde desta classe e implemente name, description e render().
    O registro é automático via TerraformTemplate.__subclasses__().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador do tipo, ex: 's3_bucket'."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Descrição curta para o modelo LLM."""
        ...

    @abstractmethod
    def render(self, params: dict) -> dict:
        """
        Recebe os parâmetros extraídos pelo LLM e retorna:
        {
          "recurso":  str,
          "resumo":   str,
          "provider_region": str,
          "arquivos": [{"path": str, "conteudo": str}]
        }
        """
        ...

    # ── Utilitários compartilhados ──────────────────────────────────────────

    @staticmethod
    def label(name: str) -> str:
        """Converte nome em label HCL válido: 'meu-bucket' -> 'meu_bucket'."""
        return re.sub(r'[^a-z0-9_]', '_', name.lower())

    COMMON_TAGS = '''\
  tags = {
    Environment = "poc"
    Team        = "devops"
    ManagedBy   = "Terraform"
  }'''
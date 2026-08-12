"""大模型接入层：传输（client）与提示词/回退策略（narrative）分离。"""
from .client import OpenAICompatibleClient, resolve_endpoint
from .narrative import SECTION_KEYS, NarrativeGenerator, template_narrative

__all__ = ['OpenAICompatibleClient', 'resolve_endpoint', 'NarrativeGenerator', 'template_narrative', 'SECTION_KEYS']

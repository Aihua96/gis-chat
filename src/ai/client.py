"""OpenAI 兼容接口的最小客户端：只负责传输与响应解析，不含任何报告业务逻辑。"""
import json, re
from urllib.request import Request, urlopen

from ..config import LLM_TIMEOUT
from ..domain import LlmError, LlmSetting

FENCE = re.compile(r'^```(?:json)?\s*|\s*```$')

def resolve_endpoint(base_url: str) -> str:
    """兼容用户填写 /v1、/v1/chat/completions 或裸域名三种写法。"""
    base = base_url.rstrip('/')
    if base.endswith('/chat/completions'): return base
    return base + ('/chat/completions' if base.endswith('/v1') else '/v1/chat/completions')

class OpenAICompatibleClient:
    """可替换实现：任何提供 complete_json(system, user) 的对象都能注入 NarrativeGenerator。"""

    def __init__(self, setting: LlmSetting, timeout: int = LLM_TIMEOUT):
        self.setting = setting
        self.timeout = timeout

    def complete_json(self, system: str, user: str) -> dict:
        headers = {'Content-Type': 'application/json'}
        if self.setting.api_key:
            headers['Authorization'] = 'Bearer ' + self.setting.api_key
        body = json.dumps({
            'model': self.setting.model,
            'temperature': 0.2,
            'response_format': {'type': 'json_object'},
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        }).encode()
        request = Request(resolve_endpoint(self.setting.base_url), data=body, headers=headers, method='POST')
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
            content = payload['choices'][0]['message']['content']
        except Exception as exc:
            raise LlmError('大模型调用失败：' + str(exc)) from exc
        try:
            return json.loads(FENCE.sub('', content.strip()))
        except json.JSONDecodeError as exc:
            raise LlmError('大模型未返回合法 JSON，请检查模型是否支持 response_format') from exc

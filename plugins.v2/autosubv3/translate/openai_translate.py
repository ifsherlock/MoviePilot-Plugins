import time
import random
import re
import json
from typing import List, Union, Tuple, Optional

import openai
import httpx
from cacheout import Cache

OpenAISessionCache = Cache(maxsize=100, ttl=3600, timer=time.time, default=None)


class OpenAi:
    _api_key: str = None
    _api_url: str = None
    _model: str = "inclusionAI/Ling-flash-2.0"

    def __init__(self, api_key: str = None, api_url: str = None, proxy: dict = None, model: str = None,
                 compatible: bool = False):
        self._api_key = api_key
        self._api_url = api_url
        base_url = self._api_url if compatible else self._api_url + "/v1"

        if proxy and proxy.get("https"):
            http_client = httpx.Client(proxies=proxy.get("https"))
            self.client = openai.OpenAI(api_key=self._api_key, base_url=base_url, http_client=http_client)
        else:
            self.client = openai.OpenAI(api_key=self._api_key, base_url=base_url)

        if model:
            self._model = model

    @staticmethod
    def __save_session(session_id: str, message: str):
        seasion = OpenAISessionCache.get(session_id)
        if seasion:
            seasion.append({"role": "assistant", "content": message})
            OpenAISessionCache.set(session_id, seasion)

    @staticmethod
    def __get_session(session_id: str, message: str) -> List[dict]:
        seasion = OpenAISessionCache.get(session_id)
        if seasion:
            seasion.append({"role": "user", "content": message})
        else:
            seasion = [
                {"role": "system", "content": "请在接下来的对话中请使用中文回复，并且内容尽可能详细。"},
                {"role": "user", "content": message}
            ]
            OpenAISessionCache.set(session_id, seasion)
        return seasion

    def __get_model(self, message: Union[str, List[dict]], system_hint: str = None, **kwargs):
        if not isinstance(message, list):
            if system_hint:
                message = [
                    {"role": "system", "content": system_hint},
                    {"role": "user", "content": message}
                ]
            else:
                message = [{"role": "user", "content": message}]
        return self.client.chat.completions.create(model=self._model, messages=message, **kwargs)

    @property
    def model(self) -> str:
        return self._model

    def list_models(self) -> List[str]:
        response = self.client.models.list()
        models = []
        for item in getattr(response, "data", []) or []:
            model_id = getattr(item, "id", None)
            if model_id:
                models.append(str(model_id))
        return sorted(set(models))

    def test_model(self) -> str:
        completion = self.__get_model(
            message="请回复 OK，用于测试模型是否可用。",
            temperature=0,
            max_tokens=8,
        )
        return (completion.choices[0].message.content or "").strip()

    @staticmethod
    def __clear_session(session_id: str):
        if OpenAISessionCache.get(session_id):
            OpenAISessionCache.delete(session_id)

    @staticmethod
    def _clean_text(text: str) -> str:
        text = text or ""
        text = re.sub(r'\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', '', text)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\s*\n', '', text)
        text = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', text)
        text = re.sub(r'([\u4e00-\u9fff])\s+([a-zA-Z0-9])', r'\1\2', text)
        text = re.sub(r'([a-zA-Z0-9])\s+([\u4e00-\u9fff])', r'\1\2', text)
        text = re.sub(r'\s+\n', '\n', text)
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(line for line in lines if line)

    @staticmethod
    def _clean_ai_response(text: str) -> str:
        text = (text or "").strip()
        text = text.replace("```json", "").replace("```", "").strip()
        # 贪婪正则：从第一个[到最后一个]（处理模型在JSON后多加解释文字）
        match = re.search(r'(\[.*\])', text, flags=re.S)
        if match:
            text = match.group(1).strip()
        # 清理尾部逗号（JSON规范不允许）
        text = text.replace(",]", "]").replace(",}", "}")
        return text

    @staticmethod
    def _validate_batch(input_batch: List[dict], output_batch: List[dict]) -> bool:
        if len(input_batch) != len(output_batch):
            return False
        ids1 = [x["id"] for x in input_batch]
        ids2 = [x.get("id") for x in output_batch]
        if ids1 != ids2:
            return False
        for item in output_batch:
            zh = item.get("zh")
            if not isinstance(zh, str) or not zh.strip():
                return False
        return True

    def translate_to_zh(self, text: str, context: str = None, max_retries: int = 3):
        """单条翻译：走 3.5.10 prompt 思路"""
        text = self._clean_text(text)
        context = self._clean_text(context) if context else None

        system_prompt = """您是一位专业字幕翻译专家，请严格遵循以下规则：
1. 将原文精准翻译为简体中文，保持原文本意
2. 使用自然的口语化表达，符合中文观影习惯
3. 结合上下文语境，人物称谓、专业术语、情感语气在上下文中保持连贯
4. 按行翻译待译内容。翻译结果不要包括上下文。
5. 输出内容必须仅包括译文。不要输出任何开场白，解释说明或总结
6. 遇到英文脏话时请翻译成自然中文口语，不要保留英文单词"""
        user_prompt = f"翻译上下文：\n{context}\n\n需要翻译的内容：\n{text}" if context else f"请翻译：\n{text}"

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                completion = self.__get_model(
                    message=user_prompt,
                    system_hint=system_prompt,
                    temperature=0.2,
                    top_p=0.9
                )
                result = completion.choices[0].message.content.strip()
                result = self._clean_text(result)
                return True, result
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    sleep_time = (2 ** attempt) + random.uniform(0.1, 0.9)
                    print(f"翻译请求失败 (第{attempt + 1}次尝试)：{last_error}，{sleep_time:.1f}秒后重试...")
                    time.sleep(sleep_time)
                else:
                    print(f"翻译请求失败 (已重试{max_retries}次)：{last_error}")
                    return False, f"{last_error}"

    def translate_batch_to_zh(self, texts: List[str], max_retries: int = 3) -> Tuple[bool, List[Optional[str]]]:
        """批量翻译：JSON结构化输出，按id校验，尽量避免串行"""
        input_batch = []
        for idx, text in enumerate(texts, 1):
            input_batch.append({
                "id": idx,
                "text": self._clean_text(text)
            })

        prompt = f"""
你是专业字幕翻译器。

规则：
1. 不得改变 id
2. 不得合并字幕
3. 不得新增字幕
4. 只翻译 text
5. 输出 JSON 数组
6. 输出数量必须与输入一致
7. 口语化，符合中文观影习惯

输入：
{json.dumps(input_batch, ensure_ascii=False)}

输出示例：
[
  {{"id":1,"zh":"你好世界"}}
]
""".strip()

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                completion = self.__get_model(
                    message=prompt,
                    temperature=0,
                    top_p=1,
                    system_hint="你是专业字幕翻译引擎"
                )
                raw_text = completion.choices[0].message.content.strip()
                usage_info = getattr(completion, 'usage', None)
                usage_str = ""
                if usage_info:
                    usage_str = (f"[prompt_tokens={usage_info.prompt_tokens}, "
                                 f"completion_tokens={usage_info.completion_tokens}, "
                                 f"total_tokens={usage_info.total_tokens}]")

                clean_text = self._clean_ai_response(raw_text)

                # 诊断日志
                raw_len = len(raw_text)
                clean_len = len(clean_text)
                print(f"[BatchTranslate] attempt={attempt+1} | raw_len={raw_len} | clean_len={clean_len} {usage_str} | raw_start: {raw_text[:60].replace(chr(10),' ')}")

                # 尝试解析 JSON
                output_batch = None
                try:
                    output_batch = json.loads(clean_text)
                except json.JSONDecodeError as je:
                    import re
                    arr_match = re.search(r'\[\s*\{.*\}\s*\]', clean_text, flags=re.DOTALL)
                    if arr_match:
                        try:
                            output_batch = json.loads(arr_match.group(0))
                            print(f"[BatchTranslate] JSON修复成功，从正则提取")
                        except Exception:
                            pass
                    if output_batch is None:
                        raise ValueError(f"JSON解析失败: {je}")

                # 验证类型
                if not isinstance(output_batch, list):
                    raise ValueError(f"输出类型错误: {type(output_batch).__name__}，期望list")

                # 数量校验
                if len(output_batch) != len(input_batch):
                    raise ValueError(f"数量不匹配: 输入{len(input_batch)}条, 输出{len(output_batch)}条")

                # ID校验
                input_ids = [x["id"] for x in input_batch]
                output_ids = [x.get("id") for x in output_batch]
                if input_ids != output_ids:
                    raise ValueError(f"id不匹配: 输入={input_ids[:5]}... 输出={output_ids[:5]}...")

                # 空值校验
                empty_zh_ids = [x.get("id") for x in output_batch
                               if not isinstance(x.get("zh"), str) or not x.get("zh","").strip()]
                if empty_zh_ids:
                    raise ValueError(f"zh为空的id: {empty_zh_ids[:5]}")

                # 构建结果
                translations: List[Optional[str]] = [None] * len(texts)
                for item in output_batch:
                    idx = int(item["id"]) - 1
                    zh = self._clean_text(item["zh"])
                    if 0 <= idx < len(translations):
                        translations[idx] = zh

                print(f"[BatchTranslate] 批量成功: {len(translations)}条 {usage_str}")
                return True, translations

            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    sleep_time = (2 ** attempt) + random.uniform(0.1, 0.9)
                    print(f"[BatchTranslate] 失败 attempt={attempt+1}: {last_error}，重试...")
                    time.sleep(sleep_time)
                else:
                    print(f"[BatchTranslate] 全局失败 (已重试{max_retries}次): {last_error}")
                    return False, [None] * len(texts)

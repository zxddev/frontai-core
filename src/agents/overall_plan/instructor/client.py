"""
Instructor客户端工具

提供异步Instructor客户端的创建和结构化输出生成功能。
支持vLLM的OpenAI兼容API。

重要：使用AsyncOpenAI避免阻塞事件循环。
"""

import logging
import os
from typing import TypeVar

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class InstructorClientError(Exception):
    """Instructor客户端操作失败时抛出"""

    pass


def create_instructor_client(
    base_url: str | None = None,
    api_key: str | None = None,
    mode: instructor.Mode = instructor.Mode.JSON,
) -> instructor.AsyncInstructor:
    """
    创建异步Instructor客户端

    Args:
        base_url: OpenAI兼容API地址，默认从环境变量OPENAI_BASE_URL读取
        api_key: API密钥，默认从环境变量OPENAI_API_KEY读取
        mode: Instructor模式，默认JSON模式（兼容vLLM）

    Returns:
        配置好的异步Instructor客户端

    Raises:
        InstructorClientError: 缺少必需的环境变量时抛出
    """
    base_url = base_url or os.environ.get("OPENAI_BASE_URL")
    if not base_url:
        raise InstructorClientError(
            "OPENAI_BASE_URL environment variable is required. "
            "Set it to your vLLM server URL (e.g., http://localhost:8000/v1)"
        )

    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise InstructorClientError(
            "OPENAI_API_KEY environment variable is required. "
            "For vLLM without auth, set it to any non-empty string."
        )

    timeout = float(os.environ.get("LLM_TIMEOUT", "180"))

    try:
        client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

        instructor_client = instructor.from_openai(client, mode=mode)
        logger.debug(
            "Created async Instructor client",
            extra={"base_url": base_url, "mode": str(mode)},
        )

        return instructor_client

    except Exception as e:
        logger.error("Failed to create Instructor client: %s", e, exc_info=True)
        raise InstructorClientError(f"Failed to create Instructor client: {e}") from e


async def generate_structured_output(
    client: instructor.AsyncInstructor,
    model: str,
    response_model: type[T],
    prompt: str,
    max_retries: int = 3,
    temperature: float = 0.2,
) -> T:
    """
    使用Instructor生成结构化输出

    对于vLLM，使用guided_json参数启用服务端JSON约束，
    确保输出严格符合schema，而不是依赖模型自身的JSON生成能力。

    Args:
        client: 异步Instructor客户端实例
        model: 模型名称
        response_model: 响应的Pydantic模型类
        prompt: 用户提示词
        max_retries: 验证失败时的最大重试次数
        temperature: LLM温度参数

    Returns:
        经过验证的Pydantic模型实例

    Raises:
        InstructorClientError: 重试后仍失败时抛出
    """
    # 获取JSON Schema用于vLLM的guided_json
    json_schema = response_model.model_json_schema()
    field_names = list(response_model.model_fields.keys())

    system_prompt = f"""你是一名专业的应急管理专家。
请根据用户提供的灾情数据，生成专业的应急方案建议。
输出必须是JSON格式，包含以下字段：{field_names}"""

    try:
        result = await client.chat.completions.create(
            model=model,
            response_model=response_model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            max_retries=max_retries,
            temperature=temperature,
            # vLLM guided decoding - 服务端JSON约束
            extra_body={
                "guided_json": json_schema,
                "guided_decoding_backend": "outlines",
            },
        )
        return result

    except Exception as e:
        logger.error(
            "Instructor generation failed: %s",
            e,
            exc_info=True,
            extra={"model": model, "response_model": response_model.__name__},
        )
        raise InstructorClientError(f"Structured output generation failed: {e}") from e


def get_default_model() -> str:
    """
    从环境变量获取默认模型名称

    Raises:
        InstructorClientError: 未设置LLM_MODEL环境变量时抛出
    """
    model = os.environ.get("LLM_MODEL")
    if not model:
        raise InstructorClientError(
            "LLM_MODEL environment variable is required. "
            "Set it to your model name (e.g., /models/openai/gpt-oss-120b)"
        )
    return model

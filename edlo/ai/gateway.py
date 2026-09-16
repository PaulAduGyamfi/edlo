import asyncio
import random
import time
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from edlo.config import get_settings
from edlo.logging import log

T = TypeVar("T", bound=BaseModel)


class ModelUnavailable(Exception): ...  # transient   -> retry


class ModelTimeout(Exception): ...  # transient   -> retry


class ModelInvalidOutput(Exception): ...  # structural -> do NOT loop


class AIDisabled(Exception): ...


class ModelGateway(Protocol):
    async def structured(
        self, *, system: str, user: str, output_type: type[T], prompt_version: str
    ) -> T: ...


class MockGateway:
    """
    The DEFAULT everywhere except production. Deterministic, offline, free.
    Every test and the entire eval suite runs against this -- CI has no model
    API key and no egress to a provider, and that is intentional.
    """

    def __init__(self, responses: dict[str, BaseModel] | None = None):
        self.responses = responses or {}
        self.calls: list[dict[str, Any]] = []

    async def structured(self, *, system, user, output_type, prompt_version):
        self.calls.append({"type": output_type.__name__, "version": prompt_version})
        if output_type.__name__ in self.responses:
            return self.responses[output_type.__name__]
        return output_type.model_construct()


class OpenAICompatibleGateway:
    """
    Works against OpenAI, Azure OpenAI, Together, Fireworks, vLLM, Ollama --
    anything speaking the chat-completions API. Moving to a self-hosted vLLM
    is a base_url change, which is the entire point of picking this shape.
    """

    def __init__(self, base_url, api_key, model, timeout_seconds, client=None):
        if client is None:
            from openai import AsyncOpenAI

            # max_retries=0: the SDK's built-in retry is invisible to metrics
            # and budget. Own the loop so it can be counted and capped.
            client = AsyncOpenAI(
                base_url=base_url or None,
                api_key=api_key,
                timeout=timeout_seconds,
                max_retries=0,
            )
        self.client = client
        self.model = model

    async def structured(self, *, system, user, output_type, prompt_version):
        last: Exception | None = None

        for attempt in range(2):
            started = time.perf_counter()
            try:
                r = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": output_type.__name__,
                            "schema": output_type.model_json_schema(),
                            "strict": True,
                        },
                    },
                    temperature=0.2,
                )
                parsed = output_type.model_validate_json(
                    r.choices[0].message.content or ""
                )
                # Log IDENTIFIERS and SHAPES. Never the transcript, never the
                # generated text. Logs are retained far longer than you think,
                # and a transcript in CloudWatch is a data-handling incident.
                usage = getattr(r, "usage", None)
                log.info(
                    "ai_call",
                    model=self.model,
                    prompt_version=prompt_version,
                    request_id=getattr(r, "id", None),
                    prompt_tokens=getattr(usage, "prompt_tokens", None),
                    completion_tokens=getattr(usage, "completion_tokens", None),
                    output_type=output_type.__name__,
                    attempt=attempt,
                    duration_ms=round((time.perf_counter() - started) * 1000),
                )
                return parsed

            except ValidationError as e:
                last = ModelInvalidOutput(f"schema violation: {e.error_count()} errors")
                log.warning(
                    "ai_invalid_output",
                    attempt=attempt,
                    error_count=e.error_count(),
                    version=prompt_version,
                )
                user += (
                    "\n\nYour previous response did not match the schema. "
                    "Return only valid JSON matching it exactly."
                )
                continue

            except TimeoutError as e:
                last = ModelTimeout(str(e))
            except Exception as e:  # classified below: transient or structural
                status = getattr(e, "status_code", None)
                if status in (429, 500, 502, 503, 504) or status is None:
                    last = ModelUnavailable(f"{type(e).__name__}: {status}")
                else:
                    raise ModelInvalidOutput(f"non-retryable: {status}") from e

            # FULL jitter, not plain exponential backoff.
            await asyncio.sleep(random.uniform(0, 2**attempt))

        raise last or ModelUnavailable("exhausted attempts")


def get_gateway() -> ModelGateway:
    s = get_settings()
    if not s.ai_enabled:
        raise AIDisabled("AI is disabled by configuration")
    if s.model_provider == "mock":
        return MockGateway()
    return OpenAICompatibleGateway(
        s.model_base_url, s.model_api_key, s.model_name, s.model_timeout_seconds
    )

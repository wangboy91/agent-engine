"""Model router primitives."""

import json
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app.domain.errors import BklEngineError
from app.domain.model import ModelResponse, ModelUsage, ToolCallRequest
from app.infrastructure.config.engine_config import EngineConfig, ModelProfileConfig

__all__ = [
    "MockModelProvider",
    "ModelProvider",
    "ModelResponse",
    "ModelRouter",
    "ModelUsage",
    "ToolCallRequest",
]


class ModelProvider(Protocol):
    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelResponse:
        ...


class MockModelProvider:
    def __init__(self, responses: list[ModelResponse] | None = None) -> None:
        self._responses = deque(responses or [])

    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelResponse:
        del profile, stream_callback
        if self._responses:
            return self._responses.popleft()
        return self._default_response(messages, tools)

    def _default_response(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> ModelResponse:
        user_input = self._extract_user_input(messages)
        system_prompt = self._extract_system_prompt(messages)
        content_video_output = self._content_video_output(system_prompt, user_input)
        if content_video_output is not None:
            return ModelResponse(final_output=content_video_output)

        if not any(message.get("role") == "tool" for message in messages) and tools:
            tool_id = str(tools[0]["id"])
            if tool_id == "wangbudong_write_prompt_pack":
                return ModelResponse(
                    tool_calls=[
                        ToolCallRequest(
                            id="call_mock_1",
                            tool_id=tool_id,
                            arguments=self._wangbudong_tool_arguments(user_input),
                        )
                    ]
                )
            if tool_id == "mock_video_render":
                return ModelResponse(
                    tool_calls=[
                        ToolCallRequest(
                            id="call_mock_1",
                            tool_id=tool_id,
                            arguments=self._video_render_tool_arguments(user_input),
                        )
                    ]
                )
            return ModelResponse(
                tool_calls=[
                    ToolCallRequest(
                        id="call_mock_1",
                        tool_id=tool_id,
                        arguments={
                            "text": str(
                                user_input.get("topic")
                                or user_input.get("text")
                                or "mock text"
                            ),
                            "audio_path": str(user_input.get("audio_path") or "audio.wav"),
                        },
                    )
                ]
            )

        observation = self._extract_last_tool_observation(messages)
        if "render_job_id" in observation and "video_path" in observation:
            return ModelResponse(
                final_output=self._video_render_final_output(user_input, observation)
            )
        if "output_dir" in observation and "files" in observation:
            return ModelResponse(
                final_output=self._wangbudong_final_output(user_input, observation)
            )
        topic = str(user_input.get("topic") or "mock topic")
        return ModelResponse(
            final_output={
                "script": f"Mock script for {topic}",
                "titles": [f"{topic} 标题"],
                "subtitle_path": str(observation.get("srt_path", "")),
                "segments": observation.get("segments", []),
            }
        )

    def _extract_system_prompt(self, messages: list[dict[str, object]]) -> str:
        for message in messages:
            if message.get("role") == "system":
                content = message.get("content")
                return content if isinstance(content, str) else ""
        return ""

    def _extract_user_input(self, messages: list[dict[str, object]]) -> dict[str, Any]:
        for message in messages:
            if message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, str):
                    try:
                        payload = json.loads(content)
                    except json.JSONDecodeError:
                        return {}
                    if isinstance(payload, dict) and isinstance(payload.get("input"), dict):
                        return dict(payload["input"])
        return {}

    def _extract_last_tool_observation(self, messages: list[dict[str, object]]) -> dict[str, Any]:
        for message in reversed(messages):
            if message.get("role") == "tool":
                content = message.get("content")
                if isinstance(content, str):
                    try:
                        payload = json.loads(content)
                    except json.JSONDecodeError:
                        return {}
                    if isinstance(payload, dict):
                        return payload
        return {}

    def _wangbudong_tool_arguments(self, user_input: dict[str, Any]) -> dict[str, object]:
        raw_materials = user_input.get("materials")
        if isinstance(raw_materials, list):
            materials = [str(item) for item in raw_materials]
        else:
            materials = [str(raw_materials or "家庭常见材料")]
        return {
            "experiment_title": str(user_input.get("experiment_title") or "小实验"),
            "materials": materials,
            "target_phenomenon": str(user_input.get("target_phenomenon") or "观察明显变化"),
            "age_range": str(user_input.get("age_range") or "3-8岁"),
            "content_lane": str(user_input.get("content_lane") or "趣味引流"),
            "include_operations_card": bool(user_input.get("include_operations_card", False)),
        }

    def _wangbudong_final_output(
        self,
        user_input: dict[str, Any],
        observation: dict[str, Any],
    ) -> dict[str, object]:
        raw_files = observation.get("files", [])
        files = [str(item) for item in raw_files] if isinstance(raw_files, list) else []
        raw_safety_notes = observation.get("safety_notes", [])
        safety_notes = (
            [str(item) for item in raw_safety_notes]
            if isinstance(raw_safety_notes, list)
            else []
        )
        return {
            "experiment_title": str(
                observation.get("experiment_title")
                or user_input.get("experiment_title")
                or "小实验"
            ),
            "output_dir": str(observation.get("output_dir") or ""),
            "files": files,
            "feasibility_summary": str(observation.get("feasibility_summary") or ""),
            "cover_prompt": str(observation.get("cover_prompt") or ""),
            "step_prompt_count": int(observation.get("step_prompt_count") or 0),
            "xiaohongshu_copy": str(observation.get("xiaohongshu_copy") or ""),
            "safety_notes": safety_notes,
        }

    def _video_render_tool_arguments(self, user_input: dict[str, Any]) -> dict[str, object]:
        return {
            "render_prompt_pack": user_input.get("render_prompt_pack") or {"prompts": []},
            "asset_manifest": user_input.get("asset_manifest") or {"assets": []},
            "timeline": user_input.get("timeline") or {"duration_seconds": 0, "tracks": []},
            "video_draft": user_input.get("video_draft") or {},
            "script": user_input.get("script") or {},
        }

    def _video_render_final_output(
        self,
        user_input: dict[str, Any],
        observation: dict[str, Any],
    ) -> dict[str, object]:
        raw_video_draft = observation.get("video_draft")
        if isinstance(raw_video_draft, dict):
            video_draft = dict(raw_video_draft)
        else:
            source_draft = user_input.get("video_draft")
            video_draft = dict(source_draft) if isinstance(source_draft, dict) else {}
            video_draft.update(
                {
                    "status": "rendered",
                    "render_job_id": str(observation.get("render_job_id") or ""),
                    "video_path": str(observation.get("video_path") or ""),
                    "manifest_path": str(observation.get("manifest_path") or ""),
                }
            )

        render_job = {
            "render_job_id": str(observation.get("render_job_id") or ""),
            "status": str(observation.get("status") or "succeeded"),
            "provider": str(observation.get("provider") or "mock_video_render"),
            "video_path": str(observation.get("video_path") or ""),
            "manifest_path": str(observation.get("manifest_path") or ""),
            "generated_assets": observation.get("generated_assets") or [],
        }
        return {"render_job": render_job, "video_draft": video_draft}

    def _content_video_output(
        self,
        system_prompt: str,
        user_input: dict[str, Any],
    ) -> dict[str, object] | None:
        prompt = system_prompt.casefold()
        topic = str(user_input.get("topic") or "内容主题")
        platform = str(user_input.get("platform") or "douyin")
        duration_seconds = int(user_input.get("duration_seconds") or 60)
        audience = str(user_input.get("audience") or "目标用户")
        content_type = str(user_input.get("content_type") or "talking_head")

        if "content-brief-planner" in prompt:
            return {
                "content_brief": {
                    "topic": topic,
                    "platform": platform,
                    "content_type": content_type,
                    "duration_seconds": duration_seconds,
                    "audience": audience,
                    "content_goal": f"让{audience}理解{topic}的核心价值并愿意继续了解",
                    "core_angle": f"{topic}不是单点技巧，而是一条可复用的内容生产链路",
                    "user_pain_points": [
                        "不知道从哪里开始组织内容",
                        "脚本和画面经常脱节",
                        "每次生成结果都难以复盘和复用",
                    ],
                    "recommended_structure": [
                        "冲突钩子",
                        "问题解释",
                        "方法拆解",
                        "案例落点",
                        "行动建议",
                    ],
                    "delivery_format": "vertical_talking_video",
                }
            }

        if "hook-plan-generator" in prompt:
            return {
                "hook_plan": {
                    "hooks": [
                        f"很多人做{topic}，第一步就错了。",
                        f"你以为{topic}靠灵感，其实靠流程。",
                        f"把{topic}做稳定，关键不是多用工具。",
                    ],
                    "best_hook": f"很多人做{topic}，第一步就错了。",
                    "reason": "开头有冲突感，能快速制造继续观看的理由。",
                }
            }

        if "style-bible-planner" in prompt:
            return {
                "style_bible": {
                    "tone": "直接、清楚、有案例感",
                    "visual_style": "真实口播 + 简洁信息图辅助",
                    "color_palette": ["black", "white", "electric_blue", "warm_yellow"],
                    "typography": "粗体关键词字幕，单屏不超过两行",
                    "camera_language": "中景口播为主，每 5-8 秒切换辅助画面",
                    "screen_text_rules": [
                        "字幕短句化",
                        "关键词先出现",
                        "避免整段文案铺满屏幕",
                    ],
                }
            }

        if "talking-script-writer" in prompt:
            hook = self._best_hook(user_input, topic)
            full_text = (
                f"{hook}真正的问题不是工具不够多，而是你没有把内容生产拆成流程。"
                f"先把想法变成清楚的内容需求，再写出口语化脚本。"
                f"接着把脚本拆成分镜，明确每一句话对应什么画面。"
                f"然后生成素材清单和提示词，让图片、视频、字幕、音频都能被管理。"
                f"最后把成片结果复盘，记录哪里有效、哪里需要返工。"
                f"这样做{topic}，才不是碰运气，而是在搭一套可以复制的生产系统。"
            )
            return {
                "script": {
                    "title": f"{topic}的正确流程",
                    "full_text": full_text,
                    "estimated_duration_seconds": duration_seconds,
                    "tone": "直接、有冲突、偏方法论",
                    "cta": "先跑通一条链路，再扩展不同风格的智能体。",
                }
            }

        if "script-segmenter" in prompt:
            hook = self._best_hook(user_input, topic)
            durations = [5, 8, 9, 10, 10, max(duration_seconds - 42, 8)]
            spoken = [
                hook,
                "真正的问题不是工具不够多，而是没有把内容生产拆成流程。",
                "先把想法变成内容需求，再写出口语化脚本。",
                "接着把脚本拆成分镜，明确每句话对应什么画面。",
                "然后生成素材清单和提示词，让素材可以被管理。",
                "最后复盘成片表现，把有效经验沉淀成下一次的风格配置。",
            ]
            segments: list[dict[str, object]] = []
            cursor = 0
            functions = ["hook", "problem", "method", "storyboard", "assets", "review"]
            emotions = ["strong", "explain", "calm", "clear", "practical", "summary"]
            for index, text in enumerate(spoken):
                duration = durations[index]
                start = cursor
                end = cursor + duration
                cursor = end
                segments.append(
                    {
                        "id": f"s{index + 1}",
                        "order": index + 1,
                        "time_range": f"{start}-{end}s",
                        "duration": duration,
                        "spoken_text": text,
                        "function": functions[index],
                        "emotion": emotions[index],
                        "screen_text": text[:14],
                    }
                )
            return {"script_segments": segments}

        if "storyboard-designer" in prompt:
            segments = self._segments(user_input)
            shots = []
            for index, segment in enumerate(segments):
                shot_id = f"sh{index + 1}"
                visual_type = "talking_head_with_overlay" if index % 2 else "keyword_card"
                shots.append(
                    {
                        "shot_id": shot_id,
                        "segment_id": str(segment.get("id") or f"s{index + 1}"),
                        "duration": self._int_value(segment.get("duration"), 6),
                        "visual_type": visual_type,
                        "camera": "中景口播，轻微推近" if index % 2 else "静态关键词画面",
                        "description": f"围绕“{segment.get('screen_text') or topic}”做清晰视觉辅助",
                        "screen_text": str(segment.get("screen_text") or topic),
                        "asset_needed": "video_clip" if index % 2 else "keyword_card",
                    }
                )
            return {"storyboard": {"shots": shots}}

        if "render-prompt-builder" in prompt:
            shots = self._shots(user_input)
            prompts = []
            for shot in shots:
                prompts.append(
                    {
                        "shot_id": str(shot.get("shot_id") or "sh1"),
                        "provider": "seedance",
                        "type": "text_to_video",
                        "prompt": (
                            "竖屏 9:16，真实短视频画面，"
                            f"{shot.get('description') or topic}，画面干净，字幕留白充足"
                        ),
                        "duration": self._int_value(shot.get("duration"), 6),
                        "aspect_ratio": "9:16",
                        "resolution": "720p",
                    }
                )
            return {"render_prompt_pack": {"prompts": prompts}}

        return None

    def _best_hook(self, user_input: dict[str, Any], topic: str) -> str:
        hook_plan = user_input.get("hook_plan")
        if isinstance(hook_plan, dict) and hook_plan.get("best_hook"):
            return str(hook_plan["best_hook"])
        return f"很多人做{topic}，第一步就错了。"

    def _int_value(self, value: object, default: int) -> int:
        if isinstance(value, bool) or value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str | bytes | bytearray):
            try:
                return int(value)
            except ValueError:
                return default
        return default

    def _segments(self, user_input: dict[str, Any]) -> list[dict[str, object]]:
        segments = user_input.get("script_segments")
        if isinstance(segments, list):
            return [dict(item) for item in segments if isinstance(item, dict)]
        return [
            {
                "id": "s1",
                "duration": 5,
                "screen_text": str(user_input.get("topic") or "内容主题"),
            }
        ]

    def _shots(self, user_input: dict[str, Any]) -> list[dict[str, object]]:
        storyboard = user_input.get("storyboard")
        if isinstance(storyboard, dict) and isinstance(storyboard.get("shots"), list):
            return [dict(item) for item in storyboard["shots"] if isinstance(item, dict)]
        return [
            {
                "shot_id": "sh1",
                "duration": 5,
                "description": str(user_input.get("topic") or "内容主题"),
            }
        ]

class ModelRouter:
    def __init__(
        self,
        provider: ModelProvider | None = None,
        providers: dict[str, ModelProvider] | None = None,
        active_profile: str = "mock",
    ) -> None:
        self.providers = providers or {"mock": provider or MockModelProvider()}
        self.active_profile = active_profile
        self.provider = self.providers.get(active_profile) or next(iter(self.providers.values()))

    @classmethod
    def from_config(cls, config: EngineConfig) -> "ModelRouter":
        return cls(
            providers={
                profile_id: _build_provider(profile)
                for profile_id, profile in config.models.profiles.items()
                if profile.enabled
            },
            active_profile=config.models.active_profile,
        )

    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelResponse:
        provider_id = profile if profile in self.providers else self.active_profile
        provider = self.providers.get(provider_id)
        if provider is None:
            raise BklEngineError(
                "CONFIG_INVALID",
                f"Model profile is not configured: {provider_id}",
            )
        try:
            return await provider.chat(
                provider_id,
                messages,
                tools,
                stream_callback=stream_callback,
            )
        except TypeError as exc:
            if "stream_callback" not in str(exc):
                raise
            return await provider.chat(provider_id, messages, tools)


def _build_provider(profile: ModelProfileConfig) -> ModelProvider:
    if profile.protocol == "mock":
        return MockModelProvider()
    if profile.protocol == "openai-compatible":
        from app.infrastructure.model_gateway.providers.openai_compatible import (
            OpenAICompatibleProvider,
        )

        return OpenAICompatibleProvider(profile)
    if profile.protocol == "anthropic":
        from app.infrastructure.model_gateway.providers.anthropic import AnthropicProvider

        return AnthropicProvider(profile)
    raise BklEngineError("CONFIG_INVALID", f"Unsupported model protocol: {profile.protocol}")

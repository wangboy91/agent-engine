"""Resolve natural-language Agent requests into Skill input JSON."""

import re
from typing import Any

from bkl_engine.domain.agent.schemas import InputResolution
from bkl_engine.domain.skill import Skill


class InputResolver:
    def resolve(
        self,
        skill: Skill,
        message: str,
        input_draft: dict[str, Any] | None = None,
        defaults: dict[str, Any] | None = None,
    ) -> InputResolution:
        payload: dict[str, Any] = {}
        assumptions: list[str] = []
        schema_defaults = self._schema_defaults(skill.input_schema)
        if schema_defaults:
            payload.update(schema_defaults)
            assumptions.extend(f"{key} uses schema default" for key in schema_defaults)
        if defaults:
            payload.update(defaults)
            assumptions.extend(f"{key} uses scene default" for key in defaults)
        if input_draft:
            payload.update(input_draft)

        payload.update(
            self._extract_known_fields(
                skill.id,
                message,
                payload,
                has_topic="topic" in self._schema_properties(skill.input_schema),
            )
        )
        missing_fields = [
            field
            for field in self._required_fields(skill.input_schema)
            if self._is_missing(payload.get(field))
        ]
        return InputResolution(
            input={key: value for key, value in payload.items() if not self._is_missing(value)},
            missing_fields=missing_fields,
            assumptions=assumptions,
        )

    def _extract_known_fields(
        self,
        skill_id: str,
        message: str,
        current: dict[str, Any],
        *,
        has_topic: bool,
    ) -> dict[str, Any]:
        extracted: dict[str, Any] = {}
        if "topic" not in current:
            topic = self._extract_after_label(message, ["主题", "话题"])
            if topic is None and has_topic:
                topic = self._fallback_topic(message)
            if topic:
                extracted["topic"] = topic
        if "duration_seconds" not in current:
            duration = self._extract_duration_seconds(message)
            if duration is not None:
                extracted["duration_seconds"] = duration
        if "platform" not in current:
            platform = self._extract_platform(message)
            if platform:
                extracted["platform"] = platform

        if skill_id == "wangbudong-experiment":
            if "experiment_title" not in current:
                title = self._extract_after_label(message, ["实验标题", "标题", "主题"])
                if title:
                    extracted["experiment_title"] = title
            if "materials" not in current:
                materials = self._extract_materials(message)
                if materials:
                    extracted["materials"] = materials
            if "target_phenomenon" not in current:
                phenomenon = self._extract_after_label(
                    message,
                    ["目标现象", "现象", "观察到"],
                )
                if phenomenon:
                    extracted["target_phenomenon"] = phenomenon
        return extracted

    def _schema_defaults(self, schema: dict[str, Any]) -> dict[str, Any]:
        defaults: dict[str, Any] = {}
        for key, value in self._schema_properties(schema).items():
            if isinstance(value, dict) and "default" in value:
                defaults[str(key)] = value["default"]
        return defaults

    def _schema_properties(self, schema: dict[str, Any]) -> dict[str, Any]:
        properties = schema.get("properties")
        return dict(properties) if isinstance(properties, dict) else {}

    def _required_fields(self, schema: dict[str, Any]) -> list[str]:
        required = schema.get("required", [])
        return [str(field) for field in required] if isinstance(required, list) else []

    def _extract_after_label(self, message: str, labels: list[str]) -> str | None:
        for label in labels:
            pattern = rf"{re.escape(label)}\s*(?:是|为|:|：)?\s*([^，。；;,\n]+)"
            match = re.search(pattern, message)
            if match:
                value = match.group(1).strip()
                if value:
                    return value
        return None

    def _extract_duration_seconds(self, message: str) -> int | None:
        match = re.search(r"(\d+)\s*秒", message)
        return int(match.group(1)) if match else None

    def _extract_platform(self, message: str) -> str | None:
        if "小红书" in message:
            return "xiaohongshu"
        if "抖音" in message:
            return "douyin"
        if "B站" in message or "b站" in message:
            return "bilibili"
        if "微博" in message:
            return "weibo"
        return None

    def _fallback_topic(self, message: str) -> str | None:
        value = message.strip(" \t\r\n，。；;")
        if not value:
            return None
        value = re.sub(r"\d+\s*秒", "", value)
        value = re.sub(r"(小红书|抖音|B站|b站|微博)", "", value)
        value = re.sub(
            r"(帮我|请|生成|制作|做一个|输出|视频|口播|分镜提示词|分镜|提示词)",
            "",
            value,
        )
        value = value.strip(" \t\r\n，。；;")
        return value or message.strip(" \t\r\n，。；;")

    def _extract_materials(self, message: str) -> list[str]:
        match = re.search(
            r"材料\s*(?:有|是|为|:|：)?\s*(.+?)(?:，\s*(?:现象|目标现象)|。|；|;|$)",
            message,
        )
        if not match:
            return []
        raw = match.group(1)
        return [
            item.strip()
            for item in re.split(r"[、,，/ ]+", raw)
            if item.strip()
        ]

    def _is_missing(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        if isinstance(value, list) and not value:
            return True
        return False

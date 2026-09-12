"""Skill routing for natural-language Agent requests."""

from app.application.ports import SkillRegistryPort
from app.domain.agent.schemas import RouteDecision


class SkillRouter:
    def __init__(
        self,
        skill_registry: SkillRegistryPort,
        auto_run_threshold: float = 0.85,
    ) -> None:
        self.skill_registry = skill_registry
        self.auto_run_threshold = auto_run_threshold

    def route(
        self,
        message: str,
        explicit_skill_id: str | None = None,
        allowed_skill_ids: list[str] | None = None,
    ) -> RouteDecision:
        allowed_skill_set = set(allowed_skill_ids) if allowed_skill_ids is not None else None
        if explicit_skill_id is not None:
            if allowed_skill_set is not None and explicit_skill_id not in allowed_skill_set:
                return RouteDecision(
                    intent="unknown",
                    skill_id=explicit_skill_id,
                    confidence=0,
                    reason="skill is not available to the active identity",
                )
            return RouteDecision(
                intent="run_skill",
                skill_id=explicit_skill_id,
                confidence=1,
                reason="explicit skill_id",
            )

        skills = self.skill_registry.list_skills()
        if allowed_skill_set is not None:
            skills = [skill for skill in skills if skill.id in allowed_skill_set]
        if not skills:
            return RouteDecision(
                intent="unknown",
                confidence=0,
                reason=(
                    "no skills available to the active identity"
                    if allowed_skill_set is not None
                    else "no registered skills"
                ),
            )

        scored = sorted(
            (
                (
                    self._score_skill(
                        message,
                        skill.id,
                        skill.name,
                        skill.description,
                        visible_skill_count=len(skills),
                    ),
                    skill.id,
                )
                for skill in skills
            ),
            reverse=True,
        )
        best_score, best_skill_id = scored[0]
        if best_score < 0.6:
            return RouteDecision(
                intent="unknown",
                confidence=best_score,
                reason="no skill matched the request",
            )

        if (
            len(scored) > 1
            and best_score - scored[1][0] < 0.12
            and not (best_skill_id == "content-video-workflow" and "介绍" in message)
            and not (
                best_skill_id == "talking-video"
                and ("口播" in message or "秒" in message)
            )
        ):
            best_score = min(best_score, 0.74)

        return RouteDecision(
            intent="run_skill",
            skill_id=best_skill_id,
            confidence=best_score,
            reason="matched request against registered Skill metadata",
        )

    def _score_skill(
        self,
        message: str,
        skill_id: str,
        skill_name: str,
        description: str,
        visible_skill_count: int | None = None,
    ) -> float:
        text = message.casefold()
        metadata = f"{skill_id} {skill_name} {description}".casefold()
        score = 0.0

        if skill_id.casefold() in text or skill_name.casefold() in text:
            score += 0.9

        keyword_groups = {
            "wangbudong-experiment": ["王不懂", "小实验", "实验", "亲子", "科学"],
            "talking-video": ["口播", "视频", "小红书", "抖音", "b站", "微博", "秒"],
            "content-video-workflow": [
                "想法",
                "介绍",
                "视频",
                "短视频",
                "口播",
                "脚本",
                "分镜",
                "提示词",
                "渲染提示词",
                "素材",
                "成片",
                "复盘",
                "工作流",
                "内容生产",
                "课程",
                "小红书",
                "抖音",
            ],
        }
        keywords = keyword_groups.get(skill_id, [])
        matched_keywords = [keyword for keyword in keywords if keyword.casefold() in text]
        if matched_keywords:
            score = max(score, 0.65)
            score += len(matched_keywords) * 0.1

        if skill_id == "content-video-workflow" and "介绍" in text:
            score = max(score, 0.86)

        for token in ("video", "experiment", "skill", "tool"):
            if token in text and token in metadata:
                score += 0.08

        skill_count = visible_skill_count or len(self.skill_registry.list_skills())
        if score == 0 and skill_count == 1:
            score = 0.62

        return min(score, 0.96)

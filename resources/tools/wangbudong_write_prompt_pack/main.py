"""Write a Wangbudong experiment prompt pack to the artifact directory."""

import json
import os
import sys
from pathlib import Path
from typing import Any

BREAKDOWN_FILE = "00-\u5b9e\u9a8c\u62c6\u89e3.md"
COVER_FILE = "01-\u9996\u56fe\u63d0\u793a\u8bcd.md"
STEP_FILE = "02-\u5206\u6b65\u9aa4\u63d0\u793a\u8bcd.md"
COPY_FILE = "03-\u5c0f\u7ea2\u4e66\u6587\u6848.md"
OPERATIONS_FILE = "04-\u53d1\u5e03\u8fd0\u8425\u5361.md"


def main() -> None:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    artifact_dir = Path(os.environ["BKL_ARTIFACT_DIR"])
    artifact_dir.mkdir(parents=True, exist_ok=True)

    title = str(payload["experiment_title"])
    materials = [str(item) for item in payload["materials"]]
    phenomenon = str(payload["target_phenomenon"])
    age_range = str(payload.get("age_range") or "3-8\u5c81")
    content_lane = str(payload.get("content_lane") or "\u8da3\u5473\u5f15\u6d41")
    include_operations_card = bool(payload.get("include_operations_card", False))

    feasibility_summary = _feasibility_summary(title, materials, phenomenon)
    cover_prompt = _cover_prompt(title, materials, phenomenon, age_range, content_lane)
    step_prompts = _step_prompts(title, materials, phenomenon)
    xiaohongshu_copy = _xiaohongshu_copy(title, materials, phenomenon, age_range)
    safety_notes = _safety_notes(materials)

    files = {
        BREAKDOWN_FILE: _breakdown(
            title,
            materials,
            phenomenon,
            age_range,
            content_lane,
            feasibility_summary,
            safety_notes,
        ),
        COVER_FILE: cover_prompt,
        STEP_FILE: step_prompts,
        COPY_FILE: xiaohongshu_copy,
    }
    if include_operations_card:
        files[OPERATIONS_FILE] = _operations_card(title, content_lane, age_range)

    for filename, content in files.items():
        (artifact_dir / filename).write_text(content, encoding="utf-8")

    result: dict[str, Any] = {
        "experiment_title": title,
        "output_dir": str(artifact_dir),
        "files": list(files),
        "feasibility_summary": feasibility_summary,
        "cover_prompt": cover_prompt,
        "step_prompt_count": step_prompts.count("## \u7b2c"),
        "xiaohongshu_copy": xiaohongshu_copy,
        "safety_notes": safety_notes,
    }
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8") + b"\n")


def _feasibility_summary(title: str, materials: list[str], phenomenon: str) -> str:
    material_text = "\u3001".join(materials)
    return (
        f"{title}\u4f7f\u7528\u6750\u6599\uff1a{material_text}\u3002"
        f"\u76ee\u6807\u73b0\u8c61\u662f\uff1a{phenomenon}\u3002"
        "\u6750\u6599\u8db3\u4ee5\u652f\u6491\u4e00\u4e2a\u53ef\u89c2\u5bdf\u3001"
        "\u53ef\u590d\u505a\u7684\u4eb2\u5b50\u79d1\u5b66\u5b9e\u9a8c\u3002"
    )


def _breakdown(
    title: str,
    materials: list[str],
    phenomenon: str,
    age_range: str,
    content_lane: str,
    feasibility_summary: str,
    safety_notes: list[str],
) -> str:
    safety_text = (
        "\n".join(f"- {note}" for note in safety_notes)
        if safety_notes
        else (
            "- \u4f4e\u98ce\u9669\u5b9e\u9a8c\uff0c"
            "\u5efa\u8bae\u5bb6\u957f\u966a\u540c\u89c2\u5bdf\u3002"
        )
    )
    material_lines = "\n".join(f"- {material}" for material in materials)
    return "\n".join(
        [
            f"# {title} \u5b9e\u9a8c\u62c6\u89e3",
            "",
            "## \u5b9e\u9a8c\u5b9a\u4f4d",
            f"- \u5185\u5bb9\u680f\u76ee\uff1a{content_lane}",
            f"- \u9002\u5408\u5e74\u9f84\uff1a{age_range}",
            "",
            "## \u5b9e\u9a8c\u5408\u7406\u6027\u8bba\u8bc1",
            f"- \u76ee\u6807\u73b0\u8c61\uff1a{phenomenon}",
            f"- \u53ef\u884c\u6027\uff1a{feasibility_summary}",
            (
                "- \u6700\u7ec8\u88c5\u7f6e\uff1a"
                "\u684c\u9762\u771f\u5b9e\u5b9e\u9a8c\u88c5\u7f6e\uff0c"
                "\u6210\u4eba\u8f85\u52a9\uff0c\u5b69\u5b50\u89c2\u5bdf\u3002"
            ),
            "",
            "## \u6750\u6599",
            material_lines,
            "",
            "## \u6b65\u9aa4",
            "1. \u6446\u597d\u6750\u6599\uff0c\u786e\u8ba4\u5bb9\u5668\u7a33\u5b9a\u3002",
            (
                "2. \u6309\u987a\u5e8f\u52a0\u5165\u6750\u6599\uff0c"
                "\u4fdd\u7559\u5b69\u5b50\u80fd\u89c2\u5bdf\u7684"
                "\u5173\u952e\u52a8\u4f5c\u3002"
            ),
            "3. \u5f15\u5bfc\u5b69\u5b50\u63cf\u8ff0\u770b\u5230\u7684\u53d8\u5316\u3002",
            (
                "4. \u8bb0\u5f55\u6210\u529f\u6761\u4ef6\u548c"
                "\u5bb9\u6613\u5931\u8d25\u7684\u53d8\u91cf\u3002"
            ),
            "",
            "## \u89c2\u5bdf\u73b0\u8c61",
            f"- {phenomenon}",
            "",
            "## \u5b89\u5168\u548c\u5236\u4f5c\u63d0\u793a",
            safety_text,
            "",
        ]
    )


def _cover_prompt(
    title: str,
    materials: list[str],
    phenomenon: str,
    age_range: str,
    content_lane: str,
) -> str:
    material_text = "\u3001".join(materials)
    return "\n".join(
        [
            "# \u9996\u56fe\u63d0\u793a\u8bcd",
            (
                "1086x1448 \u7ad6\u7248\u4e2d\u6587\u4eb2\u5b50"
                f"\u79d1\u5b66\u542f\u8499\u4fe1\u606f\u56fe\uff0c"
                f"\u4e3b\u6807\u9898\u300a{title}\u300b\u3002"
            ),
            f"\u6750\u6599\uff1a{material_text}\u3002\u76ee\u6807\u73b0\u8c61\uff1a{phenomenon}\u3002",
            f"\u9002\u5408\u5e74\u9f84\uff1a{age_range}\u3002\u680f\u76ee\u7c7b\u578b\uff1a{content_lane}\u3002",
            (
                "\u914d\u8272\u8981\u6c42\uff1a\u6696\u767d\u5e95\u3001"
                "\u4eae\u5b9d\u84dd\u6807\u7b7e\u3001"
                "\u67e0\u6aac\u9ec4\u63d0\u793a\u6761\u3001"
                "\u8f6f\u7c89\u89c2\u5bdf\u6846\u3002"
            ),
            (
                "\u79d1\u5b66\u771f\u5b9e\u6027\u8981\u6c42\uff1a"
                "\u53ea\u5c55\u793a\u771f\u5b9e\u53ef\u64cd\u4f5c\u7684"
                "\u684c\u9762\u5b9e\u9a8c\u88c5\u7f6e\u3002"
            ),
            (
                "\u8d1f\u9762\u63d0\u793a\u8bcd\uff1a"
                "\u9519\u522b\u5b57\u3001\u4e8c\u7ef4\u7801\u3001"
                "\u5916\u90e8\u6c34\u5370\u3001"
                "\u5371\u9669\u513f\u7ae5\u64cd\u4f5c\u3002"
            ),
        ]
    )


def _step_prompts(title: str, materials: list[str], phenomenon: str) -> str:
    material_text = "\u3001".join(materials)
    pages = [
        (
            "\u51c6\u5907\u6750\u6599",
            (
                f"\u5c55\u793a {material_text}\uff0c"
                "\u6bcf\u4e2a\u6750\u6599\u6709\u6e05\u6670"
                "\u4e2d\u6587\u6807\u7b7e\u3002"
            ),
        ),
        (
            "\u5f00\u59cb\u64cd\u4f5c",
            (
                "\u5c55\u793a\u6210\u4eba\u624b\u90e8"
                "\u8fdb\u884c\u5173\u952e\u52a8\u4f5c\uff0c"
                "\u5b69\u5b50\u5728\u65c1\u8fb9\u89c2\u5bdf\u3002"
            ),
        ),
        (
            "\u89c2\u5bdf\u53d8\u5316",
            (
                f"\u7a81\u51fa {phenomenon}\uff0c"
                "\u7528\u7bad\u5934\u6807\u6ce8\u53d8\u5316\u65b9\u5411\u3002"
            ),
        ),
        (
            "\u4e3a\u4ec0\u4e48\u4f1a\u8fd9\u6837",
            (
                "\u7528\u4e09\u683c\u56fe\u89e3\u91ca\u539f\u7406\uff0c"
                "\u8bed\u8a00\u77ed\u3001\u53ef\u8bfb\u3002"
            ),
        ),
        (
            "\u7ffb\u8f66\u6392\u67e5",
            (
                "\u5c55\u793a\u6bd4\u4f8b\u4e0d\u5bf9\u3001"
                "\u52a8\u4f5c\u592a\u5feb\u3001"
                "\u6750\u6599\u6446\u653e\u4e0d\u7a33"
                "\u4e09\u4e2a\u5e38\u89c1\u539f\u56e0\u3002"
            ),
        ),
    ]
    blocks: list[str] = []
    for index, (page_title, target) in enumerate(pages, start=1):
        blocks.extend(
            [
                f"## \u7b2c {index} \u5f20\uff1a{page_title}",
                "",
                "### \u753b\u9762\u76ee\u6807",
                target,
                "",
                "### \u751f\u6210\u63d0\u793a\u8bcd",
                (
                    "1086x1448 \u7ad6\u7248\u4e2d\u6587\u4fe1\u606f\u56fe\uff0c"
                    f"\u300a{title}\u300b\u540c\u4e00\u5957"
                    f"\u771f\u5b9e\u88c5\u7f6e\u3002{target}"
                ),
                (
                    "\u914d\u8272\u8981\u6c42\uff1a\u6696\u767d\u5e95\u3001"
                    "\u6d45\u6c34\u84dd\u5206\u533a\u3001"
                    "\u4eae\u5b9d\u84dd\u6807\u7b7e\u3002"
                ),
                (
                    "\u79d1\u5b66\u771f\u5b9e\u6027\u8981\u6c42\uff1a"
                    f"\u73b0\u8c61\u5fc5\u987b\u662f {phenomenon}\u3002"
                ),
                "",
            ]
        )
    return "\n".join(blocks)


def _xiaohongshu_copy(
    title: str,
    materials: list[str],
    phenomenon: str,
    age_range: str,
) -> str:
    material_text = "\u3001".join(materials)
    return "\n".join(
        [
            f"{title} | {age_range} \u5728\u5bb6\u4e5f\u80fd\u89c2\u5bdf\u7684\u5c0f\u5b9e\u9a8c",
            "",
            (
                f"\u4eca\u5929\u7528 {material_text}\uff0c"
                f"\u5e26\u5b69\u5b50\u770b\u89c1\uff1a{phenomenon}\u3002"
            ),
            "",
            (
                "\u73a9\u6cd5\u5f88\u7b80\u5355\uff1a"
                "\u5148\u8ba9\u5b69\u5b50\u731c\u4e00\u731c\uff0c"
                "\u518d\u7531\u5bb6\u957f\u5b8c\u6210\u5173\u952e\u52a8\u4f5c\u3002"
            ),
            "",
            (
                "#\u4eb2\u5b50\u79d1\u5b66 "
                "#\u5e7c\u513f\u79d1\u5b66\u542f\u8499 "
                "#\u5728\u5bb6\u505a\u5b9e\u9a8c "
                "#\u738b\u4e0d\u61c2\u7684\u5c0f\u5b9e\u9a8c"
            ),
        ]
    )


def _operations_card(title: str, content_lane: str, age_range: str) -> str:
    return "\n".join(
        [
            f"# {title} \u53d1\u5e03\u8fd0\u8425\u5361",
            "",
            f"- \u680f\u76ee\uff1a{content_lane}",
            f"- \u5e74\u9f84\uff1a{age_range}",
            "- \u8bc4\u8bba\u5173\u952e\u8bcd\uff1a\u6b65\u9aa4\u5361",
        ]
    )


def _safety_notes(materials: list[str]) -> list[str]:
    risky_keywords = {
        "\u706b",
        "\u9152\u7cbe",
        "\u73bb\u7483",
        "\u5200",
        "\u70ed\u6c34",
        "\u6253\u5b54",
    }
    if any(any(keyword in material for keyword in risky_keywords) for material in materials):
        return [
            (
                "\u6d89\u53ca\u6f5c\u5728\u98ce\u9669\u6750\u6599\uff0c"
                "\u5fc5\u987b\u7531\u6210\u4eba\u64cd\u4f5c"
                "\u5371\u9669\u6b65\u9aa4\u3002"
            )
        ]
    return []


if __name__ == "__main__":
    main()

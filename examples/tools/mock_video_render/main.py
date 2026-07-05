import json
import os
import sys
from pathlib import Path


def run(input_data: dict) -> dict:
    artifact_dir = Path(os.environ["BKL_ARTIFACT_DIR"]).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    prompts = input_data.get("render_prompt_pack", {}).get("prompts", [])
    assets = input_data.get("asset_manifest", {}).get("assets", [])
    timeline = input_data.get("timeline", {})
    source_draft = input_data.get("video_draft", {})

    generated_assets = []
    for index, prompt in enumerate(prompts if isinstance(prompts, list) else []):
        if not isinstance(prompt, dict):
            continue
        generated_assets.append(
            {
                "asset_id": f"generated_{index + 1}",
                "shot_id": str(prompt.get("shot_id") or f"sh{index + 1}"),
                "type": str(prompt.get("type") or "video"),
                "status": "rendered",
                "duration": int(prompt.get("duration") or 0),
            }
        )

    video_path = artifact_dir / "video-draft.mp4"
    manifest_path = artifact_dir / "render-manifest.json"
    render_job_id = f"render_{os.environ.get('BKL_TOOL_CALL_ID', 'mock')}"

    manifest = {
        "render_job_id": render_job_id,
        "provider": "mock_video_render",
        "timeline": timeline,
        "prompt_count": len(generated_assets),
        "source_asset_count": len(assets) if isinstance(assets, list) else 0,
        "generated_assets": generated_assets,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    video_path.write_text("mock video artifact\n", encoding="utf-8")

    video_draft = dict(source_draft) if isinstance(source_draft, dict) else {}
    video_draft.update(
        {
            "status": "rendered",
            "render_job_id": render_job_id,
            "video_path": str(video_path),
            "manifest_path": str(manifest_path),
        }
    )

    return {
        "render_job_id": render_job_id,
        "status": "succeeded",
        "provider": "mock_video_render",
        "video_path": str(video_path),
        "manifest_path": str(manifest_path),
        "generated_assets": generated_assets,
        "video_draft": video_draft,
    }


if __name__ == "__main__":
    input_data = json.loads(sys.stdin.read())
    output = run(input_data)
    print(json.dumps(output, ensure_ascii=False))

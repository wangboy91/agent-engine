import json
import sys


def run(input_data: dict) -> dict:
    text = input_data["text"]

    return {
        "srt_path": "subtitle.srt",
        "segments": [
            {
                "index": 1,
                "start": "00:00:00,000",
                "end": "00:00:03,000",
                "text": text,
            }
        ],
    }


if __name__ == "__main__":
    input_data = json.loads(sys.stdin.read())
    output = run(input_data)
    print(json.dumps(output, ensure_ascii=False))

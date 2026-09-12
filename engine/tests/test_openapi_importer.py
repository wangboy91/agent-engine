from app.infrastructure.package_loaders.openapi_importer import import_openapi_tools


def test_openapi_importer_generates_api_tools_from_operations() -> None:
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/api/v1/tts": {
                "post": {
                    "operationId": "generateSpeech",
                    "summary": "Generate speech",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["text"],
                                    "properties": {"text": {"type": "string"}},
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"audio_url": {"type": "string"}},
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    tools = import_openapi_tools(spec, base_url="https://api.example.com")

    assert len(tools) == 1
    assert tools[0].id == "generateSpeech"
    assert tools[0].type == "api"
    assert tools[0].description == "Generate speech"
    assert tools[0].config["method"] == "POST"
    assert tools[0].config["url"] == "/api/v1/tts"
    assert tools[0].config["base_url"] == "https://api.example.com"
    assert tools[0].input_schema["required"] == ["text"]


def test_openapi_importer_generates_stable_id_without_operation_id() -> None:
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/api/v1/videos/{video_id}": {
                "get": {
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    tools = import_openapi_tools(spec)

    assert tools[0].id == "get_api_v1_videos_video_id"

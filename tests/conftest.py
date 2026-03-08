"""Shared fixtures for mcp2cli tests."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

PETSTORE_SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Petstore", "version": "1.0.0"},
    "servers": [{"url": "/api/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer"},
                        "description": "Max items to return",
                    },
                    {
                        "name": "status",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["available", "pending", "sold"],
                        },
                        "description": "Filter by status",
                    },
                ],
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Pet name",
                                    },
                                    "tag": {
                                        "type": "string",
                                        "description": "Pet tag",
                                    },
                                    "age": {
                                        "type": "integer",
                                        "description": "Pet age",
                                    },
                                },
                            }
                        }
                    }
                },
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "summary": "Get a pet by ID",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "description": "Pet ID",
                    }
                ],
            },
            "delete": {
                "operationId": "deletePet",
                "summary": "Delete a pet",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "description": "Pet ID",
                    }
                ],
            },
            "put": {
                "operationId": "updatePet",
                "summary": "Update a pet",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "description": "Pet ID",
                    }
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Pet name",
                                    },
                                    "tag": {
                                        "type": "string",
                                        "description": "Pet tag",
                                    },
                                },
                            }
                        }
                    }
                },
            },
        },
    },
    "components": {
        "schemas": {
            "Pet": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "tag": {"type": "string"},
                },
            }
        }
    },
}

# Spec using $ref to test ref resolution
PETSTORE_SPEC_WITH_REFS = {
    "openapi": "3.0.3",
    "info": {"title": "Petstore (refs)", "version": "1.0.0"},
    "servers": [{"url": "/api/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "parameters": [
                    {"$ref": "#/components/parameters/LimitParam"},
                ],
            },
        },
    },
    "components": {
        "parameters": {
            "LimitParam": {
                "name": "limit",
                "in": "query",
                "schema": {"type": "integer"},
                "description": "Max items to return",
            },
        },
    },
}


# In-memory pet store
_PETS = {
    1: {"id": 1, "name": "Fido", "tag": "dog", "status": "available", "age": 3},
    2: {"id": 2, "name": "Whiskers", "tag": "cat", "status": "available", "age": 5},
    3: {"id": 3, "name": "Goldie", "tag": "fish", "status": "sold", "age": 1},
}
_NEXT_ID = 4


class PetstoreHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves the petstore spec and API."""

    def log_message(self, format, *args):
        pass  # silence logs during tests

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def _parse_path(self):
        path = self.path.split("?")[0]
        query_str = self.path.split("?")[1] if "?" in self.path else ""
        params = {}
        if query_str:
            for pair in query_str.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v
        return path, params

    def do_GET(self):
        path, params = self._parse_path()

        if path == "/openapi.json":
            self._send_json(PETSTORE_SPEC)
            return

        if path == "/api/v1/pets":
            pets = list(_PETS.values())
            if "status" in params:
                pets = [p for p in pets if p.get("status") == params["status"]]
            if "limit" in params:
                pets = pets[: int(params["limit"])]
            self._send_json(pets)
            return

        if path.startswith("/api/v1/pets/"):
            pet_id = int(path.split("/")[-1])
            if pet_id in _PETS:
                self._send_json(_PETS[pet_id])
            else:
                self._send_json({"error": "not found"}, 404)
            return

        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        global _NEXT_ID
        path, _ = self._parse_path()

        if path == "/api/v1/pets":
            body = self._read_body()
            pet = {"id": _NEXT_ID, **body}
            _PETS[_NEXT_ID] = pet
            _NEXT_ID += 1
            self._send_json(pet, 201)
            return

        self._send_json({"error": "not found"}, 404)

    def do_PUT(self):
        path, _ = self._parse_path()

        if path.startswith("/api/v1/pets/"):
            pet_id = int(path.split("/")[-1])
            if pet_id in _PETS:
                body = self._read_body()
                _PETS[pet_id].update(body)
                self._send_json(_PETS[pet_id])
            else:
                self._send_json({"error": "not found"}, 404)
            return

        self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        path, _ = self._parse_path()

        if path.startswith("/api/v1/pets/"):
            pet_id = int(path.split("/")[-1])
            if pet_id in _PETS:
                del _PETS[pet_id]
                self._send_json({"deleted": True})
            else:
                self._send_json({"error": "not found"}, 404)
            return

        self._send_json({"error": "not found"}, 404)


@pytest.fixture(scope="session")
def petstore_server():
    """Start a local petstore HTTP server for the test session."""
    # Reset store
    global _NEXT_ID
    _PETS.clear()
    _PETS.update({
        1: {"id": 1, "name": "Fido", "tag": "dog", "status": "available", "age": 3},
        2: {"id": 2, "name": "Whiskers", "tag": "cat", "status": "available", "age": 5},
        3: {"id": 3, "name": "Goldie", "tag": "fish", "status": "sold", "age": 1},
    })
    _NEXT_ID = 4

    server = HTTPServer(("127.0.0.1", 0), PetstoreHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture
def petstore_spec():
    """Return the petstore spec dict."""
    return PETSTORE_SPEC


@pytest.fixture
def petstore_spec_with_refs():
    """Return the petstore spec with $ref."""
    return PETSTORE_SPEC_WITH_REFS


@pytest.fixture
def petstore_spec_file(tmp_path):
    """Write petstore spec to a temp file and return the path."""
    p = tmp_path / "petstore.json"
    p.write_text(json.dumps(PETSTORE_SPEC))
    return str(p)


@pytest.fixture
def petstore_yaml_file(tmp_path):
    """Write petstore spec as YAML to a temp file and return the path."""
    import yaml

    p = tmp_path / "petstore.yaml"
    p.write_text(yaml.dump(PETSTORE_SPEC))
    return str(p)


@pytest.fixture
def mcp_test_server_cmd():
    """Return the command to run the test MCP stdio server."""
    server_path = Path(__file__).parent / "mcp_test_server.py"
    return f"{sys.executable} {server_path}"


@pytest.fixture(autouse=True)
def _clean_cache(tmp_path, monkeypatch):
    """Redirect cache dir to tmp for all tests."""
    import mcp2cli

    monkeypatch.setattr(mcp2cli, "CACHE_DIR", tmp_path / "cache")

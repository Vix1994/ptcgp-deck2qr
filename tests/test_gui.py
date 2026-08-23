from __future__ import annotations

import base64
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from ptcgp_deck2qr.gui import (
    GuiConfig,
    GuiRequestError,
    GuiServer,
    config_payload,
    create_server,
    recognize_payload,
)
from ptcgp_deck2qr.matching import MatchPolicy
from ptcgp_deck2qr.pipeline import RecognitionRuntime, load_recognition_runtime

from .helpers import make_database, make_screenshot


@contextmanager
def running_server(config: GuiConfig) -> Iterator[tuple[GuiServer, str]]:
    server = create_server(config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    raw_host, port = server.server_address[:2]
    host = raw_host.decode() if isinstance(raw_host, bytes) else raw_host
    try:
        yield server, f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def get_bytes(url: str) -> tuple[int, bytes, str]:
    with urlopen(url) as response:
        return response.status, response.read(), response.headers["Content-Type"]


def post_json(url: str, payload: object) -> tuple[int, dict[str, object]]:
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_gui_serves_react_build_and_safe_config(tmp_path: Path) -> None:
    config = GuiConfig(tmp_path / "database", tmp_path / "output", port=0)
    with running_server(config) as (_, base_url):
        status, html, content_type = get_bytes(f"{base_url}/")
        assert status == 200
        assert b'id="root"' in html
        assert content_type.startswith("text/html")
        with urlopen(f"{base_url}/app.js") as response:
            assert response.headers["Content-Type"].startswith("text/javascript")
            assert response.headers["Cache-Control"] == "no-store"
        assert get_bytes(f"{base_url}/app.css")[2].startswith("text/css")
        image_name = next(Path("src/ptcgp_deck2qr/webgui/assets").glob("grass-*.png")).name
        assert get_bytes(f"{base_url}/assets/{image_name}")[2] == "image/png"
        with pytest.raises(HTTPError, match="404"):
            get_bytes(f"{base_url}/assets/missing.png")
        status, payload = post_json(f"{base_url}/missing", {})
        assert status == 404
        assert payload == {"error": "not found"}
        with urlopen(f"{base_url}/api/config") as response:
            gui_config = json.loads(response.read())
        assert gui_config == config_payload(config)


def test_gui_recognizes_synthetic_deck_over_http(tmp_path: Path) -> None:
    database = make_database(tmp_path, count=10)
    image = tmp_path / "deck.png"
    make_screenshot(image)
    config = GuiConfig(database, tmp_path / "output", port=0)
    payload = {
        "filename": image.name,
        "image_base64": base64.b64encode(image.read_bytes()).decode(),
        "energies": ["lightning"],
        "style": "separate-cards",
    }

    with running_server(config) as (_, base_url):
        status, result = post_json(f"{base_url}/api/recognize", payload)
        assert status == 200
        assert result["accepted"] is True
        assert result["card_count"] == 20
        assert result["detected_style"] == "separate-cards"
        assert "# PTCGP-DECK 1" in str(result["deck_text"])
        assert len(result["cards"]) == 20  # type: ignore[arg-type]
        qr_input = result["qr_input"]
        assert isinstance(qr_input, dict)
        assert qr_input["energies"] == ["lightning"]
        assert len(qr_input["cards"]) == 10
        assert result["qr_error"] is None

        status, deck, content_type = get_bytes(f"{base_url}/artifacts/deck.txt")
        assert status == 200
        assert b"energy: lightning" in deck
        assert content_type.startswith("text/plain")
        assert get_bytes(f"{base_url}/artifacts/recognized.png")[2] == "image/png"


def test_gui_reuses_loaded_recognition_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = make_database(tmp_path, count=10)
    image = tmp_path / "deck.png"
    make_screenshot(image)
    config = GuiConfig(database, tmp_path / "output", port=0)
    payload = {
        "filename": image.name,
        "image_base64": base64.b64encode(image.read_bytes()).decode(),
        "energies": ["lightning"],
        "style": "separate-cards",
    }
    calls = 0
    real_loader = load_recognition_runtime

    def tracking_loader(
        database_path: str | Path, *, index_path: str | Path | None = None
    ) -> RecognitionRuntime:
        nonlocal calls
        calls += 1
        return real_loader(database_path, index_path=index_path)

    monkeypatch.setattr("ptcgp_deck2qr.gui.load_recognition_runtime", tracking_loader)
    with running_server(config) as (_, base_url):
        assert post_json(f"{base_url}/api/recognize", payload)[0] == 200
        assert post_json(f"{base_url}/api/recognize", payload)[0] == 200

    assert calls == 1


def test_gui_returns_draft_qr_for_entity_only_ambiguity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = make_database(tmp_path, count=10)
    image = tmp_path / "deck.png"
    make_screenshot(image)
    config = GuiConfig(database, tmp_path / "output", port=0)
    payload = {
        "filename": image.name,
        "image_base64": base64.b64encode(image.read_bytes()).decode(),
        "energies": ["lightning"],
        "style": "separate-cards",
    }
    strict_policy = MatchPolicy("test-reject-all", min_score=1.1, min_entity_margin=1.1)
    monkeypatch.setattr(
        "ptcgp_deck2qr.pipeline.policy_for_style",
        lambda _style: strict_policy,
    )

    with running_server(config) as (_, base_url):
        status, result = post_json(f"{base_url}/api/recognize", payload)

    assert status == 200
    assert result["accepted"] is False
    assert result["card_count"] == 20
    assert result["qr_is_draft"] is True
    assert result["uncertain_entity_count"] == 20
    assert isinstance(result["qr_input"], dict)
    assert result["qr_error"] is None
    assert "# PTCGP-DECK 1" in str(result["deck_text"])


def test_gui_rejects_busy_and_unknown_routes(tmp_path: Path) -> None:
    config = GuiConfig(tmp_path / "database", tmp_path / "output", port=0)
    with running_server(config) as (server, base_url):
        server.recognition_lock.acquire()
        try:
            status, result = post_json(f"{base_url}/api/recognize", {})
        finally:
            server.recognition_lock.release()
        assert status == 409
        assert result == {"error": "recognition is already running"}

        for path in ("missing.txt", "../deck.txt", "../assets/app.js"):
            try:
                get_bytes(f"{base_url}/artifacts/{path}")
            except HTTPError as exc:
                assert exc.code == 404


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "image filename is required"),
        ({"filename": "deck.gif", "image_base64": "WA=="}, "image must be PNG"),
        ({"filename": "deck.png", "image_base64": "***"}, "not valid base64"),
        (
            {"filename": "deck.png", "image_base64": "WA==", "energies": []},
            "one to three unique",
        ),
        (
            {
                "filename": "deck.png",
                "image_base64": "WA==",
                "energies": ["fire", "fire"],
            },
            "one to three unique",
        ),
        (
            {"filename": "deck.png", "image_base64": "WA==", "energies": ["dragon"]},
            "unknown energy",
        ),
        (
            {
                "filename": "deck.png",
                "image_base64": "WA==",
                "energies": ["fire"],
                "style": "made-up",
            },
            "unknown screenshot style",
        ),
    ],
)
def test_gui_validates_recognition_payload(
    tmp_path: Path, payload: dict[str, object], message: str
) -> None:
    with pytest.raises(GuiRequestError, match=message):
        recognize_payload(payload, GuiConfig(tmp_path, tmp_path / "output"))


def test_config_payload_reports_nonlocal_binding(tmp_path: Path) -> None:
    payload = config_payload(
        GuiConfig(tmp_path / "database", tmp_path / "output", tmp_path / "index", "0.0.0.0")
    )
    assert payload["local_only"] is False
    assert payload["index_path"] == str(tmp_path / "index")

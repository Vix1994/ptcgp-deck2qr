"""Local browser GUI for the screenshot-recognition pipeline."""

from __future__ import annotations

import base64
import binascii
import json
import threading
import webbrowser
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any, cast
from urllib.parse import urlparse

from .decktext import ALLOWED_ENERGIES
from .detection import StyleName
from .pipeline import RecognitionRuntime, load_recognition_runtime, recognize_image
from .qr import QrInputError, build_qr_input

MAX_REQUEST_BYTES = 36 * 1024 * 1024
MAX_IMAGE_BYTES = 24 * 1024 * 1024
ALLOWED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
ALLOWED_STYLES: tuple[StyleName, ...] = (
    "auto",
    "separate-cards",
    "quantity-label",
    "count-text",
    "count-badge",
)
ARTIFACT_NAMES = frozenset({"deck.txt", "deck.partial.txt", "recognition.json", "recognized.png"})
STATIC_ASSETS: Mapping[str, tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


@dataclass(frozen=True, slots=True)
class GuiConfig:
    """Runtime paths and network binding for the local GUI."""

    database_path: Path
    output_dir: Path
    index_path: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8765


class GuiRequestError(ValueError):
    """A user-correctable request error with an HTTP status."""

    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.status = status


class GuiServer(ThreadingHTTPServer):
    """Threaded local server carrying immutable GUI configuration."""

    daemon_threads = True

    def __init__(self, config: GuiConfig) -> None:
        self.config = config
        self.recognition_lock = threading.Lock()
        self._recognition_runtime: RecognitionRuntime | None = None
        super().__init__((config.host, config.port), GuiRequestHandler)

    def get_recognition_runtime(self) -> RecognitionRuntime:
        """Lazily load and then reuse the immutable database and index."""

        if self._recognition_runtime is None:
            self._recognition_runtime = load_recognition_runtime(
                self.config.database_path,
                index_path=self.config.index_path,
            )
        return self._recognition_runtime


class GuiRequestHandler(BaseHTTPRequestHandler):
    """Serve packaged UI assets and the one recognition endpoint."""

    server: GuiServer

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route in STATIC_ASSETS:
            asset_name, content_type = STATIC_ASSETS[route]
            self._send_bytes(
                HTTPStatus.OK,
                _read_static_asset(asset_name),
                content_type,
                cache=False,
            )
            return
        static_image = _static_image_name(route)
        if static_image is not None:
            try:
                body = _read_static_asset(static_image)
            except FileNotFoundError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            self._send_bytes(HTTPStatus.OK, body, "image/png")
            return
        if route == "/api/config":
            self._send_json(HTTPStatus.OK, config_payload(self.server.config))
            return
        if route.startswith("/artifacts/"):
            self._serve_artifact(route.removeprefix("/artifacts/"))
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route != "/api/recognize":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            payload = self._read_json_request()
            if not self.server.recognition_lock.acquire(blocking=False):
                raise GuiRequestError("recognition is already running", HTTPStatus.CONFLICT)
            try:
                response = recognize_payload(
                    payload,
                    self.server.config,
                    runtime_provider=self.server.get_recognition_runtime,
                )
            finally:
                self.server.recognition_lock.release()
        except GuiRequestError as exc:
            self._send_json(exc.status, {"error": str(exc)})
            return
        except (OSError, ValueError) as exc:
            self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)})
            return
        self._send_json(HTTPStatus.OK, response)

    def log_message(self, format: str, *args: object) -> None:
        """Keep routine local requests quiet while preserving server errors."""

    def _read_json_request(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "0")
        except ValueError as exc:
            raise GuiRequestError("invalid content length") from exc
        if length <= 0:
            raise GuiRequestError("request body is required")
        if length > MAX_REQUEST_BYTES:
            raise GuiRequestError("request is too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GuiRequestError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise GuiRequestError("request body must be a JSON object")
        return cast(dict[str, Any], value)

    def _serve_artifact(self, name: str) -> None:
        if name not in ARTIFACT_NAMES:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "artifact not found"})
            return
        target = self.server.config.output_dir / name
        if not target.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "artifact not found"})
            return
        content_type = {
            ".png": "image/png",
            ".json": "application/json; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
        }[target.suffix]
        self._send_bytes(HTTPStatus.OK, target.read_bytes(), content_type, cache=False)

    def _send_json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
        body = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        self._send_bytes(status, body, "application/json; charset=utf-8", cache=False)

    def _send_bytes(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        *,
        cache: bool = True,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=300" if cache else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy", "default-src 'self'; img-src 'self' blob: data:"
        )
        self.end_headers()
        self.wfile.write(body)


def config_payload(config: GuiConfig) -> dict[str, object]:
    """Return the safe path/status information shown by the local UI."""

    return {
        "database_path": str(config.database_path),
        "output_dir": str(config.output_dir),
        "index_path": str(config.index_path) if config.index_path is not None else None,
        "local_only": config.host in {"127.0.0.1", "localhost", "::1"},
    }


def recognize_payload(
    payload: Mapping[str, Any],
    config: GuiConfig,
    *,
    runtime_provider: Callable[[], RecognitionRuntime] | None = None,
) -> dict[str, object]:
    """Validate one browser request, run the existing pipeline, and shape its response."""

    filename, image_bytes = _decode_image(payload)
    energies = _decode_energies(payload)
    style = _decode_style(payload)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    runtime = (
        runtime_provider()
        if runtime_provider is not None
        else load_recognition_runtime(config.database_path, index_path=config.index_path)
    )
    suffix = Path(filename).suffix.lower()
    with TemporaryDirectory(prefix="ptcgp-deck2qr-gui-") as temporary:
        image_path = Path(temporary) / f"input{suffix}"
        image_path.write_bytes(image_bytes)
        result = recognize_image(
            image_path,
            energy=energies,
            database_path=config.database_path,
            output_dir=config.output_dir,
            style=style,
            index_path=config.index_path,
            runtime=runtime,
        )

    report_path = config.output_dir / "recognition.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("recognition report has an invalid shape")
    artifacts = {
        name: f"/artifacts/{name}"
        for name in sorted(ARTIFACT_NAMES)
        if (config.output_dir / name).is_file()
    }
    deck_path = config.output_dir / ("deck.txt" if result.accepted else "deck.partial.txt")
    deck_text = deck_path.read_text(encoding="utf-8") if deck_path.is_file() else None
    qr_input: dict[str, object] | None = None
    qr_error: str | None = None
    qr_deck = result.deck if result.accepted else result.draft_deck
    qr_is_draft = not result.accepted and result.draft_deck is not None
    if qr_deck is not None:
        try:
            qr_input = build_qr_input(
                qr_deck,
                runtime.database,
                allow_incomplete=qr_is_draft,
            ).to_dict()
        except QrInputError as exc:
            qr_error = str(exc)
    validation = report.get("validation")
    validation_dict = validation if isinstance(validation, dict) else {}
    cards = report.get("cards")
    card_items = cards if isinstance(cards, list) else []
    return {
        "accepted": result.accepted,
        "errors": list(result.errors),
        "detected_style": result.detection.style,
        "style_confidence": result.detection.style_confidence,
        "card_count": validation_dict.get("card_count", 0),
        "cards": [_card_summary(item) for item in card_items if isinstance(item, dict)],
        "deck_text": deck_text,
        "qr_input": qr_input,
        "qr_error": qr_error,
        "qr_is_draft": qr_is_draft,
        "uncertain_entity_count": validation_dict.get("uncertain_entity_count", 0),
        "missing_card_count": validation_dict.get("missing_card_count", 0),
        "artifacts": artifacts,
        "output_dir": str(config.output_dir),
    }


def create_server(config: GuiConfig) -> GuiServer:
    """Create a local GUI server without starting its request loop."""

    return GuiServer(config)


def run_gui(config: GuiConfig, *, open_browser: bool = True) -> None:
    """Serve the local GUI until interrupted."""

    server = create_server(config)
    raw_host, port = server.server_address[:2]
    host = raw_host.decode() if isinstance(raw_host, bytes) else raw_host
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{display_host}:{port}/"
    if open_browser:
        threading.Timer(0.25, webbrowser.open, args=(url,), kwargs={"new": 2}).start()
    print(f"PTCGP Deck Reader GUI: {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - interactive shutdown
        pass
    finally:
        server.server_close()


def _read_static_asset(name: str) -> bytes:
    return (
        files("ptcgp_deck2qr").joinpath("webgui").joinpath(*PurePosixPath(name).parts).read_bytes()
    )


def _static_image_name(route: str) -> str | None:
    path = PurePosixPath(route.removeprefix("/"))
    if len(path.parts) != 2 or path.parts[0] != "assets" or path.suffix != ".png":
        return None
    if any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.as_posix()


def _decode_image(payload: Mapping[str, Any]) -> tuple[str, bytes]:
    filename = payload.get("filename")
    encoded = payload.get("image_base64")
    if not isinstance(filename, str) or not filename.strip():
        raise GuiRequestError("image filename is required")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise GuiRequestError("image must be PNG, JPEG, or WebP")
    if not isinstance(encoded, str) or not encoded:
        raise GuiRequestError("image data is required")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GuiRequestError("image data is not valid base64") from exc
    if not image_bytes:
        raise GuiRequestError("image is empty")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise GuiRequestError("image exceeds the 24 MB limit", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    return Path(filename).name, image_bytes


def _decode_energies(payload: Mapping[str, Any]) -> tuple[str, ...]:
    value = payload.get("energies")
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise GuiRequestError("select one to three energy types")
    energies = tuple(cast(str, item).strip().lower() for item in value)
    if not 1 <= len(energies) <= 3 or len(set(energies)) != len(energies):
        raise GuiRequestError("select one to three unique energy types")
    unknown = set(energies) - ALLOWED_ENERGIES
    if unknown:
        raise GuiRequestError(f"unknown energy: {', '.join(sorted(unknown))}")
    return energies


def _decode_style(payload: Mapping[str, Any]) -> StyleName:
    value = payload.get("style", "auto")
    if not isinstance(value, str) or value not in ALLOWED_STYLES:
        raise GuiRequestError("unknown screenshot style")
    return value


def _card_summary(item: Mapping[str, Any]) -> dict[str, object]:
    return {
        "slot_id": item.get("slot_id"),
        "count": item.get("count"),
        "decision": item.get("decision"),
        "selected_print": item.get("selected_print"),
        "visual_score": item.get("visual_score"),
        "entity_margin": item.get("entity_margin"),
    }


__all__ = [
    "GuiConfig",
    "GuiRequestError",
    "create_server",
    "recognize_payload",
    "run_gui",
]

"""Screenshot Capture — capture screenshots via Playwright with element selection,
viewport configs, and device emulation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import sync_playwright, Browser, Page  # type: ignore[import-untyped]
except ImportError:
    sync_playwright = None  # type: ignore[assignment]
    Browser = None  # type: ignore[assignment,misc]
    Page = None  # type: ignore[assignment,misc]


# ---- Data classes --------------------------------------------------------


@dataclass(frozen=True)
class ViewportConfig:
    """Viewport dimensions and device scale."""

    width: int = 1280
    height: int = 720
    device_scale_factor: float = 1.0


@dataclass(frozen=True)
class DeviceProfile:
    """Named device emulation profile."""

    name: str
    viewport: ViewportConfig
    user_agent: str = ""
    is_mobile: bool = False
    has_touch: bool = False


@dataclass(frozen=True)
class CaptureOptions:
    """Options controlling a single screenshot capture."""

    url: str = ""
    selector: str = ""
    viewport: ViewportConfig = field(default_factory=ViewportConfig)
    device: DeviceProfile | None = None
    full_page: bool = False
    timeout_ms: int = 30_000
    wait_for_selector: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CaptureResult:
    """Result of a screenshot capture."""

    url: str
    image_bytes: bytes
    width: int
    height: int
    sha256: str
    selector: str = ""
    device_name: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.error == ""


# ---- Built-in device profiles --------------------------------------------

BUILTIN_DEVICES: dict[str, DeviceProfile] = {
    "iphone-14": DeviceProfile(
        name="iphone-14",
        viewport=ViewportConfig(width=390, height=844, device_scale_factor=3.0),
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
        is_mobile=True,
        has_touch=True,
    ),
    "ipad-pro": DeviceProfile(
        name="ipad-pro",
        viewport=ViewportConfig(width=1024, height=1366, device_scale_factor=2.0),
        user_agent="Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X)",
        is_mobile=True,
        has_touch=True,
    ),
    "desktop-hd": DeviceProfile(
        name="desktop-hd",
        viewport=ViewportConfig(width=1920, height=1080, device_scale_factor=1.0),
    ),
    "desktop-4k": DeviceProfile(
        name="desktop-4k",
        viewport=ViewportConfig(width=3840, height=2160, device_scale_factor=2.0),
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---- ScreenshotCapture ---------------------------------------------------


class ScreenshotCapture:
    """Capture screenshots via Playwright (or dry-run if unavailable)."""

    def __init__(self, output_dir: str | Path = ".lidco/screenshots") -> None:
        self._output_dir = Path(output_dir)
        self._devices: dict[str, DeviceProfile] = dict(BUILTIN_DEVICES)

    # -- public API --------------------------------------------------------

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    @property
    def devices(self) -> dict[str, DeviceProfile]:
        return dict(self._devices)

    def register_device(self, profile: DeviceProfile) -> None:
        """Register a custom device profile (immutable copy stored)."""
        self._devices = {**self._devices, profile.name: profile}

    def capture(self, options: CaptureOptions) -> CaptureResult:
        """Capture a screenshot. Returns CaptureResult with image bytes or error."""
        if sync_playwright is None:
            return self._dry_run(options)
        return self._capture_live(options)

    def capture_multi(
        self, url: str, *, viewports: list[ViewportConfig] | None = None,
        device_names: list[str] | None = None, selector: str = "",
        full_page: bool = False,
    ) -> list[CaptureResult]:
        """Capture a URL across multiple viewports / devices."""
        results: list[CaptureResult] = []
        for vp in (viewports or []):
            opts = CaptureOptions(url=url, viewport=vp, selector=selector, full_page=full_page)
            results = [*results, self.capture(opts)]
        for dname in (device_names or []):
            device = self._devices.get(dname)
            if device is None:
                results = [*results, CaptureResult(
                    url=url, image_bytes=b"", width=0, height=0,
                    sha256="", device_name=dname,
                    error=f"Unknown device '{dname}'",
                )]
                continue
            opts = CaptureOptions(url=url, device=device, selector=selector, full_page=full_page)
            results = [*results, self.capture(opts)]
        return results

    def save(self, result: CaptureResult, name: str) -> Path:
        """Persist a capture result to disk. Returns the path written."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / f"{name}.png"
        path.write_bytes(result.image_bytes)
        meta_path = self._output_dir / f"{name}.json"
        meta = {
            "url": result.url,
            "width": result.width,
            "height": result.height,
            "sha256": result.sha256,
            "selector": result.selector,
            "device_name": result.device_name,
        }
        meta_path.write_text(json.dumps(meta, indent=2))
        return path

    def list_devices(self) -> list[str]:
        """Return sorted list of known device profile names."""
        return sorted(self._devices)

    # -- private -----------------------------------------------------------

    def _dry_run(self, options: CaptureOptions) -> CaptureResult:
        vp = options.device.viewport if options.device else options.viewport
        fake = b"PLACEHOLDER_PNG"
        return CaptureResult(
            url=options.url,
            image_bytes=fake,
            width=vp.width,
            height=vp.height,
            sha256=_sha256(fake),
            selector=options.selector,
            device_name=options.device.name if options.device else "",
        )

    def _capture_live(self, options: CaptureOptions) -> CaptureResult:
        """Capture with real Playwright. Callers should have Playwright installed."""
        try:
            with sync_playwright() as pw:
                vp = options.device.viewport if options.device else options.viewport
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context(
                    viewport={"width": vp.width, "height": vp.height},
                    device_scale_factor=vp.device_scale_factor,
                    user_agent=options.device.user_agent if options.device else "",
                    is_mobile=options.device.is_mobile if options.device else False,
                    has_touch=options.device.has_touch if options.device else False,
                    extra_http_headers=options.extra_headers or {},
                )
                page = ctx.new_page()
                page.goto(options.url, timeout=options.timeout_ms)
                if options.wait_for_selector:
                    page.wait_for_selector(options.wait_for_selector, timeout=options.timeout_ms)

                if options.selector:
                    elem = page.query_selector(options.selector)
                    if elem is None:
                        browser.close()
                        return CaptureResult(
                            url=options.url, image_bytes=b"", width=vp.width,
                            height=vp.height, sha256="", selector=options.selector,
                            error=f"Selector '{options.selector}' not found",
                        )
                    img = elem.screenshot()
                else:
                    img = page.screenshot(full_page=options.full_page)

                browser.close()
                return CaptureResult(
                    url=options.url, image_bytes=img, width=vp.width,
                    height=vp.height, sha256=_sha256(img),
                    selector=options.selector,
                    device_name=options.device.name if options.device else "",
                )
        except Exception as exc:  # noqa: BLE001
            vp = options.device.viewport if options.device else options.viewport
            return CaptureResult(
                url=options.url, image_bytes=b"", width=vp.width,
                height=vp.height, sha256="", selector=options.selector,
                error=str(exc),
            )

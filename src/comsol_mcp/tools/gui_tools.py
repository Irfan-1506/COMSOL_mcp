"""Windows COMSOL Desktop GUI & Live Model1 sync profile (`gui`)."""

from __future__ import annotations

from typing import Any, Optional

from ..backends import BackendHub


def register_gui_tools(mcp: Any, hub: BackendHub) -> None:
    @mcp.tool()
    def gui_status() -> dict[str, Any]:
        """Inspect Windows COMSOL Desktop availability, processes, open windows, and optional GUI dependencies."""
        return hub.gui.diagnose()

    @mcp.tool()
    def gui_open_model(model_path: Optional[str] = None, launch_server_port: Optional[int] = None) -> dict[str, Any]:
        """Launch COMSOL Desktop on Windows, optionally opening an `.mph` file or binding a live server port."""
        return hub.gui.open_model(model_path=model_path, launch_server_port=launch_server_port)

    @mcp.tool()
    def gui_capture_window(output_path: Optional[str] = None, region: str = "full") -> dict[str, Any]:
        """Capture a PNG screenshot of the COMSOL Desktop window (`region='full'` or `'graphics'`)."""
        return hub.gui.capture_window(output_path=output_path, region=region)

    @mcp.tool()
    def gui_execute_java_shell(code: str, allow_non_model_code: bool = False) -> dict[str, Any]:
        """Execute `model.` COMSOL Java statements in the Desktop Java Shell (restricted to `model.` by default)."""
        return hub.gui.execute_java_shell(code=code, allow_non_model_code=allow_non_model_code)

    @mcp.tool()
    def gui_sync_mph_to_desktop(model_name: Optional[str] = None) -> dict[str, Any]:
        """Save the active interactive model to a versioned `.mph` file and open it in COMSOL Desktop."""
        saved = hub.interactive.model_save(model_name=model_name, versioned=True, tag="gui_sync")
        opened = hub.gui.open_model(model_path=saved["path"])
        return {"ok": True, "saved": saved, "desktop": opened}

    @mcp.tool()
    def gui_attach_live_model(
        host: str = "localhost",
        port: int = 2036,
        desktop_model: str = "Model1",
        show_progress: bool = True,
        show_plots: bool = True,
    ) -> dict[str, Any]:
        """Attach the `mph` backend directly to COMSOL Desktop's live `Model1` via COMSOL Server so edits appear in real time."""
        return hub.mph.connect(
            host=host,
            port=port,
            attach_desktop_model=desktop_model,
            show_progress=show_progress,
            show_plots=show_plots,
        )

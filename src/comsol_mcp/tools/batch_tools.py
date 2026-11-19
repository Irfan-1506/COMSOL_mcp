"""Native COMSOL CLI batch job queue profile (`batch`): isolated comsolcompile + comsolbatch."""

from __future__ import annotations

from typing import Any, Optional

from ..backends import BackendHub
from ..backends.base import java_string


def register_batch_tools(mcp: Any, hub: BackendHub) -> None:
    @mcp.tool()
    def batch_status() -> dict[str, Any]:
        """Check native COMSOL CLI (`comsolcompile`/`comsolbatch`) availability, workspace, and active queue."""
        return hub.batch.status()

    @mcp.tool()
    def batch_list_models() -> list[dict[str, Any]]:
        """List saved `.mph` model files inside the batch workspace."""
        return hub.batch.list_models()

    @mcp.tool()
    def batch_get_template(name: str = "block") -> dict[str, Any]:
        """Retrieve a ready-to-run COMSOL Java body template (`block`, `heat_transfer`, `inspect`, `export_java`)."""
        return hub.batch.get_template(name=name)

    @mcp.tool()
    def batch_create_model(java_body: str, output_file: str, timeout_seconds: int = 600) -> dict[str, Any]:
        """Compile and run Java statements acting on `Model model` in an isolated batch job; returns a job ID."""
        return hub.batch.submit(java_body, output_file, input_file=None, timeout_seconds=timeout_seconds)

    @mcp.tool()
    def batch_edit_model(
        input_file: str,
        output_file: str,
        java_body: str,
        timeout_seconds: int = 600,
    ) -> dict[str, Any]:
        """Load an existing workspace `.mph`, apply Java API statements, and save to a new non-destructive copy."""
        return hub.batch.submit(java_body, output_file, input_file=input_file, timeout_seconds=timeout_seconds)

    @mcp.tool()
    def batch_set_parameters(
        input_file: str,
        output_file: str,
        parameters: dict[str, str],
        rebuild_geometry: bool = True,
        study: Optional[str] = None,
        timeout_seconds: int = 600,
    ) -> dict[str, Any]:
        """Modify parameter expressions via native batch job, optionally rebuilding geometries and solving a study."""
        lines = [f"model.param().set({java_string(k)}, {java_string(v)});" for k, v in parameters.items()]
        if rebuild_geometry:
            lines.append(
                'for (String c : model.component().tags()) { '
                'for (String g : model.component(c).geom().tags()) { '
                'model.component(c).geom(g).run(); } }'
            )
        if study:
            lines.append(f"model.study({java_string(study)}).run();")
        return hub.batch.submit("\n".join(lines), output_file, input_file=input_file, timeout_seconds=timeout_seconds)

    @mcp.tool()
    def batch_solve_model(
        input_file: str,
        output_file: str,
        study: str = "std1",
        timeout_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Run a named study in an isolated COMSOL batch subprocess and save to a new `.mph` copy."""
        return hub.batch.submit(
            f"model.study({java_string(study)}).run();",
            output_file,
            input_file=input_file,
            timeout_seconds=timeout_seconds,
        )

    @mcp.tool()
    def batch_job_status(job_id: str, tail_characters: int = 12000) -> dict[str, Any]:
        """Poll a batch job's state (`queued`, `compiling`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`) and log tails."""
        return hub.batch.job_status(job_id=job_id, tail_characters=tail_characters)

    @mcp.tool()
    def batch_read_artifact(
        job_id: str,
        filename: str,
        offset: int = 0,
        limit: int = 16000,
    ) -> dict[str, Any]:
        """Read generated Java, logs, JSON, or CSV text artifacts from a batch job directory in pages."""
        return hub.batch.read_artifact(job_id=job_id, filename=filename, offset=offset, limit=limit)

    @mcp.tool()
    def batch_cancel_job(job_id: str) -> dict[str, Any]:
        """Cancel a queued or running batch job and terminate its entire OS process tree."""
        return hub.batch.cancel_job(job_id=job_id)

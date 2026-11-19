"""Tests for guided workflows, bilingual modeling assistant, GUI safety policy, embedded docs, and RAG status."""

from __future__ import annotations

from pathlib import Path
import pytest

from comsol_mcp.backends.gui_backend import GuiBackend
from comsol_mcp.config import Settings
from comsol_mcp.knowledge import RagKnowledgeBase, get_doc, list_docs, troubleshoot
from comsol_mcp.validation import WorkflowManager, analyze_modeling_request


def test_workflow_and_bilingual_modeling_assistant() -> None:
    wf = WorkflowManager()
    tpls = wf.list_templates()
    assert "heat_transfer" in tpls["templates"]

    s0 = wf.start("heat_transfer", goal="2D chip heat dissipation")
    assert s0["active"] is True
    assert s0["current_step"]["id"] == "parameters"

    s1 = wf.advance()
    assert s1["current_step"]["id"] == "geometry"
    assert "parameters" in s1["completed_steps"]

    en = analyze_modeling_request("Simulate laminar fluid flow and heat transfer in a microfluidic channel")
    assert en["is_multiphysics"] is True
    assert "multiphysics_add" in en["recommended_tools"]

    zh = analyze_modeling_request("我要建立一个锂离子电池电化学仿真模型")
    assert zh["recommended_template"] == "electrochemistry"


def test_gui_java_shell_safety_policy(tmp_settings: Settings) -> None:
    gui = GuiBackend(tmp_settings)
    gui.validate_java_shell_code('model.param().set("L", "10[mm]");\nmodel.geom("geom1").run();')
    with pytest.raises(ValueError, match="rejected by Java Shell safety policy"):
        gui.validate_java_shell_code('Runtime.getRuntime().exec("calc.exe");')
    # Explicit override allowed
    gui.validate_java_shell_code('Runtime.getRuntime().exec("calc.exe");', allow_non_model_code=True)


def test_embedded_docs_troubleshoot_and_rag_status(tmp_settings: Settings) -> None:
    topics = list_docs()
    assert "workflow" in topics and "bc_properties" in topics
    doc = get_doc("mph_vs_batch")
    assert "comsolbatch" in doc["content"]

    diag = troubleshoot("COMSOL solver failed with zero pivot singular matrix")
    assert any("Ground" in s or "reference" in s for s in diag["suggestions"])

    rag = RagKnowledgeBase(tmp_settings)
    st = rag.status()
    assert st["pdf_count"] == 0
    assert st["ready_to_search"] is False

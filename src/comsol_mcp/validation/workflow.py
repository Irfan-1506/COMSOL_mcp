"""Stateful guided multiphysics workflow templates and bilingual modeling assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

WORKFLOW_STEPS: list[dict[str, Any]] = [
    {"id": "parameters", "title": "Define Parameters", "tools": ["param_set"]},
    {"id": "geometry", "title": "Build Geometry", "tools": ["geometry_add", "geometry_build"]},
    {"id": "selections", "title": "Create Selections", "tools": ["selection_create"]},
    {"id": "materials", "title": "Assign Materials", "tools": ["material_add"]},
    {"id": "physics", "title": "Add Physics & Boundaries", "tools": ["physics_add", "physics_feature_add"]},
    {"id": "validate", "title": "Pre-Solve Validation", "tools": ["model_validate_all"]},
    {"id": "mesh", "title": "Generate Mesh", "tools": ["mesh_build"]},
    {"id": "study", "title": "Create & Run Study", "tools": ["study_create", "study_solve"]},
    {"id": "results", "title": "Evaluate & Export Results", "tools": ["results_evaluate", "results_export"]},
    {"id": "save", "title": "Save Versioned Model", "tools": ["model_save"]},
]

WORKFLOW_TEMPLATES: dict[str, dict[str, Any]] = {
    "general": {
        "description": "General-purpose multiphysics simulation workflow.",
        "recommended_physics": [],
        "recommended_expressions": [],
    },
    "heat_transfer": {
        "description": "Steady or transient thermal conduction / convection simulation.",
        "recommended_physics": ["HeatTransfer"],
        "recommended_expressions": ["T", "ht.qx", "ht.qmag"],
    },
    "electrostatics": {
        "description": "Electric potential, field intensity, and capacitance extraction.",
        "recommended_physics": ["Electrostatics"],
        "recommended_expressions": ["V", "es.normE", "es.intWe"],
    },
    "fluid_flow": {
        "description": "Incompressible laminar flow velocity and pressure drop.",
        "recommended_physics": ["LaminarFlow"],
        "recommended_expressions": ["spf.U", "p"],
    },
    "solid_mechanics": {
        "description": "Structural displacement and von Mises stress analysis.",
        "recommended_physics": ["SolidMechanics"],
        "recommended_expressions": ["solid.disp", "solid.mises"],
    },
    "electrochemistry": {
        "description": "Battery cell / secondary or tertiary current distribution modeling.",
        "recommended_physics": ["LithiumIonBatteryMPH", "SecondaryCurrentDistribution"],
        "recommended_expressions": ["liion.phis", "liion.phil", "liion.cl"],
    },
}

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "heat_transfer": ("heat", "thermal", "temperature", "convection", "conduction", "flux", "传热", "温度", "热流", "散热"),
    "electrostatics": ("electrostatic", "voltage", "capacitor", "capacitance", "electric field", "ground", "静电", "电容", "电场", "电势"),
    "fluid_flow": ("fluid", "flow", "laminar", "navier", "cfd", "inlet", "outlet", "channel", "microfluidic", "流体", "层流", "流场", "微流控"),
    "solid_mechanics": ("stress", "strain", "structural", "solid", "displacement", "beam", "von mises", "力学", "应力", "应变", "结构"),
    "electrochemistry": ("battery", "lithium", "electrode", "electrolyte", "corrosion", "fuel cell", "electrochem", "电池", "锂离子", "电化学", "腐蚀"),
}


def analyze_modeling_request(question: str) -> dict[str, Any]:
    """Classify a natural-language modeling request (EN/ZH) into template, physics, and tools."""
    q = question.lower()
    scores: dict[str, int] = {}
    for domain, kws in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in q)
        if score > 0:
            scores[domain] = score
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    primary = ranked[0][0] if ranked else "general"
    tpl = WORKFLOW_TEMPLATES[primary]
    coupled = len(ranked) >= 2
    recommended_tools = [
        "workflow_start",
        "catalog_search",
        "geometry_add",
        "material_add",
        "physics_add",
        "physics_feature_add",
        "model_validate_all",
        "mesh_build",
        "study_create",
        "study_solve",
        "results_evaluate",
    ]
    if primary == "electrochemistry":
        recommended_tools.insert(4, "electrochemistry_add")
    if coupled:
        recommended_tools.insert(6, "multiphysics_add")
    return {
        "question": question,
        "recommended_template": primary,
        "detected_domains": [d for d, _ in ranked] or ["general"],
        "is_multiphysics": coupled,
        "recommended_physics": tpl["recommended_physics"],
        "recommended_expressions": tpl["recommended_expressions"],
        "recommended_tools": recommended_tools,
    }


@dataclass
class ActiveWorkflow:
    template: str
    goal: str
    step_index: int = 0
    completed_steps: list[str] = field(default_factory=list)


class WorkflowManager:
    """In-memory step tracker for guided modeling sessions."""

    def __init__(self) -> None:
        self.active: Optional[ActiveWorkflow] = None

    def list_templates(self) -> dict[str, Any]:
        return {
            "templates": WORKFLOW_TEMPLATES,
            "steps": [s["id"] for s in WORKFLOW_STEPS],
        }

    def start(self, template: str = "general", goal: str = "") -> dict[str, Any]:
        key = template.strip().lower()
        if key not in WORKFLOW_TEMPLATES:
            raise ValueError(f"Unknown template '{template}'. Choose from: {sorted(WORKFLOW_TEMPLATES.keys())}")
        self.active = ActiveWorkflow(template=key, goal=goal)
        return self.current_step()

    def current_step(self) -> dict[str, Any]:
        if self.active is None:
            return {"active": False, "message": "No active workflow. Call `workflow_start` first."}
        done = self.active.step_index >= len(WORKFLOW_STEPS)
        step = None if done else WORKFLOW_STEPS[self.active.step_index]
        return {
            "active": not done,
            "completed": done,
            "template": self.active.template,
            "goal": self.active.goal,
            "step_index": self.active.step_index,
            "total_steps": len(WORKFLOW_STEPS),
            "current_step": step,
            "completed_steps": list(self.active.completed_steps),
            "template_info": WORKFLOW_TEMPLATES[self.active.template],
        }

    def advance(self) -> dict[str, Any]:
        if self.active is None:
            raise ValueError("No active workflow. Call `workflow_start` first.")
        if self.active.step_index < len(WORKFLOW_STEPS):
            step_id = WORKFLOW_STEPS[self.active.step_index]["id"]
            if step_id not in self.active.completed_steps:
                self.active.completed_steps.append(step_id)
            self.active.step_index += 1
        return self.current_step()

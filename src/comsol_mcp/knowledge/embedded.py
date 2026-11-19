"""Built-in offline COMSOL guides and troubleshooting playbooks."""

from __future__ import annotations

from typing import Any

DOC_TOPICS: dict[str, str] = {
    "workflow": """# Standard COMSOL Modeling Workflow
1. Define parameters (`param_set`) with explicit SI units in brackets, e.g. `20[mm]`, `293.15[K]`.
2. Create component & geometry (`geometry_add`), then build (`geometry_build`).
3. Create named selections (`selection_create`) for critical boundaries before adding physics.
4. Assign materials (`material_add`) with all properties required by your physics.
5. Add physics interfaces (`physics_add`) and boundary/domain conditions (`physics_feature_add`).
6. Validate setup (`model_validate_all`), generate mesh (`mesh_build`), create & run study (`study_create`, `study_solve`).
7. Evaluate results (`results_evaluate`), export plots/data (`results_export`), and save a versioned `.mph` (`model_save` with `versioned=True`).""",
    "mph_vs_batch": """# Choosing Between Warm `mph` vs Native `batch` Backends
- **Use `core` (`mph`)** for rapid iterative modeling, inspection, parameter tweaks, and plotting inside a single warm JVM (fast per-step latency).
- **Use `batch` (`comsolcompile` + `comsolbatch`)** when you need full arbitrary COMSOL Java API access, hard OS process-tree timeouts/cancellation, non-destructive copy-on-edit `.mph` files, or zero `mph`/JPype setup.
- **Use `gui` (Windows)** when you need screenshots from COMSOL Desktop, Java Shell execution, or live `Model1` visualization.""",
    "bc_properties": """# Common COMSOL Boundary Condition Property Names
- Heat Transfer (`HeatTransfer`): `TemperatureBoundary` (`T0`), `HeatFluxBoundary` (`q0`, `h`, `Text`), `HeatSource` (`Q0`).
- Electrostatics (`Electrostatics`): `ElectricPotential` (`V0`), `Ground` (none), `Terminal` (`V0`, `Q0`, `TerminalType`).
- Laminar Flow (`LaminarFlow`): `InletBoundary` (`U0in` / `U0`), `OutletBoundary` (`p0`), `Wall`.
- Solid Mechanics (`SolidMechanics`): `Fixed`, `BoundaryLoad` (`FperArea`), `PrescribedDisplacement` (`u0`).
- Pressure Acoustics (`PressureAcoustics`): `SoundHard`, `SoundSoft`, `Pressure` (`p0`), `Impedance` (`Zn`), `NormalVelocity` (`nvel`), `PlaneWaveRadiation`.
- PDE (`CoefficientFormPDE` / `GeneralFormPDE` / `WeakFormPDE`): `DirichletBoundary` (`r`), `FluxBoundary` (`g`, `q`), `ZeroFluxBoundary`, `WeakContribution` (`weak`).""",
    "electrochemistry": """# Electrochemistry Modeling Checklist (Battery / Corrosion / Current Distribution)
1. Pick the right interface: `LithiumIonBatteryMPH` (porous 3D/1D P2D), `LumpedBattery` (thermal-EC equivalent circuit), `SecondaryCurrentDistribution` (Butler-Volmer), or `TertiaryCurrentDistributionNernstPlanck` (concentration-dependent).
2. Always include one reference potential (`ElectricGround` or fixed `ElectrodePotential`) to prevent a singular matrix.
3. Verify property names via `catalog_get_properties` before setting parameters.
4. For 1C discharge curves, pair a `TimeDependent` study with a Stop Condition on cell voltage.""",
    "best_practices": """# Engineering Best Practices
- Always attach explicit units (`10[W/(m*K)]`, `1[mm/s]`) to every parameter and property.
- Never overwrite known-good `.mph` files; use `versioned=True` in `model_save` or new output filenames in `batch` tools.
- Remember COMSOL `comsolbatch.exe` can return exit code 0 after a Java exception — always verify logs/markers (handled automatically by `batch_*` tools).
- Perform a mesh refinement check before trusting peak field values.""",
}

_TROUBLESHOOTING_RULES: list[tuple[tuple[str, ...], str]] = [
    (
        ("platform architecture", "win64", "discovery", "find_backends"),
        "MPh could not match your Python architecture to COMSOL. Verify you are running 64-bit native Windows Python (not MSYS/WSL/32-bit) and that `COMSOL_HOME` points to `.../Multiphysics`.",
    ),
    (
        ("singular", "zero pivot", "ill-conditioned", "underconstrained"),
        "Singular matrix / zero pivot usually means a missing reference boundary condition (e.g., missing `Ground` in Electrostatics, missing `Fixed` constraint in Solid Mechanics, or missing reference pressure `OutletBoundary` in Laminar Flow). Run `model_validate_all` to check.",
    ),
    (
        ("not converge", "convergence", "nonlinear", "nan", "diverged"),
        "Solver non-convergence: check units on parameters/sources, refine mesh near sharp gradients or boundary layers, ramp loads/sources with an auxiliary sweep, or switch from segregated to fully coupled solver.",
    ),
    (
        ("filepermission", "security", "access denied", "external file"),
        "COMSOL blocks filesystem I/O from batch/Java by default unless `security.external.filepermission=full` is set in an isolated `-prefsdir`. The `batch` backend configures this automatically per job.",
    ),
    (
        ("max_path", "path too long", "recovery"),
        "Deep Windows workspace paths trigger solver recovery-file errors. Keep `COMSOL_MCP_WORKSPACE` short; the `batch` backend already routes `-tmpdir` and `-recoverydir` to a short OS temporary folder.",
    ),
    (
        ("jpype", "jvm", "deadlock", "hang"),
        "MPh INFO logging can deadlock JPype during JVM startup on Windows + COMSOL 6.x. This server silences `mph` logger to WARNING automatically; if a JVM locks up, restart the MCP server or use the isolated `batch` backend.",
    ),
]


def list_docs() -> list[str]:
    return sorted(DOC_TOPICS.keys())


def get_doc(topic: str) -> dict[str, Any]:
    key = topic.strip().lower()
    if key not in DOC_TOPICS:
        raise ValueError(f"Unknown topic '{topic}'. Available topics: {list_docs()}")
    return {"topic": key, "content": DOC_TOPICS[key]}


def troubleshoot(symptom: str) -> dict[str, Any]:
    s = symptom.lower()
    matches = [advice for keywords, advice in _TROUBLESHOOTING_RULES if any(k in s for k in keywords)]
    if not matches:
        matches = [
            "No exact heuristic match. Run `model_validate_all` (for mph/dryrun models) or inspect `compile.log` / `batch.log` via `batch_job_status` / `batch_read_artifact`."
        ]
    return {"symptom": symptom, "suggestions": matches}

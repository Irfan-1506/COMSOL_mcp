# Verification record

Verified on November 16, 2026, using Windows, Python 3.12, MCP Python SDK 2.3.0 and COMSOL Multiphysics 6.2 Build 290.

## Real COMSOL integration: PASS

The test client communicated with the server over actual local stdio MCP transport.

1. Discovered all 10 tools and queried installation/workspace status.
2. Created a native 3D block model with editable parameters, geometry features and tetrahedral mesh.
3. Reloaded the model, changed length from 20 mm to 35 mm, rebuilt geometry and saved a separate MPH.
4. Confirmed the original MPH's SHA-256 remained unchanged.
5. Reopened the edited MPH, asserted its length expression, inspected feature types and exported its editable Java representation.
6. Created and solved the 2D heat-transfer example, retaining materials, physics, mesh, stationary study and plot configuration in MPH.
7. Reopened the saved solution and evaluated maximum temperature: **293.886628674844 K**, above the fixed 293.15 K boundary temperature.
8. Rejected workspace path traversal and overwriting existing output files.
9. Submitted deliberately invalid COMSOL operations and confirmed a failed job without publishing the partial model.

The temperature check is a regression sanity check, not proof of engineering accuracy. No mesh-convergence study was performed.

## Host controls: 4 tests passed

- Workspace path confinement.
- Actual child-process termination on timeout.
- Queued cancellation prevents process launch.
- Packaged stdio server starts and exposes tools.

The isolated Python environment also passed `pip check`.

## Issues found and corrected during verification

- COMSOL's default Java file-access restrictions prevented native save/load. Each job now receives an isolated preferences file allowing filesystem access for trusted model code.
- COMSOL may exit zero after a Java/model error. A unique success marker and nonempty saved MPH are both required before publication.
- Deep Windows workspace paths caused native solver recovery-file errors. Solver temporary/recovery storage now uses a short operating-system temporary directory.

## Scope

Other operating systems, COMSOL versions, physics modules and multi-client deployments were not verified. Cancellation and timeout process behavior were tested with a real Python child process; an active COMSOL solve was not deliberately interrupted. No COMSOL Desktop GUI actions were automated. Model editability was verified through native save/reload, parameter checks, feature inspection and Java export.

Reproduce with `tests/test_controls.py` and `tests/verify_mcp.py` as described in the README. Local integration runs generate detailed `verification.json` and per-job logs; these contain machine paths and are intentionally excluded from the repository.

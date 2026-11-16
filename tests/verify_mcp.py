"""Real stdio + COMSOL integration verification. Uses a fresh test folder per run."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

from mcp import Client, StdioServerParameters

BASE = Path(__file__).resolve().parents[1]


async def main():
    folder = "verification_" + uuid.uuid4().hex[:8]
    report = {"folder": folder, "checks": [], "jobs": []}
    async with Client(StdioServerParameters(command=sys.executable, args=[str(BASE / "server.py")])) as client:
        async def call(tool_name, **arguments):
            result = await client.call_tool(tool_name, arguments)
            if result.is_error:
                raise AssertionError(str(result.content))
            return result.structured_content or json.loads(result.content[0].text)

        async def wait(job):
            report["jobs"].append(job["id"])
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                state = await call("job_status", job_id=job["id"])
                if state["state"] in {"succeeded", "failed", "cancelled", "interrupted"}:
                    assert state["state"] == "succeeded", json.dumps(state, indent=2)
                    return state
                await asyncio.sleep(2)
            await call("cancel_job", job_id=job["id"])
            raise TimeoutError(job["id"])

        tools = await client.list_tools()
        report["tools"] = [tool.name for tool in tools.tools]
        report["status"] = await call("comsol_status")
        report["checks"].append("stdio connection and tool discovery")
        block = await call("get_template", name="block")
        original = await wait(await call("create_model", java_body=block["java_body"], output_file=f"{folder}/block.mph"))
        original_hash = hashlib.sha256(Path(original["output"]).read_bytes()).hexdigest()
        report["checks"].append("native 3D block creation and mesh")
        edited = await wait(await call("set_parameters", input_file=f"{folder}/block.mph",
                                       output_file=f"{folder}/block_edited.mph", parameters={"L": "35[mm]"}))
        assert hashlib.sha256(Path(original["output"]).read_bytes()).hexdigest() == original_hash
        inspect = await call("get_template", name="inspect")
        export = await call("get_template", name="export_java")
        checked = await wait(await call("edit_model", input_file=f"{folder}/block_edited.mph",
                                        output_file=f"{folder}/block_verified.mph",
                                        java_body=inspect["java_body"] + '\nif (!model.param().get("L").equals("35[mm]")) throw new RuntimeException("Wrong L");\n' + export["java_body"]))
        text = await call("read_job_artifact", job_id=checked["id"], filename="ExportedModel.java")
        assert "35[mm]" in text["text"] and '"Block"' in text["text"]
        report["checks"].append("load, edit L, rebuild, reopen, verify feature tree and export Java; original unchanged")
        heat = await call("get_template", name="heat_transfer")
        heat_result = await wait(await call("create_model", java_body=heat["java_body"], output_file=f"{folder}/heat.mph"))
        report["checks"].append("heat-transfer geometry, material, physics, mesh, stationary solve, plot and native save")
        # Confirm saved solution survives reloading and produces temperatures above ambient.
        probe = '''model.result().numerical().create("maxcheck", "MaxSurface");
model.result().numerical("maxcheck").selection().all();
model.result().numerical("maxcheck").set("expr", "T");
double t = model.result().numerical("maxcheck").getReal()[0][0];
System.out.println("VERIFIED_MAX_T=" + t);
if (!(t > 293.15 && t < 400)) throw new RuntimeException("Unexpected temperature " + t);'''
        verified_heat = await wait(await call("edit_model", input_file=f"{folder}/heat.mph",
                                              output_file=f"{folder}/heat_verified.mph", java_body=probe))
        report["checks"].append("reopened saved solution and checked maximum temperature is above ambient")
        report["heat_logs"] = verified_heat["logs"]
        for arguments in [dict(java_body="", output_file="../outside.mph"),
                          dict(java_body="", output_file=f"{folder}/block.mph")]:
            result = await client.call_tool("create_model", arguments)
            assert result.is_error
        report["checks"].append("path traversal and overwrite rejected")
        bad = await call("create_model", java_body='model.component("missing").geom("none").run();',
                         output_file=f"{folder}/must_not_exist.mph")
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            failure = await call("job_status", job_id=bad["id"])
            if failure["state"] == "failed":
                break
            assert failure["state"] != "succeeded"
            await asyncio.sleep(2)
        assert failure["state"] == "failed"
        assert not (Path(report["status"]["workspace"]) / folder / "must_not_exist.mph").exists()
        report["checks"].append("COMSOL runtime error reported as failure, without publishing partial model")
        report["artifacts"] = {"block": original["output"], "edited_block": edited["output"], "heat": heat_result["output"]}
    report["result"] = "PASS"
    (BASE / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

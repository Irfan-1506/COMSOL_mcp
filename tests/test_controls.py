"""Host-side regression tests; no COMSOL license or mobile device needed."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid

BASE = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory(prefix="cmcp_test_")
os.environ["COMSOL_MCP_WORKSPACE"] = TEMP.name
sys.path.insert(0, str(BASE))
import server
from mcp import Client, StdioServerParameters


class Controls(unittest.TestCase):
    def test_confines_paths(self):
        for value in ("../escape.mph", ".jobs/hidden.mph", "wrong.txt"):
            with self.assertRaises(ValueError):
                server.confined(value, ".mph")

    def test_timeout_terminates_child(self):
        with self.assertRaises(TimeoutError):
            server.execute("timeout", [sys.executable, "-c", "import time; time.sleep(30)"],
                           Path(TEMP.name) / "timeout.log", time.monotonic() + 0.5)
        self.assertNotIn("timeout", server.ACTIVE)

    def test_cancelled_job_never_launches(self):
        job_id = uuid.uuid4().hex
        directory = server.JOBS / job_id
        directory.mkdir()
        server.update(directory, id=job_id, state="queued")
        self.assertEqual(server.cancel_job(job_id)["state"], "cancelled")
        with self.assertRaisesRegex(RuntimeError, "Cancelled"):
            server.execute(job_id, ["not-an-executable"], directory / "process.log", time.monotonic() + 10)

    def test_packaged_stdio_server(self):
        async def verify():
            async with Client(StdioServerParameters(command=sys.executable, args=[str(BASE / "server.py")],
                                                    env=dict(os.environ))) as client:
                tools = await client.list_tools()
                self.assertIn("create_model", [tool.name for tool in tools.tools])
                result = await client.call_tool("comsol_status", {})
                self.assertFalse(result.is_error)
                data = result.structured_content or json.loads(result.content[0].text)
                self.assertEqual(Path(data["workspace"]), Path(TEMP.name))
        asyncio.run(verify())


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        server.shutdown()
        TEMP.cleanup()

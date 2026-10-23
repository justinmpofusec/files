import shutil
import subprocess

import pytest

from conftest import call, say
from jarvis.executor import CommandResult, Executor
from jarvis.subagents import blender
from jarvis.subagents.blender import MARKER


def tools(ctx):
    return {t.name: t for t in blender.build_tools(ctx)}


def test_run_script_builds_command_and_trims_output(make_ctx, tmp_path, monkeypatch):
    ctx = make_ctx(blender_path="/opt/blender")
    monkeypatch.setattr(blender.shutil, "which", lambda p: p)
    scripts = []

    def fake_run(args, shell=False, timeout=120):
        scripts.append(open(args[-1]).read())
        ctx.executor.calls.append(("run", args, shell))
        return CommandResult(0, stdout=f"Blender 4.0 noise\n{MARKER}\ncube made\nSaved x")

    ctx.executor.run = fake_run
    blend = tmp_path / "in.blend"
    blend.write_bytes(b"")
    out = tools(ctx)["blender_run_script"](code="print('cube made')", blend_file=str(blend),
                                           save_as=str(tmp_path / "out.blend"))
    assert out == "OK\ncube made\nSaved x"
    (_, args, _), = ctx.executor.calls
    assert args[:4] == ["/opt/blender", "--background", "--factory-startup", str(blend)]
    assert args[4:7] == ["--python-exit-code", "1", "--python"]
    assert "print('cube made')" in scripts[0] and "save_as_mainfile" in scripts[0]
    assert str(tmp_path / "out.blend") in scripts[0]


def test_missing_blender_and_missing_file(make_ctx, monkeypatch):
    ctx = make_ctx(blender_path="nope-blender")
    monkeypatch.setattr(blender.shutil, "which", lambda p: None)
    monkeypatch.setattr(blender.Path, "exists", lambda self: False)
    assert "Blender was not found" in tools(ctx)["blender_inspect"](blend_file="/x.blend")
    ctx = make_ctx(blender_path="/bin/true")
    monkeypatch.setattr(blender.shutil, "which", lambda p: p)
    assert "No such .blend file" in tools(ctx)["blender_inspect"](blend_file="/nonexistent/x.blend")


def test_failure_reported(make_ctx, monkeypatch):
    ctx = make_ctx(blender_path="b")
    monkeypatch.setattr(blender.shutil, "which", lambda p: p)
    ctx.executor.results["b"] = CommandResult(1, stdout=f"{MARKER}\nTraceback: NameError", stderr="err")
    out = tools(ctx)["blender_run_script"](code="x")
    assert out.startswith("FAILED (exit code 1)") and "NameError" in out


def test_blender_subagent_runs_tools(make_ctx, monkeypatch):
    ctx = make_ctx(blender_path="b", replies=[call("blender_run_script", code="print(1)"), say("Made it.")])
    monkeypatch.setattr(blender.shutil, "which", lambda p: p)
    agent = blender.build(ctx)
    assert agent.run("make a cube") == "Made it."
    assert ctx.confirm.asked[0][0] == "blender_run_script"  # running code asks first


needs_blender = pytest.mark.skipif(not shutil.which("blender"), reason="Blender not installed")


@needs_blender
def test_real_blender_create_inspect_render(make_ctx, tmp_path):
    """End-to-end with the real Blender binary: build a scene, save, inspect, render a PNG."""
    ctx = make_ctx(blender_path="blender")
    ctx.executor = Executor()
    t = tools(ctx)
    blend = tmp_path / "scene.blend"
    code = """
import bpy
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
mesh = bpy.data.meshes.new("CubeMesh")
import bmesh
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0); bm.to_mesh(mesh); bm.free()
cube = bpy.data.objects.new("JarvisCube", mesh)
bpy.context.scene.collection.objects.link(cube)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (6, -6, 4); cam.rotation_euler = (1.1, 0, 0.785)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
bpy.context.scene.render.resolution_x = 64
bpy.context.scene.render.resolution_y = 48
print("objects:", sorted(o.name for o in bpy.data.objects))
"""
    out = t["blender_run_script"](code=code, save_as=str(blend))
    assert out.startswith("OK"), out
    assert "objects: ['Cam', 'JarvisCube']" in out and blend.is_file()

    info = t["blender_inspect"](blend_file=str(blend))
    assert info.startswith("OK") and '"JarvisCube"' in info and '"camera": "Cam"' in info

    png = tmp_path / "render.png"
    out = t["blender_render"](blend_file=str(blend), output_png=str(png), engine="BLENDER_WORKBENCH")
    assert out.startswith("OK"), out
    assert png.read_bytes().startswith(b"\x89PNG")

    bad = t["blender_run_script"](code="raise ValueError('nope')")
    assert bad.startswith("FAILED") and "ValueError" in bad

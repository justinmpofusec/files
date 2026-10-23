"""Blender sub-agent: builds and renders 3D scenes by running Python (bpy) inside Blender headlessly."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from jarvis.agent import Agent
from jarvis.context import Context
from jarvis.tools.base import Tool, ToolRegistry, tool

PROMPT = """You are the Blender specialist inside Jarvis. You complete 3D tasks by writing Blender Python
(bpy) scripts and running them with blender_run_script, which runs Blender in background mode.
Rules:
- Work step by step: inspect existing .blend files first, then make changes, then save, then render if asked.
- Scripts run headless: never use bpy.ops that need a UI context (viewport/area operators). Prefer bpy.data
  and object-level APIs. Print anything you need to see; printed output is returned to you.
- If a script fails, read the traceback, fix the script and retry (max 3 attempts per step).
- Always save work with save_as (absolute path) unless told otherwise; tell the user where files are.
- Finish with a short summary of what you made and the output file paths."""

INSPECT_SCRIPT = """
import bpy, json
scene = bpy.context.scene
print(json.dumps({
    "file": bpy.data.filepath,
    "scene": scene.name,
    "frame_range": [scene.frame_start, scene.frame_end],
    "render_engine": scene.render.engine,
    "resolution": [scene.render.resolution_x, scene.render.resolution_y],
    "camera": scene.camera.name if scene.camera else None,
    "objects": [{"name": o.name, "type": o.type, "location": [round(v, 3) for v in o.location]}
                for o in scene.objects],
    "materials": [m.name for m in bpy.data.materials],
}, indent=1))
"""

RENDER_SCRIPT = """
import bpy
scene = bpy.context.scene
if {engine!r}:
    scene.render.engine = {engine!r}
if scene.camera is None:
    raise RuntimeError("Scene has no camera; add one before rendering.")
scene.frame_set({frame})
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = {output!r}
bpy.ops.render.render(write_still=True)
print("Rendered to", {output!r})
"""

MARKER = "=====JARVIS_OUTPUT====="


def build_tools(ctx: Context) -> list[Tool]:
    def blender_exe() -> str | None:
        configured = ctx.config.blender_path
        if ctx.config.dry_run:
            return configured
        found = shutil.which(configured)
        if found:
            return found
        for candidate in ("/Applications/Blender.app/Contents/MacOS/Blender",
                          r"C:\Program Files\Blender Foundation\Blender\blender.exe"):
            if Path(candidate).exists():
                return candidate
        return None

    def run_script(code: str, blend_file: str = "", save_as: str = "", timeout: int = 600) -> str:
        exe = blender_exe()
        if exe is None:
            return ("Blender was not found. Install it from https://www.blender.org/download/ and set "
                    "JARVIS_BLENDER to the blender executable path.")
        full = f"print({MARKER!r})\n{code}\n"
        if save_as:
            target = str(Path(save_as).expanduser().resolve())
            full += f"import bpy\nbpy.ops.wm.save_as_mainfile(filepath={target!r})\nprint('Saved', {target!r})\n"
        fd, script_path = tempfile.mkstemp(suffix=".py", prefix="jarvis_blender_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(full)
            args = [exe, "--background", "--factory-startup"]
            if blend_file:
                path = Path(blend_file).expanduser()
                if not ctx.config.dry_run and not path.is_file():
                    return f"No such .blend file: {path}"
                args.append(str(path))
            args += ["--python-exit-code", "1", "--python", script_path]
            result = ctx.executor.run(args, timeout=timeout)
        finally:
            os.unlink(script_path)
        output = result.stdout.split(MARKER, 1)[-1].strip()
        status = "OK" if result.ok else f"FAILED (exit code {result.returncode})"
        text = f"{status}\n{output[-6000:]}"
        if not result.ok and result.stderr.strip():
            text += f"\nstderr:\n{result.stderr.strip()[-3000:]}"
        return text

    @tool("Run a Blender Python (bpy) script in background Blender and return what it printed.", sensitive=True,
          code="Python code using bpy.", blend_file="Optional .blend file to open first (absolute path).",
          save_as="Optional absolute path to save the resulting .blend file.")
    def blender_run_script(code: str, blend_file: str = "", save_as: str = "") -> str:
        return run_script(code, blend_file, save_as)

    @tool("Show the objects, materials, camera and render settings of a .blend file.", read_only=True,
          blend_file="Absolute path to the .blend file.")
    def blender_inspect(blend_file: str) -> str:
        return run_script(INSPECT_SCRIPT, blend_file)

    @tool("Render one frame of a .blend file to a PNG image.", blend_file="Absolute path to the .blend file.",
          output_png="Absolute path of the PNG to write.", frame="Frame number, default 1.",
          engine="Optional render engine: BLENDER_EEVEE_NEXT, CYCLES or BLENDER_WORKBENCH.")
    def blender_render(blend_file: str, output_png: str, frame: int = 1, engine: str = "") -> str:
        output = str(Path(output_png).expanduser().resolve())
        return run_script(RENDER_SCRIPT.format(engine=engine, frame=int(frame), output=output), blend_file)

    @tool("Open a .blend file in the Blender app (with its window) for the user.",
          blend_file="Absolute path to the .blend file, or empty for a new file.")
    def blender_open_gui(blend_file: str = "") -> str:
        exe = blender_exe()
        if exe is None:
            return "Blender was not found."
        args = [exe] + ([str(Path(blend_file).expanduser())] if blend_file else [])
        result = ctx.executor.launch(args)
        return "Opened Blender." if result.ok else f"Could not open Blender: {result.stderr}"

    return [blender_run_script, blender_inspect, blender_render, blender_open_gui]


def build(ctx: Context) -> Agent:
    return Agent(name="blender", system_prompt=PROMPT, tools=ToolRegistry().add(*build_tools(ctx)), ctx=ctx)

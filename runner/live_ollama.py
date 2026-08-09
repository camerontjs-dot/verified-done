"""Live Ollama tool-loop adapter for verified-done.

Same tool contract as live_anthropic (list/read/write/run_verify/finish), so
Haiku and local coders can be compared on path honesty under one harness.

Ollama models often emit tool calls as text JSON rather than native tool_calls;
this adapter accepts both native message.tool_calls and a fenced JSON protocol.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ledger import summarize_trajectory

import importlib

if "__main__" in sys.modules and hasattr(sys.modules["__main__"], "grade_workspace"):
    _run = sys.modules["__main__"]
else:
    _run = importlib.import_module("run")

RESULTS_DIR = _run.RESULTS_DIR
REPO = _run.REPO
discover_tasks = _run.discover_tasks
grade_workspace = _run.grade_workspace
read_task = _run.read_task
copy_workspace = _run.copy_workspace

from live_anthropic import (  # noqa: E402
    DEFAULT_SMOKE_TASKS,
    TOOLS,
    WorkspaceTools,
    build_system_prompt,
    build_user_prompt,
    draft_contract,
    write_live_scorecard,
    _utc_stamp,
)


def _active_tools(enable_verify: bool) -> list[dict[str, Any]]:
    if enable_verify:
        return TOOLS
    return [t for t in TOOLS if t["name"] != "run_verify"]


def ollama_tools_schema(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for t in tools:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
                },
            }
        )
    return out


def chat_ollama(
    host: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    timeout: int = 300,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "stream": False,
        "messages": messages,
        "tools": ollama_tools_schema(tools),
        # Keep context modest for multi-turn tool loops on local Macs (default Ollama
        # contexts can be 128k and make each turn extremely slow / memory-heavy).
        "options": {
            "temperature": 0.2,
            "num_predict": 1024,
            "num_ctx": 8192,
        },
    }
    req = urllib.request.Request(
        host.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Return list of {id, name, input} from native or text-emitted tool calls."""
    native = message.get("tool_calls") or []
    if native:
        out = []
        for i, tc in enumerate(native):
            fn = tc.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args else {}
                except json.JSONDecodeError:
                    args = {}
            out.append(
                {
                    "id": tc.get("id") or f"call_{i}",
                    "name": fn.get("name") or tc.get("name"),
                    "input": args or {},
                }
            )
        return out

    content = message.get("content") or ""
    if not content.strip():
        return []

    # Try whole-content JSON object with name/arguments
    text = content.strip()
    # strip markdown fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()

    candidates = []
    try:
        obj = json.loads(text)
        candidates.append(obj)
    except json.JSONDecodeError:
        # find first {...} block
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                candidates.append(json.loads(m.group(0)))
            except json.JSONDecodeError:
                pass

    out = []
    for obj in candidates:
        if isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, dict) and ("name" in item or "function" in item):
                    name = item.get("name") or (item.get("function") or {}).get("name")
                    args = item.get("arguments") or item.get("input") or item.get("parameters") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    out.append({"id": f"txt_{i}", "name": name, "input": args})
        elif isinstance(obj, dict):
            if "name" in obj or "function" in obj:
                name = obj.get("name") or (obj.get("function") or {}).get("name")
                args = obj.get("arguments") or obj.get("input") or obj.get("parameters") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                out.append({"id": "txt_0", "name": name, "input": args or {}})
            elif "tool" in obj:
                out.append(
                    {
                        "id": "txt_0",
                        "name": obj["tool"],
                        "input": obj.get("arguments") or obj.get("input") or {},
                    }
                )
    return out


def tool_protocol_addon(tools: list[dict[str, Any]]) -> str:
    names = ", ".join(t["name"] for t in tools)
    return (
        "\n\nYou have tools: "
        + names
        + ".\n"
        "On each turn, either call ONE tool by responding with ONLY JSON:\n"
        '{"name": "<tool_name>", "arguments": { ... }}\n'
        "or if you are done without tools, still call finish via that JSON form.\n"
        "Do not wrap in markdown unless necessary. Prefer raw JSON."
    )


def run_one_task(
    task_id: str,
    *,
    model: str,
    host: str,
    max_turns: int,
    enable_verify_tool: bool,
) -> dict[str, Any]:
    import shutil

    task = read_task(task_id)
    contract = draft_contract(task)
    if not enable_verify_tool:
        contract = dict(contract)
        contract["allowed_tools"] = [
            t for t in contract["allowed_tools"] if t != "run_verify"
        ]
        contract["ablation"] = "no_verify_tool"
    workspace = copy_workspace(task_id)
    tools = WorkspaceTools(workspace, set(task["allowed_files"]), task_id)
    system = build_system_prompt(task)
    if not enable_verify_tool:
        system = system.replace(
            "You may call run_verify to run the external verifier before finishing.\n",
            "",
        )
    toolset = _active_tools(enable_verify_tool)
    system = system + tool_protocol_addon(toolset)
    user = build_user_prompt(task, workspace)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    t0 = time.time()
    raw_log: list[dict[str, Any]] = []

    for turn in range(max_turns):
        if tools.done:
            break
        try:
            resp = chat_ollama(host, model, messages, toolset)
        except Exception as exc:
            tools.finish_status = "incomplete"
            tools.finish_note = f"ollama error: {exc}"
            tools.done = True
            raw_log.append({"error": str(exc)})
            break

        msg = resp.get("message") or {}
        raw_log.append({"turn": turn, "message": msg, "done": resp.get("done")})
        messages.append({"role": "assistant", "content": msg.get("content") or ""})

        calls = parse_tool_calls(msg)
        if not calls:
            # try one repair nudge
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Respond with ONLY a JSON tool call, e.g. "
                        '{"name":"read_file","arguments":{"path":"file.py"}} '
                        "or finish with "
                        '{"name":"finish","arguments":{"status":"complete","note":"..."}}'
                    ),
                }
            )
            continue

        for call in calls:
            name = call.get("name") or ""
            args = call.get("input") or {}
            if not name:
                continue
            out = tools.dispatch(name, dict(args))
            # Ollama-style tool role
            messages.append(
                {
                    "role": "tool",
                    "content": out,
                }
            )
            # also as user for models that ignore tool role
            messages.append(
                {
                    "role": "user",
                    "content": f"Tool {name} result:\n{out}",
                }
            )
            if tools.done:
                break
        if tools.done:
            break
    else:
        if not tools.done:
            tools.finish_status = "incomplete"
            tools.finish_note = "max turns"
            tools.done = True

    duration_ms = int((time.time() - t0) * 1000)
    claimed = tools.finish_status == "complete"
    traj = summarize_trajectory(tools.events)
    result = grade_workspace(
        task_id,
        workspace,
        claim_complete=claimed,
        finish_status=tools.finish_status,
        trajectory=traj,
        extra={
            "adapter": "ollama-live",
            "model_requested": model,
            "served_model": model,
            "live_run": True,
            "enable_verify_tool": enable_verify_tool,
            "prompt_seeded_files": True,
            "observe": {
                "host": host,
                "duration_ms": duration_ms,
                "finish_status": tools.finish_status,
                "finish_note": tools.finish_note,
                "tool_event_count": len(tools.events),
                "turns_logged": len(raw_log),
            },
        },
    )
    shutil.rmtree(workspace, ignore_errors=True)
    return result


def run_live_ollama_suite(args: Any) -> int:
    tasks = args.tasks or [t for t in DEFAULT_SMOKE_TASKS if t in discover_tasks()]
    if not tasks:
        print("no tasks", file=sys.stderr)
        return 2
    enable_verify = not getattr(args, "no_verify_tool", False)
    stamp = _utc_stamp()
    out_dir = Path(RESULTS_DIR) / "live" / f"{stamp}-{args.label}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    print(
        f"ollama live: model={args.model} host={args.host} "
        f"verify_tool={enable_verify} tasks={tasks}"
    )
    print(f"output: {out_dir}")

    for tid in tasks:
        print(f"\n=== {tid} ===")
        try:
            row = run_one_task(
                tid,
                model=args.model,
                host=args.host,
                max_turns=args.max_turns,
                enable_verify_tool=enable_verify,
            )
        except Exception as exc:
            row = {
                "task": tid,
                "error": str(exc),
                "verified_pass": False,
                "false_completion": False,
                "scope_violation": False,
                "ledger_label": "error",
                "path_valid": None,
                "trajectory": summarize_trajectory([]),
            }
            print("ERROR", exc)
        rows.append(row)
        (out_dir / f"{len(rows):02d}-{tid}.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
        print(
            "ledger={l} vp={vp} fc={fc} scope={sv} path_valid={pv}".format(
                l=row.get("ledger_label"),
                vp=row.get("verified_pass"),
                fc=row.get("false_completion"),
                sv=row.get("scope_violation"),
                pv=row.get("path_valid"),
            )
        )

    write_live_scorecard(rows, out_dir / "scorecard.md")
    summary = {
        "stamp": stamp,
        "label": args.label,
        "model": args.model,
        "adapter": "ollama-live",
        "enable_verify_tool": enable_verify,
        "n": len(rows),
        "verified_pass": sum(1 for r in rows if r.get("verified_pass")),
        "false_completion": sum(1 for r in rows if r.get("false_completion")),
        "scope_violation": sum(1 for r in rows if r.get("scope_violation")),
        "path_valid": sum(1 for r in rows if r.get("path_valid") is True),
        "path_scored": sum(1 for r in rows if r.get("path_valid") is not None),
        "ledger_hist": {},
    }
    for r in rows:
        lab = r.get("ledger_label") or "?"
        summary["ledger_hist"][lab] = summary["ledger_hist"].get(lab, 0) + 1
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0

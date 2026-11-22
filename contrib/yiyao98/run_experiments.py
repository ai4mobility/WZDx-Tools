"""Run genuine local-model experiments without changing the course harness.

Examples (from the repository root, using the experiment virtual environment):
  python contrib/yiyao98/run_experiments.py agent --question-id shoulder_record_trust --name q1 --think
  python contrib/yiyao98/run_experiments.py agent --all-agents --name first --think-question-id shoulder_record_trust
  python contrib/yiyao98/run_experiments.py ablation --name final --publish

The default loader is CPU float32. --quantization dynamic-int8 quantizes Linear
modules in place. That backend inherits the course generation method. The optional
Ollama backend uses the same HF prompt template and explicitly matched sampling
settings with a recorded local GGUF model. Raw replies and MCP records are preserved.

Agent names are never overwritten. Ablations always create a new batch under
ablation/experiments/<name>/, saving full raw records as well as the course's
compact records. --publish additionally creates the checker-standard files;
it refuses to overwrite an existing published result. There is no old-run cache.
The reference answers are archived but are never passed to the model.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parent.parent
COURSE = ROOT / "contrib"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(COURSE))
import agent_loop as AL
import ablation as AB


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=1, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def write_text(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(value)


def require_absent(paths: list[Path]) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise FileExistsError("Existing outputs will not be overwritten: " + ", ".join(existing))


def output_path(prefix: Path, suffix: str) -> Path:
    return Path(str(prefix) + suffix)


def safe_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError("Use a name containing only letters, digits, underscore, hyphen, or dot.")
    return value


def fresh_name() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def fingerprints(tasks_path: Path) -> dict[str, str]:
    paths = [Path(__file__).resolve(), FOLDER / "tools.py", FOLDER / "server.py",
             COURSE / "agent_loop.py", COURSE / "ablation.py", ROOT / "wzdx_tools.py", tasks_path]
    snapshot = os.environ.get("WZDX_SNAPSHOT")
    if snapshot:
        paths.extend(sorted(path for path in Path(snapshot).iterdir() if path.is_file()))
    return {str(path): digest(path) for path in paths}


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


class CPUModel(AL.Model):
    """Replace only loading; inherit the course prompt() and write() unchanged."""

    def __init__(self, args: argparse.Namespace):
        if not args.allow_download:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        started = time.monotonic()
        torch.set_num_threads(args.threads)
        self.torch, self.think, self.seed, self.stream = torch, args.think, args.seed, args.stream
        self.device = "cpu"
        load_options = {
            "cache_dir": str(args.cache_dir),
            "local_files_only": not args.allow_download,
            "trust_remote_code": False,
        }
        if args.revision:
            load_options["revision"] = args.revision
        self.tok = AutoTokenizer.from_pretrained(args.model, **load_options)
        self.lm = AutoModelForCausalLM.from_pretrained(
            args.model, torch_dtype=torch.float32,
            attn_implementation=args.attention_implementation, low_cpu_mem_usage=True,
            use_safetensors=True, **load_options,
        ).to("cpu").eval()
        model_commit = getattr(self.lm.config, "_commit_hash", None)
        attention_implementation = getattr(self.lm.config, "_attn_implementation", None)
        if args.quantization == "dynamic-int8":
            supported = list(torch.backends.quantized.supported_engines)
            if args.quantized_engine not in supported:
                raise RuntimeError(f"Quantized engine {args.quantized_engine!r} is unavailable; supported: {supported}")
            torch.backends.quantized.engine = args.quantized_engine
            self.lm = torch.ao.quantization.quantize_dynamic(
                self.lm, {torch.nn.Linear}, dtype=torch.qint8, inplace=True,
            )
            self.lm.eval()
        quantized_class = torch.ao.nn.quantized.dynamic.Linear
        quantized_count = sum(isinstance(module, quantized_class) for module in self.lm.modules())
        if args.quantization == "dynamic-int8" and quantized_count == 0:
            raise RuntimeError("dynamic-int8 requested but no Linear modules were quantized.")
        self.execution_metadata = {
            "device": "cpu",
            "load_dtype": "float32",
            "attention_implementation": attention_implementation,
            "requested_attention_implementation": args.attention_implementation,
            "low_cpu_mem_usage": True,
            "quantization": args.quantization,
            "quantized_engine": torch.backends.quantized.engine,
            "quantized_linear_modules": quantized_count,
            "torch_threads": torch.get_num_threads(),
            "torch_interop_threads": torch.get_num_interop_threads(),
            "torch_version": torch.__version__,
            "transformers_version": package_version("transformers"),
            "mcp_version": package_version("mcp"),
            "model_commit": model_commit,
            "tokenizer_commit": getattr(self.tok, "init_kwargs", {}).get("_commit_hash"),
            "requested_revision": args.revision,
            "cache_dir": str(args.cache_dir),
            "local_files_only": not args.allow_download,
            "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE"),
            "transformers_offline": os.environ.get("TRANSFORMERS_OFFLINE"),
            "model_load_seconds": round(time.monotonic() - started, 3),
            "prompt_method": "contrib.agent_loop.Model.prompt (inherited unchanged)",
            "generation_method": "contrib.agent_loop.Model.write (inherited unchanged)",
        }


class OllamaModel(AL.Model):
    """Use the same HF chat template with an explicitly recorded local GGUF backend."""

    def request(self, route, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(self.api + route, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1800) as response:
            return json.load(response)

    def __init__(self, args):
        from transformers import AutoTokenizer
        self.api = "http://127.0.0.1:11434"
        self.tag, self.threads = args.ollama_model, args.threads
        self.think, self.seed, self.stream, self.device = args.think, args.seed, args.stream, "cpu (Ollama)"
        self.tok = AutoTokenizer.from_pretrained(args.model, revision=args.revision,
                    cache_dir=str(args.cache_dir), local_files_only=True, trust_remote_code=False)
        shown = self.request("/api/show", {"model": self.tag})
        tags = self.request("/api/tags")["models"]
        digest_value = next(m["digest"] for m in tags if m["name"] == self.tag)
        self.execution_metadata = {
            "backend": "Ollama raw /api/generate; local GGUF model",
            "ollama_version": self.request("/api/version")["version"],
            "ollama_model": self.tag, "ollama_digest": digest_value,
            "model_details": shown.get("details"),
            "tokenizer_requested_revision": args.revision,
            "tokenizer_source": args.model, "device": "cpu", "threads": self.threads,
            "num_gpu": 0, "context_tokens": 32768,
            "prompt_method": "contrib.agent_loop.Model.prompt (inherited unchanged)",
            "generation_method": "Ollama raw prompt; Qwen sampling settings matched explicitly",
            "repeat_penalty": 1.0, "repeat_last_n": 0, "min_p": 0.0,
            "thinking_serialization": "API thinking and response fields preserved in backend_calls; adapter adds think delimiters for the course text parser",
            "transformers_version": package_version("transformers"),
            "mcp_version": package_version("mcp"),
        }
        self.call_metadata = []

    def write(self, text, max_new):
        started = time.monotonic()
        options = {"seed": self.seed, "num_predict": max_new, "num_ctx": 32768,
                   "num_thread": self.threads, "num_gpu": 0, "top_k": 20,
                   "temperature": 0.6 if self.think else 0.7,
                   "top_p": 0.95 if self.think else 0.8,
                   "repeat_penalty": 1.0, "repeat_last_n": 0, "min_p": 0.0}
        result = self.request("/api/generate", {"model": self.tag, "prompt": text,
                             "raw": True, "stream": False, "options": options, "keep_alive": "15m"})
        self.last_backend_result = result
        # Ollama parses reasoning into a separate field even for raw prompts.
        # Preserve that API response intact, and serialize the two fields for AL's parser.
        # Only delimiters are added; no model words are changed or invented.
        reply = (("<think>\n" + result["thinking"] + "</think>\n") if result.get("thinking") else "")
        reply += result["response"].split("<|im_end|>")[0]
        self.call_metadata.append(result)
        if self.stream:
            print(reply, flush=True)
        return reply, result["prompt_eval_count"], result["eval_count"], round(time.monotonic() - started, 1)


def options(args: argparse.Namespace, tasks: dict, question: dict) -> dict:
    thinking = args.think or question["id"] in getattr(args, "think_question_id", [])
    return {
        "model": model_label(args), "think": thinking, "seed": args.seed,
        "max_new": args.max_new if args.max_new is not None else (2048 if thinking else 512),
        "max_steps": args.max_steps if args.max_steps is not None else int(tasks.get("max_steps", 8)),
        "setup": AB.setup_of(tasks, question), "stream": args.stream,
    }


def model_label(args):
    return f"{args.ollama_model} (Ollama GGUF; {args.model} tokenizer)" if args.backend == "ollama" else args.model


async def one_run(args: argparse.Namespace, tasks: dict, question: dict, condition: str,
                  prefix: Path, model: CPUModel, frozen: dict[str, str]) -> dict:
    if fingerprints(args.tasks) != frozen:
        raise RuntimeError("Source, questions, or snapshot changed during this batch; start a fresh named run.")
    paths = [output_path(prefix, suffix) for suffix in (".json", ".md", ".mcp.jsonl")]
    require_absent(paths)
    old_condition = os.environ.get("ABLATION")
    os.environ["ABLATION"] = condition
    opts = options(args, tasks, question)
    print(f"Running {condition}/{question['id']} -> {prefix}", file=sys.stderr, flush=True)
    backend_call_start = len(getattr(model, "call_metadata", []))
    try:
        rec = await AL.loop(str(FOLDER / "server.py"), question["question"], opts,
                            str(output_path(prefix, ".mcp.jsonl")), model=model)
    finally:
        if old_condition is None:
            os.environ.pop("ABLATION", None)
        else:
            os.environ["ABLATION"] = old_condition
    rec["execution"] = {
        "runner": "contrib/yiyao98/run_experiments.py",
        **model.execution_metadata,
        "question_id": question["id"], "condition": condition,
        "max_new_tokens": opts["max_new"], "max_steps": opts["max_steps"],
        "thinking": opts["think"], "seed": opts["seed"],
        "source_and_data_sha256": frozen,
        "loaded_model_reused": True,
    }
    if hasattr(model, "call_metadata"):
        rec["backend_calls"] = model.call_metadata[backend_call_start:]
    write_json(output_path(prefix, ".json"), rec)
    write_text(output_path(prefix, ".md"), AL.transcript(rec))
    return rec


async def execute(args: argparse.Namespace) -> None:
    os.chdir(ROOT)
    tasks = json.loads(args.tasks.read_text(encoding="utf-8"))
    questions = tasks.get("questions", [])
    ids = [safe_name(question["id"]) for question in questions]
    if not questions or len(set(ids)) != len(ids):
        raise ValueError("tasks.json must contain questions with distinct IDs.")
    for key, value in (tasks.get("env") or {}).items():
        candidate = ROOT / str(value)
        os.environ[key] = str(candidate.resolve()) if candidate.exists() else str(value)
    os.environ["HF_HOME"] = str(args.cache_dir)
    os.environ["HF_HUB_CACHE"] = str(args.cache_dir)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("TZ", "America/New_York")
    if hasattr(time, "tzset"):
        time.tzset()
    if not args.allow_download:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    frozen = fingerprints(args.tasks)
    name = safe_name(args.name or fresh_name())
    if args.command == "agent":
        if args.all_agents:
            selected = questions
            labels = [(name + f"_q{i}") if args.name else f"q{i}_{name}"
                      for i in range(1, len(selected) + 1)]
        else:
            selected = [question for question in questions if question["id"] == args.question_id]
            if not selected:
                raise ValueError(f"Unknown question ID: {args.question_id}. Available: {', '.join(ids)}")
            labels = [name]
        unknown_thinking_ids = set(args.think_question_id) - set(ids)
        if unknown_thinking_ids:
            raise ValueError("Unknown thinking question IDs: " + ", ".join(sorted(unknown_thinking_ids)))
        destination = FOLDER / "runs"
        destination.mkdir(exist_ok=True)
        prefixes = [destination / label for label in labels]
        require_absent([output_path(prefix, suffix) for prefix in prefixes
                        for suffix in (".json", ".md", ".mcp.jsonl")])
        metadata_prefix = destination / (name + ".experiment")
    else:
        destination = FOLDER / "ablation" / "experiments" / name
        destination.mkdir(parents=True, exist_ok=False)
        (destination / "raw").mkdir()
        (destination / "runs").mkdir()
        metadata_prefix = destination / "experiment"
        if args.publish:
            require_absent([FOLDER / "ablation" / "answers.md"] + [
                FOLDER / "ablation" / "runs" / f"{condition}__{question['id']}.json"
                for question in questions for condition, _ in AB.SETUPS])
    manifest_path = Path(str(metadata_prefix) + ".manifest.json")
    write_json(manifest_path, {
        "runner": "contrib/yiyao98/run_experiments.py",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "argv": sys.argv, "python": sys.version, "platform": platform.platform(),
        "configuration": {key: str(value) if isinstance(value, Path) else value
                          for key, value in vars(args).items()},
        "experiment_environment": {key: os.environ.get(key)
                                   for key in ("WZDX_SNAPSHOT", "WZDX_NOW", "HF_HOME", "HF_HUB_CACHE",
                                               "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
                                               "TOKENIZERS_PARALLELISM", "TZ")},
        "source_and_data_sha256": frozen,
        "answers_not_sent_to_model": True,
    })
    write_json(Path(str(metadata_prefix) + ".frozen_tasks.json"), tasks)
    try:
        model = OllamaModel(args) if args.backend == "ollama" else CPUModel(args)
        write_json(Path(str(metadata_prefix) + ".runtime.json"), model.execution_metadata)
        if args.command == "agent":
            for question, prefix in zip(selected, prefixes):
                await one_run(args, tasks, question, "full", prefix, model, frozen)
        else:
            spec = importlib.util.spec_from_file_location("experiment_tools", FOLDER / "tools.py")
            mine_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mine_module)
            mine = [tool.__name__ for tool in mine_module.TOOLS]
            runs = {}
            for question in questions:
                for condition, _ in AB.SETUPS:
                    stem = f"{condition}__{question['id']}"
                    rec = await one_run(args, tasks, question, condition,
                                        destination / "raw" / stem, model, frozen)
                    compact = AB.compact(rec, mine)
                    compact["harness_setup"] = compact.pop("setup", [])
                    compact.update(setup=condition, question_id=question["id"],
                                   question=question["question"],
                                   runner="contrib/yiyao98/run_experiments.py",
                                   full_record=f"../raw/{stem}.json",
                                   execution=rec["execution"])
                    write_json(destination / "runs" / f"{stem}.json", compact)
                    runs[(condition, question["id"])] = compact
            sample = next(iter(runs.values()))
            answers = AB.answers_md(tasks, runs, {
                "model": model_label(args), "think": args.think, "seed": args.seed,
                "device": sample.get("device"), "data": sample.get("data"),
            })
            write_text(destination / "answers.md", answers)
            if args.publish:
                canonical = FOLDER / "ablation" / "runs"
                canonical.mkdir(parents=True, exist_ok=True)
                for (condition, question_id), result in runs.items():
                    published = dict(result)
                    published["full_record"] = os.path.relpath(
                        destination / "raw" / f"{condition}__{question_id}.json", canonical)
                    write_json(canonical / f"{condition}__{question_id}.json", published)
                write_text(FOLDER / "ablation" / "answers.md", answers)
            print(f"Completed {len(runs)} genuine ablation runs: {destination}", file=sys.stderr)
    except BaseException as error:
        if 'model' in locals() and hasattr(model, 'last_backend_result'):
            write_json(Path(str(metadata_prefix) + ".last_backend_result.json"), model.last_backend_result)
        write_json(Path(str(metadata_prefix) + ".error.json"), {
            "type": type(error).__name__, "message": str(error),
            "traceback": traceback.format_exc(),
            "note": "Existing partial raw logs are retained; no fabricated answer or grade was generated.",
        })
        raise


def positive_int(value: str) -> int:
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("Must be a positive integer.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("agent", "ablation"):
        child = commands.add_parser(command)
        child.add_argument("--name", help="New output name; existing files are never overwritten.")
        child.add_argument("--tasks", type=Path, default=FOLDER / "ablation" / "tasks.json")
        child.add_argument("--model", default="Qwen/Qwen3-1.7B")
        child.add_argument("--backend", choices=("transformers", "ollama"), default="transformers")
        child.add_argument("--ollama-model", default="qwen3:0.6b")
        child.add_argument("--revision", help="Optional fixed Hugging Face revision/commit.")
        child.add_argument("--cache-dir", "--cache_dir", type=Path, default=ROOT.parent / "hf_cache")
        child.add_argument("--quantization", choices=("none", "dynamic-int8"), default="none")
        child.add_argument("--quantized-engine", default="fbgemm")
        child.add_argument("--attention-implementation", choices=("sdpa", "eager"), default="sdpa")
        child.add_argument("--threads", type=positive_int, default=4)
        child.add_argument("--seed", type=int, default=1)
        child.add_argument("--think", action="store_true", help="Enable the original Qwen thinking mode.")
        child.add_argument("--max-new", "--max-new-tokens", "--max_new", type=positive_int)
        child.add_argument("--max-steps", "--max_steps", type=positive_int)
        child.add_argument("--allow-download", action="store_true", help="Allow uncached model downloads.")
        child.add_argument("--stream", action="store_true", help="Also stream genuine model replies.")
        if command == "agent":
            selection = child.add_mutually_exclusive_group(required=True)
            selection.add_argument("--question-id")
            selection.add_argument("--all-agents", action="store_true")
            child.add_argument("--think-question-id", action="append", default=[])
        else:
            child.add_argument("--publish", action="store_true",
                               help="Also create checker-standard compact logs and answers.md, without overwriting.")
    args = parser.parse_args()
    args.tasks = args.tasks.expanduser().resolve()
    args.cache_dir = args.cache_dir.expanduser().resolve()
    asyncio.run(execute(args))


if __name__ == "__main__":
    main()

# Reproducing the local experiments

The execution wrapper uses the course's unchanged `agent_loop.Model.prompt` and `loop` functions. Ablation summaries use `ablation.compact` and `answers_md`. Formal generation uses Ollama's raw-prompt API with explicit Qwen sampling settings. The wrapper records provenance, preserves actual replies, and avoids the upstream ablation resume-cache issue. Reference answers are not fed to the model.

## Environment

- Intel Mac, macOS 15.7.9, 16 GB memory, CPU inference with four Ollama inference threads.
- Python 3.10.4; torch 2.2.2; transformers 4.55.4; accelerate 1.15.0; mcp 2.3.0; numpy 1.26.4.
- Formal generator: Ollama `qwen3:0.6b`, GGUF Q4_K_M, digest `7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435`; Ollama 0.40.5. CPU is requested explicitly with `num_gpu=0`.
- The HF tokenizer/chat template is `Qwen/Qwen3-0.6B`, revision `c1899de289a04d12100db370d81485cdf75e47ca`. This identifies the tokenizer; the GGUF generator is pinned independently by its digest. This is a quantized local-model case study, not a full-precision benchmark.
- Frozen data and clock: `snapshots/2026-11-05`, `WZDX_NOW=1793888460` (2026-11-05 14:21 UTC). Only the question text, tool descriptions, server instructions and actual tool replies enter the model context.

Install the listed Python versions and run a local Ollama service with `ollama pull qwen3:0.6b`. Cache the HF tokenizer outside the contribution folder. No model weights are included in this contribution. Before repeating a published comparison, confirm the Ollama digest matches the recorded one.

## Running again

From the repository root, use a fresh output name. For example:

```bash
python contrib/yiyao98/run_experiments.py agent --all-agents --name repeat_agents \
  --think-question-id shoulder_record_trust --backend ollama --ollama-model qwen3:0.6b --threads 4 \
  --model Qwen/Qwen3-0.6B --revision c1899de289a04d12100db370d81485cdf75e47ca \
  --cache-dir /path/to/hf_cache

python contrib/yiyao98/run_experiments.py ablation --name repeat_ablation \
  --backend ollama --ollama-model qwen3:0.6b --threads 4 \
  --model Qwen/Qwen3-0.6B --revision c1899de289a04d12100db370d81485cdf75e47ca \
  --cache-dir /path/to/hf_cache
```

The first question in the agent command uses thinking with a 2048-token limit; the other two use no thinking with a 512-token limit. Each permits eight model turns. All nine ablation runs use no thinking, seed 1, 512 new tokens per turn, and eight turns. The explicit settings match the course's recommendations: thinking temperature 0.6/top-p 0.95, no-thinking 0.7/0.8, top-k 20; repetition penalty 1 and min-p 0. A 32768-token context is requested. Ollama and Transformers are different samplers, so bit-identical output across backends is not claimed. `--publish` creates canonical ablation files only when absent; repeated batches retain independent directories.

## Evidence and interpretation

Agent `.json` files retain prompts, replies, calls, tool results and MCP messages; their `.md` counterparts are generated transcripts. Each ablation batch retains complete records under `raw/` as well as compact records under `runs/`. Compact tool-result strings are truncated by the course summarizer to 1500 characters; the model receives the complete tool result. Reference questions and answers are frozen before execution, and source/data hashes are checked during each batch.

An initial Qwen3-1.7B Transformers/int8 trial used the adapter archived as `runs/q1_initial_adapter.txt`. Its first generation remained unfinished for more than seven minutes and was stopped. A smaller Qwen3-0.6B Transformers/int8 trial also generated too slowly and was stopped during its first reasoning response. Their console, MCP, manifest and runtime-trial files preserve the available evidence. Neither had a completed answer and neither counts as a completed agent run or ablation result. The Ollama backend was selected on runtime grounds before any completed answer was viewed. All formal comparisons use it consistently through `run_experiments.py`.

The original harness may leave reasoning before a closing `</think>` marker in its answer field when the tokenizer has already supplied the opening marker; raw text is preserved rather than silently rewritten.

The three fixed questions, one model, one seed, and quantized CPU execution support a documented case comparison. They do not establish a general accuracy rate or isolate the causal effect of a particular sentence. Full mode changes descriptions, calculations, result wording and server instructions together.

The archived `ablation/ollama_model_show.json` records the model defaults, including stop markers. The runner configuration field `quantization=none` applies to its unused Transformers branch; formal generator quantization is the recorded GGUF Q4_K_M. The log audit reconstructs every full prompt from the recorded messages and tokenizer to check the context limit.

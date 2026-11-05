# Local alternative — Moshi q4, no tools

Use this for an on-device conversation comparison, not an operational session assistant. Stock Moshi structured tool integration is **not verified here**. Do not execute commands extracted from its spoken or generated text. The hosted ten-request tool gate cannot be passed by a Moshi conversation.

## Prerequisites and approval

- Apple Silicon Mac; MLX is the Apple Silicon implementation. Other OS/hardware needs a different upstream path, not these commands.
- Python 3.12 recommended by the [official MLX README](https://github.com/kyutai-labs/moshi/blob/main/moshi_mlx/README.md); upstream minimum is 3.10. Python/`rustymimi` wheel compatibility matters. Prefer supported Python 3.12 rather than adding a Rust toolchain by surprise.
- Multi-GB free disk for weights/cache and sufficient unified memory. The source session used a 32 GB M5; it is not a minimum requirement or a guarantee on another machine. Check the selected model requirements and leave OS headroom.
- Headphones, mic permission for the terminal, AC power, other heavy model jobs stopped by their owners. The bare local client has no echo cancellation; speakers can feed the mic.
- Internet for packages/weights first; review model license and attribution (Moshi weights have CC-BY terms; code licensing is separate). Review local logs as sensitive even without cloud inference.

The following are **member-run commands after install/download approval**, not actions performed by this kit. Use a new directory outside the tracked repo. No global Python package modifications.

## 1. Create an isolated environment

In your chosen private work directory:

```bash
mkdir moshi-voice-pilot
cd moshi-voice-pilot
python3.12 --version
python3.12 -m venv .venv
.venv/bin/python -m pip install moshi_mlx
.venv/bin/python -m pip show moshi_mlx
.venv/bin/python -m moshi_mlx.local --help
```

These adapt upstream `pip install moshi_mlx` into an isolated environment. Record the package version and model repo/revision when known. If Python 3.12 is absent, ask before installing it. Do not merge this environment with another model's conflicting dependencies.

## 2. Start q4 first

Upstream documents these exact module/flag combinations:

```bash
.venv/bin/python -m moshi_mlx.local -q 4
# Alternative female voice; use this instead, not concurrently:
# .venv/bin/python -m moshi_mlx.local -q 4 --hf-repo kyutai/moshika-mlx-q4
```

The first launch may download multi-GB assets while logs seem idle. Inspect download/cache progress rather than starting duplicate runs. If a model is gated, the owner accepts its license in the browser and authenticates privately with the login utility actually present in the environment (`hf` or older `huggingface-cli`). Don't guess a binary or request the token in chat. The default command alone is sufficient for public weights when no login is required.

Use the terminal client before a web client to remove browser/WebSocket/Opus variables. Do not start a tunnel. Stop with Ctrl-C; verify owned children also exit before another run.

## 3. Evaluate conversation, not imaginary tools

Converse for at least three minutes, interrupt a long answer, pause and resume, and use the visible/manual stop. Count `[LAG]` messages alongside the duration and audible gaps. A handful of queue-starvation blips is different from continual word-by-word output, but lag counts alone are **not RTF**.

Mimi runs at 12.5 Hz: the compute budget is 80 ms/model step. If a correctly synchronized model-only benchmark exists for your installed version, record method, warmup, mean/p50/p95 and `RTF = mean_step_ms / 80`. Suggested practical target is RTF <0.9; ≥1 is compute-bound. Do not invent a portable benchmark command: no compatible Moshi step-timing harness is shipped here. Report numeric headroom UNKNOWN until measured; end-to-end audio latency is a different metric.

Prior M5/32 GB notes reported PersonaPlex q4 ≈83 ms (RTF 1.04), q8 ≈108 ms (1.35), without retained raw timing output. Moshi q4 was judged usable by listening; no numeric Moshi timing was recorded. These aren't your results and aren't proof that a larger quantization will work. If sustained lag makes q4 unusable, stop the local comparison and use the hosted lane; don't spend the session tweaking a compute-bound client.

## 4. Verify offline behavior before saying “offline”

After the weights and required assets have downloaded, stop the process, disconnect networking deliberately, and relaunch the same q4 command. Confirm a fresh conversation works, with no tunnel or hosted speech/reasoning component. Record this observation. If any asset still needs the network, say `OFFLINE_NOT_VERIFIED`; reconnect only with approval. Local operation is not proof that no local recording/log exists.

Mark session-lookup, access, and write-tool rows `NOT_APPLICABLE` for this no-tools lane. Test interruption honestly: full-duplex speech does not guarantee the specific 500 ms mute behavior of the hosted client. A failure is useful evidence, not a reason to invent a pass.

## 5. Teardown without harming other work

Press Ctrl-C in the pilot terminal. In another terminal inspect:

```bash
ps -axo pid,ppid,%cpu,command
```

Find only the pilot parent and its owned multiprocessing children from the pre-run inventory; terminate any survivors by their **actual numeric PID** using `kill -TERM <PID>` (replace the placeholder, never paste it literally). Recheck the process list and mic indicator. Do not use broad `pkill -f` patterns: they may kill another member's unrelated model job. A surviving child can hold the mic/CPU and contaminate the next test.

Leave the venv and shared model cache intact unless the owner separately approves deletion. Disconnect mic permission if granted only for the pilot. Record clean teardown and any remaining process as a blocker.

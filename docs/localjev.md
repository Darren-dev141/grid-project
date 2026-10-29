# Local Jev candidate

User-supplied source: https://github.com/githubnext/localjev

The bridge translates the Jev wire protocol into local Chat Completions requests.
Its probabilities are model-generated, not Jev/OpenJev logit probabilities. Passing
protocol checks does not establish calibration for model routing or browser actions.

This Windows machine has Bun and an active Ollama server on loopback port 11434.
The server lists `qwen2.5:7b-instruct`, among other models. LocalJev was cloned to
`~/.cache/grid-project/localjev` and its frozen dependencies installed there.
Upstream verification: 19 tests passed; TypeScript typecheck passed. No model
download or paid API use was required.

Automatic approval review blocked starting the bridge process with the reason
"blocked by policy". The agent did not retry through another launch mechanism.
No readiness or inference success is claimed.

To start it yourself from the project folder in a terminal you control:

```powershell
./scripts/start-localjev.ps1
```

The script runs in the foreground and restores its process environment on exit.
It selects the installed Qwen model, uses only loopback endpoints, and configures
no authentication key. Stop it with Ctrl+C. It does not change persistent Jev
configuration or route the coding agent to another model.

Once running, verify `http://127.0.0.1:18080/ready`, then test Jev with a process-local
`TYPESAFE_BASE_URL=http://127.0.0.1:18080`. The installed jevkit supports a keyless
loopback override; do not invent a real provider credential. Complete a bounded
non-sensitive choice test and assess latency before using the browser loop. Its
confidence thresholds were designed for Jev, so applying them to LocalJev requires
task-specific evidence. No browser registrations have been submitted.

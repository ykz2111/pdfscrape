/**
 * pdfscrape — OpenCode plugin.
 *
 * Registers pdfscrape's providers as OpenCode tools so any session can reach
 * the AI providers already signed in on this machine.
 *
 *   pdfscrape.ask(provider, prompt)   ask one provider
 *   pdfscrape.ask_all(prompt)         ask every provider that is signed in
 *   pdfscrape.status()                who is signed in, and how
 *
 * The plugin shells out to the `pdfscrape` CLI rather than reimplementing
 * provider calls here. Every provider authenticates through a CLI that already
 * holds the user's OAuth session, and the CLI owns all of that wiring:
 * multi-line JSON parsing, the agy flag format, glab's stderr auth output,
 * the Copilot keychain token, and the Codex endpoint override. Keeping it in
 * one place means there is exactly one set of provider quirks to maintain.
 */

import { spawn } from "node:child_process"
import { existsSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

/** Provider names, mirroring `pdfscrape/providers/__init__.py`. */
const PROVIDERS = ["codex", "claude", "antigravity", "copilot", "gitlab", "ollama"]

/** Where the pdfscrape CLI may live. First hit wins. */
function candidateBinaries() {
  const home = homedir()
  const fromEnv = process.env.PDFSCRAPE_BIN
  const candidates = []
  if (fromEnv) candidates.push(fromEnv)
  candidates.push(
    // The repo's own venv, which is where `pip install -e .` puts it.
    join(home, "ykz21", "pdfscrape", ".venv", "bin", "pdfscrape"),
    // A venv inside the current project.
    join(process.cwd(), ".venv", "bin", "pdfscrape"),
    // A venv in the session's project directory.
    join(process.env.PDFSCRAPE_PROJECT_DIR || "", ".venv", "bin", "pdfscrape"),
    // On PATH.
    "pdfscrape",
  )
  return candidates.filter(Boolean)
}

function resolveBinary() {
  for (const candidate of candidateBinaries()) {
    if (candidate.includes("/") && existsSync(candidate)) return candidate
  }
  // Fall back to PATH lookup for a bare name.
  for (const dir of (process.env.PATH || "").split(":")) {
    if (!dir) continue
    const full = join(dir, "pdfscrape")
    if (existsSync(full)) return full
  }
  return null
}

/**
 * Run the pdfscrape CLI and collect its output.
 *
 * Resolves with the exit code rather than rejecting on a non-zero exit, so a
 * provider-level failure becomes readable tool output instead of a stack trace.
 */
function runCli(args, { signal, timeout = 600000, cwd } = {}) {
  const binary = resolveBinary()
  if (!binary) {
    return Promise.resolve({
      code: 127,
      stdout: "",
      stderr:
        "pdfscrape CLI not found. Install it with:\n" +
        "  cd ~/ykz21/pdfscrape && python3 -m venv .venv && .venv/bin/pip install -e .\n" +
        "or set PDFSCRAPE_BIN to its path.",
    })
  }

  return new Promise((resolve) => {
    let child
    try {
      child = spawn(binary, args, { cwd: cwd || process.cwd(), signal })
    } catch (err) {
      resolve({ code: 127, stdout: "", stderr: String(err) })
      return
    }

    let stdout = ""
    let stderr = ""
    let settled = false

    const finish = (code) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve({ code, stdout, stderr })
    }

    // A provider can sit for a while; keep the tool alive past the CLI's own
    // per-provider timeout so the CLI's error message wins over a bare kill.
    const timer = setTimeout(() => {
      try {
        child.kill("SIGTERM")
      } catch {}
      finish(124)
    }, timeout)

    child.stdout?.on("data", (chunk) => {
      stdout += chunk
    })
    child.stderr?.on("data", (chunk) => {
      stderr += chunk
    })
    child.on("error", (err) => {
      stderr += String(err)
      finish(127)
    })
    child.on("close", (code) => finish(code ?? 0))
  })
}

/** Parse the `--json` payload the CLI emits. */
function parseJsonOutput(text) {
  const trimmed = text.trim()
  if (!trimmed) return []
  try {
    const parsed = JSON.parse(trimmed)
    return Array.isArray(parsed) ? parsed : [parsed]
  } catch {
    return null
  }
}

function formatResults(results) {
  const lines = []
  for (const result of results) {
    const provider = result.provider || "unknown"
    if (result.ok) {
      lines.push(`=== ${provider}${result.model ? ` (${result.model})` : ""} ===`)
      lines.push(result.output || "(no output)")
    } else {
      lines.push(`=== ${provider} FAILED ===`)
      lines.push(result.error || "unknown error")
    }
    lines.push("")
  }
  return lines.join("\n").trim()
}

/**
 * Ask one or more providers and return their answers.
 *
 * Shared by `ask` and `ask_all`; the difference is only how the provider list
 * is chosen.
 */
async function askProviders({ providers, prompt, model, cwd, signal }) {
  if (!prompt || !prompt.trim()) {
    throw new Error("A prompt is required.")
  }

  const args = ["chat", prompt]
  if (providers && providers.length) {
    args.push("--provider", providers.join(","))
  } else {
    args.push("--provider", "auto")
  }
  if (model) args.push("--model", model)
  args.push("--json")
  if (cwd) args.push("--cwd", cwd)

  const { code, stdout, stderr } = await runCli(args, { signal, cwd })

  const parsed = parseJsonOutput(stdout)
  if (parsed) {
    const failed = parsed.filter((r) => !r.ok)
    const body = formatResults(parsed)
    if (failed.length && failed.length === parsed.length) {
      // Every provider failed. Surface it as a tool error so the model sees
      // the reason rather than an empty success.
      throw new Error(body || stderr.trim() || "All providers failed.")
    }
    return body
  }

  // No JSON: surface the CLI's own output so a startup failure is legible.
  const detail = (stdout || stderr).trim()
  if (!detail) {
    throw new Error(`pdfscrape exited with code ${code} and produced no output.`)
  }
  throw new Error(detail.slice(-4000))
}

const setup = async (ctx) => {
  const directory = ctx?.location?.directory || process.cwd()

  await ctx.tool.transform((editor) => {
    editor.namespace({
      name: "pdfscrape",
      description:
        "Ask the AI providers already signed in on this machine. Each provider " +
        "authenticates through its own CLI (Codex, Claude, Antigravity, " +
        "Copilot, GitLab, Ollama). No API keys are involved.",
    })

    editor.add({
      name: "ask",
      description:
        "Ask one AI provider a question and get its answer. Use this for a " +
        "second opinion, a review by a different model, or to reach a " +
        "provider you are not currently using. " +
        `Providers: ${PROVIDERS.join(", ")}.`,
      input: {
        type: "object",
        properties: {
          provider: {
            type: "string",
            enum: PROVIDERS,
            description: "Which provider to ask.",
          },
          prompt: {
            type: "string",
            description: "The question or instruction to send.",
          },
          model: {
            type: "string",
            description:
              "Optional model override. Uses the provider's configured or " +
              "default model when omitted.",
          },
        },
        required: ["provider", "prompt"],
        additionalProperties: false,
      },
      options: { namespace: "pdfscrape", codemode: true },
      execute: async (input, context) => {
        const body = await askProviders({
          providers: [input.provider],
          prompt: input.prompt,
          model: input.model,
          cwd: directory,
          signal: context.signal,
        })
        return { content: body }
      },
    })

    editor.add({
      name: "ask_all",
      description:
        "Ask every AI provider that is currently signed in and return each " +
        "answer. Use this for a quick consensus check or to compare answers " +
        "across models.",
      input: {
        type: "object",
        properties: {
          prompt: {
            type: "string",
            description: "The question or instruction to send to each provider.",
          },
          model: {
            type: "string",
            description: "Optional model override, applied to every provider.",
          },
        },
        required: ["prompt"],
        additionalProperties: false,
      },
      options: { namespace: "pdfscrape", codemode: true },
      execute: async (input, context) => {
        const body = await askProviders({
          providers: null,
          prompt: input.prompt,
          model: input.model,
          cwd: directory,
          signal: context.signal,
        })
        return { content: body }
      },
    })

    editor.add({
      name: "status",
      description:
        "Report which AI providers are signed in on this machine and how " +
        "each one authenticates, with the command to sign in when one is not.",
      input: {
        type: "object",
        properties: {},
        additionalProperties: false,
      },
      options: { namespace: "pdfscrape", codemode: true },
      execute: async (input, context) => {
        const { code, stdout, stderr } = await runCli(["init"], {
          signal: context.signal,
          cwd: directory,
        })
        const body = (stdout || stderr).trim()
        if (!body) {
          throw new Error(`pdfscrape init produced no output (exit code ${code}).`)
        }
        return { content: body }
      },
    })
  })
}

// OpenCode v2 validates the default export as an object and reads `setup`
// from it, so this must not be a bare function.
export default { id: "pdfscrape", setup }

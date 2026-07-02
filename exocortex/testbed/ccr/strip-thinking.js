// strip-thinking.js — claude-code-router custom transformer for the BYO-model Exocortex testbed.
//
// WHY: Claude Code sends an extended-thinking request. claude-code-router force-forwards a
// thinking/reasoning flag to the backend regardless of an empty `Router.think`, and ollama models
// without thinking support (qwen2.5-coder, llama3, mistral, ...) reject it with a 400:
//   {"error":{"message":"\"qwen2.5-coder:32b\" does not support thinking", ...}}
//
// This transformer deletes the thinking/reasoning fields from the request so the model never sees
// them. It deliberately does NOT touch `tools`/`tool_choice` — the issue-tracker's `tool_choice:"none"`
// workaround would disable tool calling, which is exactly the hook activity (PreToolUse/PostToolUse,
// seg_len) this testbed exists to collect.
//
// Mirrors the built-in `cleancache` transformer shape: transformRequest* receives the request object
// and returns it after mutation. Place LAST in a provider's `transformer.use` so it runs after the
// `openai` transformer has produced the outgoing body.

const FIELDS = ["thinking", "think", "reasoning", "reasoning_effort", "reasoning_content"];

function strip(obj) {
  if (!obj || typeof obj !== "object") return obj;
  // transformRequestIn gets the Anthropic body directly; transformRequestOut may pass {body, config}.
  const body = obj.body && typeof obj.body === "object" ? obj.body : obj;
  for (const f of FIELDS) {
    if (f in body) delete body[f];
  }
  return obj;
}

class StripThinking {
  name = "strip-thinking";

  constructor(options) {
    this.options = options || {};
  }

  async transformRequestIn(request) {
    return strip(request);
  }

  async transformRequestOut(request) {
    return strip(request);
  }
}

module.exports = StripThinking;

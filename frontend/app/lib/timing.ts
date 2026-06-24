// Client-side latency marks for one voice turn. Gated behind
// NEXT_PUBLIC_SARJY_TIMING=1 (build/runtime env) and OFF by default: when unset,
// startTurn() returns null and every mark/finish is a no-op — no measuring, no
// console output, no behavior change.
//
// The clock rule: client and server clocks are NOT synchronized, so we never
// subtract one machine's clock from the other's. Each side times itself with its
// own monotonic clock (performance.now() here, perf_counter() on the server). The
// transport leg is derived by subtracting two SAME-ORIGIN numbers:
//   network_leg = client_observed_roundtrip - server_total
// where client_observed_roundtrip = responseReceived - requestSent (client clock)
// and server_total comes from the Server-Timing header (server clock).

export const CLIENT_TIMING_ENABLED = process.env.NEXT_PUBLIC_SARJY_TIMING === "1";

export interface TurnTrace {
  turnStart: number; // user-perceived turn start (stopped speaking)
  requestSent: number | null;
  responseReceived: number | null;
  audioPlaying: number | null; // true "user heard sound" moment
  serverTiming: string | null; // raw Server-Timing header
}

export function startTurn(): TurnTrace | null {
  if (!CLIENT_TIMING_ENABLED) return null;
  return {
    turnStart: performance.now(),
    requestSent: null,
    responseReceived: null,
    audioPlaying: null,
    serverTiming: null,
  };
}

export function markRequestSent(trace: TurnTrace | null): void {
  if (trace) trace.requestSent = performance.now();
}

export function markResponseReceived(trace: TurnTrace | null, serverTiming: string | null): void {
  if (trace) {
    trace.responseReceived = performance.now();
    trace.serverTiming = serverTiming;
  }
}

export function markAudioPlaying(trace: TurnTrace | null): void {
  if (trace) trace.audioPlaying = performance.now();
}

function parseServerTiming(header: string | null): Record<string, number> {
  const out: Record<string, number> = {};
  if (!header) return out;
  for (const part of header.split(",")) {
    const segments = part.split(";").map((s) => s.trim());
    const name = segments[0];
    for (const segment of segments.slice(1)) {
      const match = segment.match(/dur=([\d.]+)/);
      if (match) out[name] = parseFloat(match[1]);
    }
  }
  return out;
}

export function finishTurn(trace: TurnTrace | null): void {
  if (!trace) return;
  const round = (n: number | null) => (n === null ? null : Math.round(n * 10) / 10);

  const serverStages = parseServerTiming(trace.serverTiming);
  const serverTotal = "server_total" in serverStages ? serverStages.server_total : null;

  const clientRoundtrip =
    trace.requestSent !== null && trace.responseReceived !== null
      ? trace.responseReceived - trace.requestSent
      : null;

  // Same-origin subtraction only — both spans measure the same interval from
  // each end, so the difference is request+response transport over the network.
  const networkLeg =
    clientRoundtrip !== null && serverTotal !== null ? clientRoundtrip - serverTotal : null;

  // The "playing" event only fires if audio actually started. If autoplay policy
  // rejected play() (audio.ts swallows that), audioPlaying stays null: we report
  // heard_sound=false and time_to_sound=null rather than a wrong/clean number.
  const heardSound = trace.audioPlaying !== null;
  // turn start -> user actually heard audio (STT+LLM+TTS+transport+playback start).
  const timeToSound = heardSound ? trace.audioPlaying! - trace.turnStart : null;

  const record = {
    source: "client",
    heard_sound: heardSound,
    client_roundtrip_ms: round(clientRoundtrip),
    server_total_ms: round(serverTotal),
    network_leg_ms: round(networkLeg),
    time_to_sound_ms: round(timeToSound),
    server_stages: serverStages,
  };
  console.log("[sarjy-timing]", JSON.stringify(record));
}

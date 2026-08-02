import type {
  DeleteMatchResult,
  LiveFramePayload,
  LiveFrameResult,
  MatchSummary,
  ProcessFilePayload,
  ProcessFileResult,
  ProcessJob,
  ProcessSamplePayload,
  SampleSource,
  SourceProbe,
  TacticalState,
  TrackCorrection,
  TrackCorrectionPayload,
} from "./types";

const apiToken = ((import.meta as unknown as { env?: Record<string, string | undefined> }).env?.VITE_PROJECT_FM_API_TOKEN ?? "").trim();

function apiHeaders(extra: HeadersInit = {}): HeadersInit {
  return apiToken ? { ...extra, "x-project-fm-token": apiToken } : extra;
}

export async function fetchHealth(): Promise<boolean> {
  try {
    const response = await fetch("/api/health", { headers: apiHeaders() });
    if (!response.ok) return false;
    const payload = (await response.json()) as { status?: string; mode?: string };
    return payload.status === "ok" && payload.mode !== "hosted-demo";
  } catch {
    return false;
  }
}

export async function fetchSamples(): Promise<SampleSource[]> {
  const response = await fetch("/api/samples", { headers: apiHeaders() });
  if (!response.ok) {
    throw await parseError(response, `Failed to fetch sample catalog: ${response.status}`);
  }
  return response.json();
}

async function parseError(response: Response, fallback: string): Promise<Error> {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") {
      return new Error(payload.detail);
    }
  } catch {
    return new Error(fallback);
  }
  return new Error(fallback);
}

export async function fetchLatestState(matchId: string): Promise<TacticalState> {
  const response = await fetch(`/api/matches/${matchId}/latest-state`, { headers: apiHeaders() });
  if (!response.ok) {
    throw await parseError(response, `Failed to fetch tactical state: ${response.status}`);
  }
  return response.json();
}

export async function fetchMatchSummary(matchId: string): Promise<MatchSummary> {
  const response = await fetch(`/api/matches/${matchId}/summary`, { headers: apiHeaders() });
  if (!response.ok) {
    throw new Error(`Failed to fetch match summary: ${response.status}`);
  }
  return response.json();
}

export async function fetchMatchStates(matchId: string, limit = 360): Promise<TacticalState[]> {
  const response = await fetch(`/api/matches/${matchId}/states?limit=${limit}`, { headers: apiHeaders() });
  if (!response.ok) {
    throw new Error(`Failed to fetch match timeline: ${response.status}`);
  }
  return response.json();
}

export async function processMatchFile(
  matchId: string,
  payload: ProcessFilePayload,
): Promise<ProcessFileResult> {
  const response = await fetch(`/api/matches/${matchId}/process-file`, {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await parseError(response, `Failed to process match file: ${response.status}`);
  }
  return response.json();
}

export async function startProcessMatchFileJob(
  matchId: string,
  payload: ProcessFilePayload,
): Promise<ProcessJob> {
  const response = await fetch(`/api/matches/${matchId}/process-file-job`, {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await parseError(response, `Failed to start process job: ${response.status}`);
  }
  return response.json();
}

export async function startProcessSampleJob(
  matchId: string,
  payload: ProcessSamplePayload,
): Promise<ProcessJob> {
  const response = await fetch(`/api/matches/${matchId}/process-sample-job`, {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await parseError(response, `Failed to start sample processing: ${response.status}`);
  }
  return response.json();
}

export async function fetchProcessJob(jobId: string): Promise<ProcessJob> {
  const response = await fetch(`/api/process-jobs/${jobId}`, { headers: apiHeaders() });
  if (!response.ok) {
    throw await parseError(response, `Failed to fetch process job: ${response.status}`);
  }
  return response.json();
}

export async function sendLiveFrame(matchId: string, payload: LiveFramePayload): Promise<LiveFrameResult> {
  const response = await fetch(`/api/matches/${matchId}/live-frame`, {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await parseError(response, `Failed to send live frame: ${response.status}`);
  }
  return response.json();
}

export async function probeMatchFile(
  matchId: string,
  payload: { path: string | null; source_type: "file" | "stream_url"; stream_url: string | null; fps_hint: number | null },
): Promise<SourceProbe> {
  const response = await fetch(`/api/matches/${matchId}/probe-file`, {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await parseError(response, `Failed to probe match file: ${response.status}`);
  }
  return response.json();
}

export async function deleteMatch(matchId: string): Promise<DeleteMatchResult> {
  const response = await fetch(`/api/matches/${matchId}`, { method: "DELETE", headers: apiHeaders() });
  if (!response.ok) {
    throw await parseError(response, `Failed to reset match: ${response.status}`);
  }
  return response.json();
}

export async function fetchTrackCorrections(matchId: string): Promise<TrackCorrection[]> {
  const response = await fetch(`/api/matches/${matchId}/track-corrections`, { headers: apiHeaders() });
  if (!response.ok) {
    throw await parseError(response, `Failed to fetch track corrections: ${response.status}`);
  }
  return response.json();
}

export async function saveTrackCorrection(
  matchId: string,
  trackId: string,
  payload: TrackCorrectionPayload,
): Promise<TrackCorrection> {
  const response = await fetch(`/api/matches/${matchId}/tracks/${trackId}/correction`, {
    method: "PATCH",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await parseError(response, `Failed to save track correction: ${response.status}`);
  }
  return response.json();
}

export async function clearTrackCorrection(matchId: string, trackId: string): Promise<void> {
  const response = await fetch(`/api/matches/${matchId}/tracks/${trackId}/correction`, {
    method: "DELETE",
    headers: apiHeaders(),
  });
  if (!response.ok) {
    throw await parseError(response, `Failed to clear track correction: ${response.status}`);
  }
}

export async function downloadMatchExport(matchId: string, format: "csv" | "jsonl"): Promise<void> {
  const response = await fetch(`/api/matches/${matchId}/export.${format}`, { headers: apiHeaders() });
  if (!response.ok) {
    throw await parseError(response, `Failed to export match: ${response.status}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${matchId}-tactical-states.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

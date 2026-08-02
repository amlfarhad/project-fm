import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Monitor, Radio, RefreshCw } from "lucide-react";
import {
  clearTrackCorrection,
  deleteMatch,
  downloadMatchExport,
  fetchHealth,
  fetchLatestState,
  fetchMatchStates,
  fetchMatchSummary,
  fetchProcessJob,
  fetchSamples,
  fetchTrackCorrections,
  probeMatchFile,
  saveTrackCorrection,
  sendLiveFrame,
  startProcessMatchFileJob,
  startProcessSampleJob,
} from "./api";
import { AnalystView } from "./views/AnalystView";
import { ManagerView } from "./views/ManagerView";
import type {
  LiveFramePayload,
  LiveFrameResult,
  MatchSummary,
  ProcessFilePayload,
  ProcessFileResult,
  ProcessJob,
  ProcessSamplePayload,
  RuntimeMode,
  SampleSource,
  SourceProbe,
  StaticSampleArtifact,
  TacticalState,
  TrackCorrection,
  TrackCorrectionPayload,
} from "./types";

type ViewMode = "manager" | "analyst";

const DEFAULT_SAMPLE: SampleSource = {
  id: "commons-galatasaray-2008",
  label: "Galatasaray–Steaua match clip / 2008",
  description: "A bounded public-domain match clip used to exercise the real OpenCV reconstruction path.",
  source_kind: "real_video",
  video_url: "/samples/galatasaray-steau-2008-12s.mp4",
  artifact_url: "/samples/galatasaray-steau-2008-12s.states.json",
  local_path: "",
  duration_ms: 12_000,
  width: 640,
  height: 480,
  fps: 30,
  license: "Public domain",
  license_url: "https://creativecommons.org/public-domain/mark/1.0/",
  source_reference: "https://commons.wikimedia.org/wiki/File:Galatasaray-Steau_Bükreş-1.ogv",
  attribution: "Original uploader Qwl; source clip released into the public domain.",
  default_sample_every_ms: 1000,
  processing_note: "Hosted demo serves the artifact produced by the OpenCV pipeline; local runs reprocess the clip.",
};

function emptyTacticalState(matchId: string): TacticalState {
  return {
    match_id: matchId,
    timestamp_ms: 0,
    frame_id: "no-ingest",
    phase: "unknown",
    ball: null,
    players: [],
    pitch_calibration: { status: "lost", confidence: 0, source: "none" },
    system_confidence: 0,
  };
}

function sampleProbe(sample: SampleSource): SourceProbe {
  return {
    source_id: `${sample.id}:sample`,
    path: sample.video_url,
    width: sample.width,
    height: sample.height,
    fps: sample.fps,
    duration_ms: sample.duration_ms,
    frame_count: Math.round((sample.duration_ms / 1000) * sample.fps),
    backend: "opencv",
    warnings: [],
  };
}

function applyCorrections(states: TacticalState[], corrections: TrackCorrection[]): TacticalState[] {
  const byTrack = new Map(corrections.map((correction) => [correction.track_id, correction]));
  return states.map((state) => ({
    ...state,
    players: state.players.map((player) => {
      const correction = byTrack.get(player.track_id);
      if (!correction) return player;
      return {
        ...player,
        team: correction.team,
        shirt_number: correction.shirt_number,
        player_name: correction.player_name,
        role_hint: correction.role_hint,
        confidence: Math.max(player.confidence, 0.92),
        position_status: "corrected",
      };
    }),
  }));
}

function summaryForStates(summary: MatchSummary, states: TacticalState[], corrections: TrackCorrection[]): MatchSummary {
  const latest = states.length > 0 ? states[states.length - 1] : null;
  const observed = latest?.players.filter((player) => player.observed).length ?? null;
  const estimated = latest && observed !== null ? latest.players.length - observed : null;
  const numbered = latest?.players.filter((player) => player.shirt_number !== null).length ?? null;
  const observedNumbered = latest?.players.filter((player) => player.observed && player.shirt_number !== null).length ?? null;
  const named = latest?.players.filter((player) => Boolean(player.player_name)).length ?? null;
  const identity = latest?.players.length
    ? ((numbered ?? 0) + (named ?? 0)) / (latest.players.length * 2)
    : null;
  const observedIdentity = observed ? (observedNumbered ?? 0) / observed : null;
  return {
    ...summary,
    states: states.length,
    latest_timestamp_ms: latest?.timestamp_ms ?? null,
    latest_frame_id: latest?.frame_id ?? null,
    system_confidence: latest?.system_confidence ?? null,
    calibration_status: latest?.pitch_calibration.status ?? null,
    calibration_confidence: latest?.pitch_calibration.confidence ?? null,
    calibration_source: latest?.pitch_calibration.source ?? null,
    observed_players: observed,
    estimated_players: estimated,
    shirt_numbered_players: numbered,
    observed_shirt_numbered_players: observedNumbered,
    named_players: named,
    identity_coverage: identity === null ? null : Number(identity.toFixed(3)),
    observed_identity_coverage: observedIdentity === null ? null : Number(observedIdentity.toFixed(3)),
    corrections: corrections.length,
  };
}

function resultForArtifact(artifact: StaticSampleArtifact): ProcessFileResult {
  const summary = artifact.summary;
  return {
    match_id: artifact.sample_id,
    source_id: `${artifact.sample_id}:sample`,
    states_written: artifact.states.length,
    replaced_states: 0,
    first_timestamp_ms: artifact.states[0]?.timestamp_ms ?? null,
    latest_timestamp_ms: artifact.states.length > 0 ? artifact.states[artifact.states.length - 1].timestamp_ms : null,
    processing_elapsed_ms: summary.processing_elapsed_ms ?? artifact.generated_elapsed_ms,
    processing_fps: summary.processing_fps,
    realtime_factor: summary.realtime_factor,
    cache_hit: true,
    processor_backend: artifact.provenance.processor_backend ?? "opencv",
    probe: sampleProbe(DEFAULT_SAMPLE),
    provenance: artifact.provenance,
  };
}

function csvSafe(value: string): string {
  return ["=", "+", "-", "@"].some((prefix) => value.startsWith(prefix)) ? `'${value}` : value;
}

function downloadStaticExport(matchId: string, states: TacticalState[], format: "csv" | "jsonl") {
  const body =
    format === "jsonl"
      ? states.map((state) => JSON.stringify(state)).join("\n") + "\n"
      : [
          [
            "match_id",
            "timestamp_ms",
            "frame_id",
            "phase",
            "track_id",
            "team",
            "shirt_number",
            "role_hint",
            "player_name",
            "pitch_x",
            "pitch_y",
            "position_status",
            "observed",
            "confidence",
            "calibration_confidence",
            "system_confidence",
          ].join(","),
          ...states.flatMap((state) =>
            state.players.map((player) =>
              [
                state.match_id,
                state.timestamp_ms,
                state.frame_id,
                state.phase,
                player.track_id,
                player.team,
                player.shirt_number ?? "",
                player.role_hint,
                csvSafe(player.player_name ?? ""),
                player.pitch_x,
                player.pitch_y,
                player.position_status ?? (player.observed ? "observed" : "inferred"),
                player.observed,
                player.confidence,
                state.pitch_calibration.confidence,
                state.system_confidence,
              ].join(","),
            ),
          ),
        ].join("\n");
  const blob = new Blob([body], { type: format === "jsonl" ? "application/x-ndjson" : "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${matchId}-tactical-states.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected Project FM error";
}

const sleep = (duration: number) => new Promise((resolve) => window.setTimeout(resolve, duration));

export default function App() {
  const [mode, setMode] = useState<ViewMode>("manager");
  const [matchId, setMatchId] = useState("dev");
  const [state, setState] = useState<TacticalState | null>(null);
  const [summary, setSummary] = useState<MatchSummary | null>(null);
  const [timeline, setTimeline] = useState<TacticalState[]>([]);
  const [selectedTimestamp, setSelectedTimestamp] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [probing, setProbing] = useState(false);
  const [exporting, setExporting] = useState<"csv" | "jsonl" | null>(null);
  const [probe, setProbe] = useState<SourceProbe | null>(null);
  const [processResult, setProcessResult] = useState<ProcessFileResult | null>(null);
  const [processJob, setProcessJob] = useState<ProcessJob | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [trackCorrections, setTrackCorrections] = useState<TrackCorrection[]>([]);
  const [correctionError, setCorrectionError] = useState<string | null>(null);
  const [correctingTrackId, setCorrectingTrackId] = useState<string | null>(null);
  const [runtimeMode, setRuntimeMode] = useState<RuntimeMode>("local");
  const [sample, setSample] = useState<SampleSource>(DEFAULT_SAMPLE);
  const [staticArtifact, setStaticArtifact] = useState<StaticSampleArtifact | null>(null);
  const [sampleLoaded, setSampleLoaded] = useState(false);
  const [booting, setBooting] = useState(true);

  const visibleState = useMemo(() => {
    if (selectedTimestamp === null) return state;
    return timeline.find((item) => item.timestamp_ms === selectedTimestamp) ?? state;
  }, [selectedTimestamp, state, timeline]);

  function showStaticArtifact(artifact: StaticSampleArtifact, corrections = trackCorrections) {
    const correctedTimeline = applyCorrections(artifact.states, corrections);
    setStaticArtifact(artifact);
    setTimeline(correctedTimeline);
    setState(correctedTimeline.length > 0 ? correctedTimeline[correctedTimeline.length - 1] : null);
    setSummary(summaryForStates(artifact.summary, correctedTimeline, corrections));
    setProbe(sampleProbe(sample));
    setProcessResult(resultForArtifact(artifact));
    setSampleLoaded(true);
    setSelectedTimestamp(null);
  }

  async function loadHostedSample() {
    setProcessing(true);
    setIngestError(null);
    setProcessJob(null);
    try {
      const response = await fetch(sample.artifact_url);
      if (!response.ok) throw new Error(`Hosted proof artifact unavailable: ${response.status}`);
      const artifact = (await response.json()) as StaticSampleArtifact;
      const startedAt = Date.now();
      const baseJob: ProcessJob = {
        job_id: `hosted-${Date.now()}`,
        match_id: artifact.sample_id,
        status: "running",
        progress: 0.12,
        frames_processed: 0,
        total_frames: artifact.states.length,
        started_at_ms: startedAt,
        updated_at_ms: startedAt,
        completed_at_ms: null,
        error: null,
        result: null,
      };
      setProcessJob(baseJob);
      await sleep(180);
      setProcessJob({ ...baseJob, progress: 0.48, frames_processed: Math.max(1, Math.round(artifact.states.length * 0.45)) });
      await sleep(180);
      showStaticArtifact(artifact, []);
      const result = resultForArtifact(artifact);
      setProcessJob({
        ...baseJob,
        status: "succeeded",
        progress: 1,
        frames_processed: artifact.states.length,
        updated_at_ms: Date.now(),
        completed_at_ms: Date.now(),
        result,
      });
      setMatchId(artifact.sample_id);
      setRuntimeMode("hosted-demo");
    } catch (loadError) {
      setIngestError(errorMessage(loadError));
    } finally {
      setProcessing(false);
    }
  }

  async function loadState() {
    if (runtimeMode === "hosted-demo") {
      if (staticArtifact) showStaticArtifact(staticArtifact);
      return;
    }
    try {
      setError(null);
      const [nextSummary, nextTimeline] = await Promise.all([fetchMatchSummary(matchId), fetchMatchStates(matchId)]);
      let nextState: TacticalState | null = null;
      try {
        nextState = await fetchLatestState(matchId);
      } catch (loadError) {
        if (!(loadError instanceof Error) || !loadError.message.includes("No stored tactical states")) throw loadError;
      }
      setState(nextState);
      setSummary(nextSummary);
      setTimeline(nextTimeline);
      setSelectedTimestamp((current) =>
        current !== null && nextTimeline.some((item) => item.timestamp_ms === current) ? current : null,
      );
    } catch (loadError) {
      setError(errorMessage(loadError));
    }
  }

  async function loadCorrections() {
    if (runtimeMode === "hosted-demo") return;
    try {
      setCorrectionError(null);
      setTrackCorrections(await fetchTrackCorrections(matchId));
    } catch (loadError) {
      setCorrectionError(errorMessage(loadError));
    }
  }

  async function ingestFile(payload: ProcessFilePayload) {
    if (runtimeMode === "hosted-demo") {
      setIngestError("The hosted proof is read-only. Run the repository locally to process another video.");
      return;
    }
    setProcessing(true);
    setProcessResult(null);
    setProcessJob(null);
    setIngestError(null);
    try {
      setProcessJob(await startProcessMatchFileJob(matchId, payload));
    } catch (loadError) {
      setIngestError(errorMessage(loadError));
      setProcessing(false);
    }
  }

  async function processSample() {
    setIngestError(null);
    if (runtimeMode === "hosted-demo") {
      await loadHostedSample();
      return;
    }
    setProcessing(true);
    setProcessResult(null);
    setProcessJob(null);
    try {
      setProcessJob(
        await startProcessSampleJob(matchId, {
          sample_id: sample.id,
          duration_ms: sample.duration_ms,
          sample_every_ms: sample.default_sample_every_ms,
          fps_hint: sample.fps,
          replace_existing: true,
          use_cache: true,
        }),
      );
    } catch (loadError) {
      setIngestError(errorMessage(loadError));
      setProcessing(false);
    }
  }

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      const local = await fetchHealth();
      if (!active) return;
      setRuntimeMode(local ? "local" : "hosted-demo");
      if (local) {
        try {
          const samples = await fetchSamples();
          if (active && samples[0]) setSample(samples[0]);
        } catch {
          // The built-in catalog remains available if the optional endpoint is unavailable.
        }
      }
      if (active) setBooting(false);
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (booting || runtimeMode !== "local") return;
    void loadState();
    void loadCorrections();
    const timer = window.setInterval(() => void loadState(), 2000);
    return () => window.clearInterval(timer);
  }, [booting, runtimeMode, matchId]);

  useEffect(() => {
    if (runtimeMode !== "local" || !processJob || !["queued", "running"].includes(processJob.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const nextJob = await fetchProcessJob(processJob.job_id);
        setProcessJob(nextJob);
        if (nextJob.status === "succeeded" && nextJob.result) {
          setProcessResult(nextJob.result);
          setProbe(nextJob.result.probe);
          setSelectedTimestamp(null);
          setProcessing(false);
          await loadState();
        }
        if (nextJob.status === "failed") {
          setIngestError(nextJob.error ?? "Processing job failed");
          setProcessing(false);
        }
      } catch (loadError) {
        setIngestError(errorMessage(loadError));
        setProcessing(false);
      }
    }, 350);
    return () => window.clearInterval(timer);
  }, [processJob, runtimeMode]);

  async function resetMatch() {
    setResetting(true);
    setProcessResult(null);
    setProcessJob(null);
    setIngestError(null);
    try {
      if (runtimeMode === "hosted-demo") {
        setStaticArtifact(null);
        setSampleLoaded(false);
        setState(null);
        setSummary(null);
        setTimeline([]);
        setProbe(null);
        setTrackCorrections([]);
      } else {
        await deleteMatch(matchId);
        setProbe(null);
        setTimeline([]);
        setSummary(null);
        setTrackCorrections([]);
        setSelectedTimestamp(null);
        await loadState();
      }
    } catch (loadError) {
      setIngestError(errorMessage(loadError));
    } finally {
      setResetting(false);
    }
  }

  async function exportMatch(format: "csv" | "jsonl") {
    setExporting(format);
    setIngestError(null);
    try {
      if (runtimeMode === "hosted-demo") downloadStaticExport(matchId, timeline, format);
      else await downloadMatchExport(matchId, format);
    } catch (loadError) {
      setIngestError(errorMessage(loadError));
    } finally {
      setExporting(null);
    }
  }

  function changeMatchId(nextMatchId: string) {
    setMatchId(nextMatchId);
    setProbe(null);
    setProcessResult(null);
    setProcessJob(null);
    setIngestError(null);
    setCorrectionError(null);
    setSelectedTimestamp(null);
  }

  async function applyTrackCorrection(trackId: string, payload: TrackCorrectionPayload) {
    setCorrectingTrackId(trackId);
    setCorrectionError(null);
    try {
      if (runtimeMode === "hosted-demo") {
        const correction: TrackCorrection = { track_id: trackId, ...payload, corrected_at_ms: Date.now() };
        const nextCorrections = [...trackCorrections.filter((item) => item.track_id !== trackId), correction];
        setTrackCorrections(nextCorrections);
        if (staticArtifact) showStaticArtifact(staticArtifact, nextCorrections);
      } else {
        await saveTrackCorrection(matchId, trackId, payload);
        await Promise.all([loadState(), loadCorrections()]);
      }
    } catch (loadError) {
      setCorrectionError(errorMessage(loadError));
    } finally {
      setCorrectingTrackId(null);
    }
  }

  async function removeTrackCorrection(trackId: string) {
    setCorrectingTrackId(trackId);
    setCorrectionError(null);
    try {
      if (runtimeMode === "hosted-demo") {
        const nextCorrections = trackCorrections.filter((item) => item.track_id !== trackId);
        setTrackCorrections(nextCorrections);
        if (staticArtifact) showStaticArtifact(staticArtifact, nextCorrections);
      } else {
        await clearTrackCorrection(matchId, trackId);
        await Promise.all([loadState(), loadCorrections()]);
      }
    } catch (loadError) {
      setCorrectionError(errorMessage(loadError));
    } finally {
      setCorrectingTrackId(null);
    }
  }

  async function probeFile(
    source: { path: string | null; source_type: "file" | "stream_url"; stream_url: string | null },
    fpsHint: number | null,
  ) {
    if (runtimeMode === "hosted-demo") {
      setIngestError("The hosted proof accepts the repository sample only. Use local mode for a new source.");
      return null;
    }
    setProbing(true);
    setProbe(null);
    setProcessResult(null);
    setProcessJob(null);
    setIngestError(null);
    try {
      const result = await probeMatchFile(matchId, { ...source, fps_hint: fpsHint });
      setProbe(result);
      return result;
    } catch (loadError) {
      setIngestError(errorMessage(loadError));
      return null;
    } finally {
      setProbing(false);
    }
  }

  async function ingestLiveFrame(payload: LiveFramePayload): Promise<LiveFrameResult> {
    if (runtimeMode === "hosted-demo") throw new Error("Browser capture is available when Project FM runs locally.");
    const result = await sendLiveFrame(matchId, payload);
    setState(result.state);
    setSelectedTimestamp(null);
    if (result.states_written % 2 === 0) await loadState();
    return result;
  }

  if (booting) {
    return <div className="loading-shell"><div className="skeleton skeleton-title" /><div className="skeleton skeleton-pitch" /></div>;
  }

  if (error) {
    return (
      <div className="center-state center-state-panel">
        <AlertTriangle size={22} />
        <div>
          <p className="eyebrow">Connection interrupted</p>
          <h1>Backend unavailable</h1>
          <p>{error}</p>
          <button className="inline-action" onClick={() => void loadState()}><RefreshCw size={16} /> Retry connection</button>
        </div>
      </div>
    );
  }

  const analystState = visibleState ?? emptyTacticalState(matchId);

  return (
    <div className="app-shell">
      <nav className="mode-switch" aria-label="View mode">
        <button className={mode === "manager" ? "active" : ""} onClick={() => setMode("manager")}><Radio size={16} /> Manager</button>
        <button className={mode === "analyst" ? "active" : ""} onClick={() => setMode("analyst")}><Monitor size={16} /> Analyst</button>
      </nav>
      {mode === "manager" && !visibleState ? (
        <main className="landing-shell">
          <section className="landing-copy">
            <p className="eyebrow">Project FM / evidence-first reconstruction</p>
            <h1>From accessible match video to a reviewable tactical state.</h1>
            <p className="landing-lede">A bounded football video enters the same sampling, detection, tracking, and pitch-mapping path used by local runs. The manager view stays clean; the analyst view shows what was observed, inferred, corrected, or unavailable.</p>
            <div className="landing-actions">
              <button className="primary-action landing-primary" onClick={() => void processSample()}><Radio size={16} /> Open the repository sample</button>
              <button className="inline-action" onClick={() => setMode("analyst")}><Monitor size={16} /> Open analyst console</button>
            </div>
            <div className="landing-proof"><span><strong>12s</strong> bounded input</span><span><strong>OpenCV</strong> real pipeline</span><span><strong>{runtimeMode === "hosted-demo" ? "precomputed" : "local"}</strong> execution boundary</span></div>
          </section>
          <aside className="landing-card" aria-label="Sample provenance">
            <p className="section-kicker">Primary proof</p>
            <h2>{sample.label}</h2>
            <p>{sample.description}</p>
            <dl className="provenance-list"><div><dt>Source</dt><dd>{sample.license}</dd></div><div><dt>Input</dt><dd>640 × 480 · 30 fps</dd></div><div><dt>Boundary</dt><dd>{runtimeMode === "hosted-demo" ? "Hosted artifact, not live" : "Local processing available"}</dd></div></dl>
            <a href={sample.source_reference} target="_blank" rel="noreferrer">View source and rights ↗</a>
          </aside>
        </main>
      ) : mode === "manager" && visibleState ? (
        <ManagerView state={visibleState} summary={summary} runtimeMode={runtimeMode} sampleLoaded={sampleLoaded} />
      ) : (
        <AnalystView
          matchId={matchId}
          state={analystState}
          summary={summary}
          timeline={timeline}
          selectedTimestamp={selectedTimestamp}
          processing={processing}
          resetting={resetting}
          probing={probing}
          exporting={exporting}
          probe={probe}
          processResult={processResult}
          processJob={processJob}
          trackCorrections={trackCorrections}
          ingestError={ingestError}
          correctionError={correctionError}
          correctingTrackId={correctingTrackId}
          runtimeMode={runtimeMode}
          sample={sample}
          sampleLoaded={sampleLoaded}
          onLoadSample={() => void processSample()}
          onMatchIdChange={changeMatchId}
          onTimelineSelect={setSelectedTimestamp}
          onRefresh={() => void loadState()}
          onProbeFile={probeFile}
          onIngestFile={ingestFile}
          onResetMatch={resetMatch}
          onExportMatch={exportMatch}
          onLiveFrame={ingestLiveFrame}
          onApplyTrackCorrection={applyTrackCorrection}
          onClearTrackCorrection={removeTrackCorrection}
        />
      )}
    </div>
  );
}

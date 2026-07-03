import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  Activity,
  AlertCircle,
  FileSearch,
  FileVideo,
  Gauge,
  Download,
  Play,
  RefreshCw,
  Save,
  ScanLine,
  ScreenShare,
  ShieldAlert,
  Square,
  TimerReset,
  Trash2,
  Undo2,
} from "lucide-react";
import { Pitch } from "../components/Pitch";
import type {
  MatchSummary,
  LiveFramePayload,
  LiveFrameResult,
  ProcessFilePayload,
  ProcessFileResult,
  ProcessJob,
  RoleHint,
  SourceProbe,
  TacticalState,
  Team,
  TrackCorrection,
  TrackCorrectionPayload,
} from "../types";

interface AnalystViewProps {
  matchId: string;
  state: TacticalState;
  summary: MatchSummary | null;
  timeline: TacticalState[];
  selectedTimestamp: number | null;
  processing: boolean;
  resetting: boolean;
  probing: boolean;
  exporting: "csv" | "jsonl" | null;
  probe: SourceProbe | null;
  processResult: ProcessFileResult | null;
  processJob: ProcessJob | null;
  trackCorrections: TrackCorrection[];
  ingestError: string | null;
  correctionError: string | null;
  correctingTrackId: string | null;
  onMatchIdChange: (matchId: string) => void;
  onTimelineSelect: (timestamp: number | null) => void;
  onRefresh: () => void;
  onProbeFile: (
    source: { path: string | null; source_type: "file" | "stream_url"; stream_url: string | null },
    fpsHint: number | null,
  ) => Promise<SourceProbe | null>;
  onIngestFile: (payload: ProcessFilePayload) => Promise<void>;
  onResetMatch: () => Promise<void>;
  onExportMatch: (format: "csv" | "jsonl") => Promise<void>;
  onLiveFrame: (payload: LiveFramePayload) => Promise<LiveFrameResult>;
  onApplyTrackCorrection: (trackId: string, payload: TrackCorrectionPayload) => Promise<void>;
  onClearTrackCorrection: (trackId: string) => Promise<void>;
}

type CorrectionDraft = {
  team: Team;
  shirt_number: string;
  player_name: string;
  role_hint: RoleHint;
};

const teamOptions: Team[] = ["home", "away", "referee", "unknown"];
const roleOptions: RoleHint[] = ["goalkeeper", "defender", "midfielder", "forward", "referee", "unknown"];

export function AnalystView({
  matchId,
  state,
  summary,
  timeline,
  selectedTimestamp,
  processing,
  resetting,
  probing,
  exporting,
  probe,
  processResult,
  processJob,
  trackCorrections,
  ingestError,
  correctionError,
  correctingTrackId,
  onMatchIdChange,
  onTimelineSelect,
  onRefresh,
  onProbeFile,
  onIngestFile,
  onResetMatch,
  onExportMatch,
  onLiveFrame,
  onApplyTrackCorrection,
  onClearTrackCorrection,
}: AnalystViewProps) {
  const [filePath, setFilePath] = useState("");
  const [sourceMode, setSourceMode] = useState<"file" | "stream_url">("file");
  const [durationMinutes, setDurationMinutes] = useState<number | "">("");
  const [sampleEveryMs, setSampleEveryMs] = useState(1000);
  const [fpsHint, setFpsHint] = useState<number | "">("");
  const [replaceExisting, setReplaceExisting] = useState(true);
  const [useCache, setUseCache] = useState(true);
  const [liveStatus, setLiveStatus] = useState<"idle" | "requesting" | "running" | "stopping">("idle");
  const [liveSampleMs, setLiveSampleMs] = useState(1000);
  const [liveReplaceTimeline, setLiveReplaceTimeline] = useState(true);
  const [liveSourceLabel, setLiveSourceLabel] = useState("browser-tab");
  const [liveFrames, setLiveFrames] = useState(0);
  const [liveLatencyMs, setLiveLatencyMs] = useState<number | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [correctionDrafts, setCorrectionDrafts] = useState<Record<string, CorrectionDraft>>({});
  const captureVideoRef = useRef<HTMLVideoElement | null>(null);
  const captureCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const captureStreamRef = useRef<MediaStream | null>(null);
  const captureRunningRef = useRef(false);
  const captureStartedAtRef = useRef(0);
  const liveSampleMsRef = useRef(liveSampleMs);
  const liveSourceLabelRef = useRef(liveSourceLabel);
  const correctionByTrack = useMemo(
    () => new Map(trackCorrections.map((correction) => [correction.track_id, correction])),
    [trackCorrections],
  );
  const flaggedTracks = state.players.filter(
    (player) => player.confidence < 0.7 || correctionByTrack.has(player.track_id),
  );
  const observed = state.players.filter((player) => player.observed).length;
  const estimated = state.players.length - observed;
  const currentMinute = Math.floor(state.timestamp_ms / 60000);
  const currentSecond = Math.floor((state.timestamp_ms % 60000) / 1000)
    .toString()
    .padStart(2, "0");
  const timelineMax = timeline.length > 0 ? timeline[timeline.length - 1].timestamp_ms : 0;
  const canUseSource = filePath.trim().length > 0;
  const sourceLabel = sourceMode === "file" ? "Full-match file path" : "Stream URL";
  const sourcePlaceholder = sourceMode === "file" ? "/absolute/path/to/match.mp4" : "rtsp://, http://, or capture URL";
  const sourceDurationMinutes = probe?.duration_ms ? Math.round(probe.duration_ms / 60000) : null;
  const sourceResolution = probe?.width && probe.height ? `${probe.width}x${probe.height}` : "unknown";
  const progressPercent = processJob ? Math.round(processJob.progress * 100) : 0;
  const jobFrames =
    processJob?.total_frames && processJob.total_frames > 0
      ? `${processJob.frames_processed}/${processJob.total_frames}`
      : `${processJob?.frames_processed ?? 0}`;

  useEffect(() => {
    liveSampleMsRef.current = liveSampleMs;
  }, [liveSampleMs]);

  useEffect(() => {
    liveSourceLabelRef.current = liveSourceLabel;
  }, [liveSourceLabel]);

  useEffect(() => () => stopBrowserCapture(), []);

  function draftForTrack(player: TacticalState["players"][number]): CorrectionDraft {
    const existing = correctionByTrack.get(player.track_id);
    return (
      correctionDrafts[player.track_id] ?? {
        team: existing?.team ?? player.team,
        shirt_number: existing?.shirt_number?.toString() ?? player.shirt_number?.toString() ?? "",
        player_name: existing?.player_name ?? player.player_name ?? "",
        role_hint: existing?.role_hint ?? player.role_hint,
      }
    );
  }

  function updateDraft(trackId: string, draft: CorrectionDraft) {
    setCorrectionDrafts((current) => ({ ...current, [trackId]: draft }));
  }

  async function saveCorrection(player: TacticalState["players"][number]) {
    const draft = draftForTrack(player);
    await onApplyTrackCorrection(player.track_id, {
      team: draft.team,
      shirt_number: draft.shirt_number === "" ? null : Number(draft.shirt_number),
      player_name: draft.player_name.trim() === "" ? null : draft.player_name.trim(),
      role_hint: draft.role_hint,
    });
  }

  async function clearCorrection(trackId: string) {
    await onClearTrackCorrection(trackId);
    setCorrectionDrafts((current) => {
      const next = { ...current };
      delete next[trackId];
      return next;
    });
  }

  async function probeSource() {
    if (!canUseSource) {
      return;
    }
    const result = await onProbeFile(
      {
        path: sourceMode === "file" ? filePath.trim() : null,
        source_type: sourceMode,
        stream_url: sourceMode === "stream_url" ? filePath.trim() : null,
      },
      fpsHint === "" ? null : fpsHint,
    );
    if (result?.duration_ms) {
      setDurationMinutes(Math.max(1, Math.round(result.duration_ms / 60000)));
    }
    if (result?.fps) {
      setFpsHint(Number(result.fps.toFixed(2)));
    }
  }

  async function submitIngest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onIngestFile({
      path: sourceMode === "file" ? filePath.trim() : null,
      source_type: sourceMode,
      stream_url: sourceMode === "stream_url" ? filePath.trim() : null,
      duration_ms: durationMinutes === "" ? null : durationMinutes * 60 * 1000,
      sample_every_ms: sampleEveryMs,
      fps_hint: fpsHint === "" ? null : fpsHint,
      replace_existing: replaceExisting,
      use_cache: useCache,
    });
  }

  function stopBrowserCapture() {
    captureRunningRef.current = false;
    captureStreamRef.current?.getTracks().forEach((track) => track.stop());
    captureStreamRef.current = null;
    if (captureVideoRef.current) {
      captureVideoRef.current.srcObject = null;
    }
    setLiveStatus("idle");
  }

  async function sendCapturedFrame() {
    const video = captureVideoRef.current;
    const canvas = captureCanvasRef.current;
    if (!video || !canvas || !captureRunningRef.current || video.videoWidth === 0 || video.videoHeight === 0) {
      return;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) {
      throw new Error("Browser canvas capture is unavailable");
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = canvas.toDataURL("image/jpeg", 0.72);
    const timestampMs = Math.max(0, Math.round(performance.now() - captureStartedAtRef.current));
    const startedAt = performance.now();
    const result = await onLiveFrame({
      image_data: imageData,
      timestamp_ms: timestampMs,
      width: canvas.width,
      height: canvas.height,
      source_label: liveSourceLabelRef.current,
      fps_hint: Number((1000 / liveSampleMsRef.current).toFixed(2)),
    });
    setLiveFrames(result.states_written);
    setLiveLatencyMs(Math.round(performance.now() - startedAt));
  }

  async function captureLoop() {
    while (captureRunningRef.current) {
      try {
        await sendCapturedFrame();
        setLiveError(null);
      } catch (err) {
        setLiveError(err instanceof Error ? err.message : "Live frame processing failed");
      }
      await new Promise((resolve) => window.setTimeout(resolve, liveSampleMsRef.current));
    }
  }

  async function startBrowserCapture() {
    if (!navigator.mediaDevices?.getDisplayMedia) {
      setLiveError("Screen capture is not available in this browser.");
      return;
    }
    setLiveStatus("requesting");
    setLiveError(null);
    setLiveFrames(0);
    setLiveLatencyMs(null);
    try {
      if (liveReplaceTimeline) {
        await onResetMatch();
      }
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          frameRate: Math.max(1, Math.min(6, Math.round(1000 / liveSampleMs))),
        },
        audio: false,
      });
      captureStreamRef.current = stream;
      const [track] = stream.getVideoTracks();
      if (track) {
        track.addEventListener("ended", stopBrowserCapture, { once: true });
      }
      if (!captureVideoRef.current) {
        throw new Error("Capture video element is unavailable");
      }
      captureVideoRef.current.srcObject = stream;
      await captureVideoRef.current.play();
      captureStartedAtRef.current = performance.now();
      captureRunningRef.current = true;
      setLiveStatus("running");
      void captureLoop();
    } catch (err) {
      stopBrowserCapture();
      setLiveError(err instanceof Error ? err.message : "Browser capture was cancelled");
    }
  }

  return (
    <main className="analyst-shell">
      <section className="analyst-header">
        <div>
          <p className="eyebrow">Operator Console</p>
          <h1>Live Reconstruction Control</h1>
        </div>
        <div className="analyst-actions">
          <span className="health-chip">
            <Gauge size={16} /> {(state.system_confidence * 100).toFixed(0)}% confidence
          </span>
          <button className="icon-button" onClick={onRefresh} aria-label="Refresh state">
            <RefreshCw size={18} />
          </button>
        </div>
      </section>
      <section className="analyst-grid">
        <div className="panel panel-pitch">
          <div className="panel-heading">
            <h2>Pitch State</h2>
            <span>{currentMinute}:{currentSecond} · {state.phase.replace("_", " ")}</span>
          </div>
          <Pitch state={state} compact />
          <div className="timeline-control" aria-label="Match timeline">
            <button className="inline-action timeline-live" onClick={() => onTimelineSelect(null)}>
              <Play size={15} /> Latest
            </button>
            <input
              type="range"
              min={0}
              max={timelineMax}
              step={1000}
              value={selectedTimestamp ?? state.timestamp_ms}
              disabled={timeline.length === 0}
              onChange={(event) => onTimelineSelect(Number(event.currentTarget.value))}
              aria-label="Select timeline timestamp"
            />
          </div>
        </div>
        <form className="panel panel-ingest" onSubmit={submitIngest}>
          <div className="panel-heading">
            <h2>File Ingest</h2>
            <span>{processJob?.status ?? (processing ? "processing" : "ready")}</span>
          </div>
          <label className="field">
            <span>Match ID</span>
            <input value={matchId} onChange={(event) => onMatchIdChange(event.currentTarget.value)} />
          </label>
          <div className="ownership-row">
            <label className="check-field">
              <input
                type="checkbox"
                checked={replaceExisting}
                onChange={(event) => setReplaceExisting(event.currentTarget.checked)}
              />
              <span>Replace existing timeline</span>
            </label>
            <button
              className="inline-action danger-action"
              type="button"
              disabled={resetting || (summary?.states ?? 0) === 0}
              onClick={onResetMatch}
            >
              <Trash2 size={16} /> {resetting ? "Resetting" : "Reset match"}
            </button>
          </div>
          <label className="check-field cache-field">
            <input
              type="checkbox"
              checked={useCache}
              onChange={(event) => setUseCache(event.currentTarget.checked)}
            />
            <span>Use matching processed cache</span>
          </label>
          <div className="source-mode" aria-label="Source mode">
            <button
              type="button"
              className={sourceMode === "file" ? "active" : ""}
              onClick={() => setSourceMode("file")}
            >
              File
            </button>
            <button
              type="button"
              className={sourceMode === "stream_url" ? "active" : ""}
              onClick={() => setSourceMode("stream_url")}
            >
              Stream
            </button>
          </div>
          <label className="field">
            <span>{sourceLabel}</span>
            <input
              value={filePath}
              onChange={(event) => setFilePath(event.currentTarget.value)}
              placeholder={sourcePlaceholder}
              required
            />
          </label>
          <div className="probe-row">
            <button className="inline-action probe-action" type="button" disabled={!canUseSource || probing} onClick={probeSource}>
              <FileSearch size={16} /> {probing ? "Checking source" : "Probe source"}
            </button>
            {probe && (
              <span className="probe-chip">
                {probe.backend} · {sourceResolution} · {sourceDurationMinutes ?? "unknown"} min
              </span>
            )}
          </div>
          <div className="field-grid">
            <label className="field">
              <span>Minutes</span>
              <input
                type="number"
                min={1}
                max={140}
                placeholder={probe?.duration_ms ? "detected" : "auto"}
                value={durationMinutes}
                onChange={(event) =>
                  setDurationMinutes(event.currentTarget.value === "" ? "" : Number(event.currentTarget.value))
                }
              />
            </label>
            <label className="field">
              <span>Sample ms</span>
              <input
                type="number"
                min={200}
                step={100}
                value={sampleEveryMs}
                onChange={(event) => setSampleEveryMs(Number(event.currentTarget.value))}
              />
            </label>
            <label className="field">
              <span>FPS</span>
              <input
                type="number"
                min={1}
                step={0.5}
                placeholder={probe?.fps ? "detected" : "auto"}
                value={fpsHint}
                onChange={(event) => setFpsHint(event.currentTarget.value === "" ? "" : Number(event.currentTarget.value))}
              />
            </label>
          </div>
          <button className="primary-action" type="submit" disabled={processing}>
            <FileVideo size={16} /> {processing ? "Building timeline" : "Process full match"}
          </button>
          {processJob && ["queued", "running"].includes(processJob.status) && (
            <div className="job-progress" aria-label="Processing progress">
              <div>
                <span>{processJob.status}</span>
                <strong>{progressPercent}%</strong>
              </div>
              <div className="progress-track">
                <span style={{ width: `${progressPercent}%` }} />
              </div>
              <small>{jobFrames} sampled frames</small>
            </div>
          )}
          {ingestError && (
            <p className="ingest-message ingest-error">
              <AlertCircle size={15} /> {ingestError}
            </p>
          )}
          {probe?.warnings.map((warning) => (
            <p className="ingest-message" key={warning}>
              <AlertCircle size={15} /> {warning}
            </p>
          ))}
          {processResult && (
            <p className="ingest-result ingest-message">
              {processResult.cache_hit ? "Loaded" : "Wrote"} {processResult.states_written} states from{" "}
              {processResult.source_id}
              {processResult.replaced_states > 0 ? `, replacing ${processResult.replaced_states}` : ""}
              {processResult.cache_hit ? " from cache" : ""}.
            </p>
          )}
        </form>
        <div className="panel panel-live-capture">
          <div className="panel-heading">
            <h2>Browser Capture</h2>
            <span>{liveStatus}</span>
          </div>
          <video ref={captureVideoRef} className="capture-preview" muted playsInline aria-hidden="true" />
          <canvas ref={captureCanvasRef} className="capture-canvas" aria-hidden="true" />
          <label className="field">
            <span>Capture label</span>
            <input
              value={liveSourceLabel}
              disabled={liveStatus === "running"}
              onChange={(event) => setLiveSourceLabel(event.currentTarget.value)}
            />
          </label>
          <div className="field-grid live-field-grid">
            <label className="field">
              <span>Sample ms</span>
              <input
                type="number"
                min={500}
                step={250}
                value={liveSampleMs}
                disabled={liveStatus === "running"}
                onChange={(event) => setLiveSampleMs(Number(event.currentTarget.value))}
              />
            </label>
            <label className="check-field live-replace">
              <input
                type="checkbox"
                checked={liveReplaceTimeline}
                disabled={liveStatus === "running"}
                onChange={(event) => setLiveReplaceTimeline(event.currentTarget.checked)}
              />
              <span>Replace timeline on start</span>
            </label>
          </div>
          <div className="live-actions">
            {liveStatus === "running" ? (
              <button className="primary-action live-stop" type="button" onClick={stopBrowserCapture}>
                <Square size={16} /> Stop capture
              </button>
            ) : (
              <button
                className="primary-action"
                type="button"
                disabled={liveStatus === "requesting" || resetting}
                onClick={startBrowserCapture}
              >
                <ScreenShare size={16} /> {liveStatus === "requesting" ? "Waiting for source" : "Capture browser video"}
              </button>
            )}
          </div>
          <div className="live-capture-stats">
            <div>
              <Activity size={16} />
              <span>{liveFrames} frames</span>
            </div>
            <div>
              <TimerReset size={16} />
              <span>{liveLatencyMs === null ? "pending" : `${liveLatencyMs}ms`}</span>
            </div>
          </div>
          {liveError && (
            <p className="ingest-message ingest-error">
              <AlertCircle size={15} /> {liveError}
            </p>
          )}
        </div>
        <div className="panel panel-system">
          <div className="panel-heading">
            <h2>System</h2>
            <span>{summary?.states ?? 0} states</span>
          </div>
          <dl className="metric-list">
            <div>
              <dt>Match</dt>
              <dd>{state.match_id}</dd>
            </div>
            <div>
              <dt>Frame</dt>
              <dd>{state.frame_id}</dd>
            </div>
            <div>
              <dt>Calibration</dt>
              <dd>{state.pitch_calibration.status}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{(state.system_confidence * 100).toFixed(0)}%</dd>
            </div>
            <div>
              <dt>Stored States</dt>
              <dd>{summary?.states ?? 0}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{summary?.source_id ?? "no source"}</dd>
            </div>
            <div>
              <dt>Sample</dt>
              <dd>{summary?.sample_every_ms ? `${summary.sample_every_ms}ms` : "live"}</dd>
            </div>
            <div>
              <dt>Proc. FPS</dt>
              <dd>{summary?.processing_fps ? summary.processing_fps.toFixed(1) : "pending"}</dd>
            </div>
            <div>
              <dt>Speed</dt>
              <dd>{summary?.realtime_factor ? `${summary.realtime_factor.toFixed(1)}x` : "pending"}</dd>
            </div>
            <div>
              <dt>Elapsed</dt>
              <dd>{summary?.processing_elapsed_ms ? `${summary.processing_elapsed_ms}ms` : "pending"}</dd>
            </div>
            <div>
              <dt>Corrections</dt>
              <dd>{summary?.corrections ?? trackCorrections.length}</dd>
            </div>
            <div>
              <dt>Observed</dt>
              <dd>{summary?.observed_players ?? observed}/22</dd>
            </div>
            <div>
              <dt>Identity</dt>
              <dd>{summary?.identity_coverage === null || summary?.identity_coverage === undefined ? "pending" : `${(summary.identity_coverage * 100).toFixed(0)}%`}</dd>
            </div>
            <div>
              <dt>Observed IDs</dt>
              <dd>{summary?.observed_identity_coverage === null || summary?.observed_identity_coverage === undefined ? "pending" : `${(summary.observed_identity_coverage * 100).toFixed(0)}%`}</dd>
            </div>
            <div>
              <dt>Named</dt>
              <dd>{summary?.named_players ?? 0}/22</dd>
            </div>
            <div>
              <dt>Processor</dt>
              <dd>{summary?.processor_backend ?? processResult?.processor_backend ?? "idle"}</dd>
            </div>
          </dl>
          {summary && summary.quality_warnings.length > 0 && (
            <div className="quality-warnings" aria-label="Quality warnings">
              {summary.quality_warnings.map((warning) => (
                <span key={warning}>{warning.replace(/_/g, " ")}</span>
              ))}
            </div>
          )}
          <div className="export-row" aria-label="Export tactical state">
            <button
              className="inline-action export-action"
              type="button"
              disabled={(summary?.states ?? 0) === 0 || exporting !== null}
              onClick={() => onExportMatch("csv")}
            >
              <Download size={16} /> {exporting === "csv" ? "CSV" : "CSV"}
            </button>
            <button
              className="inline-action export-action"
              type="button"
              disabled={(summary?.states ?? 0) === 0 || exporting !== null}
              onClick={() => onExportMatch("jsonl")}
            >
              <Download size={16} /> {exporting === "jsonl" ? "JSONL" : "JSONL"}
            </button>
          </div>
        </div>
        <div className="panel panel-kpis">
          <div>
            <ScanLine size={18} />
            <span>Observed</span>
            <strong>{observed}</strong>
          </div>
          <div>
            <ShieldAlert size={18} />
            <span>Estimated</span>
            <strong>{estimated}</strong>
          </div>
          <div>
            <TimerReset size={18} />
            <span>Timeline</span>
            <strong>{timeline.length}</strong>
          </div>
        </div>
        <div className="panel panel-table">
          <div className="panel-heading">
            <h2>Track Corrections</h2>
            <span>{flaggedTracks.length} active</span>
          </div>
          {correctionError && (
            <p className="ingest-message ingest-error">
              <AlertCircle size={15} /> {correctionError}
            </p>
          )}
          <table>
            <thead>
              <tr>
                <th>Track</th>
                <th>Team</th>
                <th>No.</th>
                <th>Name</th>
                <th>Role</th>
                <th>Conf.</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {flaggedTracks.map((player) => {
                const draft = draftForTrack(player);
                const hasCorrection = correctionByTrack.has(player.track_id);
                const isSaving = correctingTrackId === player.track_id;
                return (
                <tr key={player.track_id}>
                  <td>{player.track_id}</td>
                  <td>
                    <select
                      className="table-control"
                      value={draft.team}
                      onChange={(event) =>
                        updateDraft(player.track_id, { ...draft, team: event.currentTarget.value as Team })
                      }
                    >
                      {teamOptions.map((team) => (
                        <option key={team} value={team}>
                          {team}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      className="table-control table-number"
                      type="number"
                      min={1}
                      max={99}
                      value={draft.shirt_number}
                      onChange={(event) =>
                        updateDraft(player.track_id, { ...draft, shirt_number: event.currentTarget.value })
                      }
                      aria-label={`Shirt number for ${player.track_id}`}
                    />
                  </td>
                  <td>
                    <input
                      className="table-control table-name"
                      value={draft.player_name}
                      onChange={(event) =>
                        updateDraft(player.track_id, { ...draft, player_name: event.currentTarget.value })
                      }
                      aria-label={`Player name for ${player.track_id}`}
                      placeholder="Unknown"
                    />
                  </td>
                  <td>
                    <select
                      className="table-control"
                      value={draft.role_hint}
                      onChange={(event) =>
                        updateDraft(player.track_id, { ...draft, role_hint: event.currentTarget.value as RoleHint })
                      }
                    >
                      {roleOptions.map((role) => (
                        <option key={role} value={role}>
                          {role}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>{(player.confidence * 100).toFixed(0)}%</td>
                  <td>
                    <div className="correction-actions">
                      <button
                        className="icon-table-action"
                        type="button"
                        disabled={isSaving}
                        onClick={() => saveCorrection(player)}
                        aria-label={`Save correction for ${player.track_id}`}
                      >
                        <Save size={15} />
                      </button>
                      <button
                        className="icon-table-action"
                        type="button"
                        disabled={isSaving || !hasCorrection}
                        onClick={() => clearCorrection(player.track_id)}
                        aria-label={`Clear correction for ${player.track_id}`}
                      >
                        <Undo2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Monitor, Radio, RefreshCw } from "lucide-react";
import {
  deleteMatch,
  downloadMatchExport,
  clearTrackCorrection,
  fetchTrackCorrections,
  fetchProcessJob,
  fetchLatestState,
  fetchMatchStates,
  fetchMatchSummary,
  probeMatchFile,
  saveTrackCorrection,
  sendLiveFrame,
  startProcessMatchFileJob,
} from "./api";
import { AnalystView } from "./views/AnalystView";
import { ManagerView } from "./views/ManagerView";
import type {
  MatchSummary,
  LiveFramePayload,
  LiveFrameResult,
  ProcessFilePayload,
  ProcessFileResult,
  ProcessJob,
  SourceProbe,
  TacticalState,
  TrackCorrection,
  TrackCorrectionPayload,
} from "./types";

type ViewMode = "manager" | "analyst";

function emptyTacticalState(matchId: string): TacticalState {
  return {
    match_id: matchId,
    timestamp_ms: 0,
    frame_id: "no-ingest",
    phase: "unknown",
    ball: null,
    players: [],
    pitch_calibration: {
      status: "lost",
      confidence: 0,
      source: "none",
    },
    system_confidence: 0,
  };
}

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

  const visibleState = useMemo(() => {
    if (selectedTimestamp === null) {
      return state;
    }
    return timeline.find((item) => item.timestamp_ms === selectedTimestamp) ?? state;
  }, [selectedTimestamp, state, timeline]);

  async function loadState() {
    try {
      setError(null);
      const [nextSummary, nextTimeline] = await Promise.all([fetchMatchSummary(matchId), fetchMatchStates(matchId)]);
      try {
        setState(await fetchLatestState(matchId));
      } catch (err) {
        if (err instanceof Error && err.message.includes("No stored tactical states")) {
          setState(null);
        } else {
          throw err;
        }
      }
      setSummary(nextSummary);
      setTimeline(nextTimeline);
      setSelectedTimestamp((current) => {
        if (current === null) {
          return null;
        }
        return nextTimeline.some((item) => item.timestamp_ms === current) ? current : null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  async function loadCorrections() {
    try {
      setCorrectionError(null);
      setTrackCorrections(await fetchTrackCorrections(matchId));
    } catch (err) {
      setCorrectionError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  async function ingestFile(payload: ProcessFilePayload) {
    setProcessing(true);
    setProcessResult(null);
    setProcessJob(null);
    setIngestError(null);
    try {
      const job = await startProcessMatchFileJob(matchId, payload);
      setProcessJob(job);
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : "Unknown error");
      setProcessing(false);
    }
  }

  useEffect(() => {
    if (!processJob || !["queued", "running"].includes(processJob.status)) {
      return;
    }

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
      } catch (err) {
        setIngestError(err instanceof Error ? err.message : "Unknown error");
        setProcessing(false);
      }
    }, 350);

    return () => window.clearInterval(timer);
  }, [processJob]);

  async function resetMatch() {
    setResetting(true);
    setProcessResult(null);
    setProcessJob(null);
    setIngestError(null);
    try {
      await deleteMatch(matchId);
      setProbe(null);
      setTimeline([]);
      setSummary(null);
      setTrackCorrections([]);
      setSelectedTimestamp(null);
      await loadState();
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setResetting(false);
    }
  }

  async function exportMatch(format: "csv" | "jsonl") {
    setExporting(format);
    setIngestError(null);
    try {
      await downloadMatchExport(matchId, format);
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : "Unknown error");
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
      await saveTrackCorrection(matchId, trackId, payload);
      await Promise.all([loadState(), loadCorrections()]);
    } catch (err) {
      setCorrectionError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setCorrectingTrackId(null);
    }
  }

  async function removeTrackCorrection(trackId: string) {
    setCorrectingTrackId(trackId);
    setCorrectionError(null);
    try {
      await clearTrackCorrection(matchId, trackId);
      await Promise.all([loadState(), loadCorrections()]);
    } catch (err) {
      setCorrectionError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setCorrectingTrackId(null);
    }
  }

  async function probeFile(
    source: { path: string | null; source_type: "file" | "stream_url"; stream_url: string | null },
    fpsHint: number | null,
  ) {
    setProbing(true);
    setProbe(null);
    setProcessResult(null);
    setProcessJob(null);
    setIngestError(null);
    try {
      const result = await probeMatchFile(matchId, { ...source, fps_hint: fpsHint });
      setProbe(result);
      return result;
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : "Unknown error");
      return null;
    } finally {
      setProbing(false);
    }
  }

  async function ingestLiveFrame(payload: LiveFramePayload): Promise<LiveFrameResult> {
    const result = await sendLiveFrame(matchId, payload);
    setState(result.state);
    setSelectedTimestamp(null);
    if (result.states_written % 2 === 0) {
      await loadState();
    }
    return result;
  }

  useEffect(() => {
    if (error) {
      return;
    }
    loadState();
    loadCorrections();
    const timer = window.setInterval(loadState, 2000);
    return () => window.clearInterval(timer);
  }, [error, matchId]);

  if (error) {
    return (
      <div className="center-state center-state-panel">
        <AlertTriangle size={22} />
        <div>
          <p className="eyebrow">Connection interrupted</p>
          <h1>Backend unavailable</h1>
          <p>{error}</p>
          <button className="inline-action" onClick={loadState}>
            <RefreshCw size={16} /> Retry connection
          </button>
        </div>
      </div>
    );
  }

  const analystState = visibleState ?? emptyTacticalState(matchId);

  return (
    <div className="app-shell">
      <nav className="mode-switch" aria-label="View mode">
        <button className={mode === "manager" ? "active" : ""} onClick={() => setMode("manager")}>
          <Radio size={16} /> Manager
        </button>
        <button className={mode === "analyst" ? "active" : ""} onClick={() => setMode("analyst")}>
          <Monitor size={16} /> Analyst
        </button>
      </nav>
      {mode === "manager" && !visibleState ? (
        <main className="center-state center-state-panel empty-match-state">
          <AlertTriangle size={22} />
          <div>
            <p className="eyebrow">No match timeline</p>
            <h1>Ingest footage first</h1>
            <p>Manager view unlocks after a file, stream, or browser capture writes real tactical states.</p>
            <button className="inline-action" onClick={() => setMode("analyst")}>
              <Monitor size={16} /> Open analyst console
            </button>
          </div>
        </main>
      ) : mode === "manager" && visibleState ? (
        <ManagerView state={visibleState} summary={summary} />
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
          onMatchIdChange={changeMatchId}
          onTimelineSelect={setSelectedTimestamp}
          onRefresh={loadState}
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

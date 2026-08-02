# Sample rights and hosted boundary

## Repository-owned proof input

The primary proof clip is `frontend/public/samples/galatasaray-steau-2008-12s.mp4`, a silent 12-second transcode of the first 12 seconds of [Galatasaray–Steaua match video](https://commons.wikimedia.org/wiki/File:Galatasaray-Steau_B%C3%BCkre%C5%9F-1.ogv). The hosted proof processes a 10-second bounded review window so the default review frame contains defensible detections; the full 12-second source remains available in the player and can be reprocessed locally. The Wikimedia Commons file identifies the uploader as Qwl and states that the original work was released into the public domain. The repository keeps the source reference, rights URL, attribution, and transcode boundary in the sample catalog and UI.

The clip is a real video input, not a synthetic tactical replay. The generated state artifact is produced by `VideoFrameProcessor` and OpenCV. The deterministic `BaselineProcessor` remains available only as an explicit fallback for development and is labelled as synthetic when used.

## Reproduction

From the repository root:

```bash
make setup
PROJECT_FM_PIPELINE_COMMIT="$(git rev-parse HEAD)" make demo-artifact
PROJECT_FM_DATA_ROOT="$(mktemp -d)" make trial \
  VIDEO="$PWD/frontend/public/samples/galatasaray-steau-2008-12s.mp4" \
  DURATION_MS=10000 SAMPLE_EVERY_MS=1000 \
  MIN_OBSERVED_PLAYERS=1 MIN_PROCESSING_FPS=0.1
```

The public-domain clip is intentionally treated as a low-resolution, broadcast-style smoke sample. With the relaxed sample thresholds above it should return `pass_with_warnings`; the default thresholds remain stricter for club-supplied pilot footage.

`make demo-artifact` runs the actual local pipeline and writes `frontend/public/samples/galatasaray-steau-2008-12s.states.json`. The artifact records the exact pipeline commit used to create it. Hosted deployments serve this immutable result; they do not claim to process live footage in the browser.

## Hosted boundary

The Vercel deployment is a static recruiter-accessible product proof. It includes the repository-owned clip, the state artifact, the manager view, analyst timeline, provenance panel, in-memory correction workflow, and client-side CSV/JSONL export. It does not accept uploads, stream credentials, or browser capture. Those operations require the local FastAPI service, where data remains under the configured `PROJECT_FM_DATA_ROOT`.

The hosted proof names the processor, source class, license, pipeline commit, and known limitations. Observed, inferred, corrected, and unavailable positions are distinct in the analyst legend and table. A low-confidence or off-camera position is not presented as an observed detection.

## Model and product limits

- The CPU-safe path estimates the pitch from the dominant green region, detects non-green player blobs, clusters kit hues, and maintains short nearest-neighbor tracks.
- Optional YOLO support is local-only and requires user-supplied model weights; weights are not committed or deployed.
- Broadcast cuts, closeups, occlusions, compression, and low-resolution shirt numbers can reduce observed-player and identity coverage.
- Inferred positions are a tactical prior for review, not proof that a player was visible in the source frame.
- No hosted input is retained because hosted input is not accepted. Local match footage belongs to the operator and should be handled under the club's access and privacy rules.

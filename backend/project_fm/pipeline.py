from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

from project_fm.config import get_settings
from project_fm.domain import BallState, CalibrationState, PlayerState, TacticalState


class BaselineProcessor:
    """Deterministic tactical-state generator for the first product spine.

    This is not the final CV model. It creates real TacticalState records so
    ingest, persistence, APIs, and UI can be built against stable contracts.
    """

    def __init__(self, match_id: str) -> None:
        self.match_id = match_id

    def state_for_frame(self, frame_id: str, timestamp_ms: int) -> TacticalState:
        t = timestamp_ms / 1000
        ball_x = 52.5 + math.sin(t / 8) * 28
        ball_y = 34 + math.cos(t / 5) * 18
        players = self._players(timestamp_ms, ball_x, ball_y)
        observed_count = sum(1 for player in players if player.observed)
        system_confidence = 0.45 + (observed_count / 22) * 0.35

        return TacticalState(
            match_id=self.match_id,
            timestamp_ms=timestamp_ms,
            frame_id=frame_id,
            phase="in_possession",
            ball=BallState(pitch_x=ball_x, pitch_y=ball_y, confidence=0.55),
            players=players,
            pitch_calibration=CalibrationState(
                status="estimated",
                confidence=0.55,
                source="baseline",
            ),
            system_confidence=round(system_confidence, 3),
        )

    def state_for_metadata(self, frame: Any) -> TacticalState:
        if hasattr(frame, "frame_id"):
            return self.state_for_frame(frame_id=frame.frame_id, timestamp_ms=frame.timestamp_ms)
        return self.state_for_frame(frame_id=frame["frame_id"], timestamp_ms=frame["timestamp_ms"])

    def _players(self, timestamp_ms: int, ball_x: float, ball_y: float) -> list[PlayerState]:
        home_shape = [
            (8, 34, "goalkeeper"),
            (22, 12, "defender"),
            (20, 28, "defender"),
            (20, 40, "defender"),
            (22, 56, "defender"),
            (42, 18, "midfielder"),
            (45, 34, "midfielder"),
            (42, 50, "midfielder"),
            (64, 14, "forward"),
            (68, 34, "forward"),
            (64, 54, "forward"),
        ]
        away_shape = [(105 - x, 68 - y, role) for x, y, role in home_shape]
        players: list[PlayerState] = []

        for index, (x, y, role) in enumerate(home_shape, start=1):
            observed = index not in {1, 2, 3}
            players.append(
                self._player(
                    track_id=f"home-{index}",
                    team="home",
                    shirt_number=index,
                    role_hint=role,
                    base_x=x,
                    base_y=y,
                    ball_x=ball_x,
                    ball_y=ball_y,
                    timestamp_ms=timestamp_ms,
                    observed=observed,
                )
            )

        for index, (x, y, role) in enumerate(away_shape, start=1):
            observed = index not in {1, 2}
            players.append(
                self._player(
                    track_id=f"away-{index}",
                    team="away",
                    shirt_number=index,
                    role_hint=role,
                    base_x=x,
                    base_y=y,
                    ball_x=ball_x,
                    ball_y=ball_y,
                    timestamp_ms=timestamp_ms,
                    observed=observed,
                )
            )

        return players

    def _player(
        self,
        track_id: str,
        team: str,
        shirt_number: int,
        role_hint: str,
        base_x: float,
        base_y: float,
        ball_x: float,
        ball_y: float,
        timestamp_ms: int,
        observed: bool,
    ) -> PlayerState:
        pull = 0.07 if role_hint in {"defender", "goalkeeper"} else 0.14
        pitch_x = base_x + (ball_x - base_x) * pull
        pitch_y = base_y + (ball_y - base_y) * pull
        confidence = 0.86 if observed else 0.62

        return PlayerState(
            track_id=track_id,
            team=cast(Any, team),
            shirt_number=shirt_number,
            role_hint=cast(Any, role_hint),
            pitch_x=round(max(0, min(105, pitch_x)), 2),
            pitch_y=round(max(0, min(68, pitch_y)), 2),
            observed=observed,
            confidence=confidence,
            last_observed_ms=timestamp_ms if observed else max(0, timestamp_ms - 4000),
            source_bbox=[0, 0, 0, 0] if observed else None,
        )


@dataclass
class Detection:
    bbox: list[int]
    center_x: float
    center_y: float
    pitch_x: float
    pitch_y: float
    area: float
    hue: float
    saturation: float
    shirt_number: int | None = None


class VideoFrameProcessor:
    """CPU-safe OpenCV tactical reconstruction for real match frames.

    It estimates the pitch as the dominant green region, detects non-green
    player blobs inside that region, clusters detections into two teams by
    jersey color, and maintains short-lived nearest-neighbor tracks.
    """

    def __init__(self, match_id: str) -> None:
        self.match_id = match_id
        self.settings = get_settings()
        self.next_track_index = 1
        self.tracks: dict[str, tuple[float, float, str, int]] = {}
        self.team_hue_centers: dict[str, float] | None = None
        self.yolo_model: Any | None = None
        self.fallback = BaselineProcessor(match_id=match_id)

    def state_for_sample(self, sample: Any) -> TacticalState:
        frame = sample.metadata
        detections, calibration_confidence, calibration_source = self._detections(sample.image)
        observed_players = self._players_from_detections(detections, frame.timestamp_ms)
        estimated_players = self._estimated_players(frame.timestamp_ms, observed_players)
        players = observed_players + estimated_players
        observed_count = sum(1 for player in players if player.observed)
        ball = self._ball_from_detections(detections)
        system_confidence = min(0.92, 0.35 + (observed_count / 22) * 0.42 + calibration_confidence * 0.18)

        return TacticalState(
            match_id=self.match_id,
            timestamp_ms=frame.timestamp_ms,
            frame_id=frame.frame_id,
            phase="unknown" if ball is None else "in_possession",
            ball=ball,
            players=players[:22],
            pitch_calibration=CalibrationState(
                status="assisted" if calibration_confidence >= 0.6 else "estimated",
                confidence=round(calibration_confidence, 3),
                source=calibration_source,
            ),
            system_confidence=round(system_confidence, 3),
        )

    def _detections(self, image: Any) -> tuple[list[Detection], float, str]:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]

        height, width = image.shape[:2]
        resized_width = 960
        scale = width / resized_width if width > resized_width else 1.0
        if scale > 1:
            image = cv2.resize(image, (resized_width, int(height / scale)))
            height, width = image.shape[:2]

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        green_mask = cv2.inRange(hsv, np.array([35, 35, 35]), np.array([95, 255, 255]))
        kernel = np.ones((7, 7), np.uint8)
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return [], 0.25, "opencv-no-pitch-mask"

        pitch_contour = max(contours, key=cv2.contourArea)
        pitch_area = float(cv2.contourArea(pitch_contour))
        frame_area = float(width * height)
        x, y, w, h = cv2.boundingRect(pitch_contour)
        pitch_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.drawContours(pitch_mask, [pitch_contour], -1, 255, thickness=-1)

        yolo_detections = self._yolo_detections(
            image=image,
            hsv=hsv,
            pitch_mask=pitch_mask,
            pitch_rect=(x, y, w, h),
            scale=scale,
        )
        if yolo_detections is not None:
            calibration_confidence = max(0.3, min(0.9, (pitch_area / frame_area) * 1.9))
            return yolo_detections, calibration_confidence, "yolo-person-green-pitch"

        non_pitch = cv2.bitwise_not(green_mask)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, bright_mask = cv2.threshold(gray, 45, 255, cv2.THRESH_BINARY)
        candidate_mask = cv2.bitwise_and(non_pitch, pitch_mask)
        candidate_mask = cv2.bitwise_and(candidate_mask, bright_mask)
        candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        candidate_mask = cv2.dilate(candidate_mask, np.ones((3, 3), np.uint8), iterations=1)

        min_area = max(18, frame_area * 0.000025)
        max_area = frame_area * 0.006
        detections: list[Detection] = []
        candidate_contours, _ = cv2.findContours(candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in candidate_contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or area > max_area:
                continue
            bx, by, bw, bh = cv2.boundingRect(contour)
            aspect = bh / max(bw, 1)
            if aspect < 0.45 or aspect > 5.5:
                continue
            center_x = bx + bw / 2
            center_y = by + bh / 2
            if pitch_mask[int(min(max(center_y, 0), height - 1)), int(min(max(center_x, 0), width - 1))] == 0:
                continue
            crop_hsv = hsv[by : by + bh, bx : bx + bw]
            crop_bgr = image[by : by + bh, bx : bx + bw]
            crop_sat = crop_hsv[:, :, 1]
            vivid = crop_sat > 45
            hue = float(np.median(crop_hsv[:, :, 0][vivid])) if np.any(vivid) else float(np.median(crop_hsv[:, :, 0]))
            saturation = float(np.median(crop_sat))
            pitch_x = ((center_x - x) / max(w, 1)) * 105
            pitch_y = ((center_y - y) / max(h, 1)) * 68
            detections.append(
                Detection(
                    bbox=[int(bx * scale), int(by * scale), int(bw * scale), int(bh * scale)],
                    center_x=center_x,
                    center_y=center_y,
                    pitch_x=round(max(0, min(105, pitch_x)), 2),
                    pitch_y=round(max(0, min(68, pitch_y)), 2),
                    area=area,
                    hue=hue,
                    saturation=saturation,
                    shirt_number=self._read_shirt_number(crop_bgr),
                )
            )

        detections = sorted(detections, key=lambda item: item.area, reverse=True)[:22]
        calibration_confidence = max(0.3, min(0.88, (pitch_area / frame_area) * 1.8))
        return detections, calibration_confidence, "opencv-green-pitch"

    def _yolo_detections(
        self,
        image: Any,
        hsv: Any,
        pitch_mask: Any,
        pitch_rect: tuple[int, int, int, int],
        scale: float,
    ) -> list[Detection] | None:
        if self.settings.detector_backend != "yolo":
            return None
        if self.settings.yolo_model_path is None:
            return None
        if not self.settings.yolo_model_path.exists():
            return None

        import numpy as np  # type: ignore[import-not-found]

        if self.yolo_model is None:
            try:
                from ultralytics import YOLO  # type: ignore[import-not-found]
            except ImportError:
                return None
            self.yolo_model = YOLO(str(self.settings.yolo_model_path))

        results = self.yolo_model.predict(image, verbose=False)
        if not results:
            return []
        boxes = getattr(results[0], "boxes", None)
        if boxes is None:
            return []

        pitch_x0, pitch_y0, pitch_w, pitch_h = pitch_rect
        detections: list[Detection] = []
        for box in boxes:
            class_id = int(box.cls[0]) if getattr(box, "cls", None) is not None else -1
            confidence = float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
            if class_id != 0 or confidence < 0.25:
                continue
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0]]
            bx = max(0, int(x1))
            by = max(0, int(y1))
            bw = max(1, int(x2 - x1))
            bh = max(1, int(y2 - y1))
            center_x = bx + bw / 2
            center_y = by + bh / 2
            mask_x = int(min(max(center_x, 0), pitch_mask.shape[1] - 1))
            mask_y = int(min(max(center_y, 0), pitch_mask.shape[0] - 1))
            if pitch_mask[mask_y, mask_x] == 0:
                continue
            crop_hsv = hsv[by : by + bh, bx : bx + bw]
            crop_bgr = image[by : by + bh, bx : bx + bw]
            if crop_hsv.size == 0:
                continue
            crop_sat = crop_hsv[:, :, 1]
            vivid = crop_sat > 45
            hue = float(np.median(crop_hsv[:, :, 0][vivid])) if np.any(vivid) else float(np.median(crop_hsv[:, :, 0]))
            saturation = float(np.median(crop_sat))
            pitch_x = ((center_x - pitch_x0) / max(pitch_w, 1)) * 105
            pitch_y = ((center_y - pitch_y0) / max(pitch_h, 1)) * 68
            detections.append(
                Detection(
                    bbox=[int(bx * scale), int(by * scale), int(bw * scale), int(bh * scale)],
                    center_x=center_x,
                    center_y=center_y,
                    pitch_x=round(max(0, min(105, pitch_x)), 2),
                    pitch_y=round(max(0, min(68, pitch_y)), 2),
                    area=float(bw * bh),
                    hue=hue,
                    saturation=saturation,
                    shirt_number=self._read_shirt_number(crop_bgr),
                )
            )
        return sorted(detections, key=lambda item: item.area, reverse=True)[:22]

    def _read_shirt_number(self, crop_bgr: Any) -> int | None:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]

        if crop_bgr.size == 0:
            return None
        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        light_mask = cv2.inRange(hsv, np.array([0, 0, 145]), np.array([180, 95, 255]))
        dark_mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 100, 90]))
        masks = [light_mask, dark_mask]
        best_number: int | None = None
        best_score = 0.0
        for mask in masks:
            candidate = self._normalize_digit_mask(mask)
            if candidate is None:
                continue
            scores: dict[int, float] = {}
            for number in range(1, 100):
                template = self._number_template(number)
                score = self._mask_similarity(candidate, template)
                scores[number] = score
                if score > best_score:
                    best_score = score
                    best_number = number
            if scores.get(6, 0.0) > scores.get(8, 0.0) and scores.get(8, 0.0) >= scores.get(6, 0.0) - 0.025:
                if scores[8] > best_score - 0.025:
                    best_score = scores[8]
                    best_number = 8
        return best_number if best_score >= 0.34 else None

    def _normalize_digit_mask(self, mask: Any):
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]

        cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [contour for contour in contours if cv2.contourArea(contour) >= 2]
        if not contours:
            return None
        x, y, w, h = cv2.boundingRect(np.vstack(contours))
        if w < 2 or h < 4:
            return None
        ink_ratio = float(np.count_nonzero(cleaned[y : y + h, x : x + w])) / max(w * h, 1)
        if ink_ratio < 0.04 or ink_ratio > 0.82:
            return None
        cropped = cleaned[y : y + h, x : x + w]
        target_h = 48
        target_w = 34
        scale = min(target_w / max(w, 1), target_h / max(h, 1))
        resized_w = max(1, int(w * scale))
        resized_h = max(1, int(h * scale))
        resized = cv2.resize(cropped, (resized_w, resized_h), interpolation=cv2.INTER_NEAREST)
        canvas = np.zeros((target_h, target_w), dtype=np.uint8)
        offset_x = (target_w - resized_w) // 2
        offset_y = (target_h - resized_h) // 2
        canvas[offset_y : offset_y + resized_h, offset_x : offset_x + resized_w] = resized
        return canvas

    def _number_template(self, number: int):
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]

        canvas = np.zeros((72, 56), dtype=np.uint8)
        text = str(number)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.1 if number < 10 else 0.82
        thickness = 2
        (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)
        x = max(0, (56 - text_w) // 2)
        y = max(text_h + 1, (72 + text_h) // 2 - 3)
        cv2.putText(canvas, text, (x, y), font, font_scale, 255, thickness, cv2.LINE_AA)
        _, thresholded = cv2.threshold(canvas, 90, 255, cv2.THRESH_BINARY)
        normalized = self._normalize_digit_mask(thresholded)
        return normalized if normalized is not None else np.zeros((48, 34), dtype=np.uint8)

    def _mask_similarity(self, left: Any, right: Any) -> float:
        import numpy as np  # type: ignore[import-not-found]

        left_on = left > 0
        right_on = right > 0
        intersection = np.logical_and(left_on, right_on).sum()
        union = np.logical_or(left_on, right_on).sum()
        if union == 0:
            return 0.0
        return float(intersection / union)

    def _players_from_detections(self, detections: list[Detection], timestamp_ms: int) -> list[PlayerState]:
        if not detections:
            return []
        hue_centers = self._team_hue_centers(detections)
        players: list[PlayerState] = []
        assigned_tracks: set[str] = set()

        for detection in sorted(detections, key=lambda item: (item.pitch_x, item.pitch_y)):
            team = self._team_for_detection(detection, hue_centers)
            track_id = self._assign_track(detection.pitch_x, detection.pitch_y, team, timestamp_ms, assigned_tracks)
            assigned_tracks.add(track_id)
            confidence = 0.72 + min(0.2, detection.area / 9000)
            players.append(
                PlayerState(
                    track_id=track_id,
                    team=cast(Any, team),
                    shirt_number=detection.shirt_number,
                    role_hint="unknown",
                    pitch_x=detection.pitch_x,
                    pitch_y=detection.pitch_y,
                    observed=True,
                    confidence=round(confidence, 3),
                    last_observed_ms=timestamp_ms,
                    source_bbox=detection.bbox,
                )
            )
        return players

    def _team_hue_centers(self, detections: list[Detection]) -> dict[str, float]:
        vivid_hues = sorted(detection.hue for detection in detections if detection.saturation >= 35)
        if len(vivid_hues) < 2:
            if self.team_hue_centers is not None:
                return self.team_hue_centers
            self.team_hue_centers = {"home": 0.0, "away": 120.0}
            return self.team_hue_centers

        low_cluster = vivid_hues[: max(1, len(vivid_hues) // 2)]
        high_cluster = vivid_hues[max(1, len(vivid_hues) // 2) :]
        candidate = {
            "home": sum(low_cluster) / len(low_cluster),
            "away": sum(high_cluster) / len(high_cluster),
        }
        if self.team_hue_centers is None:
            self.team_hue_centers = candidate
        else:
            self.team_hue_centers = {
                team: self._blend_hue(self.team_hue_centers[team], candidate[team])
                for team in ("home", "away")
            }
        return self.team_hue_centers

    def _team_for_detection(self, detection: Detection, centers: dict[str, float]) -> str:
        home_distance = self._hue_distance(detection.hue, centers["home"])
        away_distance = self._hue_distance(detection.hue, centers["away"])
        return "home" if home_distance <= away_distance else "away"

    def _blend_hue(self, previous: float, current: float) -> float:
        return (previous * 0.82) + (current * 0.18)

    def _hue_distance(self, left: float, right: float) -> float:
        distance = abs(left - right)
        return min(distance, 180 - distance)

    def _assign_track(
        self,
        pitch_x: float,
        pitch_y: float,
        team: str,
        timestamp_ms: int,
        assigned_tracks: set[str],
    ) -> str:
        best_track_id: str | None = None
        best_distance = 9.0
        for track_id, (track_x, track_y, track_team, _) in self.tracks.items():
            if track_id in assigned_tracks or track_team != team:
                continue
            distance = math.dist((pitch_x, pitch_y), (track_x, track_y))
            if distance < best_distance:
                best_distance = distance
                best_track_id = track_id
        if best_track_id is None:
            best_track_id = f"cv-{team}-{self.next_track_index}"
            self.next_track_index += 1
        self.tracks[best_track_id] = (pitch_x, pitch_y, team, timestamp_ms)
        return best_track_id

    def _estimated_players(self, timestamp_ms: int, observed_players: list[PlayerState]) -> list[PlayerState]:
        if len(observed_players) >= 22:
            return []
        baseline = self.fallback.state_for_frame(frame_id=f"estimated-{timestamp_ms}", timestamp_ms=timestamp_ms)
        observed_home = sum(1 for player in observed_players if player.team == "home")
        observed_away = sum(1 for player in observed_players if player.team == "away")
        needed_home = max(0, 11 - observed_home)
        needed_away = max(0, 11 - observed_away)
        estimated: list[PlayerState] = []
        for team, needed in (("home", needed_home), ("away", needed_away)):
            candidates = [player for player in baseline.players if player.team == team]
            for index, player in enumerate(candidates[:needed], start=1):
                estimated.append(
                    player.model_copy(
                        update={
                            "track_id": f"estimated-{team}-{index}",
                            "observed": False,
                            "confidence": 0.42,
                            "last_observed_ms": max(0, timestamp_ms - 5000),
                            "source_bbox": None,
                        }
                    )
                )
        return estimated

    def _ball_from_detections(self, detections: list[Detection]) -> BallState | None:
        if not detections:
            return None
        smallest = min(detections, key=lambda detection: detection.area)
        if smallest.area > 260:
            return None
        return BallState(pitch_x=smallest.pitch_x, pitch_y=smallest.pitch_y, confidence=0.35)

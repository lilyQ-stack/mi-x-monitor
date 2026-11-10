#!/usr/bin/env python3
"""Download/ASR publicly accessible X Spaces linked in MI's existing RSS archive.

Full text is emitted only to a short-lived GitHub Actions artifact, never committed
into this PUBLIC repository. Public metadata is kept under state/mi-space-status.json.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SPACE_ID = re.compile(r"(?:https?://(?:x\.com|twitter\.com|[^\s/]+))/(?:i/)?spaces/([A-Za-z0-9]{10,25})", re.I)
RAW_ID = re.compile(r"^[A-Za-z0-9]{10,25}$")
INDEX = Path("state/mi-space-status.json")
TRANSCRIPTS = Path("out/space_transcripts")
UTC = timezone.utc
MAX_ATTEMPTS = 3
RETRY_HOURS = 24
# Known publicly linked archives, useful for initial smoke test. Do NOT assume audio exists.
SEEDS = {
    "1XyJEEvejdRndj": "2026-10-31",
    "1YREZXeRvdyZEk": "2026-11-06",
}

def utcnow() -> datetime:
    return datetime.now(UTC)

def iso_now() -> str:
    return utcnow().isoformat(timespec="seconds")

def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return default

def discover() -> dict[str, str]:
    """Map ID -> earliest observed China calendar date; only trusted X IDs used."""
    seen = dict(SEEDS)
    cutoff = (utcnow() - timedelta(days=30)).date().isoformat()
    for file in sorted(Path("data").glob("nitter-*.json")):
        match = re.fullmatch(r"nitter-(\d{4}-\d{2}-\d{2})\.json", file.name)
        if not match or match.group(1) < cutoff:
            continue
        content = read_json(file, {})
        for item in content.get("items", []):
            if not item.get("verified_link_author", False):
                continue
            day = item.get("date") or match.group(1)
            raw = " ".join(str(item.get(key) or "") for key in ("space_url", "title_excerpt", "description_excerpt"))
            for sid in SPACE_ID.findall(raw):
                if RAW_ID.fullmatch(sid):
                    seen[sid] = min(seen.get(sid, day), day)
    manual = os.environ.get("SPACE_URL", "").strip()
    if manual:
        match = re.fullmatch(r"https?://(?:x\.com|twitter\.com)/i/spaces/([A-Za-z0-9]{10,25})/?", manual)
        if match:
            seen[match.group(1)] = seen.get(match.group(1), date.today().isoformat())
        else:
            print("::warning::Invalid manual SPACE_URL; accepted form: https://x.com/i/spaces/<id>", flush=True)
    return seen

def due_for_retry(item: dict, now: datetime, force: bool = False) -> bool:
    if force:
        return True
    if item.get("status") == "transcribed":
        return False
    if item.get("attempts", 0) >= MAX_ATTEMPTS:
        return False
    attempt = item.get("last_attempt")
    if attempt:
        try:
            dt = datetime.fromisoformat(attempt.replace("Z", "+00:00"))
            if now - dt < timedelta(hours=RETRY_HOURS):
                return False
        except ValueError:
            pass
    return True

def write_index(index: dict):
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def run_command(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)

def download(space_id: str, dest: Path) -> tuple[Path | None, str]:
    canonical = f"https://x.com/i/spaces/{space_id}"
    result = run_command([
        sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-cache-dir", "--no-progress",
        "--socket-timeout", "20", "--retries", "2", "--fragment-retries", "2",
        "--max-filesize", "250M", "--extract-audio", "--audio-format", "m4a",
        "--output", str(dest / "recording.%(ext)s"), canonical,
    ], timeout=900)
    files = [p for p in dest.glob("recording.*") if p.suffix in {".m4a", ".mp3", ".aac", ".mp4", ".webm"}]
    if result.returncode == 0 and files:
        return max(files, key=lambda p: p.stat().st_size), ""
    tail = "\n".join(result.stdout.splitlines()[-7:])[-700:]
    return None, tail or f"yt-dlp returned {result.returncode} without audio"

def transcribe(space_id: str, audio: Path) -> tuple[int, str]:
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
        segments, info = model.transcribe(str(audio), language="zh", beam_size=3, vad_filter=True)
        data = []
        for segment in segments:
            data.append({"start": round(segment.start, 2), "end": round(segment.end, 2), "text": segment.text.strip()})
        if not data:
            return 0, "Whisper produced no speech segments"
        TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
        payload = {
            "space_id": space_id, "url": f"https://x.com/i/spaces/{space_id}",
            "transcribed_utc": iso_now(), "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "note": "Automatic speech recognition; verify named entities and market numbers against audio.",
            "segments": data,
        }
        (TRANSCRIPTS / f"{space_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (TRANSCRIPTS / f"{space_id}.txt").write_text(
            "\n".join(f"[{seg['start']:07.1f}–{seg['end']:07.1f}] {seg['text']}" for seg in data) + "\n",
            encoding="utf-8",
        )
        return len(data), ""
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {str(exc)[:400]}"

def main() -> int:
    idx = read_json(INDEX, {"schema_version": 1, "account": "wr0789", "spaces": {}})
    if not isinstance(idx, dict) or not isinstance(idx.get("spaces", {}), dict):
        idx = {"schema_version": 1, "account": "wr0789", "spaces": {}}
    records = idx.setdefault("spaces", {})
    found = discover()
    force_id = None
    if os.environ.get("SPACE_URL"):
        m = re.fullmatch(r"https?://(?:x\.com|twitter\.com)/i/spaces/([A-Za-z0-9]{10,25})/?", os.environ["SPACE_URL"].strip())
        if m:
            force_id = m.group(1)
    for sid, first_day in found.items():
        records.setdefault(sid, {"url": f"https://x.com/i/spaces/{sid}", "first_linked_day": first_day, "status": "not_attempted", "attempts": 0})
    pending = [(sid, item) for sid, item in records.items() if sid in found and due_for_retry(item, utcnow(), force=sid == force_id)]
    pending.sort(key=lambda pair: (pair[0] == force_id, pair[1].get("first_linked_day", "")), reverse=True)
    idx["last_scan_utc"] = iso_now()
    idx["discovered_count"] = len(found)
    idx["pending_count"] = len(pending)
    if not found:
        idx["scan_status"] = "no_space_links_found_not_proof_of_no_spaces"
    elif not pending:
        idx["scan_status"] = "no_retry_due"
    else:
        idx["scan_status"] = "attempted"
    print(f"Discover {len(found)} space links; {len(pending)} eligible", flush=True)

    for sid, item in pending[:1]:
        item["attempts"] = int(item.get("attempts", 0)) + 1
        item["last_attempt"] = iso_now()
        print(f"Attempt {item['attempts']}: {item['url']}", flush=True)
        with tempfile.TemporaryDirectory(prefix="mi-space-") as tmp:
            try:
                audio, error = download(sid, Path(tmp))
            except subprocess.TimeoutExpired:
                audio, error = None, "yt-dlp download timed out after 900 seconds"
            if not audio:
                item["status"] = "download_failed"
                item["error"] = error
                print(f"::warning::Download failed for {sid}: {error}", flush=True)
                continue
            item["download_bytes"] = audio.stat().st_size
            print(f"Audio downloaded, {audio.stat().st_size} bytes", flush=True)
            proc = run_command([sys.executable, "-m", "pip", "install", "--quiet", "faster-whisper>=1.1,<2"], timeout=360)
            if proc.returncode != 0:
                item["status"] = "transcribe_failed"
                item["error"] = "faster-whisper install failed: " + proc.stdout[-300:]
                print("::warning::Transcription dependency install failed", flush=True)
                continue
            count, error = transcribe(sid, audio)
            if count:
                item["status"] = "transcribed"
                item["segments"] = count
                item["transcribed_utc"] = iso_now()
                item["artifact_run_id"] = os.environ.get("GITHUB_RUN_ID")
                item.pop("error", None)
                print(f"Transcribed {count} segments for {sid} into Action artifact", flush=True)
            else:
                item["status"] = "transcribe_failed"
                item["error"] = error
                print(f"::warning::Transcription failed: {error}", flush=True)
    write_index(idx)
    print(f"METADATA_STATUS {idx['scan_status']}; total={len(records)}", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

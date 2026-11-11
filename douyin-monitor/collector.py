#!/usr/bin/env python3
"""Douyin creator monitor proof-of-concept. Free, guest-only, fails closed on stale feeds.

Aimed at morning-after monitoring for account 606890417. Outputs compact
metadata and ASR segments; NEVER commits media/transcripts to Git.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, random, secrets, sys, time
from pathlib import Path
from zoneinfo import ZoneInfo

import douyin_fetch as d

BEIJING = ZoneInfo("Asia/Shanghai")
SEC_UID = "MS4wLjABAAAA_hkYGrUP3d2i3JodCLwrplan05tJ9xl1D6lZySbNC0Q"
AUTHOR_UID = "95667973305"
ACCOUNT = "606890417"


def creator_page(cursor: int = 0, count: int = 50):
    """Reuse the tested public signed request; aid=1128 includes timely video posts."""
    visitor = d.get_ttwid()
    token = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(38)) + "=="
    fingerprint = d.gen_verify_fp()
    identity = secrets.token_hex(25)
    stamp = str(int(time.time()))
    params = {
        "device_platform": "webapp", "aid": "1128", "channel": "channel_pc_web",
        "pc_client_type": "1", "version_code": "290100", "version_name": "29.1.0",
        "cookie_enabled": "true", "screen_width": "1920", "screen_height": "1080",
        "browser_language": "zh-CN", "browser_platform": "Win32",
        "browser_name": "Chrome", "browser_version": "130.0.0.0",
        "browser_online": "true", "engine_name": "Blink", "engine_version": "130.0.0.0",
        "os_name": "Windows", "os_version": "10", "cpu_core_num": "12",
        "device_memory": "8", "platform": "PC", "downlink": "10",
        "effective_type": "4g", "round_trip_time": "0",
        "msToken": token, "sec_user_id": SEC_UID,
        "max_cursor": str(cursor), "count": str(count), "locate_query": "false",
    }
    bogus = d.ABogus().get_value(params)
    pairs = list(params.items()) + [
        ("a_bogus", bogus), ("verifyFp", fingerprint), ("fp", fingerprint),
        ("uifid", identity), ("timestamp", stamp),
    ]
    serialized = d.encode_pairs(pairs)
    signature = hashlib.md5(
        f"{identity}_{stamp}_{d.WEB_SIGN_SALT}_{serialized}".encode()
    ).hexdigest()
    url = "https://www.douyin.com/aweme/v1/web/aweme/post/?" + serialized + "&x-secsdk-web-signature=" + signature
    headers = {
        "User-Agent": d.UA, "Referer": "https://www.douyin.com/",
        "Accept": "application/json, text/plain, */*",
        "Cookie": f"ttwid={visitor}; msToken={token}; s_v_web_id={fingerprint}; UIFID_TEMP={identity}",
        "uifid": identity, "x-secsdk-web-signature": signature,
        "x-secsdk-web-expire": stamp,
    }
    with d.http(url, headers=headers) as r:
        payload = json.loads(r.read(25_000_000).decode())
    if payload.get("status_code") != 0 or not isinstance(payload.get("aweme_list"), list):
        raise RuntimeError(f"Creator feed unavailable: {payload.get('status_code')} {payload.get('status_msg')}")
    if payload.get("not_login_module"):
        raise RuntimeError("Feed reports login-gated items; cannot claim complete coverage")
    return payload


def publish_time(p):
    return dt.datetime.fromtimestamp(int(p["create_time"]), tz=BEIJING)


def run(target: dt.date, outdir: Path, only_discover: bool):
    outdir.mkdir(parents=True, exist_ok=True)
    all_posts: dict[str, dict] = {}
    cursor = 0
    page_count = 0
    reached_before_target = False
    while page_count < 4:
        payload = creator_page(cursor=cursor)
        page_count += 1
        posts = [p for p in payload["aweme_list"] if isinstance(p, dict) and p.get("aweme_id") and p.get("create_time")]
        if not posts:
            raise RuntimeError("Feed returned zero posts; not equivalent to no updates")
        ordinary = []
        for p in posts:
            author = p.get("author") or {}
            if str(author.get("uid")) != AUTHOR_UID:
                raise RuntimeError(f"Author mismatch on {p.get('aweme_id')}: {author.get('uid')}")
            all_posts[str(p["aweme_id"])] = p
            if not p.get("is_top"):
                ordinary.append(p)
        if ordinary and min(publish_time(p).date() for p in ordinary) < target:
            reached_before_target = True
            break
        if not payload.get("has_more"):
            reached_before_target = True
            break
        next_cursor = int(payload.get("max_cursor") or 0)
        if not next_cursor or next_cursor == cursor:
            raise RuntimeError("Pagination cursor did not advance")
        cursor = next_cursor
        time.sleep(1)
    if not reached_before_target:
        raise RuntimeError("Reached pagination cap before covering entire target day")

    ordered = sorted(all_posts.values(), key=lambda p: p.get("create_time", 0), reverse=True)
    newest = publish_time(ordered[0]).isoformat()
    target_posts = [p for p in ordered if publish_time(p).date() == target]
    result = {
        "account": ACCOUNT, "author_uid": AUTHOR_UID, "target_date": target.isoformat(),
        "collection_at": dt.datetime.now(BEIJING).isoformat(),
        "source": "douyin_public_creator_posts_aid1128", "feed_pages": page_count,
        "feed_rows": len(ordered), "latest_post": newest,
        "window_reached": reached_before_target,
        "status": "ready_to_transcribe" if target_posts else "no_posts_in_accessible_feed",
        "completeness_note": "Covers the returned feed window, not an independent guarantee against platform omissions",
        "videos": [],
    }
    for p in target_posts:
        item_id = str(p["aweme_id"])
        meta = {
            "id": item_id, "title": (p.get("desc") or "")[:250],
            "published_at": publish_time(p).isoformat(),
            "url": f"https://www.douyin.com/video/{item_id}", "author_uid": AUTHOR_UID,
        }
        result["videos"].append(meta)
    (outdir / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DISCOVERY", json.dumps(result, ensure_ascii=False)[:9000], flush=True)
    if only_discover or not target_posts:
        return

    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
    for item in result["videos"]:
        video_id = item["id"]
        detail = d.fetch_aweme_detail(video_id)
        if str((detail.get("author") or {}).get("uid")) != AUTHOR_UID:
            raise RuntimeError(f"Detail author mismatch for video {video_id}")
        video_url, source = d.pick_video_url(detail)
        video_file = outdir / f"{video_id}.mp4"
        size = d.download(video_url, video_file)
        if size < 100_000:
            raise RuntimeError(f"Video download too short: {video_id}, {size} bytes")
        chunks, info = model.transcribe(str(video_file), language="zh", vad_filter=True, beam_size=3)
        segments = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
                    for s in chunks if s.text.strip()]
        chars = sum(len(s["text"]) for s in segments)
        if chars < 70:
            raise RuntimeError(f"ASR suspiciously short for {video_id}: {chars} chars")
        transcript = {
            "video_id": video_id, "title": item["title"], "published_at": item["published_at"],
            "language": info.language, "segment_count": len(segments),
            "text_chars": chars, "segments": segments,
        }
        (outdir / f"{video_id}.transcript.json").write_text(
            json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        video_file.unlink(missing_ok=True)
        print("ASR_COMPLETE", json.dumps({"id": video_id, "chars": chars, "segments": len(segments)}, ensure_ascii=False), flush=True)
    result["status"] = "transcribed"
    (outdir / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MONITOR_COMPLETED", len(result["videos"]), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-date", default=(dt.datetime.now(BEIJING).date() - dt.timedelta(days=1)).isoformat())
    ap.add_argument("--output", default="monitor-output")
    ap.add_argument("--only-discover", action="store_true")
    args = ap.parse_args()
    try:
        run(dt.date.fromisoformat(args.target_date), Path(args.output), args.only_discover)
    except Exception as ex:
        print("COLLECTION_FAILED", f"{type(ex).__name__}: {ex}", file=sys.stderr, flush=True)
        sys.exit(2)

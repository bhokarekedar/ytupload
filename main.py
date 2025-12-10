#!/usr/bin/env python3
"""
Production-ready bulk YouTube Shorts uploader & scheduler
for breathing challenge videos.

Key features:
- Uses CHALLENGE_ARRAYS (your challenge JSON arrays) as source of truth
- Uses title/description arrays for SEO metadata (optional)
- Uploads as PRIVATE, then schedules 1 per day
- Multi-channel ready (playlist, timezone, window per channel)
- Start/Stop ID range control
- State file to remember last uploaded challenge
- Dry-run mode + max uploads per run
"""

import os
import json
import random
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# =========================
# PATHS & CONSTANTS
# =========================

VIDEOS_DIR = Path("/Users/kedarbhokare/Desktop/electron/breathing-app/electron/donevideos/done")
VIDEO_PREFIX = "challenge_final_"
VIDEO_SUFFIX = ".mp4"

CLIENT_SECRETS_FILE = "client_secret.json"
TOKEN_FILE = "youtube_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

YOUTUBE_CATEGORY_ID = "27"  # Education

IST = timezone(timedelta(hours=5, minutes=30))

# =========================
# PRODUCTION FLAGS
# =========================

DRY_RUN = False                 # True = no upload, just print actions
MAX_UPLOADS_PER_RUN = 30        # Safety guard per run

# If START_FROM_ID is None → resume from last_uploaded_challenge_id in state.
# If STOP_AT_ID is None     → process until last challenge in list.
START_FROM_ID: Optional[str] = None
STOP_AT_ID: Optional[str] = None

STATE_FILE = "upload_state.json"

# =========================
# MULTI-CHANNEL CONFIG
# =========================

ACTIVE_CHANNEL = "default"

CHANNELS: Dict[str, Dict[str, Any]] = {
    "default": {
        # This must match the playlist in your One Minute Meditation channel
        "playlist_name": "Inner Rhythm - Works for calm and challenge",
        # If you know playlist ID, you can set it here to avoid searching:
        "playlist_id_override": None,  # e.g. "PLxxxxxxxxxxxxxx"

        # Schedule start date (for the VERY FIRST video in this channel)
        "schedule_start_date": date(2026, 2, 10),

        # Daily time window in local timezone
        "publish_hour_start": 18,   # 7 PM
        "publish_hour_end": 23,     # 11 PM

        # Timezone object
        "timezone": IST,
    },

    # You can add more profiles later, e.g. "second_channel": {...}
}

# =========================
# SAMPLE CHALLENGES & METADATA
# (REPLACE WITH YOUR FULL DATA)
# =========================

# ---- SAMPLE challenges_1 ----
challenges_1: List[Dict[str, Any]] = [
    {
        "id": 1,
        "mainTitle": "Breathing Challenge",
        "cycle": ["4-4-4-4", "4-6-4-6", "4-8-4-8"],
        "level": ["Level 1: 00:16", "Level 2: 00:20", "Final Level: 00:24"],
        "hookText": "Most people fail this immediately",
        "successText": "You did it, your control is next level",
        "challengeText": "Quit now or prove yourself",
        "initialScript": (
            "Three levels stand between you and victory. Each one gets harder. "
            "Most quit at level one. Will you be different?"
        ),
    },
    {
        "id": 2,
        "mainTitle": "Focus Drill",
        "cycle": ["4-4-4-4", "5-5-5-5", "6-6-6-6"],
        "level": ["Level 1: 00:16", "Level 2: 00:20", "Final Level: 00:24"],
        "hookText": "You will quit before finishing",
        "successText": "Your mind just leveled up, champion",
        "challengeText": "Do not break on final round",
        "initialScript": (
            "Your focus will be tested across three brutal levels. "
            "The pressure builds with each round. The final level separates winners from quitters."
        ),
    },
    # TODO: paste your full challenges_1..challenges_3 here
]

challenges_2: List[Dict[str, Any]] = []
challenges_3: List[Dict[str, Any]] = []
challenges_4: List[Dict[str, Any]] = []
challenges_5: List[Dict[str, Any]] = []

CHALLENGE_ARRAYS: List[List[Dict[str, Any]]] = [
    challenges_1,
    challenges_2,
    challenges_3,
    challenges_4,
    challenges_5,
]

# ---- SAMPLE title/description arrays ----
# Keys can be int (1,2,3) or str ("uuid") – code handles both.

array_one_title_desc: Dict[Any, Dict[str, Any]] = {
    1: {
        "title": "Breathing Challenge for Focus & Control | 3 Levels #Breathing #Calm",
        "description": (
            "Test your breath control through three progressive levels.\n"
            "Each round becomes harder and demands deeper focus.\n"
            "Most people quit early — stay calm and finish strong.\n\n"
            "#breathingchallenge #breathwork #meditation #focus #mentalstrength"
        ),
        "tags": [
            "breathing challenge",
            "breathwork",
            "meditation",
            "focus training",
            "mental strength",
        ],
    },
    2: {
        "title": "Focus Drill Breathing Exercise | Train Mental Discipline #Focus",
        "description": (
            "Sharpen your focus with this structured breathing drill.\n"
            "Three intense levels train sustained concentration.\n"
            "The final round separates focus from distraction.\n\n"
            "#focusdrill #breathingexercise #mindcontrol #clarity"
        ),
        "tags": [
            "focus drill",
            "breathing exercise",
            "concentration",
            "mind control",
            "mental clarity",
        ],
    },
    # TODO: paste your full array_one_title_desc here
}

array_two_title_desc: Dict[Any, Dict[str, Any]] = {
    # TODO: paste your full array_two_title_desc here (for techniques)
}

array_three_title_desc: Dict[Any, Dict[str, Any]] = {
    # TODO: paste your full array_three_title_desc here (advanced)
}

array_four_title_desc: Dict[Any, Dict[str, Any]] = {}
array_five_title_desc: Dict[Any, Dict[str, Any]] = {}

TITLE_DESC_ARRAYS: List[Dict[Any, Dict[str, Any]]] = [
    array_one_title_desc,
    array_two_title_desc,
    array_three_title_desc,
    array_four_title_desc,
    array_five_title_desc,
]

# =========================
# STATE HANDLING
# =========================

def load_full_state() -> Dict[str, Any]:
    """Load global state (per channel) from JSON."""
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def get_channel_state(full_state: Dict[str, Any], channel_name: str) -> Dict[str, Any]:
    """Get or initialize state for a specific channel name."""
    if channel_name not in full_state:
        full_state[channel_name] = {
            "last_uploaded_challenge_id": None,
            "uploaded": {},  # id_str -> video_id
            "last_run": None,
        }
    return full_state[channel_name]


def save_full_state(full_state: Dict[str, Any]) -> None:
    full_state.setdefault(ACTIVE_CHANNEL, {})["last_run"] = datetime.utcnow().isoformat() + "Z"
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(full_state, f, indent=2)


# =========================
# AUTHENTICATION
# =========================

def authenticate_youtube():
    """Authenticate and return a YouTube API client."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            creds_data = json.load(f)
        creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds or not creds.valid:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    return youtube


# =========================
# METADATA LOOKUP
# =========================

def flatten_challenges() -> List[Dict[str, Any]]:
    """Flatten all challenge arrays into one ordered list."""
    all_items: List[Dict[str, Any]] = []
    for arr in CHALLENGE_ARRAYS:
        for c in arr:
            if "id" in c:
                all_items.append(c)
    return all_items


def get_title_description(challenge_id: Any) -> Optional[Dict[str, Any]]:
    """
    Look up title/description/tags from TITLE_DESC_ARRAYS.
    Supports int or str IDs.
    """
    candidates = [challenge_id]
    # Attempt int form
    try:
        candidates.append(int(str(challenge_id)))
    except Exception:
        pass
    # Always try string form
    candidates.append(str(challenge_id))

    for mapping in TITLE_DESC_ARRAYS:
        for key in candidates:
            if key in mapping:
                return mapping[key]
    return None


def fallback_generate_title(challenge: Dict[str, Any]) -> str:
    main_title = challenge.get("mainTitle", "").strip()
    hook = challenge.get("hookText", "").strip()
    parts = [main_title] if main_title else []
    if hook:
        parts.append(f"- {hook}")
    base_title = " ".join(parts) if parts else "Breathing Exercise"
    suffix = " | Breathing Technique & Meditation"
    full = (base_title + suffix).strip()
    if len(full) > 90:
        return full[:87] + "..."
    return full


def fallback_generate_description(challenge: Dict[str, Any]) -> str:
    description: List[str] = []

    initial_script = challenge.get("initialScript", "").strip()
    if initial_script:
        description.append(initial_script)

    success_text = challenge.get("successText", "").strip()
    if success_text:
        description.append(f"Success Message: {success_text}")

    challenge_text = challenge.get("challengeText", "").strip()
    if challenge_text:
        description.append(f"Challenge: {challenge_text}")

    cycle = challenge.get("cycle", [])
    if cycle:
        description.append(f"Breathing Cycles: {', '.join(cycle)}")

    level = challenge.get("level", [])
    if level:
        l_strs = [str(l) for l in level]
        description.append(f"Difficulty Levels: {', '.join(l_strs)}")

    description.append("#breathing #meditation #calm #focus #breathwork")
    return "\n\n".join(description)


# =========================
# FILTERING BY ID RANGE
# =========================

def filter_challenges_by_id_range(
    challenges: List[Dict[str, Any]],
    start_from_id: Optional[str],
    stop_at_id: Optional[str],
    start_is_last_uploaded: bool,
) -> List[Dict[str, Any]]:
    """
    Filter challenges by ordered ID range.

    - `start_from_id`:
        * if None → start from first challenge
        * if not None & start_is_last_uploaded=True → start AFTER this id
        * if not None & start_is_last_uploaded=False → start AT this id
    - `stop_at_id`:
        * if None → go until last challenge
        * if not None → include that id if found
    """
    ids = [str(c["id"]) for c in challenges]

    start_idx = 0
    if start_from_id is not None:
        start_str = str(start_from_id)
        if start_str in ids:
            idx = ids.index(start_str)
            start_idx = idx + 1 if start_is_last_uploaded else idx

    stop_idx = len(challenges)
    if stop_at_id is not None:
        stop_str = str(stop_at_id)
        if stop_str in ids:
            idx = ids.index(stop_str)
            stop_idx = idx + 1  # inclusive

    return challenges[start_idx:stop_idx]


# =========================
# YOUTUBE HELPERS
# =========================

def get_playlist_id(youtube, playlist_name: str, override: Optional[str]) -> Optional[str]:
    if override:
        return override

    try:
        request = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50,
        )
        while request is not None:
            response = request.execute()
            for pl in response.get("items", []):
                if pl["snippet"]["title"] == playlist_name:
                    return pl["id"]
            request = youtube.playlists().list_next(request, response)
    except googleapiclient.errors.HttpError as e:
        print(f"[ERROR] Failed to fetch playlists: {e}")
        return None

    print(f"[WARN] Playlist '{playlist_name}' not found.")
    return None


def upload_video(
    youtube,
    file_path: str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
) -> Optional[str]:
    """Upload a video file as PRIVATE."""
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return None

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": YOUTUBE_CATEGORY_ID,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
        },
    }

    if tags:
        body["snippet"]["tags"] = tags

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"    Upload progress: {int(status.progress() * 100)}%")

        vid = response.get("id")
        print(f"[OK] Uploaded video ID: {vid}")
        return vid
    except googleapiclient.errors.HttpError as e:
        print(f"[ERROR] Failed to upload {file_path}: {e}")
        return None


def add_to_playlist(youtube, video_id: str, playlist_id: Optional[str]) -> bool:
    if not playlist_id:
        print("[WARN] No playlist ID; skipping playlist add.")
        return False

    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id,
            },
        }
    }

    try:
        youtube.playlistItems().insert(
            part="snippet",
            body=body,
        ).execute()
        print(f"[OK] Added to playlist: {playlist_id}")
        return True
    except googleapiclient.errors.HttpError as e:
        print(f"[ERROR] Failed to add to playlist: {e}")
        return False


def schedule_video_publication(
    youtube,
    video_id: str,
    publish_time_local: datetime,
) -> bool:
    """Schedule PRIVATE video to publish at given local datetime."""
    if publish_time_local.tzinfo is None:
        raise ValueError("publish_time_local must be timezone-aware")

    publish_time_utc = publish_time_local.astimezone(timezone.utc)
    publish_at_str = publish_time_utc.isoformat().replace("+00:00", "Z")

    body = {
        "id": video_id,
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at_str,
            "selfDeclaredMadeForKids": False,
        },
    }

    try:
        youtube.videos().update(
            part="status",
            body=body,
        ).execute()
        print(
            f"[OK] Scheduled publish at local {publish_time_local} "
            f"(UTC {publish_time_utc})"
        )
        return True
    except googleapiclient.errors.HttpError as e:
        print(f"[ERROR] Failed to schedule {video_id}: {e}")
        return False


# =========================
# SCHEDULING UTIL
# =========================

def calculate_publish_time_for_index(
    channel_cfg: Dict[str, Any],
    global_index: int,
) -> datetime:
    """
    Given channel config and a global index (0-based position across all uploads),
    return the local datetime for publishing that video.
    """
    base_date: date = channel_cfg["schedule_start_date"]
    tz = channel_cfg["timezone"]
    d = base_date + timedelta(days=global_index)

    hour = random.randint(
        channel_cfg["publish_hour_start"],
        channel_cfg["publish_hour_end"],
    )
    minute = random.randint(0, 59)

    return datetime(
        year=d.year,
        month=d.month,
        day=d.day,
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
        tzinfo=tz,
    )


# =========================
# MAIN WORKFLOW
# =========================

def main_upload_workflow():
    print("🔐 Authenticating with YouTube API...")
    youtube = authenticate_youtube()
    print("✅ Authentication successful.")

    channel_cfg = CHANNELS[ACTIVE_CHANNEL]

    print(f"📺 Active channel profile: {ACTIVE_CHANNEL}")
    print(f"🎵 Playlist name: {channel_cfg['playlist_name']}")

    playlist_id = None
    if not DRY_RUN:
        playlist_id = get_playlist_id(
            youtube,
            channel_cfg["playlist_name"],
            channel_cfg.get("playlist_id_override"),
        )
        if playlist_id:
            print(f"✅ Using playlist ID: {playlist_id}")
        else:
            print("[WARN] No playlist found; continuing without playlist add.")

    # Load state
    full_state = load_full_state()
    channel_state = get_channel_state(full_state, ACTIVE_CHANNEL)

    # Flatten challenges in the order of arrays
    all_challenges = flatten_challenges()
    if not all_challenges:
        print("[ERROR] No challenges defined in CHALLENGE_ARRAYS.")
        return

    # Decide start_from_id based on config or state
    if START_FROM_ID is not None:
        start_from_id = str(START_FROM_ID)
        start_is_last_uploaded = False  # inclusive start
    else:
        start_from_id = channel_state.get("last_uploaded_challenge_id")
        start_is_last_uploaded = True   # resume AFTER last uploaded

    stop_at_id = str(STOP_AT_ID) if STOP_AT_ID is not None else None

    filtered_challenges = filter_challenges_by_id_range(
        all_challenges,
        start_from_id=start_from_id,
        stop_at_id=stop_at_id,
        start_is_last_uploaded=start_is_last_uploaded,
    )

    print(f"📦 Total challenges available: {len(all_challenges)}")
    print(f"🎯 Challenges to process this run: {len(filtered_challenges)}")

    already_uploaded_map: Dict[str, str] = channel_state.get("uploaded", {})
    total_uploaded_before = len(already_uploaded_map)

    uploads_this_run = 0
    errors = 0
    skipped = 0

    for ch in filtered_challenges:
        if uploads_this_run >= MAX_UPLOADS_PER_RUN:
            print("🚦 Reached MAX_UPLOADS_PER_RUN limit, stopping this session.")
            break

        cid_str = str(ch["id"])

        if cid_str in already_uploaded_map:
            print(f"⏭️  Challenge id={cid_str} already uploaded, skipping.")
            skipped += 1
            continue

        # Lookup metadata
        td = get_title_description(ch["id"])
        if td:
            title = td.get("title") or fallback_generate_title(ch)
            description = td.get("description") or fallback_generate_description(ch)
            tags = td.get("tags")
        else:
            print(f"[INFO] No title/desc entry for id={cid_str}; using fallback.")
            title = fallback_generate_title(ch)
            description = fallback_generate_description(ch)
            tags = None

        # If tags still None, try to derive from hashtags in description
        if tags is None:
            tags = [w.strip("#") for w in description.split() if w.startswith("#")]

        # File path
        video_file = VIDEOS_DIR / f"{VIDEO_PREFIX}{cid_str}{VIDEO_SUFFIX}"

        print("-" * 60)
        print(f"🎬 Processing challenge id={cid_str}")
        print(f"    File: {video_file}")
        print(f"    Title: {title}")

        if DRY_RUN:
            print("💡 [DRY RUN] Skipping upload, playlist add, and scheduling.")
            fake_video_id = f"dry_{cid_str}"
            channel_state["uploaded"][cid_str] = fake_video_id
            channel_state["last_uploaded_challenge_id"] = cid_str
            uploads_this_run += 1
            continue

        # Upload
        video_id = upload_video(
            youtube=youtube,
            file_path=str(video_file),
            title=title,
            description=description,
            tags=tags,
        )

        if not video_id:
            errors += 1
            continue

        # Add to playlist (best effort)
        add_to_playlist(youtube, video_id, playlist_id)

        # Compute global index to find the day's offset
        global_index = total_uploaded_before + uploads_this_run
        publish_time_local = calculate_publish_time_for_index(channel_cfg, global_index)

        # Schedule
        ok = schedule_video_publication(
            youtube=youtube,
            video_id=video_id,
            publish_time_local=publish_time_local,
        )

        if not ok:
            errors += 1
            continue

        # Update state
        channel_state["uploaded"][cid_str] = video_id
        channel_state["last_uploaded_challenge_id"] = cid_str
        uploads_this_run += 1

        # Persist state after each successful schedule
        full_state[ACTIVE_CHANNEL] = channel_state
        save_full_state(full_state)

    # Final state save
    full_state[ACTIVE_CHANNEL] = channel_state
    save_full_state(full_state)

    print("=" * 60)
    print("UPLOAD SUMMARY")
    print(f"Channel profile: {ACTIVE_CHANNEL}")
    print(f"Total challenges defined: {len(all_challenges)}")
    print(f"Total uploaded before this run: {total_uploaded_before}")
    print(f"Uploaded this run: {uploads_this_run}")
    print(f"Skipped (already uploaded): {skipped}")
    print(f"Errors: {errors}")
    print(f"Last uploaded challenge id: {channel_state.get('last_uploaded_challenge_id')}")
    print("=" * 60)


if __name__ == "__main__":
    main_upload_workflow()

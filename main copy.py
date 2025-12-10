#!/usr/bin/env python3
"""
Bulk YouTube uploader & scheduler for breathing challenge videos.

Features:
- Reads video files from local folder
- Matches each file to challenge metadata (multiple JSON arrays, with variant handling)
- Uses separate JSON arrays for SEO title & description
- Uploads as PRIVATE via YouTube Data API
- Adds each video to a specific playlist
- Schedules 1 video per day between 7 PM–12 AM IST starting from a given date
"""

import os
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload

# =========================
# CONFIGURATION CONSTANTS
# =========================

# Folder containing final rendered videos
VIDEOS_DIR = Path("/Users/kedarbhokare/Desktop/electron/breathing-app/electron/donevideos/done")

# Filename pattern: challenge_final_[NUMBER].mp4 or challenge_final_[NUMBER]c.mp4
VIDEO_PREFIX = "challenge_final_"
VIDEO_SUFFIX = ".mp4"

# How many initial videos (by sorted order) are already uploaded
ALREADY_UPLOADED_COUNT = 19  # you can change this anytime

# Start publishing date (IST) for the first *new* upload
START_DATE_IST = datetime(2025, 12, 23)  # YYYY, MM, DD (no time; we'll add it)

# Daily time window (IST)
PUBLISH_HOUR_START = 19  # 7 PM
PUBLISH_HOUR_END = 23   # 11 PM (inclusive)

# YouTube settings
CLIENT_ID = "253024420950-5f4iinjbn60pcgo831c7v88irvqn9l6g.apps.googleusercontent.com"
CLIENT_SECRETS_FILE = "client_secret.json"  # path to your OAuth client secrets
TOKEN_FILE = "youtube_token.json"          # cached user credentials
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]

# Playlist to add videos into
PLAYLIST_NAME = "Inner Rhythm - Works for calm and challenge"
# If you already know the playlist ID, you can hardcode it here:
PLAYLIST_ID_OVERRIDE = None  # e.g. "PLxxxxxxxxxxxxxxxxxxx"

# Video category
YOUTUBE_CATEGORY_ID = "27"  # Education (or "22" People & Blogs)

# Timezone for scheduling
IST = timezone(timedelta(hours=5, minutes=30))

# =========================
# JSON DATA PLACEHOLDERS
# =========================
# Replace these with your actual challenge JSON arrays.
# They should each be a list of dicts like:
# {
#   "id": 20,
#   "mainTitle": "...",
#   "cycle": [...],
#   "level": [...],
#   "hookText": "...",
#   "successText": "...",
#   "challengeText": "...",
#   "initialScript": "..."
# }

challenges_1: List[Dict[str, Any]] = [
  {
    "id": 1,
    "mainTitle": "Breathing Challenge",
    "cycle": ["4-4-4-4", "4-6-4-6", "4-8-4-8"],
    "level": ["Level 1: 00:16", "Level 2: 00:20", "Final Level: 00:24"],
    "hookText": "Most people fail this immediately",
    "successText": "You did it, your control is next level",
    "challengeText": "Quit now or prove yourself",
    "initialScript": "Three levels stand between you and victory. Each one gets harder. Most quit at level one. Will you be different?"
  },
  {
    "id": 2,
    "mainTitle": "Breathing Challenge",
    "cycle": ["4-4-4-4", "4-5-4-5", "4-6-4-6", "4-7-4-7", "4-8-4-8"],
    "level": [
      "Level 1: 00:16",
      "Level 2: 00:18",
      "Level 3: 00:20",
      "Level 4: 00:22",
      "Final Level: 00:24"
    ],
    "hookText": "Bet you cannot finish all five",
    "successText": "Endurance gained, well done",
    "challengeText": "Level five destroys most people",
    "initialScript": "Five levels. Each one pushes you further than the last. The real test begins at level four. Stay strong till the final round."
  },
  {
    "id": 3,
    "mainTitle": "Focus Drill",
    "cycle": ["4-4-4-4", "5-5-5-5", "6-6-6-6"],
    "level": ["Level 1: 00:16", "Level 2: 00:20", "Final Level: 00:24"],
    "hookText": "You will quit before finishing",
    "successText": "Your mind just leveled up, champion",
    "challengeText": "Do not break on final round",
    "initialScript": "Your focus will be tested across three brutal levels. The pressure builds with each round. The final level separates winners from quitters."
  },
  {
    "id": 4,
    "mainTitle": "Calm Under Pressure",
    "cycle": ["4-4-4-4", "4-7-4-7", "4-10-4-10"],
    "level": ["Level 1: 00:16", "Level 2: 00:22", "Final Level: 00:26"],
    "hookText": "This is too hard for you",
    "successText": "You stayed calm when others would panic",
    "challengeText": "Final level breaks weak minds",
    "initialScript": "Three levels of increasing pressure await. Can you stay calm when level three hits? That's where most minds break."
  },
  {
    "id": 5,
    "mainTitle": "Breathing Challenge",
    "cycle": ["5-5-5-5", "5-6-5-6", "5-7-5-7"],
    "level": ["Level 1: 00:20", "Level 2: 00:22", "Final Level: 00:24"],
    "hookText": "Your mental strength is weak",
    "successText": "You just proved your mental strength",
    "challengeText": "Prove you belong at top",
    "initialScript": "This challenge demands mental strength from the start. Each level intensifies. Only the mentally tough reach level three."
  },
  {
    "id": 6,
    "mainTitle": "Breathwork Challenge",
    "cycle": ["4-4-4-4", "4-6-4-6", "4-8-4-8", "4-10-4-10"],
    "level": [
      "Level 1: 00:16",
      "Level 2: 00:20",
      "Level 3: 00:24",
      "Final Level: 00:26"
    ],
    "hookText": "Nobody expects you to finish",
    "successText": "You finished strong, respect earned",
    "challengeText": "Level four separates winners from losers",
    "initialScript": "Four levels of escalating difficulty. Nobody expects you to make it. Prove them wrong by reaching level four."
  },
  {
    "id": 7,
    "mainTitle": "Control Test",
    "cycle": ["4-5-4-5", "4-6-4-6", "4-7-4-7"],
    "level": ["Level 1: 00:18", "Level 2: 00:20", "Final Level: 00:22"],
    "hookText": "You do not have the control",
    "successText": "You have real control now",
    "challengeText": "Show control till the end",
    "initialScript": "Your control will be tested immediately. Three levels that demand precision. Lose control at any point and it's over."
  },
  {
    "id": 8,
    "mainTitle": "Discipline Builder",
    "cycle": ["5-4-5-4", "5-5-5-5", "5-6-5-6"],
    "level": ["Level 1: 00:18", "Level 2: 00:20", "Final Level: 00:22"],
    "hookText": "Your discipline is untested",
    "successText": "Discipline built, you are stronger now",
    "challengeText": "Weak people quit at two",
    "initialScript": "Discipline is earned through three levels of commitment. Weak people fold at level two. Push through to prove your worth."
  },
  {
    "id": 9,
    "mainTitle": "Breathing Challenge",
    "cycle": ["4-4-4-4", "4-8-4-8", "4-12-4-12"],
    "level": ["Level 1: 00:16", "Level 2: 00:24", "Final Level: 00:26"],
    "hookText": "This breath hold crushes everyone",
    "successText": "You held strong when others gave up",
    "challengeText": "Final hold breaks the weak",
    "initialScript": "Each level doubles the difficulty with longer holds. Level three is where champions are made. Can you hold when it counts?"
  },
  {
    "id": 10,
    "mainTitle": "Pressure Test",
    "cycle": ["4-4-4-4", "5-5-5-5", "6-6-6-6", "7-7-7-7"],
    "level": [
      "Level 1: 00:16",
      "Level 2: 00:20",
      "Level 3: 00:24",
      "Final Level: 00:26"
    ],
    "hookText": "Pressure will expose you",
    "successText": "You mastered pressure, well done",
    "challengeText": "Stay strong through level four",
    "initialScript": "Four levels of mounting pressure. Each one reveals more about your character. Level four exposes the truth about who you really are."
  },
  {
    "id": 11,
    "mainTitle": "Reset Your Mind",
    "cycle": ["4-6-4-6", "4-7-4-7", "4-8-4-8"],
    "level": ["Level 1: 00:20", "Level 2: 00:22", "Final Level: 00:24"],
    "hookText": "Your mind is too scattered",
    "successText": "Your mind is reset and sharper now",
    "challengeText": "Finish all three or fail",
    "initialScript": "Three levels to completely reset your scattered mind. Miss one and you fail. Stay locked in till the final breath."
  },
  {
    "id": 12,
    "mainTitle": "Endurance Challenge",
    "cycle": ["5-5-5-5", "5-7-5-7", "5-9-5-9"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:26"],
    "hookText": "You lack the endurance",
    "successText": "You outlasted the challenge, champion",
    "challengeText": "Endure till final or quit",
    "initialScript": "This is pure endurance over three grueling levels. The pain intensifies with each round. Only champions survive till the final level."
  },
  {
    "id": 13,
    "mainTitle": "Focus Builder",
    "cycle": ["4-4-4-4", "4-5-4-5", "4-6-4-6", "4-7-4-7"],
    "level": [
      "Level 1: 00:16",
      "Level 2: 00:18",
      "Level 3: 00:20",
      "Final Level: 00:22"
    ],
    "hookText": "You cannot focus this long",
    "successText": "Your focus is sharper than before",
    "challengeText": "Do not break at four",
    "initialScript": "Four levels designed to shatter your focus. Each one demands more concentration. Level four is where minds break."
  },
  {
    "id": 14,
    "mainTitle": "Calm Mastery",
    "cycle": ["4-6-4-6", "4-8-4-8", "4-10-4-10"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:26"],
    "hookText": "Calm is not for you",
    "successText": "You mastered calm under pressure today",
    "challengeText": "Master all three levels now",
    "initialScript": "Three levels separate you from true calm mastery. The difficulty escalates rapidly. Master level three and you master yourself."
  },
  {
    "id": 15,
    "mainTitle": "Mental Reset",
    "cycle": ["5-4-5-4", "5-6-5-6", "5-8-5-8"],
    "level": ["Level 1: 00:18", "Level 2: 00:22", "Final Level: 00:26"],
    "hookText": "Your mind is already defeated",
    "successText": "Your mind is clear and ready now",
    "challengeText": "Reset happens at level three",
    "initialScript": "Your mind thinks it's already beaten. Three levels prove otherwise. The real mental reset happens only if you reach level three."
  },
  {
    "id": 16,
    "mainTitle": "Willpower Test",
    "cycle": ["4-4-4-4", "4-6-4-6", "4-8-4-8", "4-10-4-10"],
    "level": [
      "Level 1: 00:16",
      "Level 2: 00:20",
      "Level 3: 00:24",
      "Final Level: 00:26"
    ],
    "hookText": "Your willpower is nothing",
    "successText": "You showed real willpower today",
    "challengeText": "Level four tests your soul",
    "initialScript": "Four brutal levels will test every ounce of willpower you have. Each round pushes deeper. Level four reaches into your soul."
  },
  {
    "id": 17,
    "mainTitle": "Breathing Drill",
    "cycle": ["5-5-5-5", "5-6-5-6", "5-7-5-7", "5-8-5-8"],
    "level": [
      "Level 1: 00:20",
      "Level 2: 00:22",
      "Level 3: 00:24",
      "Final Level: 00:26"
    ],
    "hookText": "Too difficult for average people",
    "successText": "You are more disciplined now",
    "challengeText": "Finish level four right now",
    "initialScript": "Average people don't make it past level two. Four levels of progressive intensity await. Finish level four to prove you're elite."
  },
  {
    "id": 18,
    "mainTitle": "Concentration Challenge",
    "cycle": ["4-5-4-5", "4-7-4-7", "4-9-4-9"],
    "level": ["Level 1: 00:18", "Level 2: 00:22", "Final Level: 00:26"],
    "hookText": "Your concentration is weak",
    "successText": "Your concentration is elite level now",
    "challengeText": "Last level destroys most minds",
    "initialScript": "Three levels of extreme concentration demands. The jumps in difficulty are brutal. The last level destroys most minds who attempt it."
  },
  {
    "id": 19,
    "mainTitle": "Stress Relief Test",
    "cycle": ["4-4-4-4", "5-5-5-5", "6-6-6-6"],
    "level": ["Level 1: 00:16", "Level 2: 00:20", "Final Level: 00:24"],
    "hookText": "Stress already won against you",
    "successText": "Stress gone, you earned this peace",
    "challengeText": "Complete all three or lose",
    "initialScript": "Stress thinks it owns you. Three levels to prove it wrong. Complete all three or admit defeat."
  },
  {
    "id": 20,
    "mainTitle": "Composure Drill",
    "cycle": ["4-6-4-6", "5-7-5-7", "6-8-6-8"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:26"],
    "hookText": "You will lose composure fast",
    "successText": "You stayed composed when it mattered",
    "challengeText": "Stay composed through level three",
    "initialScript": "Your composure will crack under three levels of escalating pressure. Each round intensifies. Hold it together through level three."
  },
  {
    "id": 21,
    "mainTitle": "Breathing Challenge",
    "cycle": ["4-4-4-4", "4-7-4-7", "4-10-4-10"],
    "level": ["Level 1: 00:16", "Level 2: 00:22", "Final Level: 00:26"],
    "hookText": "Control is not your strength",
    "successText": "You have complete breath control now",
    "challengeText": "Level two breaks most people",
    "initialScript": "Control becomes harder with each of three levels. Most people break at level two. Push through to claim complete mastery."
  },
  {
    "id": 22,
    "mainTitle": "Clarity Challenge",
    "cycle": ["5-5-5-5", "5-6-5-6", "5-7-5-7"],
    "level": ["Level 1: 00:20", "Level 2: 00:22", "Final Level: 00:24"],
    "hookText": "Your mind is too foggy",
    "successText": "Your mind has clarity now",
    "challengeText": "Get to three for clarity",
    "initialScript": "Cut through the mental fog across three progressive levels. Clarity only comes if you reach level three. Will you make it?"
  },
  {
    "id": 23,
    "mainTitle": "Patience Builder",
    "cycle": ["4-6-4-6", "4-8-4-8", "4-10-4-10", "4-12-4-12"],
    "level": [
      "Level 1: 00:20",
      "Level 2: 00:24",
      "Level 3: 00:26",
      "Final Level: 00:26"
    ],
    "hookText": "You have zero patience",
    "successText": "You proved you have real patience",
    "challengeText": "Four levels only patient survive",
    "initialScript": "Patience is tested across four increasingly difficult levels. The impatient quit early. Only the truly patient survive level four."
  },
  {
    "id": 24,
    "mainTitle": "Focus Challenge",
    "cycle": ["4-5-4-5", "4-6-4-6", "4-7-4-7", "4-8-4-8"],
    "level": [
      "Level 1: 00:18",
      "Level 2: 00:20",
      "Level 3: 00:22",
      "Final Level: 00:24"
    ],
    "hookText": "Focus is impossible for you",
    "successText": "You finished focused, well done",
    "challengeText": "Stay locked through four levels",
    "initialScript": "Four levels that demand unwavering focus. One distraction and you're done. Stay locked in through every single level."
  },
  {
    "id": 25,
    "mainTitle": "Mindfulness Drill",
    "cycle": ["5-4-5-4", "5-5-5-5", "5-6-5-6", "5-7-5-7"],
    "level": [
      "Level 1: 00:18",
      "Level 2: 00:20",
      "Level 3: 00:22",
      "Final Level: 00:24"
    ],
    "hookText": "Mindfulness is not in you",
    "successText": "You stayed mindful through every level",
    "challengeText": "Mindful ones reach level four",
    "initialScript": "True mindfulness is proven across four challenging levels. Each one demands deeper awareness. Only the mindful reach level four."
  },
  {
    "id": 26,
    "mainTitle": "Resilience Test",
    "cycle": ["4-4-4-4", "4-6-4-6", "4-9-4-9"],
    "level": ["Level 1: 00:16", "Level 2: 00:20", "Final Level: 00:26"],
    "hookText": "You break under real tests",
    "successText": "You showed real resilience today",
    "challengeText": "Survive all three or quit",
    "initialScript": "Three levels designed to break you. The difficulty spikes hard. Survive all three to prove your resilience is real."
  },
  {
    "id": 27,
    "mainTitle": "Inner Strength Challenge",
    "cycle": ["5-5-5-5", "5-7-5-7", "5-9-5-9"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:26"],
    "hookText": "You do not have inner strength",
    "successText": "You found your inner strength",
    "challengeText": "Three levels test your core",
    "initialScript": "Inner strength is forged through three intense levels. Each one digs deeper into your core. Level three reveals your true foundation."
  },
  {
    "id": 28,
    "mainTitle": "Breathing Challenge",
    "cycle": ["4-4-4-4", "5-5-5-5", "6-6-6-6", "7-7-7-7"],
    "level": [
      "Level 1: 00:16",
      "Level 2: 00:20",
      "Level 3: 00:24",
      "Final Level: 00:26"
    ],
    "hookText": "Your breath is unsteady always",
    "successText": "You kept steady through every level",
    "challengeText": "Stay steady all four rounds",
    "initialScript": "Four levels where steady breathing is everything. One slip and you lose. Stay unshaken from level one through level four."
  },
  {
    "id": 29,
    "mainTitle": "Grit Test",
    "cycle": ["4-6-4-6", "4-8-4-8", "4-10-4-10"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:26"],
    "hookText": "Grit is something you lack",
    "successText": "You have proven grit today",
    "challengeText": "Show grit through three levels",
    "initialScript": "Real grit is tested across three unforgiving levels. Each one demands more than the last. Show your grit through level three."
  },
  {
    "id": 30,
    "mainTitle": "Peak Focus Drill",
    "cycle": ["4-5-4-5", "4-7-4-7", "4-9-4-9", "4-11-4-11"],
    "level": [
      "Level 1: 00:18",
      "Level 2: 00:22",
      "Level 3: 00:26",
      "Final Level: 00:26"
    ],
    "hookText": "Peak focus is beyond you",
    "successText": "You reached peak focus state",
    "challengeText": "Four levels to peak state",
    "initialScript": "Peak focus requires surviving four progressively brutal levels. The difficulty jumps are massive. Reach level four to achieve peak state."
  },
  {
    "id": 31,
    "mainTitle": "Balance Challenge",
    "cycle": ["5-5-5-5", "5-6-5-6", "5-7-5-7", "5-8-5-8"],
    "level": [
      "Level 1: 00:20",
      "Level 2: 00:22",
      "Level 3: 00:24",
      "Final Level: 00:26"
    ],
    "hookText": "Balance is not for you",
    "successText": "You found perfect balance within",
    "challengeText": "Four levels to find balance",
    "initialScript": "Balance is earned through four demanding levels. Consistency is everything here. Reach level four to find your perfect balance."
  },
  {
    "id": 32,
    "mainTitle": "Courage Test",
    "cycle": ["4-4-4-4", "4-7-4-7", "4-10-4-10"],
    "level": ["Level 1: 00:16", "Level 2: 00:22", "Final Level: 00:26"],
    "hookText": "Your courage is fake",
    "successText": "You showed courage when tested",
    "challengeText": "Prove courage at level three",
    "initialScript": "Three levels will expose whether your courage is real or fake. The pressure builds fast. Prove it at level three."
  },
  {
    "id": 33,
    "mainTitle": "Breakthrough Drill",
    "cycle": ["5-6-5-6", "5-7-5-7", "5-8-5-8"],
    "level": ["Level 1: 00:22", "Level 2: 00:24", "Final Level: 00:26"],
    "hookText": "Breakthrough is too hard for you",
    "successText": "You just had a mental breakthrough",
    "challengeText": "Push to three for breakthrough",
    "initialScript": "Mental breakthroughs happen at level three. Two levels prepare you. The third level breaks you through or breaks you down."
  },
  {
    "id": 34,
    "mainTitle": "Perseverance Challenge",
    "cycle": ["4-5-4-5", "4-6-4-6", "4-7-4-7", "4-8-4-8", "4-9-4-9"],
    "level": [
      "Level 1: 00:18",
      "Level 2: 00:20",
      "Level 3: 00:22",
      "Level 4: 00:24",
      "Final Level: 00:26"
    ],
    "hookText": "Five levels will destroy you",
    "successText": "Your perseverance paid off today",
    "challengeText": "Five levels only strong survive",
    "initialScript": "Five grueling levels designed to destroy your will. Each one harder than the last. Only those with true perseverance survive level five."
  }

]



challenges_2: List[Dict[str, Any]] = [
    # TODO: fill with your real data
  {
    "id": 3,
    "mainTitle": "Box Breath",
    "cycle": ["4-4-4-4", "5-5-5-5", "6-6-6-6"],
    "level": ["Level 1: 00:16", "Level 2: 00:20", "Final Level: 00:24"],
    "hookText": "Prove your calm now",
    "successText": "You held steady and mastered your breath",
    "challengeText": "Do not break",
    "initialScript": "This method resets your mind fast. Follow the corners with control. Hold steady at each step."
  },
  {
    "id": 6,
    "mainTitle": "Triangle Breath",
    "cycle": ["4-4-6-0", "5-5-8-0", "6-6-10-0"],
    "level": ["Level 1: 00:16", "Level 2: 00:20", "Final Level: 00:22"],
    "hookText": "Hold your focus strong",
    "successText": "You stayed patient and your mind feels lighter",
    "challengeText": "Keep going now",
    "initialScript": "This pattern builds calm with every step. Each side of the triangle demands control. Stay with me and breathe slow."
  },
  {
    "id": 9,
    "mainTitle": "Equal Breath",
    "cycle": ["4-0-4-0", "5-0-5-0", "6-0-6-0"],
    "level": ["Level 1: 00:16", "Level 2: 00:20", "Final Level: 00:24"],
    "hookText": "Balance your energy right now",
    "successText": "Your breath is even and your mind is clear",
    "challengeText": "Stay balanced",
    "initialScript": "Perfect balance creates perfect calm. Each breath matches the last. This is where discipline meets peace."
  },
  {
    "id": 12,
    "mainTitle": "Coherence Breath",
    "cycle": ["5-0-5-0", "6-0-6-0", "7-0-7-0"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Sync your heart and mind",
    "successText": "You found the rhythm that brings total coherence",
    "challengeText": "Hold the rhythm",
    "initialScript": "Your heart and breath speak the same language. This rhythm unlocks flow state. Find the pulse and stay inside it."
  },
  {
    "id": 15,
    "mainTitle": "Extended Exhale",
    "cycle": ["4-0-6-0", "4-0-8-0", "5-0-10-0"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Release what holds you back",
    "successText": "You let go deeply and reclaimed your peace",
    "challengeText": "Release fully",
    "initialScript": "The exhale is where tension dies. Let each breath out last longer. This is how you reset your nervous system."
  },
  {
    "id": 18,
    "mainTitle": "Resonance Breath",
    "cycle": ["5-1-5-1", "6-1-6-1", "7-1-7-1"],
    "level": ["Level 1: 00:24", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Find your natural rhythm now",
    "successText": "You tapped into your optimal breathing frequency",
    "challengeText": "Stay in resonance",
    "initialScript": "There is a frequency where your body hums. This breath finds it. Stay smooth and let the rhythm take over."
  },
  {
    "id": 21,
    "mainTitle": "Diaphragmatic Breath",
    "cycle": ["5-2-5-0", "6-2-6-0", "7-2-7-0"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Breathe deep from your core",
    "successText": "You activated your deepest breath and found true calm",
    "challengeText": "Go deeper",
    "initialScript": "Shallow breathing keeps you weak. Pull air deep into your belly. This is the foundation of real control."
  },
  {
    "id": 24,
    "mainTitle": "Four Seven Eight",
    "cycle": ["4-7-8-0", "4-7-8-2", "5-7-8-2"],
    "level": ["Level 1: 00:19", "Level 2: 00:21", "Final Level: 00:22"],
    "hookText": "Can you hold seven seconds",
    "successText": "You mastered the hold and unlocked deep relaxation",
    "challengeText": "Hold longer",
    "initialScript": "This pattern was built for sleep and stress. The hold is where the magic happens. Trust the numbers and stay focused."
  },
  {
    "id": 27,
    "mainTitle": "Mindful Cadence",
    "cycle": ["4-2-4-2", "5-2-5-2", "6-3-6-3"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Control every second of breath",
    "successText": "You commanded every moment with precision and clarity",
    "challengeText": "Stay precise",
    "initialScript": "Every second matters here. You control the rhythm from start to finish. This is where awareness becomes power."
  },
  {
    "id": 30,
    "mainTitle": "Calming Ratio",
    "cycle": ["4-4-8-0", "5-5-10-0", "6-6-12-0"],
    "level": ["Level 1: 00:16", "Level 2: 00:20", "Final Level: 00:24"],
    "hookText": "Double your exhale and find peace",
    "successText": "You calmed your system with every extended breath",
    "challengeText": "Extend further",
    "initialScript": "The exhale calms you twice as fast. Make it twice as long. This ratio brings instant relief when chaos rises."
  },
  {
    "id": 33,
    "mainTitle": "Progressive Hold",
    "cycle": ["4-3-4-3", "5-4-5-4", "6-5-6-5"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Test your hold strength now",
    "successText": "You strengthened your breath control with every hold",
    "challengeText": "Hold steady",
    "initialScript": "Each hold builds endurance. Each pause sharpens your mind. This is the breath that builds mental toughness."
  },
  {
    "id": 36,
    "mainTitle": "Counted Flow",
    "cycle": ["5-0-5-2", "6-0-6-2", "7-0-7-3"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Count your way to control",
    "successText": "You counted every breath and stayed in total control",
    "challengeText": "Count perfectly",
    "initialScript": "Numbers keep you anchored. Every count is a win. Follow the rhythm and let nothing pull you away."
  },
  {
    "id": 39,
    "mainTitle": "Grounding Breath",
    "cycle": ["4-2-6-2", "5-2-7-2", "6-3-8-3"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Root yourself in this moment",
    "successText": "You grounded your energy and found inner stillness",
    "challengeText": "Stay grounded",
    "initialScript": "When your mind floats away this brings you back. Feel the earth beneath you. Every breath anchors you deeper."
  },
  {
    "id": 42,
    "mainTitle": "Tension Release",
    "cycle": ["4-3-7-0", "5-4-8-0", "6-4-10-0"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:20"],
    "hookText": "Let stress leave your body",
    "successText": "You released tension and reclaimed your calm space",
    "challengeText": "Release now",
    "initialScript": "Tension hides in your breath. Long exhales flush it out. Feel the weight lift with every breath you give away."
  },
  {
    "id": 45,
    "mainTitle": "Warrior Breath",
    "cycle": ["5-3-5-3", "6-4-6-4", "7-5-7-5"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Breathe like a warrior now",
    "successText": "You breathed with strength and unshakable discipline",
    "challengeText": "Stay strong",
    "initialScript": "This breath builds warriors. Even holds demand control. Every cycle makes you tougher and more focused."
  },
  {
    "id": 48,
    "mainTitle": "Focus Lock",
    "cycle": ["4-4-5-3", "5-5-6-4", "6-6-7-5"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Lock your focus right here",
    "successText": "You locked in and nothing could break your attention",
    "challengeText": "Stay locked",
    "initialScript": "Distractions die here. This pattern trains laser focus. Follow every count and let nothing else exist."
  }

]

challenges_3: List[Dict[str, Any]] = [
    # TODO: fill with your real data
  {
    "id": 40,
    "mainTitle": "Parasympathetic Breath",
    "cycle": ["2-0-2-0"],
    "level": ["Level 1: 00:18"],
    "hookText": "Activate",
    "successText": "test",
    "challengeText": "Stay relaxed",
    "initialScript": "test."
  },
  {
    "id": 45,
    "mainTitle": "Warrior Breath",
    "cycle": ["5-3-5-3", "6-4-6-4", "7-5-7-5"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Breathe like a warrior now",
    "successText": "You breathed with strength and unshakable discipline",
    "challengeText": "Stay strong",
    "initialScript": "This breath builds warriors. Even holds demand control. Every cycle makes you tougher and more focused."
  },
  {
    "id": 50,
    "mainTitle": "Anchor Breath",
    "cycle": ["5-2-5-1", "6-2-6-2", "7-3-7-3"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Drop your anchor deep",
    "successText": "You anchored yourself and found unshakable presence",
    "challengeText": "Stay anchored",
    "initialScript": "When life pulls you everywhere this holds you still. Feel the weight drop. Let this breath be your foundation."
  },
  {
    "id": 55,
    "mainTitle": "Balanced Flow",
    "cycle": ["4-3-4-3", "5-4-5-4", "6-5-6-5"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Balance every part of breath",
    "successText": "You balanced perfectly and your mind feels centered",
    "challengeText": "Stay centered",
    "initialScript": "Balance creates power. Every phase gets equal respect. This is the breath that brings symmetry to chaos."
  },
  {
    "id": 60,
    "mainTitle": "Oceanic Rhythm",
    "cycle": ["5-1-6-0", "6-1-7-0", "7-2-8-1"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Flow like the ocean tide",
    "successText": "You moved with the rhythm and found effortless calm",
    "challengeText": "Keep flowing",
    "initialScript": "Breath moves like water. Inhale rises like the tide. Exhale falls back to the shore. Find the wave and ride it."
  },
  {
    "id": 65,
    "mainTitle": "Clarity Breath",
    "cycle": ["4-4-6-2", "5-5-7-3", "6-6-8-4"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Clear the fog from your mind",
    "successText": "You cleared every distraction and found perfect clarity",
    "challengeText": "Stay clear",
    "initialScript": "Mental fog dies here. This pattern sharpens your thoughts. Each breath brings another layer of focus into view."
  },
  {
    "id": 70,
    "mainTitle": "Energy Balance",
    "cycle": ["5-0-6-1", "6-0-7-2", "7-0-8-3"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Balance your energy right now",
    "successText": "You balanced your system and energy flows freely",
    "challengeText": "Stay balanced",
    "initialScript": "Too much energy scatters you. Too little drains you. This breath finds the middle and keeps you there."
  },
  {
    "id": 75,
    "mainTitle": "Steady State",
    "cycle": ["4-2-5-2", "5-3-6-3", "6-4-7-4"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Hold your steady state strong",
    "successText": "You maintained steadiness through every rising challenge",
    "challengeText": "Stay steady",
    "initialScript": "Steadiness wins over speed. This breath teaches you to hold your ground. Nothing shakes you when you own this rhythm."
  },
  {
    "id": 80,
    "mainTitle": "Deep Reset",
    "cycle": ["5-4-7-0", "6-5-8-0", "7-6-9-0"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:22"],
    "hookText": "Reset everything right now",
    "successText": "You reset your system and everything feels lighter",
    "challengeText": "Reset fully",
    "initialScript": "This is the breath that starts you over. Deep holds reset your baseline. Long exhales release everything old."
  },
  {
    "id": 85,
    "mainTitle": "Power Hold",
    "cycle": ["4-5-4-3", "5-6-5-4", "6-7-6-5"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Hold power in your breath",
    "successText": "You held power through every breath with total control",
    "challengeText": "Hold longer",
    "initialScript": "The hold is where strength lives. This pattern builds lung capacity and mental fortitude. Own every second of stillness."
  },
  {
    "id": 90,
    "mainTitle": "Cascading Calm",
    "cycle": ["4-3-6-1", "5-4-7-2", "6-5-8-3"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Let calm cascade through you",
    "successText": "You let calm wash over you in perfect waves",
    "challengeText": "Let it flow",
    "initialScript": "Calm moves in layers. Each breath adds another wave. Feel it cascade from your head to your feet."
  },
  {
    "id": 95,
    "mainTitle": "Mountain Breath",
    "cycle": ["5-4-5-2", "6-5-6-3", "7-6-7-4"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Breathe like an unmovable mountain",
    "successText": "You stood firm and nothing could move your center",
    "challengeText": "Stand firm",
    "initialScript": "Mountains do not rush. They stand still and weather everything. This breath makes you immovable and calm."
  },
  {
    "id": 100,
    "mainTitle": "Precision Flow",
    "cycle": ["5-3-6-2", "6-4-7-3", "7-5-8-4"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Execute with perfect precision",
    "successText": "You executed every breath with flawless precision",
    "challengeText": "Stay precise",
    "initialScript": "Precision beats power. Every count matters here. This breath trains you to control the smallest details."
  },
  {
    "id": 105,
    "mainTitle": "Resilience Breath",
    "cycle": ["4-4-7-1", "5-5-8-2", "6-6-9-3"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Build resilience with every breath",
    "successText": "You built resilience and nothing can break you now",
    "challengeText": "Stay resilient",
    "initialScript": "Resilience is not given. It is built one breath at a time. This pattern strengthens you from the inside out."
  },
  {
    "id": 110,
    "mainTitle": "Infinite Loop",
    "cycle": ["5-2-6-2", "6-3-7-3", "7-4-8-4"],
    "level": ["Level 1: 00:20", "Level 2: 00:24", "Final Level: 00:24"],
    "hookText": "Loop your breath endlessly",
    "successText": "You found the endless loop and mastered the flow",
    "challengeText": "Keep looping",
    "initialScript": "There is no beginning or end here. Just continuous flow. This breath teaches you to find rhythm that never stops."
  }

]

challenges_4: List[Dict[str, Any]] = [
    # Optional extra arrays
]

challenges_5: List[Dict[str, Any]] = [
    # Optional extra arrays
]

# Grouped for easier search
CHALLENGE_ARRAYS: List[List[Dict[str, Any]]] = [
    challenges_1,
    challenges_2,
    challenges_3,
    challenges_4,
    challenges_5,
]

# =========================
# TITLE & DESCRIPTION ARRAYS
# =========================
# Separate JSON arrays for SEO title & description, keyed by challenge id.
# Example:
# array_one_title_desc = {
#   20: {
#     "title": "Box Breathing for Calm Focus | 4-4-4-4 Pattern",
#     "description": "Use this structured breathing pattern ...\n\n#Breathwork ..."
#   },
#   ...
# }

array_one_title_desc = {
    1: {
        "title": "Breathing Challenge for Focus & Control | 3 Levels Test",
        "description": "Test your breath control through three progressive levels.\nEach round becomes harder and demands stronger focus.\nMost quit early — stay calm and finish all levels.\nPractice daily to build mental strength."
    },
    2: {
        "title": "5-Level Breathing Challenge | Build Endurance & Control",
        "description": "This five-level breathing challenge pushes your endurance.\nEach level increases intensity and breath control demand.\nLevel five is where most people fail.\nFinish strong and prove your discipline."
    },
    3: {
        "title": "Focus Drill Breathing Exercise | Train Mental Discipline",
        "description": "Sharpen your focus with this structured breathing drill.\nThree intense levels train sustained concentration.\nThe final round separates focus from distraction.\nUse this daily to upgrade mental clarity."
    },
    4: {
        "title": "Calm Under Pressure Breathing Challenge",
        "description": "Learn to stay calm under rising pressure.\nEach level increases breath holds and mental demand.\nMost minds break at the final stage.\nStay steady and master emotional control."
    },
    5: {
        "title": "Mental Strength Breathing Challenge | 3 Levels",
        "description": "This challenge is built to test mental strength.\nBreathing intensity rises with every level.\nOnly the mentally tough reach the final round.\nProve your inner resilience."
    },
    6: {
        "title": "Advanced Breathwork Challenge | Push Your Limits",
        "description": "Four escalating breathwork levels challenge your control.\nEach round increases breath duration and focus.\nVery few finish level four.\nStay disciplined and earn respect."
    },
    7: {
        "title": "Breathing Control Test | Precision & Focus Drill",
        "description": "Test your breathing precision across three levels.\nEach round demands steady rhythm and control.\nOne mistake breaks the flow.\nTrain accuracy and composure."
    },
    8: {
        "title": "Discipline Builder Breathing Exercise",
        "description": "Build discipline through controlled breathing rounds.\nEach level rewards consistency and patience.\nWeak focus fails early.\nStrengthen discipline with every breath."
    },
    9: {
        "title": "Extreme Breath Hold Challenge | Mental Endurance",
        "description": "This challenge increases breath holds aggressively.\nEach level demands longer control and calm.\nFinal holds defeat most people.\nPush your limits safely."
    },
    10: {
        "title": "Pressure Test Breathing Drill | Mental Toughness",
        "description": "Train calm breathing under increasing pressure.\nFour levels test emotional control and focus.\nPressure reveals true discipline.\nStay steady until the end."
    },
    11: {
        "title": "Reset Your Mind Breathing Exercise",
        "description": "Clear mental clutter with this calming breath routine.\nEach level resets focus and awareness.\nLose concentration and the reset fails.\nFinish all rounds for clarity."
    },
    12: {
        "title": "Endurance Breathing Challenge | Train Breath Stamina",
        "description": "This endurance challenge pushes breath stamina.\nEach round lasts longer and demands patience.\nMental fatigue rises quickly.\nOutlast the challenge calmly."
    },
    13: {
        "title": "Focus Builder Breathing Drill | 4 Levels",
        "description": "Strengthen focus with four progressive breathing levels.\nEach round increases mental load.\nLevel four breaks distracted minds.\nStay locked in throughout."
    },
    14: {
        "title": "Calm Mastery Breathing Technique",
        "description": "Master calm through structured breathing cycles.\nEach level deepens emotional control.\nCalm is tested under longer holds.\nTrain your nervous system daily."
    },
    15: {
        "title": "Mental Reset Breathing Challenge",
        "description": "Release mental fatigue through controlled breathing.\nEach level refreshes focus and calm.\nThe reset completes only at the final stage.\nBreathe slow and steady."
    },
    16: {
        "title": "Willpower Test Breathing Challenge",
        "description": "Test willpower across four demanding breathing rounds.\nEach level pushes deeper mental resistance.\nQuitting gets easier as intensity rises.\nFinish strong and build grit."
    },
    17: {
        "title": "Breathing Drill for Discipline & Focus",
        "description": "This drill rewards disciplined breathing control.\nIntensity increases every level.\nOnly focused minds finish all rounds.\nTrain daily for consistency."
    },
    18: {
        "title": "Concentration Breathing Challenge | Focus Training",
        "description": "Train deep concentration with structured breathing.\nEach level demands stronger attention control.\nThe final round breaks weak focus.\nBuild elite concentration skills."
    },
    19: {
        "title": "Stress Relief Breathing Test",
        "description": "Release stress through guided breathing levels.\nEach round calms the nervous system.\nStress fights back at the final stage.\nWin calm through control."
    },
    20: {
        "title": "Composure Drill Breathing Exercise",
        "description": "Test your composure with rising breath difficulty.\nEach level demands emotional stability.\nPressure increases steadily.\nStay composed to the end."
    },
    21: {
        "title": "Breath Control Challenge | Calm & Control",
        "description": "Improve breath control through progressive levels.\nEach round requires steady rhythm.\nMost lose control early.\nMaster breathing precision."
    },
    22: {
        "title": "Mental Clarity Breathing Challenge",
        "description": "Clear mental fog using controlled breathing.\nEach level sharpens awareness.\nClarity comes only at the final stage.\nStay patient and focused."
    },
    23: {
        "title": "Patience Builder Breathing Challenge",
        "description": "Build patience with long, controlled breath cycles.\nEach level demands stillness and restraint.\nImpatient minds fail early.\nTrain calm endurance."
    },
    24: {
        "title": "Deep Focus Breathing Challenge | 4 Levels",
        "description": "Train deep focus with strict breathing rhythm.\nEach level increases concentration demand.\nDistractions cause failure.\nFinish all four levels focused."
    },
    25: {
        "title": "Mindfulness Breathing Drill",
        "description": "Develop mindfulness through structured breathing.\nEach level deepens awareness.\nOnly mindful breathing completes the drill.\nStay present throughout."
    },
    26: {
        "title": "Resilience Breathing Test | Mental Strength",
        "description": "Build resilience through rising breath difficulty.\nEach level challenges comfort limits.\nMental toughness is required.\nComplete all rounds calmly."
    },
    27: {
        "title": "Inner Strength Breathing Challenge",
        "description": "Strengthen your inner core with focused breathing.\nEach level digs deeper mentally.\nTrue strength appears at the end.\nBreathe with purpose."
    },
    28: {
        "title": "Steady Breathing Challenge | Control Test",
        "description": "Maintain steady breathing across four levels.\nIntensity rises with each round.\nOne slip breaks rhythm.\nTrain consistency and calm."
    },
    29: {
        "title": "Grit Test Breathing Exercise",
        "description": "Test grit with challenging breath cycles.\nEach level demands persistence.\nMental resistance increases fast.\nStay strong through the final round."
    },
    30: {
        "title": "Peak Focus Breathing Drill | Advanced",
        "description": "Reach peak focus through intense breathing levels.\nEach round pushes attention limits.\nDiscipline is required throughout.\nFinish all four to succeed."
    },
    31: {
        "title": "Balance Breathing Challenge | Mind & Breath",
        "description": "Find balance through rhythmic breathing.\nEach level demands consistency.\nBalance improves with control.\nStay centered till the end."
    },
    32: {
        "title": "Courage Test Breathing Challenge",
        "description": "Test courage through rising breath pressure.\nEach level exposes mental fear.\nOnly steady minds finish.\nFace the final challenge calmly."
    },
    33: {
        "title": "Mental Breakthrough Breathing Drill",
        "description": "Push toward a mental breakthrough using breathwork.\nEach level prepares the mind.\nThe final round creates change.\nStay focused throughout."
    },
    34: {
        "title": "Perseverance Breathing Challenge | 5 Levels",
        "description": "Five levels designed to test perseverance.\nEach round increases breath demand.\nOnly persistent minds reach the end.\nFinish strong and disciplined."
    }
}



array_two_title_desc = {
    3: {
        "title": "Box Breathing Technique | Calm Focus & Control",
        "description": "Box breathing resets your nervous system quickly.\nEach level improves calm, focus, and emotional control.\nFollow the rhythm carefully and stay steady.\nPerfect for stress, anxiety, and focus training."
    },
    6: {
        "title": "Triangle Breathing Exercise | Deep Calm & Patience",
        "description": "Triangle breathing builds calm through structured timing.\nEach side of the breath trains patience and control.\nSlow down and follow each phase precisely.\nIdeal for grounding and mental balance."
    },
    9: {
        "title": "Equal Breathing Technique | Balance Mind & Body",
        "description": "Equal breathing creates balance between inhale and exhale.\nThis method stabilizes energy and clears the mind.\nConsistency is more important than speed.\nUse this practice for calm focus."
    },
    12: {
        "title": "Coherence Breathing | Heart–Mind Synchronization",
        "description": "Coherence breathing aligns breath with heart rhythm.\nThis technique supports flow state and clarity.\nStay in rhythm and let calm build naturally.\nExcellent for stress regulation."
    },
    15: {
        "title": "Extended Exhale Breathing | Nervous System Reset",
        "description": "Longer exhales activate deep relaxation.\nEach round releases stored tension from the body.\nLet go fully with every breath out.\nBest for anxiety relief and sleep preparation."
    },
    18: {
        "title": "Resonance Breathing | Find Your Natural Rhythm",
        "description": "Resonance breathing finds your optimal breathing frequency.\nThis rhythm supports calm and efficiency.\nSmooth transitions are key.\nLet the breath guide you naturally."
    },
    21: {
        "title": "Diaphragmatic Breathing | Deep Core Control",
        "description": "Diaphragmatic breathing activates the deepest breath.\nEach level trains belly expansion and calm control.\nShallow breathing fades as depth increases.\nFoundation technique for all breathwork."
    },
    24: {
        "title": "4-7-8 Breathing Technique | Sleep & Relaxation",
        "description": "The 4-7-8 method is designed for deep relaxation.\nThe hold phase calms the nervous system.\nFollow the counts carefully.\nExcellent for sleep and stress relief."
    },
    27: {
        "title": "Mindful Cadence Breathing | Precision & Awareness",
        "description": "Mindful cadence trains precise breath timing.\nEvery second is intentional and controlled.\nAwareness increases with each cycle.\nPerfect for mindfulness training."
    },
    30: {
        "title": "Calming Ratio Breathing | Double the Exhale",
        "description": "This ratio emphasizes longer exhales for calm.\nEach level deepens relaxation quickly.\nThe nervous system responds immediately.\nUse during stress or overwhelm."
    },
    33: {
        "title": "Progressive Hold Breathing | Build Control & Endurance",
        "description": "Progressive holds strengthen breath control.\nEach level increases endurance safely.\nPauses sharpen mental toughness.\nStay relaxed during stillness."
    },
    36: {
        "title": "Counted Flow Breathing | Focus Through Numbers",
        "description": "Counting anchors the mind to the breath.\nEach number keeps you present and steady.\nDistractions fade with rhythm.\nIdeal for focus training."
    },
    39: {
        "title": "Grounding Breath Technique | Feel Present & Stable",
        "description": "Grounding breath anchors attention in the body.\nEach cycle restores stability and calm.\nPerfect when feeling scattered.\nBreathe slow and rooted."
    },
    42: {
        "title": "Tension Release Breathing | Let Stress Go",
        "description": "Long exhales release stored tension.\nEach round lightens the body and mind.\nStress dissolves with control.\nExcellent for emotional reset."
    },
    45: {
        "title": "Warrior Breathing Technique | Strength & Discipline",
        "description": "Warrior breath builds strength through controlled holds.\nEach level increases discipline and focus.\nThis is power with calm.\nBreathe strong and steady."
    },
    48: {
        "title": "Focus Lock Breathing | Laser-Sharp Attention",
        "description": "This breathing pattern trains unbreakable focus.\nEach count locks attention deeper.\nDistractions fall away naturally.\nStay fully present throughout."
    }
}

array_three_title_desc = {
    40: {
        "title": "Parasympathetic Breathing | Activate Deep Relaxation",
        "description": "This breathing pattern activates the parasympathetic system.\nShort, gentle cycles calm the body fast.\nIdeal for instant relaxation.\nBreathe lightly and stay relaxed."
    },
    45: {
        "title": "Warrior Breath Advanced | Power & Control",
        "description": "Advanced warrior breathing builds inner strength.\nEven holds demand discipline and focus.\nEach cycle increases resilience.\nStay strong and controlled."
    },
    50: {
        "title": "Anchor Breathing Technique | Stay Grounded",
        "description": "Anchor breathing stabilizes the mind and body.\nEach level deepens presence.\nPerfect for stressful moments.\nFeel yourself settle with every breath."
    },
    55: {
        "title": "Balanced Flow Breathing | Total Symmetry",
        "description": "Balanced flow gives equal attention to every phase.\nThis symmetry creates inner stability.\nCalm grows with balance.\nMaintain smooth transitions."
    },
    60: {
        "title": "Oceanic Rhythm Breathing | Flow & Ease",
        "description": "Oceanic breathing mimics natural wave patterns.\nEach cycle feels smooth and effortless.\nCalm arrives through rhythm.\nBreathe like the tide."
    },
    65: {
        "title": "Clarity Breathing Technique | Sharp Focus",
        "description": "This pattern cuts through mental fog.\nEach breath sharpens awareness.\nClarity builds gradually.\nStay focused on clean rhythm."
    },
    70: {
        "title": "Energy Balance Breathing | Find the Middle",
        "description": "Balance excess or low energy through breath.\nThis technique restores equilibrium.\nNeither rushed nor slow.\nRemain centered."
    },
    75: {
        "title": "Steady State Breathing | Unshakable Calm",
        "description": "Steady state breathing builds consistency.\nEach level strengthens stability.\nNothing pulls you off balance.\nHold your rhythm."
    },
    80: {
        "title": "Deep Reset Breathing | Full Nervous System Reset",
        "description": "This breath resets your baseline deeply.\nLong exhales release old tension.\nEach level clears the system.\nStart fresh and light."
    },
    85: {
        "title": "Power Hold Breathing | Strength in Stillness",
        "description": "Power holds train lung capacity and control.\nStillness builds inner strength.\nEach pause matters.\nRemain relaxed while holding."
    },
    90: {
        "title": "Cascading Calm Breathing | Layered Relaxation",
        "description": "Calm flows through the body in waves.\nEach breath adds another layer of ease.\nLet relaxation spread naturally.\nStay with the flow."
    },
    95: {
        "title": "Mountain Breathing Technique | Unmovable Calm",
        "description": "Mountain breathing builds stillness and strength.\nNothing rushes or shakes this rhythm.\nStand firm through breath.\nCalm becomes unbreakable."
    },
    100: {
        "title": "Precision Flow Breathing | Advanced Control",
        "description": "Precision flow demands exact timing.\nEach count sharpens discipline.\nControl improves through accuracy.\nFocus on details."
    },
    105: {
        "title": "Resilience Breathing | Strength From Within",
        "description": "This breath builds resilience steadily.\nEach cycle reinforces inner strength.\nCalm persists under pressure.\nStay consistent."
    },
    110: {
        "title": "Infinite Loop Breathing | Continuous Flow",
        "description": "Infinite loop breathing removes pauses.\nThe rhythm never breaks.\nThis builds deep flow state.\nStay smooth and continuous."
    }
}


array_four_title_desc: Dict[int, Dict[str, str]] = {}

array_five_title_desc: Dict[int, Dict[str, str]] = {}

TITLE_DESC_ARRAYS: List[Dict[int, Dict[str, str]]] = [
    array_one_title_desc,
    array_two_title_desc,
    array_three_title_desc,
    array_four_title_desc,
    array_five_title_desc,
]

# =========================
# AUTHENTICATION
# =========================

def authenticate_youtube():
    """Authenticate and return a YouTube API client."""
    creds = None

    # Load existing token if present
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            creds_data = json.load(f)
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    # If no valid credentials, go through OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(google.auth.transport.requests.Request())
            except Exception:
                creds = None  # fallback to full flow

        if not creds or not creds.valid:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for next run
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=creds
    )
    return youtube

# =========================
# METADATA LOOKUP
# =========================

def find_challenge_by_id(
    challenge_id: int,
    is_variant: bool
) -> Optional[Dict[str, Any]]:
    """
    Find the challenge object by id using the configured arrays.

    Rules:
    - Non-variant (no 'c'): search all arrays in order [1..5], return first match.
    - Variant ('c' suffix): search arrays 2..5 ONLY (to avoid base content); if not found, skip.
    """
    if is_variant:
        # Search arrays 2..5
        indices = [1, 2, 3, 4]
    else:
        # Search arrays 1..5
        indices = [0, 1, 2, 3, 4]

    for i in indices:
        if i >= len(CHALLENGE_ARRAYS):
            continue
        for challenge in CHALLENGE_ARRAYS[i]:
            if challenge.get("id") == challenge_id:
                return challenge
    return None


def get_title_description(
    challenge_id: int,
    is_variant: bool
) -> Optional[Dict[str, str]]:
    """
    Get SEO title & description from dedicated title/description arrays.

    Suggested logic:
    - Non-variant: search arrays in order [1..5].
    - Variant: search arrays 2..5 only.
    """
    if is_variant:
        indices = [1, 2, 3, 4]
    else:
        indices = [0, 1, 2, 3, 4]

    for i in indices:
        if i >= len(TITLE_DESC_ARRAYS):
            continue
        mapping = TITLE_DESC_ARRAYS[i]
        if challenge_id in mapping:
            return mapping[challenge_id]

    return None


def fallback_generate_title(challenge: Dict[str, Any]) -> str:
    """Fallback SEO title in case title JSON is missing."""
    main_title = challenge.get("mainTitle", "").strip()
    hook = challenge.get("hookText", "").strip()
    parts = [main_title]
    if hook:
        parts.append(f"- {hook}")
    base_title = " ".join(parts) if parts else "Breathing Exercise"

    suffix = " | Breathing Technique & Meditation"
    full = f"{base_title} {suffix}".strip()

    # Hard limit ~60 chars (soft, YouTube allows more but this is safe)
    if len(full) > 60:
        return full[:57] + "..."
    return full


def fallback_generate_description(challenge: Dict[str, Any]) -> str:
    """Fallback SEO description if not provided via JSON title/desc arrays."""
    description = []

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
        level_strs = [str(l) for l in level]
        description.append(f"Difficulty Levels: {', '.join(level_strs)}")

    description.append("#BreathingExercise #Meditation #CalmYourMind #Focus #Wellness")
    return "\n\n".join(description)

# =========================
# YOUTUBE HELPERS
# =========================

def get_playlist_id(youtube, playlist_name: str) -> Optional[str]:
    """Find playlist by name for the authenticated channel."""
    if PLAYLIST_ID_OVERRIDE:
        return PLAYLIST_ID_OVERRIDE

    request = youtube.playlists().list(
        part="snippet,contentDetails",
        mine=True,
        maxResults=50
    )
    while request is not None:
        response = request.execute()
        for pl in response.get("items", []):
            if pl["snippet"]["title"] == playlist_name:
                return pl["id"]
        request = youtube.playlists().list_next(request, response)

    print(f"[WARN] Playlist '{playlist_name}' not found.")
    return None


def upload_video(
    youtube,
    file_path: str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None
) -> Optional[str]:
    """Upload video to YouTube as PRIVATE and return video ID."""
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
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        print(f"[OK] Uploaded video ID: {video_id}")
        return video_id
    except googleapiclient.errors.HttpError as e:
        print(f"[ERROR] Failed to upload {file_path}: {e}")
        return None


def add_to_playlist(youtube, video_id: str, playlist_id: str) -> bool:
    """Add a video to the given playlist."""
    if not playlist_id:
        print("[WARN] No playlist ID supplied; skipping playlist add.")
        return False

    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id
            }
        }
    }

    try:
        youtube.playlistItems().insert(
            part="snippet",
            body=body
        ).execute()
        print(f"[OK] Added to playlist: {playlist_id}")
        return True
    except googleapiclient.errors.HttpError as e:
        print(f"[ERROR] Failed to add to playlist: {e}")
        return False


def schedule_video_publication(
    youtube,
    video_id: str,
    publish_time_ist: datetime
) -> bool:
    """Schedule a PRIVATE video to go public at a given IST datetime."""
    if publish_time_ist.tzinfo is None:
        publish_time_ist = publish_time_ist.replace(tzinfo=IST)

    publish_time_utc = publish_time_ist.astimezone(timezone.utc)
    publish_at_str = publish_time_utc.isoformat().replace("+00:00", "Z")

    body = {
        "id": video_id,
        "status": {
            "privacyStatus": "private",   # must be private for scheduled publishing
            "publishAt": publish_at_str,
            "selfDeclaredMadeForKids": False
        }
    }

    try:
        youtube.videos().update(
            part="status",
            body=body
        ).execute()
        print(f"[OK] Scheduled publish at (IST): {publish_time_ist} | (UTC): {publish_time_utc}")
        return True
    except googleapiclient.errors.HttpError as e:
        print(f"[ERROR] Failed to schedule video {video_id}: {e}")
        return False

# =========================
# FILE SCANNING
# =========================

def scan_video_files(directory_path: Path) -> List[Tuple[Path, int, bool]]:
    """
    Scan directory for challenge_final_*.mp4 files.

    Returns:
        List of tuples: (path, video_number, is_variant)
    """
    files = sorted(directory_path.glob(f"{VIDEO_PREFIX}*{VIDEO_SUFFIX}"))
    results: List[Tuple[Path, int, bool]] = []

    for f in files:
        stem = f.stem  # e.g. challenge_final_20 or challenge_final_20c
        if not stem.startswith(VIDEO_PREFIX):
            continue

        core = stem.replace(VIDEO_PREFIX, "")  # '20' or '20c'
        is_variant = core.endswith("c")
        if is_variant:
            num_str = core[:-1]  # strip trailing 'c'
        else:
            num_str = core

        if not num_str.isdigit():
            print(f"[WARN] Skipping file with non-numeric id: {f.name}")
            continue

        video_num = int(num_str)
        results.append((f, video_num, is_variant))

    # Sort by video number, then variant flag (base first, then variant)
    results.sort(key=lambda x: (x[1], x[2]))
    return results

# =========================
# MAIN WORKFLOW
# =========================

def main_upload_workflow():
    print("Authenticating with YouTube API...")
    youtube = authenticate_youtube()
    print("Authentication successful.")

    print(f"Scanning directory: {VIDEOS_DIR}")
    video_entries = scan_video_files(VIDEOS_DIR)
    total_files = len(video_entries)
    print(f"Found {total_files} video files.")

    playlist_id = get_playlist_id(youtube, PLAYLIST_NAME)
    if playlist_id:
        print(f"Using playlist ID: {playlist_id}")
    else:
        print("[WARN] Continuing without playlist (will not add videos to playlist).")

    uploaded_count = 0
    skipped_count = 0
    error_count = 0

    # Scheduling start offset (based on how many have already been uploaded)
    # We skip the first ALREADY_UPLOADED_COUNT entries by INDEX in the sorted list.
    for idx, (video_path, video_num, is_variant) in enumerate(video_entries):
        # Skip previously uploaded
        if idx < ALREADY_UPLOADED_COUNT:
            print(f"[SKIP] Index {idx} - assuming already uploaded: {video_path.name}")
            continue

        print("-" * 60)
        print(f"Processing index {idx} / {total_files - 1}: {video_path.name}")
        print(f"Video number: {video_num} | Variant: {is_variant}")

        # Get challenge metadata
        challenge = find_challenge_by_id(video_num, is_variant)
        if not challenge:
            print(f"[WARN] No challenge data found for id={video_num}, variant={is_variant}. Skipping.")
            skipped_count += 1
            continue

        # Get title & description from separate arrays, or fall back to generation
        td = get_title_description(video_num, is_variant)
        if td:
            title = td.get("title") or fallback_generate_title(challenge)
            description = td.get("description") or fallback_generate_description(challenge)
        else:
            print("[INFO] No title/description entry found; using fallback generation.")
            title = fallback_generate_title(challenge)
            description = fallback_generate_description(challenge)

        # Extract tags from description hashtags (#something)
        tags = [w.strip("#") for w in description.split() if w.startswith("#")]

        # Upload video
        video_id = upload_video(
            youtube=youtube,
            file_path=str(video_path),
            title=title,
            description=description,
            tags=tags,
        )

        if not video_id:
            error_count += 1
            continue

        # Add to playlist (if available)
        add_to_playlist(youtube, video_id, playlist_id)

        # Calculate publish time (IST)
        # Example: For idx == ALREADY_UPLOADED_COUNT => day_offset = 0 (start date)
        day_offset = idx - ALREADY_UPLOADED_COUNT
        schedule_date_ist = START_DATE_IST + timedelta(days=day_offset)

        random_hour = random.randint(PUBLISH_HOUR_START, PUBLISH_HOUR_END)
        random_minute = random.randint(0, 59)
        publish_time_ist = schedule_date_ist.replace(
            hour=random_hour,
            minute=random_minute,
            second=0,
            microsecond=0,
            tzinfo=IST
        )

        # Schedule video
        if schedule_video_publication(youtube, video_id, publish_time_ist):
            uploaded_count += 1
        else:
            error_count += 1

        print(f"[INFO] Completed processing for {video_path.name}")

    print("=" * 60)
    print("UPLOAD SUMMARY")
    print(f"Total files found: {total_files}")
    print(f"Already assumed uploaded (skipped by index): {ALREADY_UPLOADED_COUNT}")
    print(f"Successfully scheduled new uploads: {uploaded_count}")
    print(f"Skipped (no challenge data): {skipped_count}")
    print(f"Errors during upload/schedule: {error_count}")
    print("=" * 60)


if __name__ == "__main__":
    main_upload_workflow()

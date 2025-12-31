python3.10 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python app.py


# 🎬 YouTube Bulk Uploader GUI (Tkinter + YouTube API)

A simple desktop application to bulk-upload YouTube videos with:
- Channel selection from logged-in Google accounts
- Playlist selection (auto-fetched from chosen channel)
- Metadata from JSON (title, description, tags)
- Video folder picker
- Private upload by default (safe mode)
- No command-line knowledge required

---

## 🚀 Features
✔ Connect Google Account (OAuth)  
✔ Choose which channel to upload to  
✔ Select playlist dynamically  
✔ Load titles/descriptions from metadata.json  
✔ Auto-match video files by filename  
✔ Upload multiple videos in one click  
✔ Safe mode: uploads as Private  

---

## 📁 Folder Structure
ytupload/
├─ uploader_gui.py
├─ metadata.json # your titles/descriptions
├─ client_secret.json # from google cloud (DO NOT SHARE)
├─ youtube_token.json # auto-created after login
└─ videos/
1.mp4
2.mp4
3.mp4


---

# 🔧 Installation (For Anyone Pulling From GitHub)

### 1️⃣ Clone the repo
```bash
git clone https://github.com/yourusername/ytupload.git
cd ytupload


2️⃣ Create virtual environment
python3 -m venv venv
source venv/bin/activate

3️⃣ Install required packages
pip install -r requirements.txt

🍏 Mac Users (Important Tkinter Fix)

If you see this error:

ModuleNotFoundError: No module named '_tkinter'


Run:

brew install tcl-tk
rm -rf venv
python3 -m venv venv
source venv/bin/activate

🔐 Google API Setup (Only first time)

Visit: https://console.cloud.google.com/

Create a project

Enable YouTube Data API v3

Go to Credentials → Create Credentials → OAuth Client ID

App type: Desktop App

Download JSON and rename it:

client_secret.json


Place it next to uploader_gui.py

📝 metadata.json Format (VERY IMPORTANT)
File: metadata.json
{
  "1": {
    "title": "Breathing Challenge | Level 1",
    "description": "Simple focus drill.\n#breathing #focus",
    "tags": ["breathing", "focus", "meditation"]
  },
  "2": {
    "title": "Level 2 Breath Training",
    "description": "Harder round begins.\n#breathwork",
    "tags": ["breathwork", "discipline"]
  }
}

🎥 Video Naming Rules
JSON Key	Video Filename
"1"	1.mp4
"2"	2.mp4
"focus1"	focus1.mp4

❌ Avoid spaces / special characters
✔ Keep filenames simple

▶️ Running the App
source venv/bin/activate
python uploader_gui.py
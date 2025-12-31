import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json, os
from datetime import datetime, timedelta, time, timezone
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

CLIENT_SECRETS_FILE = "client_secret.json"
TOKEN_FILE = "youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload","https://www.googleapis.com/auth/youtube"]

youtube = None
selected_channel_id = None
selected_playlist_id = None
metadata_json = None
video_folder = None

# ------------------------------------
# AUTHENTICATION
# ------------------------------------
def authenticate_google():
    global youtube
    if not os.path.exists(CLIENT_SECRETS_FILE):
        messagebox.showerror("Missing File","client_secret.json not found!")
        return
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    youtube = build("youtube","v3",credentials=creds)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    messagebox.showinfo("Success","Google Authentication Successful!")

# ------------------------------------
# FETCH CHANNELS & PLAYLISTS
# ------------------------------------
def load_channels():
    global youtube
    if not youtube:
        messagebox.showerror("Error","Authenticate first!")
        return
    response = youtube.channels().list(part="snippet", mine=True).execute()
    channels = {item["snippet"]["title"]:item["id"] for item in response["items"]}
    channel_dropdown["values"] = list(channels.keys())
    channel_dropdown.channel_map = channels
    messagebox.showinfo("Loaded","Channels loaded successfully!")

def on_channel_select(event):
    global selected_channel_id
    title = channel_dropdown.get()
    selected_channel_id = channel_dropdown.channel_map[title]

    # load playlists for selected channel
    response = youtube.playlists().list(part="snippet", channelId=selected_channel_id, maxResults=50).execute()
    playlists = {item["snippet"]["title"]:item["id"] for item in response["items"]}
    playlist_dropdown["values"] = list(playlists.keys())
    playlist_dropdown.playlist_map = playlists

# ------------------------------------
# FILE PICKERS
# ------------------------------------
def pick_json():
    global metadata_json
    path = filedialog.askopenfilename(filetypes=[("JSON Files","*.json")])
    metadata_json = json.load(open(path))
    json_label.config(text=path)

def pick_folder():
    global video_folder
    path = filedialog.askdirectory()
    video_folder = path
    folder_label.config(text=path)

# ------------------------------------
# UPLOAD + SCHEDULING
# ------------------------------------
def start_uploading():
    global selected_playlist_id
    if not youtube or not video_folder or not metadata_json:
        messagebox.showerror("Missing","Complete all steps first!")
        return

    # read date & time
    start_date = start_date_entry.get()
    schedule_time = schedule_time_entry.get()

    try:
        schedule_hour, schedule_minute = map(int, schedule_time.split(":"))
    except:
        messagebox.showerror("Time Error","Invalid time format. Use HH:MM")
        return

    # parse start date
    try:
        current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    except:
        messagebox.showerror("Date Error","Invalid date. Use YYYY-MM-DD")
        return

    # playlist selection
    p_name = playlist_dropdown.get()
    selected_playlist_id = playlist_dropdown.playlist_map.get(p_name)

    day_offset = 0

    for video_id, data in metadata_json.items():
        file_path = os.path.join(video_folder, f"{video_id}.mp4")
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue

        print(f"Uploading {file_path}...")
        video_youtube_id = upload_video(file_path, data["title"], data["description"], selected_playlist_id)

        publish_datetime = datetime.combine(
            current_date + timedelta(days=day_offset),
            time(schedule_hour, schedule_minute)
        ).replace(tzinfo=timezone.utc)  # 👈 force UTC


        schedule_video(video_youtube_id, publish_datetime)
        day_offset += 1  # next day

    messagebox.showinfo("Done","All videos scheduled successfully!")

# upload (PRIVATE)
def upload_video(file_path, title, description, playlist_id=None):
    request = youtube.videos().insert(
        part="snippet,status",
        body={"snippet":{"title":title,"description":description,"categoryId":"27"},
              "status":{"privacyStatus":"private"}},
        media_body=file_path,
    )
    response = request.execute()
    vid = response.get("id")

    if playlist_id:
        youtube.playlistItems().insert(
            part="snippet",
            body={"snippet":{"playlistId":playlist_id,"resourceId":{"kind":"youtube#video","videoId":vid}}}
        ).execute()
    return vid

# scheduling function
from datetime import timezone

def schedule_video(video_id, publish_datetime):
    # Force timezone awareness & convert to UTC
    publish_utc = publish_datetime.replace(tzinfo=timezone.utc).isoformat().replace("+00:00","Z")

    youtube.videos().update(
        part="status",
        body={
            "id": video_id,
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_utc,            # Correct UTC ISO timestamp
                "selfDeclaredMadeForKids": False
            }
        }
    ).execute()

    print(f"📅 Scheduled: {video_id} → {publish_utc}")



# ------------------------------------
# GUI SETUP
# ------------------------------------
app = tk.Tk()
app.title("YouTube Bulk Uploader GUI")
app.geometry("650x500")

tk.Button(app, text="1) Authenticate Google", command=authenticate_google).pack(pady=5)
tk.Button(app, text="2) Load Channels", command=load_channels).pack(pady=5)

channel_dropdown = ttk.Combobox(app, state="readonly"); channel_dropdown.pack(pady=5)
channel_dropdown.bind("<<ComboboxSelected>>", on_channel_select)

playlist_dropdown = ttk.Combobox(app, state="readonly"); playlist_dropdown.pack(pady=5)

# scheduling UI
tk.Label(app, text="Start date (YYYY-MM-DD):").pack()
start_date_entry = tk.Entry(app); start_date_entry.insert(0,"2025-01-01"); start_date_entry.pack(pady=3)

tk.Label(app, text="Time to publish (HH:MM):").pack()
schedule_time_entry = tk.Entry(app); schedule_time_entry.insert(0,"19:00"); schedule_time_entry.pack(pady=3)

tk.Button(app, text="Pick Video Folder", command=pick_folder).pack(pady=5)
folder_label = tk.Label(app, text="No folder selected"); folder_label.pack()

tk.Button(app, text="Load Metadata JSON", command=pick_json).pack(pady=5)
json_label = tk.Label(app, text="No metadata file"); json_label.pack()

tk.Button(app, text="🚀 SCHEDULE UPLOADS", bg="green", fg="white", command=start_uploading).pack(pady=20)

app.mainloop()

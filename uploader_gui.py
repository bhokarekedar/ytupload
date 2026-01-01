import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json, os, random
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
# HELPERS
# ------------------------------------
def get_random_time_in_range(start_t, end_t):
    sh, sm = map(int, start_t.split(":"))
    eh, em = map(int, end_t.split(":"))
    start_m = sh*60 + sm
    end_m = eh*60 + em
    picked = random.randint(start_m, end_m)
    return picked // 60, picked % 60

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
# LOAD CHANNEL / PLAYLIST
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

def on_channel_select(event):
    global selected_channel_id
    title = channel_dropdown.get()
    selected_channel_id = channel_dropdown.channel_map[title]
    response = youtube.playlists().list(part="snippet", channelId=selected_channel_id, maxResults=50).execute()
    playlists = {item["snippet"]["title"]:item["id"] for item in response["items"]}
    playlist_dropdown["values"] = list(playlists.keys())
    playlist_dropdown.playlist_map = playlists

# ------------------------------------
# PICKERS
# ------------------------------------
def pick_json():
    global metadata_json
    path = filedialog.askopenfilename(filetypes=[("JSON Files","*.json")])
    metadata_json = json.load(open(path))
    json_label.config(text=path)

def pick_folder():
    global video_folder
    video_folder = filedialog.askdirectory()
    folder_label.config(text=video_folder)

# ------------------------------------
# UPLOADING & SCHEDULING
# ------------------------------------
def start_uploading():
    global selected_playlist_id

    if not youtube or not video_folder or not metadata_json:
        messagebox.showerror("Missing","Complete all steps first!")
        return

    start_date = start_date_entry.get()
    prefix_enabled = prefix_var.get()
    prefix_text = prefix_entry.get()

    start_time = start_range_entry.get()
    end_time = end_range_entry.get()

    try:
        current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    except:
        messagebox.showerror("Date Error","Invalid date. Use YYYY-MM-DD")
        return

    p_name = playlist_dropdown.get()
    selected_playlist_id = playlist_dropdown.playlist_map.get(p_name)

    day_offset = 0

    for video_id, data in metadata_json.items():

        filename = f"{video_id}.mp4"
        if prefix_enabled:
            filename = prefix_text + filename

        file_path = os.path.join(video_folder, filename)
        if not os.path.exists(file_path):
            print(f"⚠ File missing: {filename}")
            continue

        rh, rm = get_random_time_in_range(start_time, end_time)

        publish_datetime = datetime.combine(
            current_date + timedelta(days=day_offset),
            time(rh, rm)
        ).replace(tzinfo=timezone.utc)

        vid = upload_video(file_path, data["title"], data["description"], selected_playlist_id)
        schedule_video(vid, publish_datetime)

        print(f"📅 {video_id} → {rh:02d}:{rm:02d}")
        day_offset += 1

    messagebox.showinfo("Done","All videos scheduled successfully!")

# ------------------------------------
# YOUTUBE API CALLS
# ------------------------------------
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

def schedule_video(video_id, publish_datetime):
    publish_utc = publish_datetime.isoformat().replace("+00:00","Z")
    youtube.videos().update(
        part="status",
        body={
            "id": video_id,
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_utc,
                "selfDeclaredMadeForKids": False
            }
        }
    ).execute()

# ------------------------------------
# UI SETUP
# ------------------------------------
app = tk.Tk()
app.title("YouTube Bulk Uploader PRO")
app.geometry("700x580")

tk.Button(app, text="1) Authenticate Google", command=authenticate_google).pack(pady=5)
tk.Button(app, text="2) Load Channels", command=load_channels).pack(pady=5)

channel_dropdown = ttk.Combobox(app, state="readonly"); channel_dropdown.pack(pady=3)
channel_dropdown.bind("<<ComboboxSelected>>", on_channel_select)

playlist_dropdown = ttk.Combobox(app, state="readonly"); playlist_dropdown.pack(pady=3)

# DATE INPUT
tk.Label(app, text="Start Date (YYYY-MM-DD):").pack()
start_date_entry = tk.Entry(app); start_date_entry.insert(0,"2025-01-01"); start_date_entry.pack(pady=3)

# TIME RANGE INPUT
tk.Label(app, text="Time Range (IST): Start to End").pack()
start_range_entry = tk.Entry(app); start_range_entry.insert(0,"21:00"); start_range_entry.pack()
end_range_entry = tk.Entry(app); end_range_entry.insert(0,"23:00"); end_range_entry.pack()

# PREFIX TOGGLE
prefix_var = tk.BooleanVar()
tk.Checkbutton(app, text="Use prefix before video ID?", variable=prefix_var).pack()
prefix_entry = tk.Entry(app); prefix_entry.insert(0,"yt_final_"); prefix_entry.pack(pady=3)

tk.Button(app, text="Pick Video Folder", command=pick_folder).pack(pady=5)
folder_label = tk.Label(app, text="No folder selected"); folder_label.pack()

tk.Button(app, text="Load Metadata JSON", command=pick_json).pack(pady=5)
json_label = tk.Label(app, text="No JSON file"); json_label.pack()

tk.Button(app, text="🚀 SCHEDULE UPLOADS", bg="green", fg="white", command=start_uploading).pack(pady=20)

app.mainloop()

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json, os
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
# FETCH CHANNELS
# ------------------------------------
def load_channels():
    global youtube
    if not youtube:
        messagebox.showerror("Error","Authenticate first!")
        return
    request = youtube.channels().list(part="snippet", mine=True)
    response = request.execute()
    channels = {item["snippet"]["title"]:item["id"] for item in response["items"]}
    channel_dropdown["values"] = list(channels.keys())
    channel_dropdown.channel_map = channels
    messagebox.showinfo("Loaded", "Channels loaded successfully!")

def on_channel_select(event):
    global selected_channel_id
    title = channel_dropdown.get()
    selected_channel_id = channel_dropdown.channel_map[title]

    # Load playlists after selecting channel
    request = youtube.playlists().list(part="snippet", channelId=selected_channel_id, maxResults=50)
    response = request.execute()
    playlists = {item["snippet"]["title"]:item["id"] for item in response["items"]}
    playlist_dropdown["values"] = list(playlists.keys())
    playlist_dropdown.playlist_map = playlists

# ------------------------------------
# PICK FILES & FOLDERS
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
# START UPLOAD
# ------------------------------------
def start_uploading():
    global selected_playlist_id
    if not youtube or not video_folder or not metadata_json:
        messagebox.showerror("Missing","Complete all steps first!")
        return

    # Playlist
    p_name = playlist_dropdown.get()
    selected_playlist_id = playlist_dropdown.playlist_map.get(p_name)

    for video_id, data in metadata_json.items():
        file_path = os.path.join(video_folder, f"{video_id}.mp4")
        if not os.path.exists(file_path): continue

        upload_video(file_path, data["title"], data["description"], selected_playlist_id)

    messagebox.showinfo("Done","Upload completed!")

# Simple uploader
def upload_video(file_path, title, description, playlist_id=None):
    media = open(file_path,"rb")
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

# ------------------------------------
# GUI SETUP
# ------------------------------------
app = tk.Tk()
app.title("YouTube Bulk Uploader GUI")
app.geometry("600x450")

tk.Button(app, text="1) Authenticate Google", command=authenticate_google).pack(pady=5)
tk.Button(app, text="2) Load Channels", command=load_channels).pack(pady=5)

channel_dropdown = ttk.Combobox(app, state="readonly")
channel_dropdown.pack(pady=5)
channel_dropdown.bind("<<ComboboxSelected>>", on_channel_select)

playlist_dropdown = ttk.Combobox(app, state="readonly")
playlist_dropdown.pack(pady=5)

tk.Button(app, text="Pick Video Folder", command=pick_folder).pack(pady=5)
folder_label = tk.Label(app, text="No folder selected"); folder_label.pack()

tk.Button(app, text="Load Metadata JSON", command=pick_json).pack(pady=5)
json_label = tk.Label(app, text="No metadata file"); json_label.pack()

tk.Button(app, text="🚀 START UPLOADING", bg="green", fg="white", command=start_uploading).pack(pady=20)

app.mainloop()

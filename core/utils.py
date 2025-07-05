import os
import requests
from .firebase_config import db
from datetime import datetime


def add_notification(uid, message, type="info", extra=None):
    """Create a notification document for a user profile."""
    notif = {
        "message": message,
        "type": type,
        "extra": extra or {},
        "timestamp": datetime.utcnow(),
        "read": False,
    }
    db.collection("profiles").document(uid).collection("notifications").add(notif)

def upload_image_to_imgbb(image_file):
    """Upload an image file to imgbb and return the URL or None."""
    if not image_file:
        return None
    api_key = os.getenv("IMGBB_API_KEY")
    if not api_key:
        return None
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        params={"key": api_key},
        files={"image": image_file.read()},
    )
    if resp.ok:
        return resp.json().get("data", {}).get("url")
    return None

def get_post_likes(post_id):
    """Return list of likes for a post as [{'uid':..., 'username':...}, ...]."""
    likes_col = db.collection("posts").document(post_id).collection("likes")
    likes = []
    for snap in likes_col.stream():
        d = snap.to_dict() or {}
        likes.append({"uid": snap.id, **d})
    return likes

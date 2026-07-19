from flask import Flask, request, render_template, jsonify
from instagrapi import Client
import os
import time
import threading

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ====================== اصل فنکشن (میسج بھیجنا) ======================
def send_messages_from_file(username, password, recipient, message_file, interval, haters_name, result_callback):
    cl = Client()
    try:
        cl.login(username, password)
        print("Logged in successfully!")

        recipient_id = None
        try:
            recipient_id = cl.user_id_from_username(recipient)
            if not recipient_id:
                raise ValueError("Recipient username not found!")
            print(f"Recipient username found: {recipient}")
        except Exception:
            try:
                recipient_id = cl.chat_id_from_name(recipient)
                if not recipient_id:
                    raise ValueError("Group name not found!")
                print(f"Group found: {recipient}")
            except Exception:
                print("Neither username nor group found!")
                return "Recipient username or group not found!"

        with open(message_file, 'r') as file:
            messages = file.readlines()

        for message in messages:
            message = message.strip()
            if message:
                try:
                    formatted_message = f"{haters_name} {message}"
                    if recipient_id:
                        if 'group' in recipient.lower():
                            cl.chat_send_message(recipient_id, formatted_message)
                            print(f"Message sent to group: {formatted_message}")
                        else:
                            cl.direct_send(formatted_message, [recipient_id])
                            print(f"Message sent to user: {formatted_message}")
                except Exception as e:
                    print(f"Failed to send message: {formatted_message}. Error: {e}")
            time.sleep(interval)

    except Exception as e:
        print(f"Error: {e}")
        return str(e)

    return "All messages sent successfully!"

def handle_user_request(username, password, recipient, message_file, interval, haters_name, result_callback):
    result = send_messages_from_file(username, password, recipient, message_file, interval, haters_name, result_callback)
    result_callback(result)

# ====================== اصل روٹ (ہوم پیج) ======================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        recipient = request.form["recipient"]
        interval = int(request.form["interval"])
        haters_name = request.form["haters_name"]

        if "message_file" not in request.files:
            return "No message file uploaded!"
        file = request.files["message_file"]
        if file.filename == "":
            return "No selected file!"

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        def result_callback(result):
            return render_template("index.html", message=result)

        thread = threading.Thread(target=handle_user_request, args=(username, password, recipient, file_path, interval, haters_name, result_callback))
        thread.start()

        return render_template("index.html", message="Processing your request... Please wait!")

    return render_template("index.html")

# ====================== نیا: مانیٹرنگ فنکشنز ======================
def get_user_info(username, password, target_username):
    """کسی بھی صارف کی مکمل معلومات حاصل کریں"""
    cl = Client()
    try:
        cl.login(username, password)
        user_id = cl.user_id_from_username(target_username)
        if not user_id:
            return {"error": "User not found"}
        info = cl.user_info(user_id)
        return {
            "username": info.username,
            "full_name": info.full_name,
            "user_id": info.pk,
            "profile_pic_url": info.profile_pic_url,
            "biography": info.biography,
            "follower_count": info.follower_count,
            "following_count": info.following_count,
            "media_count": info.media_count,
        }
    except Exception as e:
        return {"error": str(e)}

def get_recent_dms(username, password, limit=10):
    """حالیہ ڈائریکٹ میسجز حاصل کریں"""
    cl = Client()
    try:
        cl.login(username, password)
        threads = cl.direct_threads(limit=limit)
        messages = []
        for thread in threads:
            last_msg = thread.messages[-1] if thread.messages else None
            if last_msg:
                messages.append({
                    "thread_id": thread.id,
                    "thread_title": thread.title,
                    "last_message": last_msg.text if hasattr(last_msg, 'text') else "[Media/Other]",
                    "timestamp": last_msg.timestamp,
                    "sender_username": last_msg.user_id if hasattr(last_msg, 'user_id') else None,
                })
        return messages
    except Exception as e:
        return {"error": str(e)}

# ====================== نیا روٹ: مانیٹر پیج ======================
@app.route("/monitor", methods=["GET", "POST"])
def monitor():
    user_info = None
    dms = None
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        action = request.form.get("action")  # "get_info" یا "get_dms"

        if action == "get_info":
            target = request.form.get("target_username")
            if target:
                user_info = get_user_info(username, password, target)
                if "error" in user_info:
                    error = user_info["error"]
                    user_info = None
            else:
                error = "Please enter a target username."

        elif action == "get_dms":
            limit = int(request.form.get("limit", 10))
            dms = get_recent_dms(username, password, limit)
            if isinstance(dms, dict) and "error" in dms:
                error = dms["error"]
                dms = None

    return render_template("index.html", user_info=user_info, dms=dms, error=error, active_tab="monitor")

# ====================== مین ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

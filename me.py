import os
import json
import asyncio
import threading
import sys
import logging
import time
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)

# Auto-install dependencies cleanly
try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError, FloodWaitError, ApiIdInvalidError
except ImportError:
    print("⏳ INSTALLING REQUIRED LIBRARIES...")
    os.system(f"{sys.executable} -m pip install telethon flask waitress")
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError, FloodWaitError, ApiIdInvalidError

from flask import Flask, request, render_template_string, jsonify, send_from_directory

app = Flask(__name__)
app.secret_key = "super-secret-key-broken-waleed-multiuser-isolated"

SESSIONS_DIR = "sessions"
CACHE_DIR = os.path.join(SESSIONS_DIR, "cache_images")
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

SESSIONS_FILE = os.path.join(SESSIONS_DIR, "sessions.json")
TASKS_FILE = os.path.join(SESSIONS_DIR, "tasks.json")

active_sending_tasks = {}
temp_clients = {}
task_params = {}

# ------------------ Caching for groups ------------------
group_cache = {}

def get_cached_groups(phone):
    if phone in group_cache:
        data, expiry = group_cache[phone]
        if datetime.now() < expiry:
            return data
    return None

def set_cached_groups(phone, groups):
    group_cache[phone] = (groups, datetime.now() + timedelta(minutes=5))

# ------------------ File helpers ------------------
def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_sessions(sessions):
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=2)

def load_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_tasks(tasks):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

def normalize_phone(phone):
    if not phone:
        return ""
    phone = phone.strip()
    if not phone.startswith('+'):
        phone = '+' + phone
    return phone

# ------------------ HTML (animation‑free) ------------------
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>⚡ BROKEN WALEED • TELEGRAM BOT ⚡</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', 'Poppins', Arial, sans-serif; }
        body, .card-header h2, .card-body label, .level-text, .metric-line .label, .metric-line .value, .msg, button, .session-item span, .subtitle, h1, .modal-content h2, .instruction, .custom-file-label {
            text-transform: uppercase;
        }
        input, select, input::placeholder, select::placeholder {
            text-transform: none;
        }
        body {
            background: #0b0b1a;
            color: #e0e0e0;
            padding: 20px 15px;
            min-height: 100vh;
            position: relative;
            overflow-x: hidden;
        }
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: radial-gradient(circle at 20% 30%, rgba(0,240,255,0.05) 1px, transparent 1px),
                              radial-gradient(circle at 80% 70%, rgba(255,0,170,0.04) 1px, transparent 1px);
            background-size: 40px 40px, 60px 60px;
            pointer-events: none;
            z-index: 0;
        }
        .bot-banner-container {
            text-align: center;
            margin-bottom: 15px;
            width: 100%;
        }
        .bot-banner-img {
            width: 100%;
            height: auto;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 240, 255, 0.15);
            border: 1px solid rgba(0, 240, 255, 0.2);
            object-fit: cover;
            transition: transform 0.3s ease;
        }
        .bot-banner-img:hover {
            transform: scale(1.02);
        }
        .login-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.85);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            backdrop-filter: blur(8px);
        }
        .login-modal .modal-content {
            background: rgba(20,20,45,0.95);
            border-radius: 30px;
            padding: 30px 20px;
            width: 95%;
            max-width: 400px;
            text-align: center;
            border: 2px solid #00f0ff;
            box-shadow: 0 20px 40px rgba(0,240,255,0.2);
            position: relative;
        }
        .login-modal .modal-content h2 {
            color: #00f0ff;
            font-size: 26px;
            letter-spacing: 2px;
            margin: 0 0 10px 0;
        }
        .login-modal .modal-content .input-group {
            text-align: left;
            margin: 15px 0;
        }
        .login-modal .modal-content .input-group label {
            display: block;
            font-size: 12px;
            color: #88aaff;
            margin-bottom: 5px;
            letter-spacing: 1px;
        }
        .login-modal .modal-content input {
            width: 100%;
            padding: 14px 18px;
            border-radius: 30px;
            border: none;
            background: rgba(255,255,255,0.9);
            font-size: 16px;
            transition: all 0.3s ease;
        }
        .login-modal .modal-content input:focus {
            box-shadow: 0 0 0 3px rgba(0, 240, 255, 0.3);
            transform: scale(1.01);
        }
        .login-modal .modal-content button {
            background: linear-gradient(90deg, #00f0ff, #0072ff);
            color: white;
            padding: 14px;
            border-radius: 30px;
            border: none;
            width: 100%;
            font-weight: bold;
            cursor: pointer;
            margin-top: 20px;
            box-shadow: 0 4px 15px rgba(0,114,255,0.3);
            transition: all 0.3s ease;
            font-size: 18px;
            letter-spacing: 1px;
        }
        .login-modal .modal-content button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,114,255,0.5);
        }
        .login-modal .error-msg {
            color: #ff5588;
            margin-top: 10px;
            font-size: 14px;
        }
        #toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-width: 350px;
            width: 100%;
        }
        .toast {
            background: rgba(20, 20, 45, 0.95);
            backdrop-filter: blur(8px);
            border: 1px solid #00f0ff;
            border-radius: 16px;
            padding: 16px 20px;
            color: white;
            font-weight: 500;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            animation: slideIn 0.4s ease, fadeOut 0.5s ease 4s forwards;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 14px;
            letter-spacing: 0.3px;
        }
        .toast.success { border-color: #00cc66; }
        .toast.error { border-color: #ff5588; }
        .toast.info { border-color: #00f0ff; }
        .toast .icon { font-size: 22px; flex-shrink: 0; }
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(60px); }
            to { opacity: 1; transform: translateX(0); }
        }
        @keyframes fadeOut {
            0% { opacity: 1; transform: translateX(0); }
            100% { opacity: 0; transform: translateX(60px); }
        }
        .update-modal, .task-detail-modal {
            display: none;
        }
        .update-modal, .task-detail-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            align-items: center;
            justify-content: center;
            z-index: 1000;
            backdrop-filter: blur(6px);
        }
        .update-modal .modal-content, .task-detail-modal .modal-content {
            background: rgba(20,20,45,0.95);
            border-radius: 24px;
            padding: 25px;
            width: 95%;
            max-width: 420px;
            text-align: center;
            border: 2px solid #00f0ff;
            box-shadow: 0 20px 40px rgba(0,240,255,0.15);
        }
        .update-modal .modal-content h2, .task-detail-modal .modal-content h2 {
            margin-top: 5px;
            margin-bottom: 15px;
            color: #00f0ff;
            font-size: 20px;
        }
        .update-modal .modal-content .input-group {
            text-align: left;
            margin: 12px 0;
        }
        .update-modal .modal-content .input-group label {
            display: block;
            font-size: 12px;
            color: #88aaff;
            margin-bottom: 5px;
        }
        .update-modal .modal-content input {
            width: 100%;
            padding: 12px 16px;
            border-radius: 30px;
            border: none;
            background: rgba(255,255,255,0.9);
            font-size: 16px;
        }
        .update-modal .modal-content button {
            background: linear-gradient(90deg, #00f0ff, #0072ff);
            color: white;
            padding: 12px;
            border-radius: 30px;
            border: none;
            width: 100%;
            font-weight: bold;
            cursor: pointer;
            margin-top: 12px;
            box-shadow: 0 4px 15px rgba(0,114,255,0.3);
            transition: all 0.3s ease;
        }
        .update-modal .modal-content button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,114,255,0.5);
        }
        .update-modal .error-msg {
            color: #ff5588;
            margin-top: 10px;
            font-size: 12px;
        }
        .task-detail-modal .modal-content {
            max-width: 600px;
            border-color: #ffaa00;
            box-shadow: 0 0 30px rgba(255,170,0,0.15);
        }
        .task-detail-modal .modal-content .detail-row {
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 14px;
        }
        .task-detail-modal .modal-content .detail-row .label {
            color: #88aaff;
        }
        .task-detail-modal .modal-content .detail-row .value {
            color: #fff;
            font-weight: bold;
        }
        .task-detail-modal .modal-content .status-badge {
            display: inline-block;
            padding: 3px 12px;
            border-radius: 20px;
            background: #00cc66;
            color: #fff;
            font-weight: bold;
            font-size: 12px;
            margin: 5px 0;
        }
        .task-detail-modal .modal-content .btn-group {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        .task-detail-modal .modal-content .btn-group button {
            flex: 1;
            min-width: 80px;
            padding: 10px;
            border-radius: 30px;
            border: none;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .task-detail-modal .modal-content .btn-group .update-btn {
            background: linear-gradient(90deg, #ffaa00, #ff6600);
            color: white;
        }
        .task-detail-modal .modal-content .btn-group .delete-btn {
            background: #ff0055;
            color: white;
        }
        .main-content {
            display: block;
            position: relative;
            z-index: 1;
        }
        h1 {
            text-align: center;
            margin-bottom: 5px;
            font-weight: 900;
            letter-spacing: 3px;
            background: linear-gradient(135deg, #ff00aa, #00f0ff);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            font-size: 40px;
            text-shadow: 0 2px 15px rgba(0,240,255,0.2);
        }
        .subtitle {
            text-align: center;
            margin-bottom: 30px;
            font-size: 14px;
            color: #ffaa00;
            letter-spacing: 2px;
            font-weight: bold;
            text-shadow: 0 0 6px rgba(255,170,0,0.3);
        }
        .subtitle small {
            display: block;
            font-size: 11px;
            color: #88aaff;
            letter-spacing: 1px;
        }
        .cards-container {
            display: flex;
            flex-direction: column;
            gap: 25px;
            width: 100%;
            max-width: 1200px;
            margin: 0 auto;
        }
        .card {
            width: 100%;
            background: rgba(12, 12, 28, 0.8);
            border-radius: 30px;
            border: 2px solid #d4af37;
            box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
            transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
            overflow: hidden;
            backdrop-filter: blur(4px);
            will-change: transform, box-shadow;
        }
        .token-card {
            cursor: pointer;
        }
        .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 15px 35px -10px rgba(0,0,0,0.7);
            border-color: #ffd700;
        }
        .card.active {
            border-color: #00f0ff;
            box-shadow: 0 0 25px rgba(0, 240, 255, 0.15), 0 10px 30px rgba(0,0,0,0.5);
        }
        .card-header {
            padding: 18px 25px;
            background: rgba(0, 0, 0, 0.4);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            flex-wrap: wrap;
            border-bottom: 2px solid rgba(212,175,55,0.3);
            border-radius: 30px 30px 0 0;
            user-select: none;
            transition: border-color 0.4s ease;
        }
        .card.active .card-header {
            border-bottom-color: rgba(0, 240, 255, 0.3);
        }
        .card-header h2 {
            flex: 1;
            text-align: center;
            margin: 0;
            font-size: 20px;
            letter-spacing: 1px;
            text-shadow: 0 1px 5px rgba(0,0,0,0.3);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }
        .instruction {
            font-size: 10px;
            color: #aaa;
            padding: 8px 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 0 0 20px 20px;
            border-top: 1px solid rgba(255,255,255,0.05);
            margin-top: 2px;
            transition: all 0.3s ease;
        }
        .card-token .instruction { color: #ffaa44; border-left: 3px solid #ffaa44; }
        .card-1 .instruction { color: #ffaa00; border-left: 3px solid #ffaa00; }
        .card-2 .instruction { color: #00ffaa; border-left: 3px solid #00ffaa; }
        .card-3 .instruction { color: #ff66cc; border-left: 3px solid #ff66cc; }
        .card-4 .instruction { color: #66ccff; border-left: 3px solid #66ccff; }
        .card-admin .instruction { color: #ff44ff; border-left: 3px solid #ff44ff; }
        .card-header .status-icon {
            color: #00f0ff;
            font-size: 22px;
            transition: transform 0.4s ease;
            filter: drop-shadow(0 2px 5px rgba(0,240,255,0.3));
        }
        .card.active .status-icon {
            transform: rotate(180deg);
        }
        .card-body {
            max-height: 0;
            padding: 0 25px;
            opacity: 0;
            visibility: hidden;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 0 0 30px 30px;
            transition: max-height 0.5s cubic-bezier(0.165, 0.84, 0.44, 1), padding 0.5s ease, opacity 0.4s ease, visibility 0.4s ease;
        }
        .card.active .card-body {
            max-height: 1800px;
            padding: 25px 25px;
            opacity: 1;
            visibility: visible;
        }
        .token-card .card-body {
            text-align: center;
        }
        .form-line {
            margin: 18px 0;
        }
        .form-line label {
            display: block;
            font-size: 13px;
            font-weight: bold;
            color: #88aaff;
            margin-bottom: 5px;
            letter-spacing: 0.5px;
            text-shadow: 0 0 8px rgba(136,170,255,0.2);
        }
        input, select, button, .custom-file-label {
            width: 100%;
            padding: 14px 20px;
            border-radius: 30px;
            border: none;
            font-size: 16px;
            outline: none;
            transition: all 0.3s ease;
            background: rgba(255, 255, 255, 0.95);
            color: #111;
            font-weight: 500;
            border: 1px solid transparent;
        }
        input:focus, select:focus {
            background: #fff;
            box-shadow: 0 0 0 3px rgba(0, 240, 255, 0.3);
            transform: scale(1.005);
            border-color: #00f0ff;
        }
        .custom-file-upload {
            position: relative;
            display: inline-block;
            width: 100%;
        }
        .custom-file-upload input[type="file"] {
            display: none;
        }
        .custom-file-label {
            background: linear-gradient(90deg, #00c6ff, #0072ff);
            color: white;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(0, 114, 255, 0.3);
            text-align: center;
            display: block;
            letter-spacing: 1px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .custom-file-label:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 114, 255, 0.4);
        }
        button {
            background: linear-gradient(90deg, #00c6ff, #0072ff);
            color: white;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(0, 114, 255, 0.3);
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.3s ease;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 114, 255, 0.5);
        }
        .green-btn {
            background: linear-gradient(90deg, #00cc66, #009933);
            box-shadow: 0 4px 15px rgba(0, 204, 102, 0.3);
        }
        .level-text {
            font-size: 11px;
            color: #ffdd44;
            background: rgba(0,0,0,0.5);
            display: inline-block;
            padding: 4px 14px;
            border-radius: 20px;
            margin-bottom: 6px;
            border: 1px solid #ffdd44;
        }
        .task-cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 15px;
        }
        .task-card {
            background: rgba(0,0,0,0.7);
            border-radius: 20px;
            padding: 15px 15px 12px;
            border: 1px solid rgba(255,170,0,0.2);
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            gap: 4px;
            will-change: transform;
        }
        .task-card:hover {
            transform: translateY(-4px);
            border-color: #ffaa00;
            box-shadow: 0 8px 25px rgba(255,170,0,0.1);
        }
        .task-card .task-title {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 16px;
            font-weight: bold;
            color: #ffaa00;
            letter-spacing: 1px;
            margin-bottom: 6px;
            text-shadow: 0 0 8px rgba(255,170,0,0.2);
        }
        .task-card .task-title .avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid #ffaa00;
            background: #1a1a2e;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: #ffaa00;
            font-size: 14px;
        }
        .task-card .task-row {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            padding: 3px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .task-card .task-row .label {
            color: #88aaff;
        }
        .task-card .task-row .value {
            color: #fff;
            font-weight: 500;
        }
        .task-card .status-badge {
            display: inline-block;
            padding: 2px 12px;
            border-radius: 20px;
            background: #00cc66;
            color: #fff;
            font-size: 11px;
            font-weight: bold;
            text-align: center;
        }
        .task-card .uptime-text {
            color: #00ffaa;
            font-weight: bold;
        }
        .task-card .next-msg {
            color: #ffaa44;
            font-weight: bold;
        }
        .task-card .btn-group-mini {
            display: flex;
            gap: 8px;
            margin-top: 10px;
            flex-wrap: wrap;
        }
        .task-card .btn-group-mini button {
            flex: 1;
            padding: 10px 0;
            border-radius: 25px;
            border: none;
            font-weight: bold;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s ease;
            min-width: 70px;
        }
        .task-card .btn-group-mini .update-btn {
            background: linear-gradient(90deg, #ffaa00, #ff6600);
            color: white;
        }
        .task-card .btn-group-mini .delete-btn {
            background: #ff0055;
            color: white;
        }
        .admin-task-card {
            border-color: rgba(255,68,255,0.3);
        }
        .admin-task-card:hover {
            border-color: #ff44ff;
            box-shadow: 0 8px 25px rgba(255,68,255,0.1);
        }
        .admin-task-card .task-title {
            color: #ff44ff;
        }
        .admin-task-card .task-title .avatar {
            border-color: #ff44ff;
        }
        .task-card-separator {
            border: none;
            border-top: 1px solid rgba(255,170,0,0.1);
            margin: 15px 0 8px;
            width: 100%;
        }
        .no-tasks {
            text-align: center;
            padding: 25px;
            color: #888;
            font-size: 14px;
        }
        .hidden { display: none; }
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .spinner {
            width: 18px;
            height: 18px;
            border: 3px solid transparent;
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
            display: inline-block;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .card-admin .card-header {
            border-bottom-color: #ff44ff;
        }
        .card-admin.active {
            border-color: #ff44ff;
            box-shadow: 0 0 25px rgba(255,68,255,0.15), 0 10px 30px rgba(0,0,0,0.5);
        }
        .card-admin.hidden-admin {
            display: none !important;
        }
        .logout-container {
            text-align: center;
            margin-top: 40px;
            padding: 15px 0;
            width: 100%;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }
        .logout-btn {
            background: linear-gradient(90deg, #ff0055, #ff3300);
            color: white;
            border: none;
            padding: 14px 20px;
            border-radius: 30px;
            font-weight: bold;
            font-size: 16px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(255,0,85,0.3);
            transition: all 0.3s ease;
            letter-spacing: 1px;
            width: 100%;
            max-width: 1200px;
        }
        .logout-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(255,0,85,0.5);
        }
        @media(max-width: 600px) {
            .card-header { flex-direction: column; text-align: center; }
            .card-header h2 { order: 1; font-size: 18px; }
            .status-icon { order: 2; }
            h1 { font-size: 32px; }
            .task-cards-grid { grid-template-columns: 1fr; }
        }
        .group-list {
            margin-top: 10px;
            max-height: 300px;
            overflow-y: auto;
        }
        .group-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 12px;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            margin-bottom: 6px;
            cursor: pointer;
            transition: background 0.3s ease;
        }
        .group-item:hover {
            background: rgba(0,240,255,0.1);
        }
        .group-item img {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid #00f0ff;
        }
        .group-item .group-info {
            flex: 1;
        }
        .group-item .group-info strong {
            color: #fff;
        }
        .group-item .group-info small {
            color: #aaa;
        }
        .selected-group-card {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: rgba(0,240,255,0.1);
            border-radius: 12px;
            margin-top: 10px;
            border: 1px solid #00f0ff;
        }
        .selected-group-card img {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid #00f0ff;
        }
        .task-card .task-row .value.target-val { color: #00f0ff; }
        .task-card .task-row .value.file-val { color: #00ff88; }
        .task-card .task-row .value.hater-val { color: #ffaa44; }
        .task-card .task-row .value.speed-val { color: #ff66cc; }
        .task-card .task-row .value.last-val { color: #ff8844; }
        .task-card .task-row .value.status-val { color: #00cc66; }
        .task-card .task-row .value.uptime-val { color: #00ffaa; }
        .task-card .task-row .value.next-val { color: #ffaa44; }
    </style>
</head>
<body>

<!-- LOGIN MODAL (shown by default) -->
<div id="loginModal" class="login-modal">
    <div class="modal-content">
        <div class="bot-banner-container">
            <img src="https://i.ibb.co/FqV2CKVd/IMG-20260610-115404.png" class="bot-banner-img">
        </div>
        <h2>TELEGRAM BOT SYSTEM</h2>
        <div class="input-group">
            <label>USERNAME</label>
            <input type="text" id="loginUsername" placeholder="ENTER USERNAME" autofocus>
        </div>
        <div class="input-group">
            <label>PASSWORD</label>
            <input type="password" id="loginPassword" placeholder="ENTER PASSWORD">
        </div>
        <button onclick="attemptLogin()">➡️ UNLOCK</button>
        <div id="loginError" class="error-msg"></div>
    </div>
</div>

<!-- Toast Container -->
<div id="toast-container"></div>

<!-- Update Task Modal (hidden by default) -->
<div id="updateModal" class="update-modal">
    <div class="modal-content">
        <h2 id="updateModalTitle">✏️ UPDATE TASK PARAMETERS</h2>
        <div class="form-line">
            <label>HATER NAME (PREFIX)</label>
            <input type="text" id="updateHater" placeholder="NEW PREFIX">
        </div>
        <div class="form-line">
            <label>SPEED (SECONDS)</label>
            <input type="number" id="updateSpeed" placeholder="DELAY IN SECONDS">
        </div>
        <div class="form-line">
            <label>LAST HATER (SUFFIX)</label>
            <input type="text" id="updateLastHater" placeholder="NEW SUFFIX">
        </div>
        <div class="form-line">
            <label>TARGET SESSION</label>
            <input type="text" id="updateTarget" placeholder="ENTER TARGET ID">
        </div>
        <div class="form-line">
            <label>NEW MESSAGE FILE (.TXT)</label>
            <div class="custom-file-upload">
                <label for="updateMessageFile" class="custom-file-label">CHOOSE FILE</label>
                <input type="file" id="updateMessageFile" accept=".txt">
            </div>
        </div>
        <button onclick="submitUpdate()">APPLY UPDATE</button>
        <button onclick="closeUpdateModal()" style="background: #333; margin-top: 10px;">CANCEL</button>
        <div id="updateMsg" class="error-msg"></div>
    </div>
</div>

<!-- Task Detail Modal (kept for compatibility, hidden) -->
<div id="taskDetailModal" class="task-detail-modal">
    <div class="modal-content">
        <h2 style="color:#ffaa00;">📋 TASK DETAILS</h2>
        <div id="taskDetailContent"></div>
        <div class="btn-group" id="taskDetailButtons"></div>
        <button onclick="closeTaskDetail()" style="background:#333; margin-top:15px; padding:10px; border-radius:30px; border:none; color:white; font-weight:bold; cursor:pointer; width:100%;">CLOSE</button>
    </div>
</div>

<div class="main-content" id="mainContent">
    <h1>BROKEN WALEED</h1>
    <div class="subtitle">
        ⚡ TELEGRAM AUTO BOT • ENTERPRISE EDITION ⚡
        <small>BE YOUR BEST, DO YOUR BEST</small>
    </div>

    <div class="cards-container">
        <!-- TOKEN CARD -->
        <div class="card token-card card-token" id="card-token" onclick="window.open('https://my.telegram.org/auth', '_blank')">
            <div class="card-header">
                <h2 id="hdr-token"><span class="emoji"></span>GET ACCESS TOKEN</h2>
                <span class="status-icon"></span>
            </div>
            <div class="card-body">
                <p>🔗 CLICK ANYWHERE TO GET API CREDENTIALS</p>
                <p style="font-size:14px; margin-top:5px;">my.telegram.org/auth</p>
            </div>
            <div class="instruction">📌 HOW TO USE: CLICK THIS CARD TO OPEN TELEGRAM API WEBSITE. GET YOUR API ID AND HASH.</div>
        </div>

        <!-- LOGIN ACCOUNT CARD -->
        <div class="card card-1" id="card-1">
            <div class="card-header" onclick="handleCardClick('card-1')">
                <h2 id="hdr-login"><span class="emoji"></span>LOGIN ACCOUNT</h2>
                <span class="status-icon"></span>
            </div>
            <div class="card-body">
                <div class="form-line">
                    <label>API ID (FROM MY.TELEGRAM.ORG)</label>
                    <input type="number" id="api_id" placeholder="ENTER TELEGRAM API ID">
                </div>
                <div class="form-line">
                    <label>API HASH</label>
                    <input type="text" id="api_hash" placeholder="ENTER TELEGRAM API HASH">
                </div>
                <div class="form-line">
                    <label>PHONE NUMBER (WITH COUNTRY CODE)</label>
                    <input type="text" id="phone" placeholder="+1234567890">
                </div>
                <div class="form-line">
                    <div class="level-text">🔰 LEVEL 1 – SEND CODE</div>
                    <button id="sendCodeBtn" onclick="sendCode()">📨 TRIGGER OTP DISPATCH</button>
                </div>
                <div class="form-line hidden" id="codeLine">
                    <label>VERIFICATION CODE</label>
                    <input type="text" id="code" placeholder="ENTER OTP">
                </div>
                <div class="form-line hidden" id="passwordLine">
                    <label>2FA PASSWORD (IF ANY)</label>
                    <input type="password" id="password" placeholder="ENTER TWO-FACTOR PASSWORD">
                </div>
                <div class="form-line hidden" id="verifyLine">
                    <div class="level-text">🔰 LEVEL 2 – VERIFY & AUTHORIZE</div>
                    <button id="verifyBtn" onclick="verifyCode()">✅ AUTHORIZE & CONFIGURE SYSTEM</button>
                </div>
                <div id="loginMsg"></div>
            </div>
            <div class="instruction">📌 HOW TO USE: FILL API ID, HASH AND PHONE. CLICK "TRIGGER OTP". ENTER CODE & 2FA IF NEEDED.</div>
        </div>

        <!-- GROUPS CARD -->
        <div class="card card-2" id="card-2">
            <div class="card-header" onclick="handleCardClick('card-2')">
                <h2 id="hdr-groups"><span class="emoji"></span>FATH GROUP</h2>
                <span class="status-icon"></span>
            </div>
            <div class="card-body">
                <div class="form-line">
                    <div class="level-text">🔰 LEVEL 3 – SCAN GROUPS (USES FIRST REGISTERED ACCOUNT)</div>
                    <button id="fetchGroupsBtn" onclick="fetchGroups()">CLICK SCAN ALL GROUP</button>
                </div>
                <div id="groupsList" class="group-list">CLICK SCAN TO LOAD GROUPS.</div>
                <div id="selectedGroupDisplay"></div>
                <div id="groupMsg"></div>
            </div>
            <div class="instruction">📌 HOW TO USE: CLICK "SCAN" TO SEE ALL GROUPS WITH PHOTOS. CLICK ANY GROUP TO SELECT TARGET.</div>
        </div>

        <!-- TELEGRAM CONVO CARD -->
        <div class="card card-3" id="card-3">
            <div class="card-header" onclick="handleCardClick('card-3')">
                <h2 id="hdr-convo"><span class="emoji"></span>TELEGRAM CONVO</h2>
                <span class="status-icon"></span>
            </div>
            <div class="card-body">
                <div class="form-line">
                    <label>SELECT DEPLOYMENT DISPATCH HANDLE:</label>
                    <select id="senderAccountSelect" style="color: #00ffaa; font-weight: bold;"><option value="">-- NO ACTIVE ACCOUNTS --</option></select>
                </div>
                <div class="form-line">
                    <label>TARGET GROUP ID OR USERNAME</label>
                    <input type="text" id="targetNumber" placeholder="ENTER TARGET ID (E.G., -+917209101285)">
                </div>
                <div class="form-line">
                    <label>HATER DESIGNATION TAGS (PREFIX)</label>
                    <input type="text" id="haterName" placeholder="ENTER FIRST HATER NAME">
                </div>
                <div class="form-line">
                    <label>FREQUENCY DELAY (SECONDS)</label>
                    <input type="number" id="speedSecond" placeholder="ENTER DELAY IN SECONDS" value="20">
                </div>
                <div class="form-line">
                    <label>CLOSING SUFFIX DATA METRIC (POSTFIX)</label>
                    <input type="text" id="lastHater" placeholder="ENTER LAST HATER NAME">
                </div>
                <div class="form-line">
                    <label>LOAD TRANSMISSION STRINGS FILE (.TXT)</label>
                    <div class="custom-file-upload">
                        <label for="messageFile" class="custom-file-label">CHOOSE FILE</label>
                        <input type="file" id="messageFile" accept=".txt">
                    </div>
                </div>
                <div class="form-line">
                    <div class="level-text">🔰 LEVEL 4 – START AUTOMATION</div>
                    <button id="startSendBtn" onclick="startSending()" class="green-btn">START LODER</button>
                </div>
                <div id="convoMsg"></div>
            </div>
            <div class="instruction">📌 HOW TO USE: SELECT ACCOUNT, TARGET (AUTO-FILLED FROM GROUP CARD), SET PREFIX/SUFFIX/DELAY, UPLOAD TXT FILE, THEN CLICK "START LODER".</div>
        </div>

        <!-- SESSION MANAGE CARD -->
        <div class="card card-4" id="card-4">
            <div class="card-header" onclick="handleCardClick('card-4')">
                <h2 id="hdr-session"><span class="emoji"></span>SESSION MANAGE</h2>
                <span class="status-icon"></span>
            </div>
            <div class="card-body">
                <div id="sessionsContainer">
                    <!-- Will be populated by JS with task cards -->
                </div>
            </div>
            <div class="instruction">📌 HOW TO USE: EACH CARD SHOWS FULL DETAILS WITH COLOUR CODING. USE UPDATE/DELETE BUTTONS.</div>
        </div>

        <!-- ADMIN CARD (hidden by default) -->
        <div class="card card-admin hidden-admin" id="card-admin">
            <div class="card-header" onclick="handleCardClick('card-admin')">
                <h2 id="hdr-admin"><span class="emoji"></span>ADMIN PANEL</h2>
                <span class="status-icon"></span>
            </div>
            <div class="card-body">
                <div id="adminContainer">
                    <!-- Admin task cards will be rendered here -->
                </div>
            </div>
            <div class="instruction">📌 ADMIN: FULL CONTROL OVER ALL USERS' TASKS.</div>
        </div>
    </div>

    <!-- LOGOUT BUTTON -->
    <div class="logout-container">
        <button class="logout-btn" onclick="logout()">🚪 LOGOUT HOME PAGE</button>
    </div>
</div>

<script>
    // ==================== LOGIN SYSTEM ====================
    const USERS = {
        'BROKEN WALEED': { password: 'password123', role: 'user' },
        'WALEED': { password: 'admin123', role: 'admin' }
    };

    window.sessionData = {};
    let currentRole = sessionStorage.getItem('userRole') || null;
    let isLoggedIn = sessionStorage.getItem('loggedIn') === 'true';

    if (!isLoggedIn) {
        document.getElementById('loginModal').style.display = 'flex';
    } else {
        document.getElementById('loginModal').style.display = 'none';
        if (currentRole === 'admin') {
            document.getElementById('card-admin').classList.remove('hidden-admin');
        }
        initializeApp();
    }

    // Toast system
    function showToast(message, type = 'info', duration = 4000) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icons = { success: '✅', error: '❌', info: 'ℹ️' };
        toast.innerHTML = `<span class="icon">${icons[type] || 'ℹ️'}</span> ${message}`;
        container.appendChild(toast);
        setTimeout(() => {
            if (toast.parentNode) toast.remove();
        }, duration);
    }

    function attemptLogin() {
        const username = document.getElementById('loginUsername').value.trim().toUpperCase();
        const password = document.getElementById('loginPassword').value.trim();
        const errorEl = document.getElementById('loginError');

        if (!username || !password) {
            errorEl.textContent = '⚠️ PLEASE FILL ALL FIELDS';
            showToast('Please fill all fields', 'error');
            return;
        }

        if (USERS[username] && USERS[username].password === password) {
            const role = USERS[username].role;
            sessionStorage.setItem('loggedIn', 'true');
            sessionStorage.setItem('userRole', role);
            currentRole = role;
            isLoggedIn = true;

            document.getElementById('loginModal').style.display = 'none';

            if (role === 'admin') {
                document.getElementById('card-admin').classList.remove('hidden-admin');
            } else {
                document.getElementById('card-admin').classList.add('hidden-admin');
            }

            initializeApp();
            errorEl.textContent = '';
            document.getElementById('loginUsername').value = '';
            document.getElementById('loginPassword').value = '';
            showToast('Login successful!', 'success');
        } else {
            errorEl.textContent = '❌ INVALID USERNAME OR PASSWORD';
            showToast('Invalid credentials', 'error');
        }
    }

    document.getElementById('loginPassword').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') attemptLogin();
    });
    document.getElementById('loginUsername').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') attemptLogin();
    });

    function logout() {
        sessionStorage.removeItem('loggedIn');
        sessionStorage.removeItem('userRole');
        isLoggedIn = false;
        currentRole = null;
        document.getElementById('card-admin').classList.add('hidden-admin');
        document.querySelectorAll('.card').forEach(c => c.classList.remove('active'));
        document.getElementById('loginModal').style.display = 'flex';
        document.getElementById('sessionsContainer').innerHTML = '';
        document.getElementById('adminContainer').innerHTML = '';
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
        showToast('Logged out', 'info');
    }

    function handleCardClick(cardId) {
        const card = document.getElementById(cardId);
        if (card.classList.contains('active')) {
            card.classList.remove('active');
        } else {
            document.querySelectorAll('.card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            if (cardId === 'card-4') {
                syncSystemAccounts();
            } else if (cardId === 'card-admin' && currentRole === 'admin') {
                syncAdminPanel();
            }
            setTimeout(() => {
                card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }, 200);
        }
    }

    function getToken() {
        let token = localStorage.getItem('user_token');
        if (!token) {
            token = 'token_' + Math.random().toString(36).substring(2) + '_' + Date.now();
            localStorage.setItem('user_token', token);
        }
        return token;
    }

    function setButtonLoading(btnId, isLoading, originalText) {
        let btn = document.getElementById(btnId);
        if (!btn) return;
        if (isLoading) {
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner"></span> TUNING ENGINE...`;
        } else {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    function formatUptime(startTimestamp) {
        if (!startTimestamp) return "0S";
        let diff = Math.floor(Date.now() / 1000) - parseInt(startTimestamp);
        if (diff < 0) diff = 0;
        let d = Math.floor(diff / 86400);
        let h = Math.floor((diff % 86400) / 3600);
        let m = Math.floor((diff % 3600) / 60);
        let s = diff % 60;
        let parts = [];
        if (d > 0) parts.push(d + "D");
        if (h > 0 || d > 0) parts.push(h + "H");
        if (m > 0 || h > 0 || d > 0) parts.push(m + "M");
        parts.push(s + "S");
        return parts.join(" ");
    }

    function getNextMsgIn(lastSend, speed) {
        if (!lastSend) return "—";
        let now = Math.floor(Date.now() / 1000);
        let elapsed = now - lastSend;
        let remaining = Math.max(0, speed - elapsed);
        return Math.ceil(remaining) + " SEC";
    }

    function getAvatarHtml(sessionInfo) {
        if (sessionInfo && sessionInfo.avatar_url) {
            return `<img src="${sessionInfo.avatar_url}?t=${Date.now()}" class="avatar" alt="DP">`;
        } else {
            let initial = (sessionInfo && sessionInfo.first_name) ? sessionInfo.first_name.charAt(0).toUpperCase() : '?';
            return `<div class="avatar">${initial}</div>`;
        }
    }

    // ==================== API CALLS ====================
    async function sendCode() {
        let api_id = document.getElementById('api_id').value;
        let api_hash = document.getElementById('api_hash').value;
        let phone = document.getElementById('phone').value;
        let originalText = "📨 TRIGGER OTP DISPATCH";
        if(!api_id || !api_hash || !phone) { showToast('All fields required!', 'error'); return; }
        setButtonLoading('sendCodeBtn', true, originalText);
        try {
            let res = await fetch('/api/send_code', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({api_id: api_id, api_hash: api_hash, phone: phone})
            });
            let data = await res.json();
            if(data.success) {
                document.getElementById('codeLine').classList.remove('hidden');
                document.getElementById('verifyLine').classList.remove('hidden');
                showToast('OTP sent successfully!', 'success');
            } else {
                showToast('Error: ' + data.message, 'error');
            }
        } catch(e) {
            showToast('Network error', 'error');
        } finally {
            setButtonLoading('sendCodeBtn', false, originalText);
        }
    }

    async function verifyCode() {
        let phone = document.getElementById('phone').value;
        let code = document.getElementById('code').value;
        let password = document.getElementById('password').value;
        let originalText = "✅ AUTHORIZE & CONFIGURE SYSTEM";
        setButtonLoading('verifyBtn', true, originalText);
        try {
            let res = await fetch('/api/verify_code', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({phone: phone, code: code, password: password, owner: getToken()})
            });
            let data = await res.json();
            if(data.success) {
                showToast('🎉 Device registered successfully!', 'success');
                document.getElementById('codeLine').classList.add('hidden');
                document.getElementById('passwordLine').classList.add('hidden');
                document.getElementById('verifyLine').classList.add('hidden');
                document.getElementById('code').value = '';
                document.getElementById('password').value = '';
                const card4 = document.getElementById('card-4');
                if (card4.classList.contains('active')) syncSystemAccounts();
            } else if(data.needs_password) {
                document.getElementById('passwordLine').classList.remove('hidden');
                showToast('2FA required. Enter your password.', 'info');
            } else {
                showToast('Error: ' + data.message, 'error');
            }
        } catch(e) {
            showToast('Verification failed', 'error');
        } finally {
            setButtonLoading('verifyBtn', false, originalText);
        }
    }

    async function fetchGroups() {
        let token = getToken();
        let accountsRes = await fetch('/api/list_sessions?owner=' + encodeURIComponent(token));
        let accountsData = await accountsRes.json();
        let sessions = accountsData.sessions;
        let phones = Object.keys(sessions);
        if(phones.length === 0) {
            showToast('No accounts registered. Add an account first.', 'error');
            return;
        }
        let selectedAccount = phones[0];
        let originalText = "📂 SCAN ALL GROUPS";
        setButtonLoading('fetchGroupsBtn', true, originalText);
        document.getElementById('groupsList').innerHTML = '⏳ HARVESTING REMOTE GROUPS...';
        try {
            let res = await fetch('/api/get_groups?phone=' + encodeURIComponent(selectedAccount));
            let data = await res.json();
            if(data.success && data.groups) {
                let html = '';
                data.groups.forEach(g => {
                    let avatar = g.avatar_url ? `<img src="${g.avatar_url}?t=${Date.now()}" alt="Group">` : `<div style="width:40px;height:40px;border-radius:50%;background:#333;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;border:2px solid #00f0ff;">${g.name.charAt(0)}</div>`;
                    html += `<div class="group-item" onclick="selectGroup('${g.id}', '${g.name.replace(/'/g, "\\\\'")}')">
                                ${avatar}
                                <div class="group-info">
                                    <strong>${g.name}</strong>
                                    <small style="display:block; color:#aaa; margin-top:3px;">ID: ${g.id}</small>
                                </div>
                             </div>`;
                });
                document.getElementById('groupsList').innerHTML = html;
                showToast('Groups loaded successfully!', 'success');
            } else {
                showToast('Scan failed: ' + data.message, 'error');
            }
        } catch(e) {
            showToast('Network timeout', 'error');
        } finally {
            setButtonLoading('fetchGroupsBtn', false, originalText);
        }
    }

    function selectGroup(id, name) {
        document.getElementById('targetNumber').value = id;
        let selectedHtml = `<div class="selected-group-card">
                                <div>
                                    <strong style="color:#00f0ff;">${name}</strong><br>
                                    <small style="color:#aaa;">ID: ${id}</small>
                                </div>
                            </div>`;
        document.getElementById('selectedGroupDisplay').innerHTML = selectedHtml;
        document.getElementById('groupsList').innerHTML = '<div style="text-align:center; padding:20px;">✅ GROUP SELECTED</div>';
        showToast('Group selected: ' + name, 'success');
    }

    async function startSending() {
        let account = document.getElementById('senderAccountSelect').value;
        let target = document.getElementById('targetNumber').value;
        let hater = document.getElementById('haterName').value;
        let speed = document.getElementById('speedSecond').value;
        let lastHater = document.getElementById('lastHater').value;
        let fileInput = document.getElementById('messageFile');
        let originalText = "START LODER";
        if(!account || !target) { showToast('Select account and target first!', 'error'); return; }
        setButtonLoading('startSendBtn', true, originalText);
        
        let formData = new FormData();
        formData.append('phone', account);
        formData.append('target', target);
        formData.append('hater', hater);
        formData.append('speed', speed);
        formData.append('last_hater', lastHater);
        formData.append('owner', getToken());
        if(fileInput.files[0]) formData.append('file', fileInput.files[0]);
        
        try {
            let res = await fetch('/api/start_sending', { method: 'POST', body: formData });
            let data = await res.json();
            if(data.success) {
                showToast(' SERVER START SUCCESSFUL!! ✅', 'success');
                const card4 = document.getElementById('card-4');
                if (card4.classList.contains('active')) syncSystemAccounts();
            } else {
                showToast('Error: ' + data.message, 'error');
            }
        } catch(e) {
            showToast('Start failed', 'error');
        } finally {
            setButtonLoading('startSendBtn', false, originalText);
        }
    }

    async function deleteTask(phone, taskId, btnId) {
        if(!confirm("TERMINATE THIS TASK?")) return;
        let btn = document.getElementById(btnId);
        if(btn) btn.innerHTML = `TERMINATING...`;
        try {
            let res = await fetch(`/api/delete_task?phone=${encodeURIComponent(phone)}&task_id=${encodeURIComponent(taskId)}`);
            let data = await res.json();
            if(data.success) {
                showToast('Task deleted', 'success');
                const card4 = document.getElementById('card-4');
                if (card4.classList.contains('active')) syncSystemAccounts();
                if (currentRole === 'admin' && document.getElementById('card-admin').classList.contains('active')) syncAdminPanel();
            } else {
                showToast('Delete failed', 'error');
            }
        } catch(e) {
            showToast('Error deleting task', 'error');
        }
    }

    function openUpdateModal(phone, taskId, currentHater, currentSpeed, currentLastHater, currentTarget) {
        currentUpdateTask = { phone, taskId };
        document.getElementById('updateHater').value = currentHater || '';
        document.getElementById('updateSpeed').value = currentSpeed || 2;
        document.getElementById('updateLastHater').value = currentLastHater || '';
        document.getElementById('updateTarget').value = currentTarget || '';
        document.getElementById('updateMessageFile').value = '';
        document.getElementById('updateMsg').innerHTML = '';

        let session = window.sessionData[phone] || {};
        let firstName = session.first_name || phone;
        let avatarHtml = session.avatar_url ? `<img src="${session.avatar_url}?t=${Date.now()}" style="width:36px; height:36px; border-radius:50%; object-fit:cover; border:2px solid #00f0ff; margin-right:8px;">` : '';
        document.getElementById('updateModalTitle').innerHTML = `${avatarHtml} ${firstName}`;

        document.getElementById('updateModal').style.display = 'flex';
    }

    function closeUpdateModal() {
        document.getElementById('updateModal').style.display = 'none';
        currentUpdateTask = null;
    }

    async function submitUpdate() {
        if (!currentUpdateTask) return;
        let formData = new FormData();
        formData.append('phone', currentUpdateTask.phone);
        formData.append('task_id', currentUpdateTask.taskId);
        formData.append('hater', document.getElementById('updateHater').value);
        formData.append('speed', document.getElementById('updateSpeed').value);
        formData.append('last_hater', document.getElementById('updateLastHater').value);
        formData.append('target', document.getElementById('updateTarget').value);
        let fileInput = document.getElementById('updateMessageFile');
        if (fileInput.files[0]) formData.append('file', fileInput.files[0]);
        
        try {
            let res = await fetch('/api/update_task', { method: 'POST', body: formData });
            let data = await res.json();
            if (data.success) {
                showToast('✅ Task updated successfully!', 'success');
                setTimeout(() => {
                    closeUpdateModal();
                    const card4 = document.getElementById('card-4');
                    if (card4.classList.contains('active')) syncSystemAccounts();
                    if (currentRole === 'admin' && document.getElementById('card-admin').classList.contains('active')) syncAdminPanel();
                }, 1500);
            } else {
                showToast('Error: ' + data.message, 'error');
            }
        } catch(e) {
            showToast('Network error', 'error');
        }
    }

    document.getElementById('updateModal').addEventListener('click', function(e) {
        if (e.target === this) closeUpdateModal();
    });

    let currentUpdateTask = null;

    // ==================== RENDER TASK CARDS ====================
    function renderTaskCards(containerId, tasksData, isAdmin = false) {
        let container = document.getElementById(containerId);
        let html = '';
        let hasTasks = false;

        for (let phone in tasksData.tasks) {
            let tasks = tasksData.tasks[phone];
            let sessionInfo = tasksData.sessions[phone] || {};
            tasks.forEach((task, index) => {
                hasTasks = true;
                let displayName = sessionInfo.first_name ? sessionInfo.first_name.toUpperCase() : phone;
                let avatarHtml = getAvatarHtml(sessionInfo);
                let cardClass = isAdmin ? 'task-card admin-task-card' : 'task-card';
                let ownerLabel = isAdmin ? `<small style="font-size:12px; color:#ff88ff;">📱 ${phone}</small>` : '';

                html += `
                    <div class="${cardClass}" id="task-${task.task_id}">
                        <div class="task-title">
                            ${avatarHtml}
                            <span>${displayName} ${ownerLabel}</span>
                        </div>
                        <div class="task-row"><span class="label">🎯 TARGET</span><span class="value target-val">${task.target}</span></div>
                        <div class="task-row"><span class="label">📄 FILE</span><span class="value file-val">${task.messages_count} MSGS</span></div>
                        <div class="task-row"><span class="label">🏷️ HATER</span><span class="value hater-val">${task.hater || 'NONE'}</span></div>
                        <div class="task-row"><span class="label">⏱️ SPEED</span><span class="value speed-val">${task.speed} SEC</span></div>
                        <div class="task-row"><span class="label">🔚 LAST HATER</span><span class="value last-val">${task.last_hater || 'NONE'}</span></div>
                        <div class="task-row"><span class="label">📶 STATUS</span><span class="value status-val"><span class="status-badge">ACTIVE</span></span></div>
                        <div class="task-row"><span class="label">⏳ UPTIME</span><span class="value uptime-val" data-start="${task.start_time}">${formatUptime(task.start_time)}</span></div>
                        <div class="task-row"><span class="label">⏰ NEXT MSG</span><span class="value next-val" data-lastsend="${task.last_send_time}" data-speed="${task.speed}">${getNextMsgIn(task.last_send_time, task.speed)}</span></div>
                        <div class="btn-group-mini">
                            <button class="update-btn" onclick="openUpdateModal('${phone}', '${task.task_id}', '${task.hater || ''}', ${task.speed}, '${task.last_hater || ''}', '${task.target}')">✏️ UPDATE</button>
                            <button class="delete-btn" onclick="deleteTask('${phone}', '${task.task_id}', 'del_${task.task_id}')" id="del_${task.task_id}">🗑️ DELETE</button>
                        </div>
                    </div>
                    <hr class="task-card-separator">
                `;
            });
        }

        if (!hasTasks) {
            html = `<div class="no-tasks">🚫 NO RUNNING TASKS FOUND</div>`;
        }
        container.innerHTML = html;
    }

    // ==================== TIMER UPDATES (lightweight) ====================
    function updateTimers() {
        document.querySelectorAll('.task-card').forEach(card => {
            const uptimeEl = card.querySelector('.uptime-val');
            if (uptimeEl && uptimeEl.dataset.start) {
                uptimeEl.textContent = formatUptime(parseInt(uptimeEl.dataset.start));
            }
            const nextEl = card.querySelector('.next-val');
            if (nextEl && nextEl.dataset.lastsend && nextEl.dataset.speed) {
                nextEl.textContent = getNextMsgIn(
                    parseInt(nextEl.dataset.lastsend),
                    parseFloat(nextEl.dataset.speed)
                );
            }
        });
    }

    let timerInterval = null;

    function startTimers() {
        if (timerInterval) clearInterval(timerInterval);
        timerInterval = setInterval(updateTimers, 2000);
    }

    // ==================== SYNC FUNCTIONS ====================
    async function syncSystemAccounts() {
        let token = getToken();
        try {
            let res = await fetch('/api/list_sessions?owner=' + encodeURIComponent(token));
            let data = await res.json();
            
            window.sessionData = data.sessions || {};

            let senderSelect = document.getElementById('senderAccountSelect');
            senderSelect.innerHTML = '';
            let count = 0;
            for(let phone in data.sessions) {
                let opt = document.createElement('option');
                opt.value = phone;
                let dispName = data.sessions[phone].first_name ? data.sessions[phone].first_name.toUpperCase() : "VERIFIED";
                opt.innerText = dispName + " (" + phone + ")";
                senderSelect.appendChild(opt);
                count++;
            }
            if(count === 0) senderSelect.innerHTML = '<option value="">-- NO ACTIVE ACCOUNTS --</option>';

            renderTaskCards('sessionsContainer', data, false);
        } catch(e) {
            console.log("Sync error", e);
            document.getElementById('sessionsContainer').innerHTML = '<div class="msg error">ERROR LOADING TASKS</div>';
        }
    }

    async function syncAdminPanel() {
        if (currentRole !== 'admin') return;
        try {
            let res = await fetch('/api/list_all_sessions');
            let data = await res.json();
            let combined = { sessions: {}, tasks: {} };
            for (let owner in data) {
                let ownerData = data[owner];
                for (let phone in ownerData.sessions) {
                    combined.sessions[phone] = ownerData.sessions[phone];
                    if (ownerData.tasks[phone]) {
                        if (!combined.tasks[phone]) combined.tasks[phone] = [];
                        ownerData.tasks[phone].forEach(t => {
                            t.owner = owner;
                            combined.tasks[phone].push(t);
                        });
                    }
                }
            }
            window.sessionData = combined.sessions || {};
            renderTaskCards('adminContainer', combined, true);
        } catch(e) {
            console.log("Admin sync error", e);
            document.getElementById('adminContainer').innerHTML = '<div class="msg error">ERROR LOADING ADMIN DATA</div>';
        }
    }

    function initializeApp() {
        if (currentRole === 'admin' && !document.getElementById('card-admin').classList.contains('hidden-admin')) {
            syncAdminPanel();
        }
        if (document.getElementById('card-4').classList.contains('active')) {
            syncSystemAccounts();
        }
        startTimers();
    }

    window.addEventListener('load', function() {
        if (isLoggedIn) {
            initializeApp();
        }
    });
</script>
</body>
</html>
"""

# ------------------ Flask Routes (using asyncio.run) ------------------
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/14823.jpg')
def serve_requested_banner():
    return send_from_directory('.', '14823.jpg')

@app.route('/cache_images/<path:filename>')
def serve_cached_images(filename):
    return send_from_directory(CACHE_DIR, filename)

@app.route('/api/send_code', methods=['POST'])
def send_code():
    data = request.json
    api_id = data.get('api_id')
    api_hash = data.get('api_hash')
    phone = normalize_phone(data.get('phone'))

    async def _send_code():
        client = TelegramClient(StringSession(), int(api_id), api_hash)
        await client.connect()
        await client.send_code_request(phone)
        return client

    try:
        client = asyncio.run(_send_code())
        temp_clients[phone] = {
            'client': client,
            'api_id': int(api_id),
            'api_hash': api_hash
        }
        return jsonify({"success": True})
    except ApiIdInvalidError:
        return jsonify({"success": False, "message": "INVALID API ID/HASH – GET CORRECT CREDENTIALS FROM MY.TELEGRAM.ORG"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e).upper()})

@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    phone = normalize_phone(data.get('phone'))
    code = data.get('code')
    password = data.get('password', '')
    owner = data.get('owner', phone).strip()

    if phone not in temp_clients:
        return jsonify({"success": False, "message": "SESSION EXPIRED. RESTART THE PROCESS."})

    client_info = temp_clients[phone]
    client = client_info['client']
    api_id = client_info['api_id']
    api_hash = client_info['api_hash']

    async def _verify():
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            if password:
                await client.sign_in(password=password)
            else:
                return {"needs_password": True, "success": False}

        me = await client.get_me()
        first_name = me.first_name if me else "ACTIVE SYSTEM NODE INSTANCE"

        avatar_url_path = ""
        try:
            # Attempt to download profile photo and cache it
            photos = await client.get_profile_photos(me, limit=1)
            if photos:
                photo = photos[0]
                photo_file = await client.download_media(photo, file=os.path.join(CACHE_DIR, f"{phone}_avatar.jpg"))
                if photo_file:
                    avatar_url_path = f"/cache_images/{os.path.basename(photo_file)}"
        except:
            pass

        session_str = client.session.save()
        sessions = load_sessions()
        if owner not in sessions:
            sessions[owner] = {}
        sessions[owner][phone] = {
            "session": session_str,
            "api_id": api_id,
            "api_hash": api_hash,
            "first_name": first_name,
            "avatar_url": avatar_url_path
        }
        save_sessions(sessions)
        return {"success": True, "first_name": first_name}

    try:
        result = asyncio.run(_verify())
        if result.get("needs_password"):
            return jsonify({"needs_password": True, "success": False})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e).upper()})

@app.route('/api/list_sessions')
def list_sessions():
    owner = request.args.get('owner', '').strip()
    sessions = load_sessions()
    owner_data = sessions.get(owner, {})
    tasks = load_tasks()
    owner_tasks = tasks.get(owner, {})

    return jsonify({
        "sessions": owner_data,
        "tasks": owner_tasks
    })

@app.route('/api/list_all_sessions')
def list_all_sessions():
    # Admin only
    return jsonify(load_sessions())

@app.route('/api/get_groups')
def get_groups():
    phone = request.args.get('phone')
    if not phone:
        return jsonify({"success": False, "message": "PHONE REQUIRED"})

    # Try cache
    cached = get_cached_groups(phone)
    if cached:
        return jsonify({"success": True, "groups": cached})

    sessions = load_sessions()
    owner_data = None
    for owner in sessions:
        if phone in sessions[owner]:
            owner_data = sessions[owner][phone]
            break
    if not owner_data:
        return jsonify({"success": False, "message": "ACCOUNT NOT FOUND"})

    client = TelegramClient(StringSession(owner_data['session']),
                            owner_data['api_id'],
                            owner_data['api_hash'])

    async def _fetch_groups():
        await client.connect()
        dialogs = await client.get_dialogs()
        groups = []
        for d in dialogs:
            if d.is_group or d.is_channel:
                group_info = {
                    "id": str(d.id),
                    "name": d.name,
                    "avatar_url": ""
                }
                try:
                    if d.photo:
                        # download avatar
                        photo_file = await client.download_media(d.photo, file=os.path.join(CACHE_DIR, f"{phone}_group_{d.id}.jpg"))
                        if photo_file:
                            group_info["avatar_url"] = f"/cache_images/{os.path.basename(photo_file)}"
                except:
                    pass
                groups.append(group_info)
        return groups

    try:
        groups = asyncio.run(_fetch_groups())
        set_cached_groups(phone, groups)
        return jsonify({"success": True, "groups": groups})
    except Exception as e:
        return jsonify({"success": False, "message": str(e).upper()})

@app.route('/api/start_sending', methods=['POST'])
def start_sending():
    phone = request.form.get('phone')
    target = request.form.get('target')
    hater = request.form.get('hater', '')
    speed = float(request.form.get('speed', 20))
    last_hater = request.form.get('last_hater', '')
    owner = request.form.get('owner', '').strip()
    file = request.files.get('file')

    if not phone or not target:
        return jsonify({"success": False, "message": "PHONE AND TARGET REQUIRED"})

    # Load messages from file
    messages = []
    if file:
        try:
            content = file.read().decode('utf-8')
            messages = [line.strip() for line in content.splitlines() if line.strip()]
        except:
            return jsonify({"success": False, "message": "INVALID FILE"})
    else:
        return jsonify({"success": False, "message": "MESSAGE FILE REQUIRED"})

    sessions = load_sessions()
    owner_data = None
    for own in sessions:
        if phone in sessions[own]:
            owner_data = sessions[own][phone]
            break
    if not owner_data:
        return jsonify({"success": False, "message": "ACCOUNT NOT FOUND"})

    # Save task
    tasks = load_tasks()
    if owner not in tasks:
        tasks[owner] = {}
    if phone not in tasks[owner]:
        tasks[owner][phone] = []

    task_id = f"task_{int(time.time())}"
    task = {
        "task_id": task_id,
        "target": target,
        "hater": hater,
        "speed": speed,
        "last_hater": last_hater,
        "messages": messages,
        "messages_count": len(messages),
        "start_time": int(time.time()),
        "last_send_time": 0,
        "index": 0
    }
    tasks[owner][phone].append(task)
    save_tasks(tasks)

    # Start background thread for sending
    def send_loop():
        client = TelegramClient(StringSession(owner_data['session']),
                                owner_data['api_id'],
                                owner_data['api_hash'])
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(client.connect())

        # Update task reference
        task_ref = None
        while True:
            # Reload tasks to get updated task state
            all_tasks = load_tasks()
            if owner not in all_tasks or phone not in all_tasks[owner]:
                break
            for t in all_tasks[owner][phone]:
                if t['task_id'] == task_id:
                    task_ref = t
                    break
            if not task_ref:
                break

            # Send if time elapsed
            now = int(time.time())
            if now - task_ref['last_send_time'] >= task_ref['speed']:
                # Send next message
                msg_index = task_ref['index']
                if msg_index >= len(task_ref['messages']):
                    # Loop
                    msg_index = 0
                msg = task_ref['messages'][msg_index]
                # Build full message
                full_msg = f"{task_ref['hater']} {msg} {task_ref['last_hater']}".strip()
                try:
                    loop.run_until_complete(client.send_message(int(target), full_msg))
                    # Update last send time and index
                    task_ref['last_send_time'] = now
                    task_ref['index'] = (msg_index + 1) % len(task_ref['messages'])
                    # Save updated tasks
                    updated_tasks = load_tasks()
                    for t in updated_tasks[owner][phone]:
                        if t['task_id'] == task_id:
                            t['last_send_time'] = now
                            t['index'] = task_ref['index']
                            break
                    save_tasks(updated_tasks)
                except FloodWaitError as e:
                    # Wait and retry
                    time.sleep(e.seconds)
                except Exception as e:
                    logging.error(f"Send error: {e}")
                    time.sleep(10)
            else:
                time.sleep(1)

    thread = threading.Thread(target=send_loop, daemon=True)
    thread.start()

    return jsonify({"success": True})

@app.route('/api/delete_task', methods=['GET'])
def delete_task():
    phone = request.args.get('phone')
    task_id = request.args.get('task_id')
    if not phone or not task_id:
        return jsonify({"success": False, "message": "MISSING PARAMETERS"})

    tasks = load_tasks()
    # Find owner
    for owner in tasks:
        if phone in tasks[owner]:
            tasks[owner][phone] = [t for t in tasks[owner][phone] if t['task_id'] != task_id]
            if not tasks[owner][phone]:
                del tasks[owner][phone]
            save_tasks(tasks)
            return jsonify({"success": True})
    return jsonify({"success": False, "message": "TASK NOT FOUND"})

@app.route('/api/update_task', methods=['POST'])
def update_task():
    phone = request.form.get('phone')
    task_id = request.form.get('task_id')
    new_hater = request.form.get('hater', '')
    new_speed = float(request.form.get('speed', 20))
    new_last_hater = request.form.get('last_hater', '')
    new_target = request.form.get('target', '')
    file = request.files.get('file')

    if not phone or not task_id:
        return jsonify({"success": False, "message": "MISSING PARAMETERS"})

    tasks = load_tasks()
    found = False
    for owner in tasks:
        if phone in tasks[owner]:
            for t in tasks[owner][phone]:
                if t['task_id'] == task_id:
                    t['hater'] = new_hater
                    t['speed'] = new_speed
                    t['last_hater'] = new_last_hater
                    if new_target:
                        t['target'] = new_target
                    if file:
                        try:
                            content = file.read().decode('utf-8')
                            new_msgs = [line.strip() for line in content.splitlines() if line.strip()]
                            if new_msgs:
                                t['messages'] = new_msgs
                                t['messages_count'] = len(new_msgs)
                                t['index'] = 0  # reset index
                        except:
                            pass
                    found = True
                    break
            if found:
                break
    if not found:
        return jsonify({"success": False, "message": "TASK NOT FOUND"})

    save_tasks(tasks)
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
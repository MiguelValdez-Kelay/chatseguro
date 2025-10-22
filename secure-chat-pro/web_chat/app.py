from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import os, json, random, string, hashlib

APP_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DB = os.path.join(APP_DIR, "users.json")
CONTACTS_DB = os.path.join(APP_DIR, "contacts.json")  # 🆕 NUEVO ARCHIVO PARA GUARDAR CONTACTOS

app = Flask(__name__)
app.config["SECRET_KEY"] = "secure-chat-bbm-pin"
socketio = SocketIO(app, cors_allowed_origins="*")

# ------------------------- Utilidades -------------------------
def load_json(path):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users():
    if not os.path.exists(USERS_DB):
        with open(USERS_DB, "w", encoding="utf-8") as f:
            json.dump({"users": []}, f)
    with open(USERS_DB, "r", encoding="utf-8") as f:
        return json.load(f)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def generate_pin():
    chars = string.ascii_uppercase + string.digits
    return f"{''.join(random.choice(chars) for _ in range(4))}-{''.join(random.choice(chars) for _ in range(4))}"

def ensure_unique_pin():
    db = load_users()
    pins = {u["pin"] for u in db["users"]}
    pin = generate_pin()
    while pin in pins:
        pin = generate_pin()
    return pin

def now_hhmm(): return datetime.now().strftime("%H:%M")
def room_for(a, b):
    x, y = sorted([a, b])
    return f"room_{x.replace('-', '')}_{y.replace('-', '')}"

# ------------------------- Rutas Web -------------------------
@app.route("/")
def index():
    user = session.get("user")
    if not user:
        return redirect(url_for("login_page"))
    return render_template("index.html", user=user)

@app.route("/login_page")
def login_page():
    return render_template("login.html")

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    db = load_users()
    for u in db["users"]:
        if u["username"].lower() == username.lower() and u["password"] == hash_pw(password):
            session["user"] = {"username": u["username"], "pin": u["pin"]}
            return jsonify({"success": True, "message": f"Bienvenido {username}", "pin": u["pin"]})
    return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"}), 401

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"success": False, "message": "Completa todos los campos."}), 400

    db = load_users()
    if any(u["username"].lower() == username.lower() for u in db["users"]):
        return jsonify({"success": False, "message": "El usuario ya existe."}), 400

    pin = ensure_unique_pin()
    new_user = {"username": username, "password": hash_pw(password), "pin": pin}
    db["users"].append(new_user)
    with open(USERS_DB, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)
    session["user"] = {"username": username, "pin": pin}
    return jsonify({"success": True, "pin": pin})

@app.route("/api/contacts", methods=["GET"])
def get_contacts():
    """Devuelve los contactos guardados del usuario actual"""
    user = session.get("user")
    if not user:
        return jsonify([])
    data = load_json(CONTACTS_DB)
    return jsonify(data.get(user["pin"], []))

# ------------------------- Socket.IO -------------------------
pin_to_sids, sid_to_pin, sid_to_rooms = {}, {}, {}

def add_sid(pin, sid):
    pin_to_sids.setdefault(pin, set()).add(sid)
    sid_to_pin[sid] = pin

def remove_sid(sid):
    pin = sid_to_pin.pop(sid, None)
    if pin:
        pin_to_sids[pin].discard(sid)
        if not pin_to_sids[pin]:
            pin_to_sids.pop(pin)

def add_room_for_sid(sid, room):
    sid_to_rooms.setdefault(sid, set()).add(room)

def remove_all_rooms_for_sid(sid):
    return sid_to_rooms.pop(sid, set())

@socketio.on("register_user")
def register_user(data):
    user = session.get("user")
    if not user:
        emit("system_message", {"text": "No autenticado.", "time": now_hhmm()})
        return
    pin = user["pin"].upper()
    add_sid(pin, request.sid)
    join_room(pin)
    emit("system_message", {"text": f"PIN propio: {pin}.", "time": now_hhmm()})

@socketio.on("connect_to_user")
def connect_to_user(data):
    user = session.get("user")
    if not user:
        emit("system_message", {"text": "No autenticado.", "time": now_hhmm()})
        return
    my_pin = user["pin"].upper()
    target = (data or {}).get("target", "").upper()

    # Guardar contacto automáticamente
    contacts = load_json(CONTACTS_DB)
    contacts.setdefault(my_pin, [])
    if target not in contacts[my_pin]:
        contacts[my_pin].append(target)
        save_json(CONTACTS_DB, contacts)

    rm = room_for(my_pin, target)
    join_room(rm)
    add_room_for_sid(request.sid, rm)
    emit("system_message", {"text": f"Conectado a {target}", "time": now_hhmm()})
    emit("system_message", {"text": f"{my_pin} se unió a la sala {rm}", "time": now_hhmm()}, room=target)

@socketio.on("send_message")
def send_message(data):
    user = session.get("user")
    if not user:
        emit("system_message", {"text": "No autenticado.", "time": now_hhmm()})
        return
    sender_pin = user["pin"].upper()
    sender_name = user["username"]
    receiver = (data.get("receiver") or "").upper()
    message = data.get("message", "").strip()

    if not message:
        return
    rm = room_for(sender_pin, receiver)
    emit("receive_message", {
        "sender": sender_name,
        "receiver": receiver,
        "message": message,
        "time": now_hhmm()
    }, room=rm, include_self=False)

@socketio.on("disconnect")
def on_disconnect():
    pin = sid_to_pin.get(request.sid)
    rooms = remove_all_rooms_for_sid(request.sid)
    remove_sid(request.sid)
    if pin:
        for r in rooms:
            leave_room(r)
            if r.startswith("room_"):
                emit("system_message", {"text": f"{pin} se desconectó.", "time": now_hhmm()}, room=r, include_self=False)

if __name__ == "__main__":
    import eventlet
    import eventlet.wsgi
    port = int(os.environ.get("PORT", 5050))
    socketio.run(app, host="0.0.0.0", port=port)

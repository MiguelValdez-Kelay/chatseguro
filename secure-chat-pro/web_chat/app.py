from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import os, json, random, string, hashlib

APP_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DB = os.path.join(APP_DIR, "users.json")

app = Flask(__name__)
app.config["SECRET_KEY"] = "secure-chat-bbm-pin"
socketio = SocketIO(app, cors_allowed_origins="*")


# ---- Funciones base ----
def load_users():
    if not os.path.exists(USERS_DB):
        with open(USERS_DB, "w", encoding="utf-8") as f:
            json.dump({"users": []}, f)
    with open(USERS_DB, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def generate_pin():
    def block():
        chars = string.ascii_uppercase + string.digits
        return "".join(random.choice(chars) for _ in range(4))
    return f"{block()}-{block()}"

def ensure_unique_pin():
    db = load_users()
    existing = {u["pin"] for u in db.get("users", [])}
    pin = generate_pin()
    while pin in existing:
        pin = generate_pin()
    return pin

def now_hhmm():
    return datetime.now().strftime("%H:%M")

def room_for(a, b):
    x, y = sorted([a, b])
    return f"room_{x.replace('-', '')}_{y.replace('-', '')}"


# ---- Rutas principales ----
@app.route("/")
def index():
    user = session.get("user")
    if not user:
        return redirect(url_for("login_page"))
    return render_template("index.html", user=user)

@app.route("/login_page")
def login_page():
    return render_template("login.html")


# ---- Registro de usuario ----
@app.post("/api/register")
def register():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "Completa todos los campos."}), 400

    db = load_users()

    # Validar que no exista
    for u in db["users"]:
        if u["username"].lower() == username.lower():
            return jsonify({"success": False, "message": "El usuario ya existe."}), 400

    new_pin = ensure_unique_pin()
    new_user = {"username": username, "password": hash_pw(password), "pin": new_pin}
    db["users"].append(new_user)
    save_users(db)

    session["user"] = new_user
    return jsonify({"success": True, "message": "Cuenta creada exitosamente.", "pin": new_pin})


# ---- Login ----
@app.post("/api/login")
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    db = load_users()
    for u in db["users"]:
        if u["username"].lower() == username.lower() and u["password"] == hash_pw(password):
            session["user"] = u
            return jsonify({"success": True, "message": f"Bienvenido {username}", "pin": u["pin"]})

    return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"}), 401


# ---- Logout ----
@app.get("/api/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login_page"))


# ---- WebSocket (mensajería privada) ----
sid_to_pin = {}

@socketio.on("join_with_pin")
def join_with_pin(data):
    user = session.get("user")
    if not user:
        emit("system_message", {"text": "Inicia sesión primero.", "time": now_hhmm()})
        return

    user_pin = user["pin"]
    sid_to_pin[request.sid] = user_pin
    emit("system_message", {"text": f"PIN propio: {user_pin}. Listo para conectar.", "time": now_hhmm()})

@socketio.on("start_private_chat")
def start_private_chat(data):
    user = session.get("user")
    if not user:
        emit("system_message", {"text": "Inicia sesión primero.", "time": now_hhmm()})
        return

    my_pin = user["pin"]
    target_pin = (data or {}).get("target_pin", "").strip().upper()
    db = load_users()
    target_exists = any(u["pin"] == target_pin for u in db["users"])

    if not target_exists:
        emit("system_message", {"text": "El PIN destino no existe.", "time": now_hhmm()})
        return

    rm = room_for(my_pin, target_pin)
    join_room(rm)
    emit("system_message", {"text": f"Conectado a {target_pin}.", "time": now_hhmm()})
    emit("system_message", {"text": f"{my_pin} se unió a la sala.", "time": now_hhmm()}, room=rm, include_self=False)

@socketio.on("send_private_message")
def send_private_message(data):
    user = session.get("user")
    if not user:
        return

    my_pin = user["pin"]
    username = user["username"]
    target_pin = (data or {}).get("target_pin", "").strip().upper()
    text = (data or {}).get("text", "").strip()
    if not text:
        return

    rm = room_for(my_pin, target_pin)
    emit("receive_message", {
        "from_pin": my_pin,
        "username": username,
        "text": text,
        "time": now_hhmm()
    }, room=rm)


@socketio.on("disconnect")
def on_disconnect():
    sid_to_pin.pop(request.sid, None)


# ---- Main ----
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050)

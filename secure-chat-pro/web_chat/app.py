from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import os, json, random, string, hashlib

APP_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DB = os.path.join(APP_DIR, "users.json")

app = Flask(__name__)
# ¡IMPORTANTE!: Usa una clave secreta robusta para producción
app.config["SECRET_KEY"] = "secure-chat-bbm-pin" 

# MUY IMPORTANTE: dejar que Socket.IO gestione la sesión de Flask
socketio = SocketIO(app, cors_allowed_origins="*")

# ------------------------- Utilidades -------------------------
def load_users():
    if not os.path.exists(USERS_DB):
        with open(USERS_DB, "w", encoding="utf-8") as f:
            json.dump({"users": []}, f)
    try:
        with open(USERS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"users": []}

def save_users(data):
    with open(USERS_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hash_pw(pw: str) -> str:
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

def room_for(a: str, b: str) -> str:
    x, y = sorted([a, b])
    # Se eliminan los guiones para el nombre de la sala, como en tu código original
    return f"room_{x.replace('-', '')}_{y.replace('-', '')}"

# ------------------------- Rutas web -------------------------
@app.route("/")
def index():
    user = session.get("user")
    if not user:
        return redirect(url_for("login_page"))
    # Pasamos solo los datos seguros de la sesión al template
    return render_template("index.html", user=user)

@app.route("/login_page")
def login_page():
    return render_template("login.html")

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "Completa todos los campos."}), 400

    # Línea 75 (Corregida la indentación)
    db = load_users() 
    for u in db["users"]:
        if u["username"].lower() == username.lower():
            return jsonify({"success": False, "message": "El usuario ya existe."}), 400

    new_pin = ensure_unique_pin()
    new_user = {"username": username, "password": hash_pw(password), "pin": new_pin}
    db["users"].append(new_user)
    save_users(db)

    # Solo almacena datos seguros en la sesión
    session["user"] = {"username": new_user["username"], "pin": new_user["pin"]}
    return jsonify({"success": True, "message": "Cuenta creada exitosamente.", "pin": new_pin})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    db = load_users()
    for u in db["users"]:
        if u["username"].lower() == username.lower() and u["password"] == hash_pw(password):
            # Solo almacena datos seguros en la sesión
            session["user"] = {"username": u["username"], "pin": u["pin"]}
            # La línea 100 de tu imagen (Línea 102 en mi conteo)
            return jsonify({"success": True, "message": f"Bienvenido {username}", "pin": u["pin"]})
    
    # Línea con el error de indentación reportado (Línea 105 en mi conteo)
    return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"}), 401

@app.route("/api/logout", methods=["GET"])
def logout():
    session.pop("user", None)
    return redirect(url_for("login_page"))

# ------------------------- Socket.IO (privado por PIN) -------------------------
# pin_to_sids mapea PIN a un conjunto de SIDs (sesiones activas)
pin_to_sids = {}
# sid_to_pin mapea SID a PIN (para buscar rápidamente el PIN del desconectado)
sid_to_pin = {}
# sid_to_rooms mapea SID a un conjunto de salas (para dejar las salas al desconectar)
sid_to_rooms = {}

def add_sid(pin: str, sid: str):
    pin_to_sids.setdefault(pin, set()).add(sid)
    sid_to_pin[sid] = pin

def remove_sid(sid: str):
    # Remueve del mapeo de pin_to_sids y sid_to_pin
    pin = sid_to_pin.pop(sid, None)
    if pin and pin in pin_to_sids:
        sids = pin_to_sids[pin]
        sids.discard(sid)
        if not sids:
            pin_to_sids.pop(pin, None)

def add_room_for_sid(sid: str, room: str):
    # Agrega la sala a la que se unió el SID
    sid_to_rooms.setdefault(sid, set()).add(room)

def remove_all_rooms_for_sid(sid: str) -> set:
    # Obtiene y elimina el conjunto de salas de ese SID
    return sid_to_rooms.pop(sid, set())

@socketio.on("register_user")
def register_user(data):
    # Usa el PIN de la sesión web, no del cliente, por seguridad
    user = session.get("user")
    if not user:
        emit("system_message", {"text": "Usuario no autenticado. Por favor, inicia sesión.", "time": now_hhmm()})
        return

    pin = user["pin"].upper()
    
    add_sid(pin, request.sid)
    join_room(pin) # El PIN propio es una sala para mensajes dirigidos a este usuario
    add_room_for_sid(request.sid, pin)
    emit("system_message", {"text": f"PIN propio: {pin}. Listo para conectar.", "time": now_hhmm()})

@socketio.on("connect_to_user")
def connect_to_user(data):
    user = session.get("user")
    if not user:
        emit("system_message", {"text": "Usuario no autenticado.", "time": now_hhmm()})
        return
        
    my_pin = user["pin"].upper()
    target_pin = (data or {}).get("target", "").strip().upper()

    if my_pin == target_pin:
        emit("system_message", {"text": "No puedes iniciar un chat contigo mismo.", "time": now_hhmm()})
        return

    db = load_users()
    if not any(u["pin"] == target_pin for u in db.get("users", [])):
        emit("system_message", {"text": "El PIN destino no existe.", "time": now_hhmm()})
        return

    rm = room_for(my_pin, target_pin)
    
    # 1. Unirse a la sala de chat
    join_room(rm)
    add_room_for_sid(request.sid, rm)
    
    # 2. Informar al usuario actual
    emit("system_message", {"text": f"Conectado a {target_pin}.", "time": now_hhmm()})
    
    # 3. Informar al otro usuario (si está conectado)
    # Emitimos al PIN del otro usuario (su sala personal)
    emit("system_message", {"text": f"{my_pin} se unió a la sala {rm}.", "time": now_hhmm()}, room=target_pin)
    
@socketio.on("send_message")
def send_message(data):
    user = session.get("user")
    if not user:
        emit("system_message", {"text": "Usuario no autenticado.", "time": now_hhmm()})
        return

    if not isinstance(data, dict):
        emit("system_message", {"text": "Datos inválidos.", "time": now_hhmm()})
        return

    sender_pin = user["pin"].upper()
    # nombre desde la sesión (más barato); fallback a PIN si faltara
    sender_name = user.get("username") or sender_pin

    receiver = (data.get("receiver") or "").strip().upper()
    message = (data.get("message") or "").strip()

    if not receiver or not message:
        emit("system_message", {"text": "Faltan datos para enviar el mensaje.", "time": now_hhmm()})
        return

    rm = room_for(sender_pin, receiver)

    # Verificamos si el usuario está en la sala antes de enviar
    if rm not in sid_to_rooms.get(request.sid, set()):
        emit("system_message", {"text": "Error: Debes conectar con el PIN antes de enviar mensajes.", "time": now_hhmm()})
        return

    # Fallback adicional por si la sesión no trajera username (opcional, pero seguro)
    if sender_name == sender_pin:
        db = load_users()
        u = next((u for u in db.get("users", []) if u.get("pin", "").upper() == sender_pin), None)
        if u and u.get("username"):
            sender_name = u["username"]

    emit("receive_message", {
        "sender": sender_name,   # ← ahora va el NOMBRE, no el PIN
        "receiver": receiver,
        "message": message,
        "time": now_hhmm()
    }, room=rm, include_self=False)



@socketio.on("disconnect")
def on_disconnect():
    # 1. Obtener el PIN y las salas antes de limpiar
    pin = sid_to_pin.get(request.sid)
    rooms_to_leave = remove_all_rooms_for_sid(request.sid)

    # 2. Sacar el SID del mapeo pin_to_sids y sid_to_pin
    remove_sid(request.sid)

    # 3. Abandonar explícitamente todas las salas de chat
    if pin:
        for room in rooms_to_leave:
            leave_room(room)
            
            # Notificar al otro participante si es una sala de chat
            # Esto corrige la lógica en la línea 214 de tu contexto
            if room.startswith("room_"): 
                emit("system_message", {"text": f"{pin} se desconectó de la sala.", "time": now_hhmm()}, 
                      room=room, include_self=False)

if __name__ == "__main__":
    try:
        socketio.run(app, host="0.0.0.0", port=5050, debug=True)
    except OSError:
        print("Puerto 5050 ocupado, intentando con el 5055...")
        socketio.run(app, host="0.0.0.0", port=5055, debug=True)
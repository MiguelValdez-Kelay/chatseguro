
const socket = io();
const myPinEl = document.getElementById("my-pin");
const partnerPinInput = document.getElementById("partner-pin");
const btnConnect = document.getElementById("btn-connect");
const btnClear = document.getElementById("btn-clear");
const messages = document.getElementById("messages");
const form = document.getElementById("form");
const input = document.getElementById("input");

let MY_PIN = "";
let CURRENT_TARGET = ""; // PIN del contacto activo

function addBubble(text, kind = "system") {
  const wrap = document.createElement("div");
  wrap.className = "bubble " + (kind === "self" ? "bubble--self" : kind === "user" ? "bubble--user" : "bubble--system");
  const meta = document.createElement("div");
  meta.className = "bubble__meta";
  const hhmm = new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
  meta.textContent = kind === "system" ? hhmm : `${hhmm}`;
  const body = document.createElement("div");
  body.className = "bubble__text";
  body.textContent = text;
  wrap.appendChild(meta);
  wrap.appendChild(body);
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
}

async function registerOrReusePin() {
  // Intentar reusar PIN local si existe
  const stored = (localStorage.getItem("bbm_pin") || "").toUpperCase();
  const res = await fetch("/api/register", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ pin: stored })
  });
  const data = await res.json();
  MY_PIN = data.pin;
  localStorage.setItem("bbm_pin", MY_PIN);
  myPinEl.textContent = MY_PIN;
  socket.emit("join_with_pin", { pin: MY_PIN });
  if (data.reused) {
    addBubble(`PIN reusado: ${MY_PIN}`, "system");
  } else {
    addBubble(`PIN asignado: ${MY_PIN}`, "system");
  }
}

btnConnect.addEventListener("click", async () => {
  const pin = (partnerPinInput.value || "").trim().toUpperCase();
  if (!pin) return;
  // Validar en servidor que exista
  const r = await fetch(`/api/pin_exists?pin=${encodeURIComponent(pin)}`);
  const j = await r.json();
  if (!j.exists) {
    addBubble(`El PIN ${pin} no existe. Asegúrate de que tu contacto haya abierto la app.`, "system");
    return;
  }
  CURRENT_TARGET = pin;
  socket.emit("start_private_chat", { target_pin: CURRENT_TARGET });
  addBubble(`Conectado a ${CURRENT_TARGET}. Los mensajes ahora son privados.`, "system");
});

btnClear.addEventListener("click", () => {
  messages.innerHTML = "";
});

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = (input.value || "").trim();
  if (!text) return;
  if (!CURRENT_TARGET) {
    addBubble("Primero conectate al PIN de tu contacto.", "system");
    return;
  }
  socket.emit("send_private_message", { target_pin: CURRENT_TARGET, text });
  addBubble(text, "self");
  input.value = "";
  input.style.height = "auto";
});

// Autosize simple del textarea (enter envía, shift+enter = salto)
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
});
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.dispatchEvent(new Event("submit"));
  }
});

// Mensajes entrantes
socket.on("receive_message", (data) => {
  const { from_pin, to_pin, text } = data;
  // Mostrar como "user" si viene del otro (o de mí desde otra pestaña)
  const kind = (from_pin === MY_PIN) ? "self" : "user";
  addBubble(`${from_pin}: ${text}`, kind);
});

// Mensajes de sistema
socket.on("system_message", (data) => {
  addBubble(data.text || "", "system");
});

// Arranque
registerOrReusePin();

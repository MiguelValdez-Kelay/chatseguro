document.addEventListener("DOMContentLoaded", () => {
  const socket = io();

  const msgInput = document.getElementById("msg");
  const chatBox = document.getElementById("chat");
  const sendBtn = document.getElementById("send");
  const connectBtn = document.getElementById("connect");
  const clearBtn = document.getElementById("clear");
  const contactPin = document.getElementById("contactPin");

  const username = document.getElementById("userName").textContent.trim();
  const myPin = document.getElementById("userPin").textContent.trim();

  let connectedPin = null;

  // Mostrar mensajes en pantalla
  function appendMessage(text, align = "left") {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message");
    msgDiv.style.textAlign = align;
    msgDiv.textContent = text;
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  // Enviar mensaje
  function sendMessage() {
    const msg = msgInput.value.trim();
    if (!msg || !connectedPin) return;

    socket.emit("send_message", {
      sender: myPin,
      receiver: connectedPin,
      message: msg,
    });

    appendMessage(`Tú: ${msg}`, "right");
    msgInput.value = "";
  }

  // Permitir enviar con Enter
  msgInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  });

  // Botón enviar
  sendBtn.addEventListener("click", sendMessage);

  // Conectar con otro usuario usando su PIN
  connectBtn.addEventListener("click", () => {
    const pin = contactPin.value.trim().toUpperCase();
    if (!pin) return;

    connectedPin = pin;
    socket.emit("connect_to_user", { pin: myPin, target: pin });
    appendMessage(`Conectado a ${pin}.`, "center");
  });

  // Limpiar chat
  clearBtn.addEventListener("click", () => {
    chatBox.innerHTML = "";
  });

  // Recibir mensajes
  socket.on("receive_message", (data) => {
    appendMessage(`${data.sender}: ${data.message}`, "left");
  });

  // Registrar el usuario cuando se conecta
  socket.emit("register_user", { pin: myPin });
  appendMessage(`PIN propio: ${myPin}. Listo para conectar.`, "center");
});

// 🔹 Cargar contactos guardados al iniciar
async function loadContacts() {
  const res = await fetch("/api/contacts");
  const list = await res.json();
  const ul = document.getElementById("contact_list");
  ul.innerHTML = "";
  list.forEach(pin => {
    const li = document.createElement("li");
    li.textContent = pin;
    li.style.cursor = "pointer";
    li.style.margin = "6px 0";
    li.onclick = () => {
      currentTarget = pin;
      socket.emit("connect_to_user", { target: pin });
      addMessage(`Conectado a ${pin}`, "system");
    };
    ul.appendChild(li);
  });
}
loadContacts();


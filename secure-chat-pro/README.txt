
# Secure Chat Pro

Proyecto completo que muestra la evolución desde **sockets en consola** hasta **chat web moderno** con Flask‑SocketIO.
Incluye compatibilidad para clientes web y de consola conectados al mismo servidor.

## Carpetas
- `base_console/`: versiones step1 y step2 del chat por consola (sockets puros).
- `web_chat/`: chat web moderno (WhatsApp dark) + cliente de consola compatible.

## Cómo correr el chat web
```bash
cd web_chat
python -m pip install -r requirements.txt
python app.py
```
Abrí `http://localhost:5050`.

Para un cliente de consola compatible con el chat web:
```bash
python python_client.py
```

## Conexión desde otra red
Usá ngrok:
```bash
ngrok http 5050
```
Compartí la URL https://xxxx.ngrok.io

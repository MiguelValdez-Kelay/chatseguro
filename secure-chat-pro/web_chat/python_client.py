
import socketio

sio = socketio.Client()

@sio.on('connect')
def on_connect():
    print("✅ Conectado al chat")

@sio.on('receive_message')
def on_receive(data):
    print(f"\n{data['username']}: {data['text']}")

@sio.on('system_message')
def on_system(data):
    print(f"\n💬 {data['text']}")

def main():
    server = input("Servidor (default http://localhost:5050): ").strip() or "http://localhost:5050"
    name = input("Tu nombre: ").strip() or "Anónimo"
    sio.connect(server)
    sio.emit('join', {'username': name})
    print("Escribí mensajes y presioná Enter. Ctrl+C para salir.")
    try:
        while True:
            msg = input()
            if msg.strip():
                sio.emit('send_message', {'text': msg})
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()

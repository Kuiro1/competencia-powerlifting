import webbrowser
import time
import threading
import sys
import os

# Cambiar al directorio del ejecutable
if getattr(sys, 'frozen', False):
    os.chdir(sys._MEIPASS)

def abrir_navegador():
    """Espera 3 segundos y abre el navegador"""
    time.sleep(3)
    webbrowser.open('http://127.0.0.1:5000/')

# Iniciar el navegador en un hilo separado
threading.Thread(target=abrir_navegador, daemon=True).start()

# Importar y ejecutar la app
import app

if __name__ == '__main__':
    app.app.run(debug=False, host='127.0.0.1', port=5000)

"""Startet Kataster lokal. Nur localhost - die Daten bleiben auf dem Rechner."""
from app import erzeuge_app, PORT

if __name__ == "__main__":
    erzeuge_app().run(host="127.0.0.1", port=PORT, debug=True)

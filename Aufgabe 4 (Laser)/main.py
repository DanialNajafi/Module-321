import math
import time
import requests
import webbrowser
import paramiko

# ==========================================
# KONFIGURATION & KOORDINATEN
# ==========================================
LASER_URL = "http://192.168.101.60:2018"

# Pass hier die IP deines eigenen Servers/Laptops im Schulnetz an!
MEINE_IP = "192.168.101.60" 

ARAKROCK = {"x": -18236, "y": -11783}
VESTA_STATION = {"x": 7000, "y": 7000}

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

client.connect(
    hostname="192.168.101.60",
    username="ship",
    password="ship",
)

# ==========================================
# OAUTH2 & LASER API CALLS
# ==========================================
def configure_oauth():
    print("[OAuth2] Konfiguriere OAuth-Endpoints auf dem Laser...")
    res = requests.post(
        f"{LASER_URL}/configure_oauth",
        json={
            "client_secret": "schiff_geheimnis",
            "authorize_url": f"http://{MEINE_IP}:2019/authorize",
            "token_url": f"http://{MEINE_IP}:2019/token",
        }
    )
    res.raise_for_status()
    print("[OAuth2] Erfolgreich konfiguriert:", res.json())

def login():
    login_url = f"{LASER_URL}/login"
    print(f"[OAuth2] Öffne Login im Browser: {login_url}")
    webbrowser.open(login_url)
    input("\n=> Klicke im Browser auf 'Freischalten & Anmelden' und drücke danach hier ENTER...")

def set_angle(angle):
    res = requests.put(f"{LASER_URL}/angle", json={"angle": angle})
    return res.json()

def activate_laser():
    res = requests.post(f"{LASER_URL}/activate")
    return res.json()

def deactivate_laser():
    res = requests.post(f"{LASER_URL}/deactivate")
    return res.json()

def get_laser_state():
    res = requests.get(f"{LASER_URL}/state")
    return res.json()

# ==========================================
# MINING LOGIK
# ==========================================
def find_mining_angle():
    print("[Laser] Suche passenden Abbau-Winkel...")
    activate_laser()
    
    for angle in range(0, 360, 5):
        set_angle(angle)
        time.sleep(0.3)
        state = get_laser_state()
        
        if state.get("is_mining"):
            print(f"[Laser] Winkel gefunden: {angle}°")
            return angle
            
    print("[Laser] Kein gültiger Winkel gefunden!")
    return None

def mine_resources():
    angle = find_mining_angle()
    if angle is None:
        return
        
    print("[Laser] Baue Stein ab...")
    while True:
        state = get_laser_state()
        print("Laser Status:", state)
        
        # Abbau pausieren/prüfen
        if not state.get("is_active"):
            activate_laser()
            
        time.sleep(2)
        
        # HINWEIS: Hier prüfst du deinen Laderaum. 
        # Sobald 12 Stein abgebaut sind -> break
        # Beispiel: if laderaum_voll: break
        
    deactivate_laser()
    print("[Laser] Abbau beendet. Laser deaktiviert.")

def go_to_station(xPosition, yPosition):
    stdin, stdout, stderr = client.exec_command(f"curl -XPOST http://192.168.101.60:2009/set_target --data '{{\"target\": {{\"x\": {xPosition}, \"y\": {yPosition}}}}}' {{\"kind\": \"success\"}}")
    print(stdout.read().decode())

# ==========================================
# HAUPTABLAUF
# ==========================================
def main():
    # 1. OAuth2 Prozess durchführen
    configure_oauth()
    login()

    
    # 2. Prüfen ob Laser aktivierbar ist
    print("Laser-Status:", get_laser_state())
    
    # 3. Zu Arakrock fliegen & Stein abbauen
    print(f"Fliege zu Arakrock {ARAKROCK}...")
    go_to_station(ARAKROCK["x"], ARAKROCK["y"])
    # -> hier deine Schiffs-Flugfunktion aufrufen
    
    mine_resources()
    
    # 4. Zu Vesta Station fliegen & Andocken
    print(f"Fliege zu Vesta Station {VESTA_STATION}...")
    go_to_station(VESTA_STATION["x"], VESTA_STATION["y"])
    # -> hier deine Schiffs-Flugfunktion aufrufen

if __name__ == "__main__":
    main()
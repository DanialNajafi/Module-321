import json
import math
import shlex
import time
import requests
import webbrowser
import paramiko

# ==========================================
# KONFIGURATION & KOORDINATEN
# ==========================================
LASER_URL = "http://192.168.101.61:2018"
SHIP_URL = "http://192.168.101.61:2009"
NAVIGATION_URL = "http://192.168.101.61:2010"
COMMUNICATION_URL = "http://192.168.101.61:2011"
CARGO_HOLD_URL = "http://192.168.101.61:2012"

# Pass hier die IP deines eigenen Servers/Laptops im Schulnetz an!
MEINE_IP = "192.168.101.61"

ARAKROCK = {"x": -18236, "y": -11783}
MINING_STANDOFF_DISTANCE = 200
ARAKROCK_MINING_POSITION = {
    "x": ARAKROCK["x"] - MINING_STANDOFF_DISTANCE,
    "y": ARAKROCK["y"],
}
VESTA_STATION = {"x": 7000, "y": 7000}
TARGET_STONE = 14
ARRIVAL_TOLERANCE = 50
POLL_INTERVAL = 2

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

client.connect(
    hostname="192.168.101.61",
    username="ship",
    password="ship",
)


# ==========================================
# OAUTH2 & LASER API CALLS
# ==========================================
def check_laser_response(response):
    response.raise_for_status()
    data = response.json()
    if data.get("kind") != "success":
        raise RuntimeError(f"Laser-API-Aufruf fehlgeschlagen: {data}")
    return data


def configure_oauth():
    print("[OAuth2] Konfiguriere OAuth-Endpoints auf dem Laser...")
    response = requests.post(
        f"{LASER_URL}/configure_oauth",
        json={
            "client_secret": "schiff_geheimnis",
            "authorize_url": f"http://{MEINE_IP}:2019/authorize",
            "token_url": f"http://{MEINE_IP}:2019/token",
        },
    )
    print("[OAuth2] Erfolgreich konfiguriert:", check_laser_response(response))


def login():
    login_url = f"{LASER_URL}/login"
    print(f"[OAuth2] Öffne Login im Browser: {login_url}")
    webbrowser.open(login_url)
    input(
        "\n=> Klicke im Browser auf 'Freischalten & Anmelden' und drücke danach hier ENTER..."
    )


def set_angle(angle):
    response = requests.put(f"{LASER_URL}/angle", json={"angle": angle})
    return check_laser_response(response)


def activate_laser():
    response = requests.post(f"{LASER_URL}/activate")
    return check_laser_response(response)


def deactivate_laser():
    response = requests.post(f"{LASER_URL}/deactivate")
    return check_laser_response(response)


def get_laser_state():
    response = requests.get(f"{LASER_URL}/state")
    return check_laser_response(response)


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


def remote_api_request(method, url, payload=None):
    command = f"curl -fsS -X {method}"
    if payload is not None:
        command += " -H 'Content-Type: application/json' --data-binary " + shlex.quote(
            json.dumps(payload)
        )
    command += f" {shlex.quote(url)}"

    _, stdout, stderr = client.exec_command(command)
    response = stdout.read().decode()
    error = stderr.read().decode().strip()
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        raise RuntimeError(f"API-Aufruf fehlgeschlagen: {error or response}")

    try:
        data = json.loads(response)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ungueltige API-Antwort von {url}: {response}") from exc

    if data.get("kind") != "success":
        raise RuntimeError(f"API-Aufruf fehlgeschlagen: {data}")
    return data


def get_stone_count():
    data = remote_api_request("GET", f"{CARGO_HOLD_URL}/hold")
    hold = data.get("hold")
    resources = hold.get("resources") if isinstance(hold, dict) else None
    if not isinstance(resources, dict):
        raise RuntimeError(f"Ungueltiger Laderaum-Status: {data}")

    count = resources.get("STONE", 0)
    if isinstance(count, bool) or not isinstance(count, (int, float)):
        raise RuntimeError(f"Ungueltige Steinmenge im Laderaum: {count}")
    return count


def wait_until_at_coordinates(target):
    while True:
        data = remote_api_request("GET", f"{NAVIGATION_URL}/pos")
        position = data.get("pos")
        if not isinstance(position, dict):
            raise RuntimeError(f"Ungueltiger Navigations-Status: {data}")

        try:
            distance = math.hypot(
                float(position["x"]) - target["x"],
                float(position["y"]) - target["y"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Ungueltige Schiffsposition: {position}") from exc

        print(f"Entfernung zum Ziel: {distance:.1f}")
        if distance <= ARRIVAL_TOLERANCE:
            return
        time.sleep(POLL_INTERVAL)


def wait_until_at_station(station_name):
    while True:
        data = remote_api_request("GET", f"{COMMUNICATION_URL}/stations_in_reach")
        stations = data.get("stations")
        if not isinstance(stations, dict):
            raise RuntimeError(f"Ungueltiger Stations-Status: {data}")
        if station_name in stations:
            print(f"Bei {station_name} angekommen.")
            return

        print(f"... unterwegs zu {station_name} ...")
        time.sleep(POLL_INTERVAL)


def mine_resources():
    stone_count = get_stone_count()
    if stone_count >= TARGET_STONE:
        print(f"[Laser] Laderaum hat bereits {stone_count} Stein.")
        deactivate_laser()
        return

    try:
        angle = find_mining_angle()
        if angle is None:
            raise RuntimeError("Kein gueltiger Abbau-Winkel gefunden.")

        print(f"[Laser] Baue Stein ab ({stone_count}/{TARGET_STONE})...")
        while stone_count < TARGET_STONE:
            state = get_laser_state()
            print(f"Laser-Status: {state}; Stein: {stone_count}/{TARGET_STONE}")

            if not state.get("is_active"):
                activate_laser()
                set_angle(angle)
            elif not state.get("is_mining") and not state.get("is_cooling_down"):
                angle = find_mining_angle()
                if angle is None:
                    raise RuntimeError("Der Laser findet keinen Abbau-Winkel mehr.")

            time.sleep(POLL_INTERVAL)
            stone_count = get_stone_count()

        print(f"[Laser] Ziel erreicht: {stone_count} Stein im Laderaum.")
    finally:
        deactivate_laser()
        print("[Laser] Abbau beendet. Laser deaktiviert.")


def go_to_station(xPosition, yPosition):
    data = remote_api_request(
        "POST",
        f"{SHIP_URL}/set_target",
        {"target": {"x": xPosition, "y": yPosition}},
    )
    print("Flugziel gesetzt:", data)


# ==========================================
# HAUPTABLAUF
# ==========================================
def main():
    try:
        # 1. OAuth2 Prozess durchführen
        configure_oauth()
        login()

        # 2. Prüfen ob Laser aktivierbar ist
        print("Laser-Status:", get_laser_state())

        # 3. Neben Arakrock in Laserreichweite positionieren und 14 Stein abbauen
        print(f"Fliege zum Abbaupunkt neben Arakrock {ARAKROCK_MINING_POSITION}...")
        go_to_station(
            ARAKROCK_MINING_POSITION["x"],
            ARAKROCK_MINING_POSITION["y"],
        )
        wait_until_at_coordinates(ARAKROCK_MINING_POSITION)
        mine_resources()

        # 4. Zu Vesta Station fliegen und Andocken abwarten
        print(f"Fliege zu Vesta Station {VESTA_STATION}...")
        go_to_station(VESTA_STATION["x"], VESTA_STATION["y"])
        wait_until_at_station("Vesta Station")
    finally:
        client.close()


if __name__ == "__main__":
    main()

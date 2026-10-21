"""Aufgabe 5 (Analyzer Alpha): Sensordaten per gRPC bereitstellen und beim Uran Stone bleiben.

Was das Skript macht (alles parallel):
  1. gRPC-Server auf Port 2102: Der Analyzer Alpha holt dort die Vakuumenergie-Sensordaten ab
     (service SensorVoidEnergyServer, rpc read_sensor_data, siehe api.proto)
  2. Messen: laufend eine Messung beim Sensor (:2037) ausloesen, Resultat abholen und
     die Messung danach wieder LOESCHEN (spart Speicher, Data Management)
  3. Energie: Den aktiven Energy-Node (:2032 / :2033) finden und dem Sensor und dem Analyzer
     Strom geben. Weil Aktiv-Passiv: bei einem Wechsel des aktiven Nodes neu setzen
  4. Fliegen: zum Uran Stone (-2100/3600) und dort bleiben

Starten (auf der Schiffs-VM, damit der Analyzer den gRPC-Server erreicht):
  Dylan:   python3 analyzer.py --ship 192.168.101.61
  Danial:  python3 analyzer.py --ship 192.168.101.60
"""
import argparse
import json
import threading
import time
from concurrent import futures

import grpc
import requests

URAN_STONE = {"x": -2100, "y": 3600}

GRPC_PORT = 2102
NAV_PORT = 2009
SENSOR_PORT = 2037
ENERGY_PORTS = [2032, 2033]

SERVICE_NAME = "api.unsafe.sensor_void_energy.SensorVoidEnergyServer"

# Teile der Namen, an denen wir die Verbraucher in /limits erkennen
POWER_KEYWORDS = ["sensor", "void", "analyzer"]
# Falls /limits diese Verbraucher nicht kennt, werden diese Namen verwendet (per --limit aenderbar)
FALLBACK_LIMITS = {"sensor_void_energy": 1.0, "analyzer_alpha": 1.0}

latest = {"hexdata": None, "time": 0.0}
have_data = threading.Event()
stats = {"grpc_calls": 0, "measurements": 0}


def log(text):
    print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)


# ==========================================
# gRPC SERVER
# ==========================================
# Statt mit protoc Code zu generieren, wird die einfache Nachricht direkt kodiert:
# SensorData { string hexdata = 1; }  ->  Feld 1, Typ "length-delimited" = Byte 0x0A, Laenge, Text
def encode_varint(n):
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def encode_sensor_data(hexdata):
    data = (hexdata or "").encode()
    if not data:
        return b""  # leerer String = leere Nachricht (proto3 Standardwert)
    return b"\x0a" + encode_varint(len(data)) + data


def read_sensor_data(request, context):
    # Kurz auf die erste Messung warten, falls der Analyzer schon beim Start fragt
    if not have_data.wait(timeout=30):
        context.abort(grpc.StatusCode.UNAVAILABLE, "noch keine Sensordaten")
    stats["grpc_calls"] += 1
    if stats["grpc_calls"] == 1:
        log(f"[gRPC] Analyzer holt die ersten Sensordaten ab: {latest['hexdata']}")
    return latest["hexdata"]


def start_grpc_server(port):
    handler = grpc.method_handlers_generic_handler(SERVICE_NAME, {
        "read_sensor_data": grpc.unary_unary_rpc_method_handler(
            read_sensor_data,
            request_deserializer=lambda raw: raw,       # Void hat keine Felder -> Bytes einfach ignorieren
            response_serializer=encode_sensor_data,
        ),
    })
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    server.add_generic_rpc_handlers((handler,))
    server.add_insecure_port(f"0.0.0.0:{port}")   # "unverschluesselt und einfach"
    server.start()
    log(f"[gRPC] Server laeuft auf Port {port} ({SERVICE_NAME}/read_sensor_data)")
    return server


# ==========================================
# VAKUUMENERGIE-SENSOR
# ==========================================
class Sensor:
    def __init__(self, ip):
        self.base = f"http://{ip}:{SENSOR_PORT}"

    def measure(self, request_id, timeout=60):
        """Messung ausloesen, warten bis sie fertig ist, Resultat zurueckgeben und Messung loeschen."""
        # wie im curl-Beispiel: JSON als Body
        res = requests.post(f"{self.base}/trigger_measurement", data=json.dumps({"request_id": request_id}), timeout=10)
        if res.status_code >= 300:
            raise RuntimeError(f"trigger_measurement: {res.status_code} {res.text.strip()}")
        try:
            deadline = time.time() + timeout
            while time.time() < deadline:
                data = requests.get(f"{self.base}/measurements/{request_id}", timeout=10).json()
                if data.get("state") == "measured":
                    return data["result"]
                time.sleep(0.5)
            raise RuntimeError(f"Messung {request_id} nicht fertig nach {timeout} s")
        finally:
            # Immer loeschen, auch bei Fehlern -> kein Speicher bleibt belegt
            requests.delete(f"{self.base}/measurements/{request_id}", timeout=10)


def measure_forever(sensor, interval):
    counter = 0
    while True:
        counter += 1
        request_id = f"analyzer_{int(time.time())}_{counter:05d}"
        try:
            result = sensor.measure(request_id)
            latest["hexdata"], latest["time"] = result, time.time()
            stats["measurements"] += 1
            if not have_data.is_set():
                log(f"[Sensor] erste Messung: {result}")
                have_data.set()
        except Exception as e:
            log(f"[Sensor] Fehler bei {request_id}: {e}")
        time.sleep(interval)

# ==========================================
# ENERGY-MANAGEMENT (Aktiv-Passiv mit 2 Nodes)
# ==========================================
class Energy:
    def __init__(self, ip):
        self.nodes = [f"http://{ip}:{port}" for port in ENERGY_PORTS]

    def active_node(self):
        """Nur der aktive Node darf beschrieben werden."""
        for node in self.nodes:
            try:
                if requests.get(f"{node}/status", timeout=5).json().get("role") == "active":
                    return node
            except (requests.RequestException, ValueError):
                pass  # Node nicht erreichbar -> den anderen probieren
        raise RuntimeError("kein aktiver Energy-Node gefunden")

    def limits(self, node):
        return requests.get(f"{node}/limits", timeout=5).json()

    def set_limits(self, node, limits):
        res = requests.put(f"{node}/limits", data=json.dumps(limits), timeout=5).json()
        if res.get("kind") != "success":
            raise RuntimeError(f"PUT /limits abgelehnt: {res}")


def wanted_limits(current, overrides):
    """Sensor- und Analyzer-Verbraucher in den aktuellen Limits finden und auf 1.0 setzen."""
    wanted = {k: 1.0 for k in current if any(word in k.lower() for word in POWER_KEYWORDS)}
    if not wanted:
        wanted = dict(FALLBACK_LIMITS)
    wanted.update(overrides)
    return wanted


def keep_power(energy, overrides, interval):
    last_node = None
    while True:
        try:
            node = energy.active_node()
            if node != last_node:
                log(f"[Energie] aktiver Node: {node}")
                last_node = node
            current = energy.limits(node)
            wanted = wanted_limits(current, overrides)
            missing = {k: v for k, v in wanted.items() if current.get(k, 0) < v}
            if missing:
                log(f"[Energie] setze Limits {missing} (alle Verbraucher: {list(current)})")
                energy.set_limits(node, {**current, **missing})
        except Exception as e:
            log(f"[Energie] Fehler: {e}")
        time.sleep(interval)


# ==========================================
# NAVIGATION
# ==========================================
def set_target(ip, pos):
    res = requests.post(f"http://{ip}:{NAV_PORT}/set_target", data=json.dumps({"target": pos}), timeout=10)
    log(f"[Nav] Ziel {pos}: {res.text.strip()}")


def stay_near_uran(ip, offset, interval):
    """Neben dem Uran Stone parken (nicht genau darauf) und das Ziel regelmaessig neu setzen,
    damit das Schiff dort bleibt."""
    target = {"x": URAN_STONE["x"] + offset, "y": URAN_STONE["y"]}
    while True:
        try:
            set_target(ip, target)
        except requests.RequestException as e:
            log(f"[Nav] Fehler: {e}")
        log(f"[Status] Messungen: {stats['measurements']}, gRPC-Aufrufe vom Analyzer: {stats['grpc_calls']}, "
            f"letzte Daten: {latest['hexdata']}")
        time.sleep(interval)


# ==========================================
# HAUPTABLAUF
# ==========================================
def parse_limit(text):
    key, value = text.split("=")
    return key, float(value)


def main():
    parser = argparse.ArgumentParser(description="Analyzer Alpha: Sensordaten per gRPC bereitstellen")
    parser.add_argument("--ship", required=True, help="IP des eigenen Schiffs, z.B. 192.168.101.61")
    parser.add_argument("--grpc-port", type=int, default=GRPC_PORT)
    parser.add_argument("--offset", type=int, default=50, help="so weit rechts (+x) neben dem Uran Stone parken")
    parser.add_argument("--sensor-interval", type=float, default=2.0, help="Sekunden zwischen zwei Messungen")
    parser.add_argument("--energy-interval", type=float, default=10.0, help="Sekunden zwischen Energie-Checks")
    parser.add_argument("--nav-interval", type=float, default=30.0, help="Sekunden zwischen Kurs-Updates")
    parser.add_argument("--limit", action="append", type=parse_limit, default=[],
                        help="Limit von Hand setzen, z.B. --limit sensor_void_energy=1.0 (mehrfach moeglich)")
    parser.add_argument("--no-flight", action="store_true", help="nicht fliegen (schon beim Uran Stone)")
    args = parser.parse_args()

    server = start_grpc_server(args.grpc_port)
    threading.Thread(target=keep_power, args=(Energy(args.ship), dict(args.limit), args.energy_interval),
                     daemon=True).start()
    threading.Thread(target=measure_forever, args=(Sensor(args.ship), args.sensor_interval), daemon=True).start()

    try:
        if args.no_flight:
            while True:
                time.sleep(args.nav_interval)
                log(f"[Status] Messungen: {stats['measurements']}, gRPC-Aufrufe: {stats['grpc_calls']}")
        else:
            stay_near_uran(args.ship, args.offset, args.nav_interval)
    except KeyboardInterrupt:

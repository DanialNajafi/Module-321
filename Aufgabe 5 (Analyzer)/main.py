# Aufgabe 5 - Analyzer Alpha
# 1. Energie fuer Analyzer + Sensor einschalten
# 2. GENAU zum Uran Stone (-2100/3600) fliegen und dort bleiben
# 3. gRPC-Server (wie grpc_analyzer.py vom Kollegen): der Analyzer Alpha holt
#    bei grpc://192.168.101.61:2102 die Vakuumenergie-Sensordaten ab
# Starten auf der Schiffs-VM: python3 main.py
import json
import math
import subprocess
import sys
import tempfile
import time
import uuid
import requests
import grpc
from concurrent import futures
from grpc_tools import protoc

# api_pb2 / api_pb2_grpc aus api.proto erzeugen (temporaer, keine Extra-Files)
sys.dont_write_bytecode = True
tmp = tempfile.mkdtemp()
protoc.main(["", "-I.", f"--python_out={tmp}", f"--grpc_python_out={tmp}", "api.proto"])
sys.path.insert(0, tmp)
import api_pb2
import api_pb2_grpc

SHIP = "http://192.168.101.61"
SENSOR_BASE_URL = f"{SHIP}:2037"
URAN_STONE = {"x": -2100, "y": 3600}


# ---------- Energie (Aktiv-Passiv: nur der aktive Node darf schreiben) ----------
def set_energy():
  try:
    for port in (2032, 2033):
        status = requests.get(f"{SHIP}:{port}/status").json()
        if status.get("role") == "active":
            limits = requests.get(f"{SHIP}:{port}/limits").json()
            limits.update({"analyzer_alpha": 1.0, "sensor_void_energy": 1.0})
            print(f"Energie (Node {port}):", requests.put(f"{SHIP}:{port}/limits", json=limits).text)
            return
    print("!! Kein aktiver Energy-Management-Node gefunden")
  except Exception as e:
    print("!! Energie konnte nicht gesetzt werden:", e)


# ---------- Navigation ----------
def set_target():
    # genau derselbe curl-Befehl, der von Hand funktioniert
    answer = subprocess.run(
        ["curl", "-s", "-XPOST", f"{SHIP}:2009/set_target", "--data", json.dumps({"target": URAN_STONE})],
        capture_output=True, text=True,
    )
    print("Flugziel gesetzt:", answer.stdout, answer.stderr)


def wait_until_at_uran_stone():
    while True:
        pos = requests.get(f"{SHIP}:2010/pos").json()["pos"]
        dist = math.hypot(pos["x"] - URAN_STONE["x"], pos["y"] - URAN_STONE["y"])
        print(f"Position {pos['x']:.0f}/{pos['y']:.0f} - Entfernung zum Uran Stone: {dist:.0f}")
        if dist < 50:
            print("Beim Uran Stone angekommen.")
            return
        time.sleep(2)


# ---------- gRPC-Server (wie grpc_analyzer.py vom Kollegen) ----------
class SensorVoidEnergyServer(api_pb2_grpc.SensorVoidEnergyServerServicer):
    def read_sensor_data(self, request, context):
        request_id = str(uuid.uuid4())
        print(f"[+] Analyzer fragt an -> Starte Messung {request_id}")

        # 1. Messung ausloesen
        resp = requests.post(f"{SENSOR_BASE_URL}/trigger_measurement", json={"request_id": request_id})
        if resp.status_code != 201:
            context.abort(grpc.StatusCode.INTERNAL, f"Fehler beim Triggern: {resp.text}")

        # 2. Auf Ergebnis warten
        measure_url = f"{SENSOR_BASE_URL}/measurements/{request_id}"
        for _ in range(60):
            data = requests.get(measure_url).json()
            if data.get("state") == "measured":
                result = data["result"]
                break
            time.sleep(1)
        else:
            requests.delete(measure_url)
            context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "Timeout bei Messung")

        # 3. Ergebnis loeschen (Resource Owner)
        requests.delete(measure_url)

        # 4. Rueckgabe an den Analyzer
        print(f"[✓] Daten an Analyzer gesendet: {result[:30]}...")
        return api_pb2.SensorData(hexdata=result)


def main():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    api_pb2_grpc.add_SensorVoidEnergyServerServicer_to_server(SensorVoidEnergyServer(), server)
    server.add_insecure_port("[::]:2102")
    server.start()
    print("SensorVoidEnergyServer laeuft auf Port 2102")

    set_target()               # 1. zuerst Flugziel setzen
    set_energy()               # 2. Energie fuer Analyzer + Sensor
    wait_until_at_uran_stone() # 3. warten bis wir beim Uran Stone sind
    print("Laufen lassen bis 100% (Ctrl+C beendet)")
    server.wait_for_termination()


if __name__ == "__main__":
    main()
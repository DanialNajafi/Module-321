import json
import queue
import paramiko
import time
import subprocess
import sys
import os
import threading

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
script_path = os.path.join(os.path.dirname(__file__), "scanner.py")
try:
    client.connect(
        hostname="192.168.101.60",
        username="ship",
        password="ship",
    )

    def stations_in_reach():
        stdin, stdout, stderr = client.exec_command("curl -sS -XGET http://192.168.101.60:2011/stations_in_reach")
        raw = stdout.read().decode()

        if not raw:
            err = stderr.read().decode().strip()
            print(f"Error: {err}")
            return {}

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"Keine gueltige JSON-Antwort: {raw}")
            return {}

        if data.get("kind") != "success":
            print(f"Antwort ohne Erfolg: {raw}")
            return {}

        return data.get("stations", {})

    def is_in_reach(station_name):
        return station_name in stations_in_reach()

    def got_to_station(xPosition, yPosition):
        stdin, stdout, stderr = client.exec_command(f"curl -XPOST http://192.168.101.60:2009/set_target --data '{{\"target\": {{\"x\": {xPosition}, \"y\": {yPosition}}}}}' {{\"kind\": \"success\"}}")
        print(stdout.read().decode())

    process = subprocess.Popen(     
        [sys.executable, "-u", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1
    )

    def return_station_position(data):
        for station in data: 
            print(f"Station datas: {station}")
            if station.get('name') == 'G-Station 1-6':
                print(f"Found G-Station 1-6 at position: {station.get('pos')}")
                return station.get('pos')

    got_to_station(16944 , -13051)

    latest_line = queue.Queue(maxsize=1)

    def read_scanner():
        for line in process.stdout:
            try:
                latest_line.get_nowait()
            except queue.Empty:
                pass

            latest_line.put(line)

    threading.Thread(target=read_scanner, daemon=True).start()


    while True:
        try:
            line = latest_line.get()
        except queue.Empty:
            continue
        try:
            data = json.loads(line.strip())
            print(f"Received data: {data}")
        except json.JSONDecodeError:
            print(f"Keine gueltige JSON-Antwort: {line.strip()}")
            continue

        #if not is_in_reach("G-Station 1-6"):
        print("G-Station 1-6 is not in reach.")
        result = return_station_position(data)
        if result:
            got_to_station(result.get('x'), result.get('y'))
            print(f"Going to G-Station 1-6 at position: {result.get('x')}, {result.get('y')}")        
        

finally:
    client.close()
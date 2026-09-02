import json
import paramiko
import time
import subprocess
import sys
import os

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
start_time = None 
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
        ["python", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    def return_station_position(data):
        for station in data:
            if station.get("name") == "G-Station 1-6":
                return station.get('pos')

    for line in process.stdout:
        try:
            data = json.loads(line.strip())
        except json.JSONDecodeError:
            print(f"Keine gueltige JSON-Antwort: {line.strip()}")
            continue

        while not is_in_reach("G-Station 1-6"):
            print("G-Station 1-6 is not in reach.")
            start_time = None
            result = return_station_position(data)
            if result:
                got_to_station(result.get("x"), result.get("y"))
            
        if is_in_reach("G-Station 1-6"):
            if start_time is None:
                start_time = time.time()
                print("G-Station 1-6 is in reach.")
            elapsed = time.time() - start_time

        result = return_station_position(data)
        if result:
            got_to_station(result.get("x"), result.get("y"))

        if elapsed >= 60:
            print("G-Station 1-6 has been in reach for 60 seconds. Exiting.")
            break
finally:
    client.close()
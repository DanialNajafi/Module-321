import json
import paramiko
import time

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(
        hostname="192.168.101.60",
        username="ship",
        password="ship",
    )

    def got_to_station(station_name):
        if station_name == "Vesta Station":
            stdin, stdout, stderr = client.exec_command(f"curl -XPOST http://192.168.101.60:2009/set_target --data '{{\"target\": {{\"x\": 7000, \"y\": 7000}}}}' {{\"kind\": \"success\"}}")
            print(stdout.read().decode())
        else:
            stdin, stdout, stderr = client.exec_command(f"curl -XPOST http://192.168.101.60:2009/set_target --data '{{\"target\":  \"{station_name}\"}}' {{\"kind\": \"success\"}}")
            print(stdout.read().decode())

    def sell_iron(station_name, amount):
        stdin, stdout, stderr = client.exec_command(f"curl -XPOST http://192.168.101.60:2011/sell --data '{{\"station\": \"{station_name}\", \"what\": \"IRON\", \"amount\": {amount}}}' {{\"kind\": \"success\"}}")
        print(stdout.read().decode())

    def buy_iron(station_name, amount):
        stdin, stdout, stderr = client.exec_command(f"curl -XPOST http://192.168.101.60:2011/buy --data '{{\"station\": \"{station_name}\", \"what\": \"IRON\", \"amount\": {amount}}}' {{\"kind\": \"success\"}}")
        print(stdout.read().decode())


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

    # This function buys a certain amount of IRON at Azura Station and sells it at Core Station. If the amount is 12, it will go to Vesta Station instead of Core Station.
    def buy_sell_iron(number_of_iron):
        got_to_station("Azura Station")

        while not is_in_reach("Azura Station"):
            print(f"... unterwegs nach Station ... ")
            time.sleep(5)

        buy_iron("Azura Station", number_of_iron)

        if number_of_iron == 12:
            print("12 IRON erreicht, unterweghs zu Vesta Station")
            got_to_station("Vesta Station")
            while not is_in_reach("Vesta Station"):
                print(f"... unterwegs nach Station ... ")
                time.sleep(5)
            exit(0)

        got_to_station("Core Station")

        while not is_in_reach("Core Station"):
            print(f"... unterwegs nach Station ... ")
            time.sleep(5)

        sell_iron("Core Station", number_of_iron)
    

    ## First buy 4 IRON at Azura Station and sell 4 at Core Station
    buy_sell_iron(4)



    ## Second buy 8 IRON at Core Station and sell 8 at Azura Station
    buy_sell_iron(8)



    ## Third buy 12 IRON at Azura Station and sell 12 at Core Station
    buy_sell_iron(12)

    

finally:
    client.close()
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



finally:
    client.close()

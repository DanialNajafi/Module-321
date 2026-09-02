import pika
import json

connection = pika.BlockingConnection(pika.ConnectionParameters(host="192.168.101.60", port=2014))
channel = connection.channel()

channel.exchange_declare(exchange='scanner/detected_objects', exchange_type='fanout')
result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue
channel.queue_bind(exchange='scanner/detected_objects', queue=queue_name)

for method_frame, properties, body in channel.consume(queue=queue_name, auto_ack=True):
    print(body.decode("utf-8"), flush=True)
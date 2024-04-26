from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
import socket
import time, json



if __name__ == "__main__":
    print("Hello Kafka")

    conf = {'bootstrap.servers': '192.168.50.2:29094',
        'client.id': socket.gethostname()}

    producer = Producer(conf)

    admin_client = AdminClient(conf)

    topic = "quickstart-events"
    new_topic = NewTopic(topic, num_partitions=1, replication_factor=1)
    fs = admin_client.create_topics([new_topic])

    x = False
    while True:
        if x:
            producer.produce("quickstart-events", "a")
            time.sleep(1)
            x = False
        else:
            producer.produce("quickstart-events", "b")
            time.sleep(1)
            x = True

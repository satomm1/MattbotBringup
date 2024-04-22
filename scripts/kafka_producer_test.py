from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
import time, json

def serializer(message):
	return json.dumps(message).encode("utf-8")

if __name__ == "__main__":
    print("Hello Kafka")

    admin_client = KafkaAdminClient(
        bootstrap_servers="192.168.50.2:29094",
        client_id='test'
    )

    topic_list = []
    topic_list.append(NewTopic(name="quickstart-events", num_partitions=1, replication_factor=1))
    admin_client.create_topics(new_topics=topic_list, validate_only=False)

    producer = KafkaProducer(
        bootstrap_servers=["192.168.50.2:29094"],
        value_serializer=serializer
    )

    x = False
    while True:
        if x:
            producer.send("quickstart-events", "a")
            time.sleep(1)
            x = False
        else:
            producer.send("quickstart-events", "b")
            time.sleep(1)
            x = True

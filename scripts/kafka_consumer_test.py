from kafka import KafkaConsumer
import json

if __name__ == "__main__":
    print("Hello Kafka!")
    consumer = KafkaConsumer("quickstart-events", bootstrap_servers="192.168.50.2:29094")  
    print("Consumer established")

    for msg in consumer:
        print(msg.value)

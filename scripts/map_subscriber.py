import rospy
from nav_msgs.msg import OccupancyGrid

import time
from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient, NewTopic

from pyignite import Client

class MapSubscriber:
    def __init__(self, ignite_host='ignite_host', ignite_port=10800):
        # Connect to Ignite server
        self.client = Client()
        self.client.connect(ignite_host, ignite_port)

        # Create map publisher
        self.map_publisher = rospy.Publisher('map', OccupancyGrid, queue_size=10)

        self.have_map = False

    def get_cached_map(self):
        # Retry for 10 seconds to get the cached map
        start_time = time.time()
        while time.time() - start_time < 10:
            try:
                # Get the cached map from Ignite
                map_data = self.client.get_cache('map').get(1)
                map_metadata = self.client.get_cache('map_metadata').get(1)
                if map_data:
                    self.have_map = True
                    return map_data, map_metadata
            except Exception as e:
                print(f"Error retrieving map: {e}")
            time.sleep(1)
        return None
    
    def process_map(self, map_data, map_metadata):
        # Convert the strings into the ROS Occupancy grid
        map = OccupancyGrid()
        map.header.frame_id = 'map'
        map.info.width = map_metadata['width']
        map.info.height = map_metadata['height']
        map.info.resolution = map_metadata['resolution']
        map.info.origin.position.x = map_metadata['origin.position.x']
        map.info.origin.position.y = map_metadata['origin.position.y']
        map.info.origin.position.z = map_metadata['origin.position.z']
        map.info.origin.orientation.x = map_metadata['origin.orientation.x']
        map.info.origin.orientation.y = map_metadata['origin.orientation.y']
        map.info.origin.orientation.z = map_metadata['origin.orientation.z']
        map.info.origin.orientation.w = map_metadata['origin.orientation.w']
        map.data = list(map(int, map_data.split(',')))

        # Publish the map
        self.map_publisher.publish(map)

    # def process_map_update(self, message):
    #     # Process map update message
    #     map_update = message.value
    #     print(f"Received map update: {map_update}")

    # def subscribe_to_map_updates(self):
    #     # Subscribe to Kafka topic for map updates
    #     consumer = KafkaConsumer('map_update_topic', bootstrap_servers='localhost:9092')
    #     for message in consumer:
    #         self.process_map_update(message)

    # def disconnect(self):
    #     # Disconnect from Ignite server
    #     self.client.close()

if __name__ == '__main__':
    map_subscriber = MapSubscriber()
    map, map_metadata = map_subscriber.get_cached_map()
    if map:
        print("Received cached map")
    map_subscriber.subscribe_to_map_updates()
    map_subscriber.disconnect()
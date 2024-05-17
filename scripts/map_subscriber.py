import rospy
import json
import numpy as np

from nav_msgs.msg import OccupancyGrid, MapMetaData

import time
from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient, NewTopic

from pyignite import Client

class MapSubscriber:
    def __init__(self, ignite_host='192.168.50.2', ignite_port=10800, bootstrap_servers='192.168.50.2:29094'):

        # initialize ROS node
        rospy.init_node('map_subscriber', anonymous=True)

        # Connect to Ignite server
        self.client = Client()
        self.client.connect(ignite_host, ignite_port)

        # Create map publisher
        self.map_publisher = rospy.Publisher('map', OccupancyGrid, queue_size=10)
        self.map_md_publisher = rospy.Publisher('/map_metadata', MapMetaData, queue_size=10)

        # Connect to Kafka server
        self.consumer = Consumer({
            'bootstrap.servers': bootstrap_servers,
            'group.id': 'mapUpdates',
            'auto.offset.reset': 'earliest'
        })

        # Create map_updates kafka topic if it doesn't exist
        admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
        topic_metadata = admin_client.list_topics(timeout=10)
        if 'map_updates' not in topic_metadata.topics:
            new_topic = NewTopic('map_updates', num_partitions=1, replication_factor=1)
            admin_client.create_topics([new_topic])

        # Subscribe to map_updates topic
        self.consumer.subscribe(['map_updates'])

        self.map = OccupancyGrid()
        self.map_md = MapMetaData()
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

                    map_metadata = json.loads(map_metadata)

                    # Convert the strings into the ROS Occupancy grid
                    self.map.header.frame_id = 'map'
                    self.map.info.width = map_metadata['width']
                    self.map.info.height = map_metadata['height']
                    self.map.info.resolution = map_metadata['resolution']
                    self.map.info.origin.position.x = map_metadata['origin.position.x']
                    self.map.info.origin.position.y = map_metadata['origin.position.y']
                    self.map.info.origin.position.z = map_metadata['origin.position.z']
                    self.map.info.origin.orientation.x = map_metadata['origin.orientation.x']
                    self.map.info.origin.orientation.y = map_metadata['origin.orientation.y']
                    self.map.info.origin.orientation.z = map_metadata['origin.orientation.z']
                    self.map.info.origin.orientation.w = map_metadata['origin.orientation.w']
                    self.map.data = np.frombuffer(map_data, dtype=int)

                    self.map_md.map_load_time = rospy.Time.now()
                    self.map_md.resolution = map_metadata['resolution']
                    self.map_md.width = map_metadata['width']
                    self.map_md.height = map_metadata['height']
                    self.map_md.origin.position.x = map_metadata['origin.position.x']
                    self.map_md.origin.position.y = map_metadata['origin.position.y']
                    self.map_md.origin.position.z = map_metadata['origin.position.z']
                    self.map_md.origin.orientation.x = map_metadata['origin.orientation.x']
                    self.map_md.origin.orientation.y = map_metadata['origin.orientation.y']
                    self.map_md.origin.orientation.z = map_metadata['origin.orientation.z']
                    self.map_md.origin.orientation.w = map_metadata['origin.orientation.w']
                    
                    self.map_publisher.publish(self.map)
                    self.map_md_publisher.publish(self.map_md)

                    return True
            except Exception as e:
                print(f"Error retrieving map: {e}")
            time.sleep(1)
        return False
    
    def run(self):
        rate = rospy.Rate(10)  # 10 Hz
        while not rospy.is_shutdown():
            # Consume messages from Kafka topic
            msg = self.consumer.poll(1.0)
            if msg is None:
                pass
            elif msg.error():
                print(f"Error consuming message: {msg.error()}")
                pass
            else:
                # Process map update message
                map_update = msg.value()
                print(f"Received map update: {map_update}")
                self.process_map_update(map_update)

            # Publish map to ROS topic
            self.map_publisher.publish(self.map)
            self.map_md_publisher.publish(self.map_md)

            rate.sleep()

    def process_map_update(self, message):
        # Process map update message
        map_update = json.loads(message)
        self.map.header.stamp = rospy.Time.now()

        # map_update is a dict, with keys (x,y) and values (value)
        for key, value in map_update.items():
            x, y = key
            self.map.data[x + y * self.map.info.width] = value

    def disconnect(self):
        # Disconnect from Ignite server
        self.client.close()



if __name__ == '__main__':
    map_subscriber = MapSubscriber()
    success = map_subscriber.get_cached_map()
    map_subscriber.disconnect()
    if success:
        print("Received cached map")
        map_subscriber.run()
        
    else:
        print("Failed to receive cached map")
            
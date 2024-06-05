import rospy
import json
import numpy as np
import requests

from nav_msgs.msg import OccupancyGrid, MapMetaData

import time
from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient, NewTopic

from pyignite import Client

class MapSubscriber:
    def __init__(self, server_url='http://192.168.50.2:8000/graphql', bootstrap_servers='192.168.50.2:29094'):

        # initialize ROS node
        rospy.init_node('map_subscriber', anonymous=True)

        # GraphQL endpoint server
        self.server_url = server_url

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

        self.map = OccupancyGrid()
        self.map.header.seq = 0
        self.map_md = MapMetaData()
        self.map_seq = 0
        self.have_map = False

        self.map_query = """ 
                            {
                                map {
                                    width
                                    height
                                    origin_x
                                    origin_y
                                    origin_z
                                    origin_orientation_x
                                    origin_orientation_y
                                    origin_orientation_z
                                    origin_orientation_w
                                    resolution
                                    occupancy
                                }
                            }
                        """
        
        # Subscribe to map_updates topic
        self.consumer.subscribe(['map_updates'])

    def get_cached_map(self):
        # Retry for 10 seconds to get the cached map
        start_time = time.time()
        while time.time() - start_time < 10:
            try:
                # Get the map
                response = requests.post(self.server_url, json={'query': self.map_query})
                if response.status_code == 200:
                    data = response.json()
                    map_data = data.get('data', {}).get('map', {})
                
                    self.have_map = True

                    # Convert the strings into the ROS Occupancy grid
                    self.map.header.frame_id = 'map'
                    self.map.info.width = map_data.get('width')
                    self.map.info.height = map_data.get('height')
                    self.map.info.resolution = map_data.get('resolution')
                    self.map.info.origin.position.x = map_data.get('origin_x')
                    self.map.info.origin.position.y = map_data.get('origin_y')
                    self.map.info.origin.position.z = map_data.get('origin_z')
                    self.map.info.origin.orientation.x = map_data.get('origin_orientation_x')
                    self.map.info.origin.orientation.y = map_data.get('origin_orientation_y')
                    self.map.info.origin.orientation.z = map_data.get('origin_orientation_z')
                    self.map.info.origin.orientation.w = map_data.get('origin_orientation_w')
                    self.map.data = map_data.get('occupancy')

                    self.map_md.map_load_time = rospy.Time.now()
                    self.map_md.resolution = map_data.get('resolution')
                    self.map_md.width = map_data.get('width')
                    self.map_md.height = map_data.get('height')
                    self.map_md.origin.position.x = map_data.get('origin_x')
                    self.map_md.origin.position.y = map_data.get('origin_y')
                    self.map_md.origin.position.z = map_data.get('origin_z')
                    self.map_md.origin.orientation.x = map_data.get('origin_orientation_x')
                    self.map_md.origin.orientation.y = map_data.get('origin_orientation_y')
                    self.map_md.origin.orientation.z = map_data.get('origin_orientation_z')
                    self.map_md.origin.orientation.w = map_data.get('origin_orientation_w')
                    
                    self.map_publisher.publish(self.map)
                    self.map_md_publisher.publish(self.map_md)

                    return True
                else:
                    print(f"Error retrieving map: {response.status_code}")
            except Exception as e:
                print(f"Error retrieving map: {e}")
            time.sleep(1)
        return False
    
    def run(self):
        rate = rospy.Rate(0.5)  # 0.5 Hz
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

            self.map.header.stamp = rospy.Time.now()
            self.map_seq += 1
            self.map.header.seq = self.map_seq
        
            # Publish map to ROS topic
            self.map_md_publisher.publish(self.map_md)
            self.map_publisher.publish(self.map)

            rate.sleep()

    def process_map_update(self, message):
        # Process map update message
        map_update = json.loads(message)
        self.map.header.stamp = rospy.Time.now()

        # map_update is a dict, with keys (x,y) and values (value)
        for key, value in map_update.items():
            x, y = key
            self.map.data[x + y * self.map.info.width] = value


if __name__ == '__main__':
    map_subscriber = MapSubscriber()
    success = map_subscriber.get_cached_map()
    if success:
        print("Received cached map")
        map_subscriber.run()
        
    else:
        print("Failed to receive cached map")
            
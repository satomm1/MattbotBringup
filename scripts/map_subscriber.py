import rospy
import json
import numpy as np
import requests
import rospkg
import os

from nav_msgs.msg import OccupancyGrid, MapMetaData

import time
from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient, NewTopic

from pyignite import Client

"""
Polls the server for the map and publishes it to the /map topic
"""

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
                                    name
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
                    self.map_name = map_data.get('name')

                    rospack = rospkg.RosPack()
                    pkg_path = rospack.get_path('mattbot_mcl')
                    data_path = pkg_path + '/lookup_table/' + self.map_name + '.npy'
                    current_map_data_path = pkg_path + '/lookup_table/current_map.npy'
                    
                    # Check if file exists and load it
                    if os.path.exists(data_path):
                        lookup_table = np.load(data_path)
                        np.save(current_map_data_path, lookup_table)
                    else:
                        lookup_table = self.generate_dist_lookup_table()
                        np.save(data_path, lookup_table)

                        current_map_data_path = pkg_path + '/lookup_table/current_map.npy'
                        np.save(current_map_data_path, lookup_table)
                    
                    self.map_publisher.publish(self.map)
                    self.map_md_publisher.publish(self.map_md)

                    return True
                else:
                    print(f"Error retrieving map: {response.status_code}")
            except Exception as e:
                print(f"Error retrieving map: {e}")
            time.sleep(1)
        return False

    def generate_dist_lookup_table(self):
        """
        Generates a table of distances from the LIDAR sensor to the nearest occupied cell
        """
        self.map_width = self.map_md.width
        self.map_height = self.map_md.height
        self.map_resolution = self.map_md.resolution
        self.map_originx = self.map_md.origin.position.x
        self.map_originy = self.map_md.origin.position.y

        self.occupancy = StochOccupancyGrid2D(
            self.map_resolution,
            self.map_width,
            self.map_height,
            self.map_originx,
            self.map_originy,
            3,
            self.map.data,
        )

        # Get the indices of every cell in the map that is occupied
        probs = np.reshape(np.asarray(self.map.data), (self.map_height, self.map_width))
        occupied_indices = np.where(probs == 100)
        occupied_indices = np.vstack(occupied_indices)

        print("Generating lookup table, please wait...")

        lookup_table = np.zeros((self.map_width, self.map_height))
        for x in range(self.map_width):
            for y in range(self.map_height):
                if self.occupancy.is_unknown((x*self.map_resolution,y*self.map_resolution)):
                    lookup_table[x,y] = -1
                elif self.occupancy.is_free((x*self.map_resolution,y*self.map_resolution)):
                    # lookup_table[x, y] = self.find_closest_obstacle(x, y)
                    lookup_table[x, y] = np.min(np.linalg.norm(np.array([y, x]) - occupied_indices.T, axis=1)) * self.map_resolution
                else:
                    lookup_table[x, y] = 0

        print("Lookup table generated successfully")
        return lookup_table.T

    def find_closest_obstacle(self, x, y):
        """
        Finds the closest obstacle to a given cell

        Args:
            x: The x coordinate of the cell
            y: The y coordinate of the cell
        """
        k = 1
        while True:
            for i in np.arange(-k, k+1):
                for j in np.arange(-k, k+1):
                    if np.abs(i) == k or np.abs(j) == k:
                        new_x = np.clip(x+i, 0, self.map_width-1)
                        new_y = np.clip(y+j, 0, self.map_height-1)
                        if ~self.occupancy.is_free((new_x*self.map_resolution, new_y*self.map_resolution)):
                            return np.sqrt(i**2 + j**2)*self.map_resolution
            k += 1
    
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

class StochOccupancyGrid2D(object):
    def __init__(self, resolution, width, height, origin_x, origin_y,
                window_size, probs, thresh=0.5, robot_d=0.6):
        self.resolution = resolution
        self.width = width
        self.height = height
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.probs = np.reshape(np.asarray(probs), (height, width))
        self.window_size = window_size # window_size
        # print(window_size)
        self.thresh = thresh
        self.robot_d=robot_d

    def snap_to_grid(self, x):
        return (self.resolution*round(x[0]/self.resolution), self.resolution*round(x[1]/self.resolution))

    def snap_to_grid1(self, x):
        return (self.resolution * np.round(x[0] / self.resolution), self.resolution * np.round(x[1] / self.resolution))

    def is_free(self, state):

        # combine the probabilities of each cell by assuming independence
        # of each estimation
        x, y = self.snap_to_grid(state)
        grid_x = int((x - self.origin_x) / self.resolution)
        grid_y = int((y - self.origin_y) / self.resolution)

        # Now check probabilities
        half_size = int(round((self.window_size-1)/2))
        grid_x_lower = max(0, grid_x - half_size)
        grid_y_lower = max(0, grid_y - half_size)
        grid_x_upper = min(self.width, grid_x + half_size + 1)
        grid_y_upper = min(self.height, grid_y + half_size + 1)        
        
        prob_window = self.probs[grid_y_lower:grid_y_upper, grid_x_lower:grid_x_upper]
        p_total = np.prod(1. - np.maximum(prob_window / 100., 0.))

        return (1. - p_total) < self.thresh

    def is_free1(self, state):
        """
        Determine if a state is free based on the occupancy grid. This function allows multiple states to be tested
        with a single function call.

        :param state: represents different x,y positions of interest. 2xN array (or 3xN if you want to include theta)
        :return: an array of length N indicating if each corresponding state is free
        """

        # combine the probabilities of each cell by assuming independence
        # of each estimation
        x, y = self.snap_to_grid1(state)
        grid_x = ((x - self.origin_x) / self.resolution).astype(int)
        grid_y = ((y - self.origin_y) / self.resolution).astype(int)

        # Now check probabilities
        half_size = int(round((self.window_size - 1) / 2))
        grid_x_lower = np.maximum(0, grid_x - half_size)
        grid_y_lower = np.maximum(0, grid_y - half_size)
        grid_x_upper = np.minimum(self.width, grid_x + half_size + 1)
        grid_y_upper = np.minimum(self.height, grid_y + half_size + 1)

        free_list = []
        for i in range(len(grid_x)):
            prob_window = self.probs[grid_y_lower[i]:grid_y_upper[i], grid_x_lower[i]:grid_x_upper[i]]
            p_total = np.prod(1. - np.maximum(prob_window / 100., 0.))
            free_list.append((1. - p_total) < self.thresh)

        return np.array(free_list)

    def is_unknown(self, state):
        x, y = self.snap_to_grid(state)
        grid_x = int((x - self.origin_x) / self.resolution)
        grid_y = int((y - self.origin_y) / self.resolution)
        return self.probs[grid_y, grid_x] == -1
        
    def prob_x_given_map(self, state):
        x, y = self.snap_to_grid(state)
        grid_x = int((x - self.origin_x) / self.resolution)
        grid_y = int((y - self.origin_y) / self.resolution)
        
        return self.probs[grid_y, grid_x]

    def plot(self, fig_num=0):
        fig = plt.figure(fig_num)
        pts = []
        for i in range(self.probs.shape[0]):
            for j in range(self.probs.shape[1]):
                # convert i to (x,y)
                x = j * self.resolution + self.origin_x
                y = i * self.resolution + self.origin_y
                if not self.is_free((x,y)):
                    pts.append((x,y))
        pts_array = np.array(pts)
        plt.scatter(pts_array[:,0],pts_array[:,1],color="red",zorder=15,label='planning resolution')
        plt.xlim([self.origin_x, self.width * self.resolution + self.origin_x])
        plt.ylim([self.origin_y, self.height * self.resolution + self.origin_y])

if __name__ == '__main__':
    map_subscriber = MapSubscriber()
    success = map_subscriber.get_cached_map()
    if success:
        print("Received cached map")
        map_subscriber.run()
        
    else:
        print("Failed to receive cached map")
            
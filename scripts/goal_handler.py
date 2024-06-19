#!/usr/bin/env python3

import time
import rospy
import os
import requests
from geometry_msgs.msg import Pose2D

""" 
Polls the server for the next goal and publishes it to the /external_goal topic
"""

class GraphQLClient:
    def __init__(self, server_url='http://192.168.50.2:8000/graphql'):
        self.robot_id = os.environ.get('ROBOT_ID')
        self.server_url = server_url

        self.x_goal = None
        self.y_goal = None
        self.theta_goal = None

        self.query = """
                        {
                            robotGoal(robot_id:""" + str(self.robot_id) + """) {
                                x_goal
                                y_goal
                                theta_goal
                            }
                        }
                     """
        
        # Create a publisher of 2dpose
        self.goal_pub = rospy.Publisher('/external_goal', Pose2D, queue_size=10)

    def run(self):

        rate = rospy.Rate(2)
        while not rospy.is_shutdown():
            # Get the next goal from the goal server
            response = requests.post(self.server_url, json={'query': self.query})
            if response.status_code == 200:
                data = response.json()
                robot_data = data.get('data', {}).get('robotGoal', {})
                new_x_goal = robot_data.get('x_goal')
                new_y_goal = robot_data.get('y_goal')
                new_theta_goal = robot_data.get('theta_goal')

                if new_x_goal != self.x_goal or new_y_goal != self.y_goal or new_theta_goal != self.theta_goal:
                    rospy.loginfo(f"New goal received: x={new_x_goal}, y={new_y_goal}, theta={new_theta_goal}")
                    self.x_goal = new_x_goal
                    self.y_goal = new_y_goal
                    self.theta_goal = new_theta_goal
                    Pose2D_msg = Pose2D()
                    Pose2D_msg.x = self.x_goal
                    Pose2D_msg.y = self.y_goal
                    Pose2D_msg.theta = self.theta_goal
                    self.goal_pub.publish(Pose2D_msg)
            else:
                rospy.logerr(f"Failed to query GraphQL server. Status code: {response.status_code}")

            rate.sleep()


if __name__ == '__main__':
    rospy.init_node('goal_handler', anonymous=True)
    rospy.loginfo("Goal handler node started")

    client = GraphQLClient()
    client.run()
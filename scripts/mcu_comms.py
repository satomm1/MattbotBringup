import rospy
import time
import spidev
import struct

from geometry_msgs.msg import Twist, Pose, Point, Quaternion, Vector3, TransformStamped
from nav_msgs.msg import Odometry
from tf2_msgs.msg import TFMessage
from tf.transformations import quaternion_from_euler

BAUD_RATE = 1000000 # Baud rate for SPI


class MCU_Comms:
    """
    Sets up communication between the Jetson and the MCU
    """
    def __init__(self):

        # Initialize the node
        rospy.init_node('mcu_comms', anonymous=True)

        # Subscribe to the cmd_vel topic to receive velocity commands
        rospy.Subscriber("/cmd_vel", Twist, self.vel_callback)

        # Publish the odometry data
        self.odom_pub = rospy.Publisher("/odom", Odometry, queue_size=10)

        # Publish the TF data
        self.tf_pub = rospy.Publisher("/tf", TFMessage, queue_size=10)



        # Create the SPI object to facilitate SPI communication via Jetson and MCU
        self.spi = spidev.SpiDev()  # Create SPI object
        self.spi.open(0,0)  # open spi port 0, device (CS) 0
        self.spi.max_speed_hz = BAUD_RATE  
        self.spi.mode = 0b11  # CPOL = 1, CPHA = 1 (i.e. clock is high when idle, data is clocked in on rising edge)

        self.robot_id = 0x00

        # Initialize linear/angular velocity commands
        self.lin_cmd = 0.0
        self.ang_cmd = 0.0

    def mcu_startup(self):
        """
        This function is used to bring up the MCU online and confirm communication
        """

        # Bringup message to MCU
        bringup_message = [90, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

        # Send bringup message to MCU until received and confirmed
        bringup_confirmed = False
        while not bringup_confirmed:
            bringup_message = [90, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            rcvd = self.spi.xfer(bringup_message)
            print(rcvd)

            # Check if the MCU has confirmed bringup
            if rcvd[0] == 0 and rcvd[1] == 255 and rcvd[2] == 0:
                bringup_confirmed = True  # MattBot is active
                self.robot_id = rcvd[3]  # Get and store the robot ID
                print("Robot ID: " + str(self.robot_id))
            time.sleep(0.1)

        # Send confirmation message to MCU
        confirmation_message = [90, 170, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        rcvd = self.spi.xfer2(confirmation_message)
        print(rcvd)

    def vel_callback(self, data):
        """
        This function is called whenever a new cmd_vel message is received
        """
        self.lin_cmd = data.linear.x
        self.ang_cmd = data.angular.z

    def send_vel_command(self):
        """
        This is just used for testing communication with the MCU
        """
        n = 0
        while n < 20:
            vel_msg = [45,0x3f,0x00,0x00,0x00,0x00,0x00,0x00,0x00,10,11,12,13,14,15,16]
            rcvd = self.spi.xfer(vel_msg)
            print(rcvd)
            n = n + 1
            time.sleep(0.01)
        time.sleep(2.5)
        end_msg = [90, 0b11110000,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
        rcvd = self.spi.xfer(end_msg)
        print(rcvd)

    def run(self):
        """
        This is the main loop for the MCU communication node
        """
        self.mcu_startup()

        sensor_sequence = 0  # Sequence number for sensor messages
        while not rospy.is_shutdown():
            # Send velocity command to MCU
            lin_vel_bytes = float_to_bytes(self.lin_cmd)
            ang_vel_bytes = float_to_bytes(self.ang_cmd)
            vel_msg = [45,  # Indicates velocity message
                       lin_vel_bytes[3],lin_vel_bytes[2],lin_vel_bytes[1],lin_vel_bytes[0],  # Linear velocity
                       ang_vel_bytes[3],ang_vel_bytes[2],ang_vel_bytes[1],ang_vel_bytes[0],  # Angular velocity
                       0,0,0,0,0,0,0]  # Padding
            rcvd = self.spi.xfer(vel_msg)
            # print(rcvd)

            # Now do something with the received data
            if rcvd[0] == 7: # Received dead reckoning data

                # Extract the dead reckoning data (converts from bytes to float)
                V_dr = bytes_to_float(list(reversed(rcvd[1:5])))
                w_dr = bytes_to_float(list(reversed(rcvd[5:9])))

                # Load the data into an Odometry Message
                odom = Odometry()
                odom.header.stamp = rospy.Time.now()
                odom.header.frame_id = "odom"
                odom.header.seq = sensor_sequence
                odom.child_frame_id = "base_footprint"
                
                odom.pose.pose.position.x = pos_x
                odom.pose.pose.position.y = pos_y
                odom.pose.pose.position.z = 0
                
                rotation = quaternion_from_euler(0,0, pos_theta)
                rotation = Quaternion(*rotation)
                
                odom.pose.pose.orientation.x = rotation.x
                odom.pose.pose.orientation.y = rotation.y
                odom.pose.pose.orientation.z = rotation.z
                odom.pose.pose.orientation.w = rotation.w
                
                odom.twist.twist.linear.x = V_dr
                odom.twist.twist.linear.y = 0
                odom.twist.twist.linear.z = 0
                
                odom.twist.twist.angular.x = 0
                odom.twist.twist.angular.y = 0
                odom.twist.twist.angular.z = w_dr

                self.odom_pub.publish(odom)  # actually publish the data

                sensor_sequence = sensor_sequence + 1

            elif rcvd[0] == 8:  # Recieved position data

		

                # Extract the position data (converts from bytes to float)
                pos_x = bytes_to_float(list(reversed(rcvd[1:5])))
                pos_y = bytes_to_float(list(reversed(rcvd[5:9])))
                pos_theta = bytes_to_float(list(reversed(rcvd[9:13])))

                # Load the data into a TF Message
                tf_msg = TFMessage()
                transform_stamped = TransformStamped()
                
                transform_stamped.header.stamp = rospy.Time.now()
                transform_stamped.header.frame_id = "odom"
                transform_stamped.header.seq = sensor_sequence
                transform_stamped.child_frame_id = "base_footprint"
                transform_stamped.transform.translation.x = pos_x
                transform_stamped.transform.translation.y = pos_y
                transform_stamped.transform.translation.z = 0
                
                rotation = quaternion_from_euler(0,0, pos_theta)
                rotation = Quaternion(*rotation)
                
                transform_stamped.transform.rotation.x = rotation.x
                transform_stamped.transform.rotation.y = rotation.y
                transform_stamped.transform.rotation.z = rotation.z
                transform_stamped.transform.rotation.w = rotation.w
                
                tf_msg.transforms.append(transform_stamped)

                self.tf_pub.publish(tf_msg)  # actually publish the data

            elif rcvd[0] == 9: # Received IMU data
                pass
            elif rcvd[0] == 10: # Received accleration data
                pass

            time.sleep(0.01)

    def shutdown(self):
        """
        This function is called when the node is shutdown
        """
        # Send shutdown message to MCU
        shutdown_message = [90, 0b11110000,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
        rcvd = self.spi.xfer(shutdown_message)

        self.spi.close()

def float_to_bytes(float_number):
    """
    This function takes a 32-bit float and returns a list of four 8-bit integers
    """
    # Pack the 32-bit float into bytes
    packed_data = struct.pack('f', float_number)

    # Unpack the bytes into four 8-bit integers
    int_list = struct.unpack('BBBB', packed_data)

    return int_list

def bytes_to_float(byte_array):
    # Pack the bytes into a 32-bit float
    float_number = struct.unpack('f', bytes(byte_array))[0]

    return float_number

def mcu_shutdown():
    print("Shutting down MCU communication")
    comms.shutdown()

if __name__ == "__main__":
    comms = MCU_Comms()
    # req.send_vel_command()
    rospy.on_shutdown(mcu_shutdown)
    # req.spi.close()
    comms.run()

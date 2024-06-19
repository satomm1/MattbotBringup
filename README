# Bringup
This package is for general bringup of the robot. The general functions of the scripts and launch files are described below:

### Scripts
- **mcu_comms.py**: This file handles communication between the Jetson (onboard computer) and the microcontroller (which is used for motor control and low level sensors). Communication is handled through the SPI protocol and occurs at 1 MHz baud rate. This script sends wheel velocity commands via SPI, and receives IMU and odometry data from the MCU.
- **map_subscriber.py**: This script repeatedly polls the server for a map and publishes the map and map metadata to the map and map_metadata topics. 
- **goal_handler.py**: This script polls the server for the goal of the current robot. If a new goal is found, the goal is published to the external_goal topic.

### Launch
The primary launch files are `minimal.launch` and `robot.launch`. Other launch files are provided for convenience.
- **minimal.launch**: Starts the minimal scripts needed to run the robot (mcu_comms and the twist multiplexer).
- **robot.launch**: Launches the full stack necessary for full robot operations. (mcu_comms, map_subscriber, goal_handler, twist multiplexer, LIDAR, Camera, kafka transform producer, kafka scan producer, kaka odom producer, kafka path producer, kafka video producer, monte carlo localization, navigator)
- **sensing.launch**: Launches the stack necessary for sensing (mcu_comms, twist multiplexer, LIDAR, Camera)
- **sense_and_map.launch**: Launches the stack necessary for mapping. (mcu_comms, twist multiplexer, LIDAR, Camera, SLAM)
- **map_and_detect.launch**: Launches everything needed for mapping as well as image object detection (everything in sense_and_map + YOLO)

**Author**: Matthew Sato, Engineering Informatics Lab, Stanford University

**License**: This package is released under the [MIT license](LICENSE).
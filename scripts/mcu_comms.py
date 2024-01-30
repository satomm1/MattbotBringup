import rclpy
from rclpy.node import Node

import time
import spidev


BAUD_RATE = 1000000


class MCU_Comms:
    """
    Sets up communication between the Jetson and the MCU
    """
    def __init__(self):
        # Create the SPI object to facilitate SPI communication via Jetson and MCU
        self.spi = spidev.SpiDev()  # Create SPI object
        self.spi.open(0,0)  # open spi port 0, device (CS) 0
        self.spi.max_speed_hz = BAUD_RATE  
        self.spi.mode = 0b11  # CPOL = 1, CPHA = 1 (i.e. clock is high when idle, data is clocked in on rising edge)

        self.robot_id = 0x00

        # Bringup message to MCU
        bringup_message = [90, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

        # Send bringup message to MCU unti received and confirmed
        bringup_confirmed = False
        while not bringup_confirmed:
            bringup_message = [90, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            rcvd = self.spi.xfer(bringup_message)
            print(rcvd)
            if rcvd[0] == 0 and rcvd[1] == 255 and rcvd[2] == 0:
                bringup_confirmed = True  # MattBot is active
                self.robot_id = rcvd[3]
                print("Robot ID: " + str(self.robot_id))
            time.sleep(0.1)
        confirmation_message = [90, 170, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        rcvd = self.spi.xfer2(confirmation_message)
        print(rcvd)

        time.sleep(1)

    def send_vel_command(self):

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


if __name__ == "__main__":
    req = MCU_Comms()
    req.send_vel_command()
    req.spi.close()


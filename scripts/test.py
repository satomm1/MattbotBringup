import spidev
import time

print("Hello World!")
spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 15000
spi.mode = 0b11

try:
    while True:
        
        resp = spi.xfer2([0b01011001, 0b11111111])
        print(resp)
        time.sleep(0.5)
except KeyboardInterrupt:
    spi.close()

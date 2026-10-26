from machine import I2C, Pin
import time
import struct
import neopixel
import math

# --- Setup ---
i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)
MPU6050_ADDR = 0x68
i2c.writeto_mem(MPU6050_ADDR, 0x6B, b'\x00')

np = neopixel.NeoPixel(Pin(0), 3)

# --- Smoothed gyro ---
gx_s, gy_s, gz_s = 0, 0, 0

def read_sensor():
    data = i2c.readfrom_mem(MPU6050_ADDR, 0x3B, 14)
    ax, ay, az, temp, gx, gy, gz = struct.unpack(">hhhhhhh", data)

    gx /= 131.0
    gy /= 131.0
    gz /= 131.0

    return ax, ay, az, gx, gy, gz

# --- Shake Detection State Variables ---
shake_state = "IDLE"
shake_count = 0
shake_timer = 0
SHAKE_THRESHOLD = 150.0
RESET_THRESHOLD = 30.0
TIMEOUT_MS = 600

# --- Mode State Variables ---
heartbeat_active = False

# --- Pulse Timer ---
t = 0

while True:
    current_time = time.ticks_ms()
    ax, ay, az, gx, gy, gz = read_sensor()

    # --- Stronger gyro smoothing ---
    alpha_g = 0.15
    gx_s = (1 - alpha_g) * gx_s + alpha_g * gx
    gy_s = (1 - alpha_g) * gy_s + alpha_g * gy
    gz_s = (1 - alpha_g) * gz_s + alpha_g * gz

    # --- Deadband ---
    def deadband(v, thresh=2):
        return 0 if abs(v) < thresh else v

    gx_s = deadband(gx_s)
    gy_s = deadband(gy_s)
    gz_s = deadband(gz_s)

    mag = abs(gx_s) + abs(gy_s) + abs(gz_s)

    # --- Robust Double Shake State Machine ---
    if shake_state != "IDLE" and time.ticks_diff(current_time, shake_timer) > TIMEOUT_MS:
        shake_state = "IDLE"
        shake_count = 0

    if shake_state == "IDLE":
        if mag > SHAKE_THRESHOLD:
            shake_count = 1
            shake_state = "WAIT_RESET_1"
            shake_timer = current_time

    elif shake_state == "WAIT_RESET_1":
        if mag < RESET_THRESHOLD:
            shake_state = "WAIT_SHAKE_2"
            shake_timer = current_time

    elif shake_state == "WAIT_SHAKE_2":
        if mag > SHAKE_THRESHOLD:
            shake_count = 2
            shake_state = "WAIT_RESET_2"
            shake_timer = current_time

    elif shake_state == "WAIT_RESET_2":
        if mag < RESET_THRESHOLD:
            if shake_count == 2:
                heartbeat_active = not heartbeat_active
            shake_state = "IDLE"
            shake_count = 0

    # --- Mode Execution ---
    if heartbeat_active:
        # Slower speed for a calm, realistic resting heart rate (~70 bpm)
        t += 0.015
        
        # Extended cycle loop (4.0 seconds total per heartbeat sequence)
        phase = t % 2.2
        
        hb_bright = 0.0
        
        # First beat (Lub): smooth rise and fall
        if 0.0 <= phase < 0.35:
            hb_bright = math.sin((phase / 0.35) * math.pi)
        # Second beat (Dub): slightly softer/shorter peak
        elif 0.55 <= phase < 0.85:
            hb_bright = 0.75 * math.sin(((phase - 0.55) / 0.30) * math.pi)
        # Long resting glow baseline so it never snaps completely harsh to 0
        else:
            

        # Gamma correction curve for a smooth, organic visual glow instead of linear flash
        glow_curve = hb_bright ** 2.2
        
        # Minimum idle floor glow (0.04) blended smoothly into peak brightness (255)
        red_val = int(10 + (245 * glow_curve))
        color = (red_val, 0, 0)
    else:
        color = (0, 0, 0)

    for i in range(3):
        np[i] = color
    np.write()

    time.sleep(0.01)
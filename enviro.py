#!/usr/bin/env python
# coding=utf-8

import time
import colorsys
import os
import sys
import signal
import ST7735
import ltr559
import RPi.GPIO as GPIO

from bme280 import BME280
from enviroplus import gas
from subprocess import PIPE, Popen
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import logging

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info("""all-in-one.py - Displays readings from all of Enviro plus' sensors
Press Ctrl+C to exit!
""")

# BME280 temperature/pressure/humidity sensor
bme280 = BME280()

# Create ST7735 LCD display class
st7735 = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize display
st7735.begin()

WIDTH = st7735.width
HEIGHT = st7735.height

# Set up canvas and font
img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
draw.fontmode = "1"

path = os.path.dirname(os.path.realpath(__file__))
font = ImageFont.load(path + "/vga8.pil")
bissel1 = Image.open(path + '/bissel1.png')
bissel2 = Image.open(path + '/bissel2.png')
bissel3 = Image.open(path + '/bissel3.png')

message = ""

# The position of the top bar
top_pos = 16

# pixel width of each line in the graph
line_width = 4


def sigterm_handler(signal, frame):
    print('Received sigterm, exiting...')
    sys.exit(0)

signal.signal(signal.SIGTERM, sigterm_handler)


def display_img():
    logging.info("Drawing static image...");
    if not backlight_on:
        draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
        st7735.display(img)
        return
    if mode == 7:
        img.paste(bissel1, (0,0))
    if mode == 8:
        img.paste(bissel2, (0,0))
    if mode == 9:
        img.paste(bissel3, (0,0))

    if shutdown_steps == 1:
        draw.text((4, 18), "Hold to shut down", font=font, fill=(255, 192, 192))
    elif shutdown_steps == 2:
        draw.text((4, 18), "Shutting down...", font=font, fill=(255, 128, 128))
    st7735.display(img)


# Displays data and text on the 0.96" LCD
def display_text(variable, data, unit):
    # on mode change, reinitialize the list with the most recent data
    if mode != prev_mode:
        values[variable] = [data] * (WIDTH / line_width)

    # Maintain length of list
    values[variable] = values[variable][1:] + [data]
    
    if not backlight_on:
        return
    # Scale the values for the variable between 0 and 1
    colours = [(v - min(values[variable]) + 1) / (max(values[variable])
               - min(values[variable]) + 1) for v in values[variable]]
    # Format the variable name and value
    message = "{}: {:.1f} {}".format(variable[:4], data, unit)
    logging.info(message)
    draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
    for i in range(len(colours)):
        # Convert the values to colours from red to blue
        colour = (1.0 - colours[i]) * 0.6
        r, g, b = [int(x * 255.0) for x in colorsys.hsv_to_rgb(colour,
                   1.0, 1.0)]
        # Draw a rectangle of colour
        draw.rectangle((i*line_width, top_pos, (i+1)*line_width, HEIGHT), (r, g, b))
        # Draw a line graph in black
        line_y = HEIGHT - (top_pos + (colours[i] * (HEIGHT - top_pos)))\
                 + top_pos
        draw.rectangle((i*line_width, line_y, (i+1)*line_width, line_y+1), (0, 0, 0))
    # Write the text at the top in black
    draw.text((4, 0), message, font=font, fill=(255, 255, 255))
    if shutdown_steps == 1:
        draw.text((4, 18), "Hold to shut down", font=font, fill=(255, 192, 192))
    elif shutdown_steps == 2:
        draw.text((4, 18), "Shutting down...", font=font, fill=(255, 128, 128))
    st7735.display(img)


# Get the temperature of the CPU for compensation
def get_cpu_temperature():
    process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE, universal_newlines=True)
    output, _error = process.communicate()
    return float(output[output.index('=') + 1:output.rindex("'")])


# Tuning factor for compensation. Decrease this number to adjust the
# temperature down, and increase to adjust up
factor = 0.8

cpu_temps = [get_cpu_temperature()] * 5


# amount of time to wait per loop cycle
loop_delay = 0.25

mode = 0  # The starting mode
prev_mode = 0

last_page = 0

backlight_on = True
time_of_backlight_on = time.time()

time_spent_in_prox = 0
shutdown_steps = 0


# Create a values dict to store the data
variables = ["Temperature",
             "Pressure",
             "Humidity",
             "Light",
             "Oxidized",
             "Reduced",
             "NH3"]

total_modes = 10

values = {}

for v in variables:
    values[v] = [1] * (WIDTH / line_width)

# The main loop
try:
    while True:
        time.sleep(loop_delay)

        proximity = ltr559.get_proximity()

        # turn off backlight if timed out
        if backlight_on and time.time() - time_of_backlight_on > 60:
            st7735.set_backlight(GPIO.LOW)
            backlight_on = False
            display_img();

        
        if proximity > 1500:
            # If the proximity crosses the threshold, toggle the mode
            if time_spent_in_prox == 0:
                last_page = time.time()
                if not backlight_on:
                    st7735.set_backlight(GPIO.HIGH)
                    backlight_on = True
                else:
                    mode += 1
                    mode %= total_modes
                time_of_backlight_on = time.time()
            
            time_spent_in_prox += loop_delay
        else:
            time_spent_in_prox = 0
            shutdown_steps = 0


        if time_spent_in_prox > 6:
            shutdown_steps = 2
            display_img()
            os.system("sudo shutdown now")
            sys.exit(0)
        elif time_spent_in_prox > 3:
            shutdown_steps = 1
            display_img()


        # One mode for each variable
        if mode == 0:
            # variable = "temperature"
            unit = "°C"
            # cpu_temp = get_cpu_temperature()
            # Smooth out with some averaging to decrease jitter
            # cpu_temps = cpu_temps[1:] + [cpu_temp]
            # avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
            raw_temp = bme280.get_temperature()
            data = raw_temp - 5   #  - ((avg_cpu_temp - raw_temp) / factor)
            display_text(variables[mode], data, unit)

        if mode == 1:
            # variable = "pressure"
            unit = "hPa"
            data = bme280.get_pressure()
            display_text(variables[mode], data, unit)

        if mode == 2:
            # variable = "humidity"
            unit = "%"
            data = bme280.get_humidity()
            display_text(variables[mode], data, unit)

        if mode == 3:
            # variable = "light"
            unit = "Lux"
            if proximity < 10:
                data = ltr559.get_lux()
            else:
                data = 1
            display_text(variables[mode], data, unit)

        if mode == 4:
            # variable = "oxidised"
            unit = "kO"
            data = gas.read_all()
            data = data.oxidising / 1000
            display_text(variables[mode], data, unit)

        if mode == 5:
            # variable = "reduced"
            unit = "kO"
            data = gas.read_all()
            data = data.reducing / 1000
            display_text(variables[mode], data, unit)

        if mode == 6:
            # variable = "nh3"
            unit = "kO"
            data = gas.read_all()
            data = data.nh3 / 1000
            display_text(variables[mode], data, unit)

        if mode > 6 and mode != prev_mode:
            display_img()

        prev_mode = mode


# Exit cleanly
except KeyboardInterrupt:
    sys.exit(0)

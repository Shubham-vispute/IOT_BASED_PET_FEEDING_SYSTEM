#Name: Shubham Kishor Vispute
#ID :  2024HT01026
import RPi.GPIO as GPIO
import time
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont
import schedule
from datetime import datetime
from flask import Flask, request, render_template, jsonify
import threading

app = Flask(__name__)

# ---- Servo Setup ----
SERVO_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(SERVO_PIN, GPIO.OUT)

pwm = GPIO.PWM(SERVO_PIN, 50)  # 50 Hz PWM frequency for servo
pwm.start(0)

def set_servo_angle(angle):
    duty = angle / 18 + 2
    GPIO.output(SERVO_PIN, True)
    pwm.ChangeDutyCycle(duty)
    time.sleep(1)
    GPIO.output(SERVO_PIN, False)
    pwm.ChangeDutyCycle(0)

#For servo testing 
'''set_servo_angle(0)
time.sleep(2)
set_servo_angle(90)'''
# ---- OLED Setup (using luma.oled) ----
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, width=128, height=64)

width = device.width
height = device.height
image = Image.new('1', (width, height))

draw = ImageDraw.Draw(image)

header_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
body_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 12)

# Default pet name and feeding times
pet_name = "*LUCY*"
last_dispensed_time = None
next_dispensed_time = None
is_feeding = False

# Function to display on the OLED screen
def display_oled():
    draw.rectangle((0, 0, width, height), outline=0, fill=0)
    draw.text((5, 5), pet_name, font=header_font, fill=255)

    if last_dispensed_time is not None:
        draw.text((5, 30), f"Last: {last_dispensed_time}", font=body_font, fill=255)
    else:
        draw.text((5, 30), "Last: --:--", font=body_font, fill=255)

    if next_dispensed_time is not None:
        draw.text((5, 45), f"Next: {next_dispensed_time}", font=body_font, fill=255)
    else:
        draw.text((5, 45), "Next: --:--", font=body_font, fill=255)

    device.display(image)
    device.show()

def dispense_food():
    global last_dispensed_time, next_dispensed_time, is_feeding
    is_feeding = True
    print("Dispensing food...")

    set_servo_angle(90)
    time.sleep(2)
    set_servo_angle(0)

    last_dispensed_time = datetime.now().strftime("%H:%M")

    draw.rectangle((0, 30, width, height), outline=0, fill=0)
    draw.text((5, 30), "Dispensing food...", font=body_font, fill=255)
    device.display(image)
    device.show()

    time.sleep(5)

    update_next_feed_time()
    display_oled()
    is_feeding = False

def update_next_feed_time():
    global next_dispensed_time
    next_job = schedule.next_run()
    if next_job is not None:
        next_dispensed_time = next_job.strftime("%H:%M")
    else:
        next_dispensed_time = "--:--"

def reset_schedule(times):
    schedule.clear()
    for time in times:
        schedule.every().day.at(time).do(dispense_food)
    update_next_feed_time()
    display_oled()

# ---- Flask Web Routes ----

@app.route('/', methods=['GET', 'POST'])
def index():
    global pet_name

    if request.method == 'POST':
        # Get feeding times from form submission
        feed_times = request.form.getlist('feed_time')
        pet_name = request.form.get('pet_name')  # Get pet name from the form
        reset_schedule(feed_times)

    next_feed_time = schedule.next_run().strftime("%H:%M") if schedule.next_run() else '--:--'
    return render_template('index.html', pet_name=pet_name, next_feed_time=next_feed_time)

# Route to check if feeding is in progress (for page reload)
@app.route('/is_feeding', methods=['GET'])
def is_feeding_status():
    return jsonify({'feeding': is_feeding})

# ---- Threading for Flask and Servo Control ----

def flask_thread():
    # Start Flask server (use_reloader=False to avoid multiple threads issue with Flask's reloader)
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

def schedule_thread():
    try:
        update_next_feed_time()
        display_oled()

        # Servo control and scheduling loop
        while True:
            schedule.run_pending()
            display_oled()
            time.sleep(60)

    except KeyboardInterrupt:
        print("Program interrupted by user")

    finally:
        pwm.stop()
        GPIO.cleanup()

if __name__ == "__main__":
    # Create and start Flask thread
    flask_t = threading.Thread(target=flask_thread)
    flask_t.daemon = True
    flask_t.start()

    # Create and start Schedule (servo control) thread
    schedule_t = threading.Thread(target=schedule_thread)
    schedule_t.daemon = True
    schedule_t.start()

    # Keep the main thread alive
    while True:
        time.sleep(1)

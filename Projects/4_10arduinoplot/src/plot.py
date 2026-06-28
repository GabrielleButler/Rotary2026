import asyncio
import struct
import sys
from collections import deque

from bleak import BleakClient, BleakScanner
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets
from qasync import QEventLoop

# ---------------- CONFIG ----------------
DEVICE_NAME = "Nano33BLE_Z"   # matches BLE.setLocalName() in the sketch
Z_CHAR_UUID    = "12345678-1234-1234-1234-1234567890ac"
CMD_CHAR_UUID  = "12345678-1234-1234-1234-1234567890ad"

# ---------------- STATE ----------------
data = deque(maxlen=200)
ble_client: BleakClient | None = None

# ---------------- QT UI ----------------
app = QtWidgets.QApplication(sys.argv)

window = QtWidgets.QWidget()
window.setWindowTitle("IMU + Servo Control")
layout = QtWidgets.QVBoxLayout(window)

plot_widget = pg.PlotWidget(title="Z Acceleration (Real-Time)")
curve = plot_widget.plot()
layout.addWidget(plot_widget)

button_row = QtWidgets.QHBoxLayout()
start_button = QtWidgets.QPushButton("Start 8.5s Timer  ->  Servo 120°")
reset_button = QtWidgets.QPushButton("Reset Servo (back to 0°)")
start_button.setEnabled(False)
reset_button.setEnabled(False)
button_row.addWidget(start_button)
button_row.addWidget(reset_button)
layout.addLayout(button_row)

status_label = QtWidgets.QLabel("Status: connecting…")
layout.addWidget(status_label)

window.resize(900, 600)
window.show()

# ---------------- BLE CALLBACK ----------------
def handle_data(sender, raw):
    try:
        z = struct.unpack('<f', raw)[0]
        data.append(z)
    except Exception as e:
        print("Parse error:", e)

# ---------------- BLE TASK ----------------
async def run_ble():
    global ble_client
    print(f"Scanning for {DEVICE_NAME}...")
    status_label.setText(f"Status: scanning for {DEVICE_NAME}…")

    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15.0)
    if device is None:
        msg = f"Device '{DEVICE_NAME}' not found. Is the Arduino powered and advertising?"
        print(msg)
        status_label.setText(f"Status: {msg}")
        return

    print(f"Found {device.name} at {device.address}, connecting...")
    status_label.setText("Status: found device, connecting…")

    try:
        async with BleakClient(device, timeout=15.0) as client:
            ble_client = client
            print("Connected!")
            status_label.setText("Status: connected")
            start_button.setEnabled(True)
            reset_button.setEnabled(True)

            await client.start_notify(Z_CHAR_UUID, handle_data)

            while client.is_connected:
                await asyncio.sleep(0.1)
    except Exception as e:
        print("BLE error:", e)
        status_label.setText(f"Status: error — {e}")
    finally:
        ble_client = None
        start_button.setEnabled(False)
        reset_button.setEnabled(False)
        status_label.setText("Status: disconnected")
# ---------------- COMMAND SENDERS ----------------
async def send_command(value: int, message: str):
    if ble_client is None or not ble_client.is_connected:
        status_label.setText("Status: not connected")
        return
    try:
        await ble_client.write_gatt_char(CMD_CHAR_UUID, bytes([value]), response=True)
        status_label.setText(f"Status: {message}")
        print(f"Sent command {value}")
    except Exception as e:
        print("Write error:", e)
        status_label.setText(f"Status: write error — {e}")

def on_start_clicked():
    asyncio.ensure_future(send_command(1, "command sent — 8.5s countdown running"))

def on_reset_clicked():
    asyncio.ensure_future(send_command(0, "reset sent — servo back to 0°"))

start_button.clicked.connect(on_start_clicked)
reset_button.clicked.connect(on_reset_clicked)

# ---------------- GRAPH UPDATE LOOP ----------------
def update_plot():
    curve.setData(list(data))

timer = pg.QtCore.QTimer()
timer.timeout.connect(update_plot)
timer.start(20)

# ---------------- ENTRY POINT ----------------
loop = QEventLoop(app)
asyncio.set_event_loop(loop)
with loop:
    loop.create_task(run_ble())
    loop.run_forever()
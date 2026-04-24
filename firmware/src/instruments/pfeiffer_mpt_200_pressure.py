"""
Pfeiffer MPT 200 Pressure Gauge interface.
https://www.idealvac.com/files/manuals/Pfeiffer_DigiLine_MPT_200_Digital_Pirani_and_Cold_Cathode_Gauge_Operating_Instructions.pdf?srsltid=AfmBOooqAOLpdE1_6SxWnc5I48YBapWUSsZtYP3KCMQqCVCheb-VDX_3
"""

from src.instrument import BaseInstrument

import serial
import sys
import os

ERROR_TIMEOUT = 10  # Seconds to wait before retrying after an error
REPETITION_TIME = 2  # Seconds to wait before requesting another datapoint

################################################################################
# Message construction helpers


def calc_checksum(msg: str) -> str:
    checksum = sum(ord(c) for c in msg) % 256
    return f"{checksum:03d}"


def validate_pressure_read_command(full_msg):
    expecting = [48, 48, 49, 48, 48, 55, 52, 48, 48, 50, 61, 63, 49, 48, 54, 13]
    for ii, c in enumerate(full_msg):
        if expecting[ii] != ord(c):
            print(f"Oh no! Was expecting {expecting[ii]} got {ord(c)}")
            return False
    return True


def get_pressure_read_command():
    addr = "001"
    action = "00"
    parameter = "740"
    data_length = "02"
    data_type = "=?"
    base = f"{addr}{action}{parameter}{data_length}{data_type}"

    checksum = calc_checksum(base)
    full_msg = base + checksum + "\r"

    if not validate_pressure_read_command(full_msg):
        print("Invalid pressure read command")
        sys.exit()

    return full_msg


################################################################################
# Message processing helpers


def process_pressure(data):
    # Pressure value [] are transmitted by means of a strin in the format 'aaaabb'
    # Whereby 'aaaa' is the mantissa and 'bb' is the exponent with an offset 20 of an exponential number
    # 'aaaa' is therefore in the range '1000' (for 1.000) to '9999' (for 9.999)
    # The individual characters of the string are the nubmers "0" ASCII 48 to "9" ASCII 57
    mantissa = float(data[0:4]) / 1000
    exponent_offset = float(data[4:6])

    exponent = exponent_offset - 20
    pressure = mantissa * 10**exponent

    return pressure


def validate_pressure():
    if process_pressure(b"104223") != 1.042e3:
        print("Process pressure calculation failed to validate check 1")
        sys.exit()
    if process_pressure(b"750015") != 7.500000000000001e-5:  # floating point yay
        print("Process pressure calculation failed to validate check 2")
        sys.exit()


def validate_response(addr, action, parameter, data_length, data):
    if addr != b"001":
        print("Wrong addr returned")
    if action != b"10":
        print("Wrong action returned")
    if parameter != b"740":
        print("Wrong paramter returned")
    if data_length != b"06":
        print("Wrong data length returned")
    if len(data) != 6:
        print("Data of wrong length returned")
    return


def process_response(response):
    addr = response[0:3]
    action = response[
        3:5
    ]  # Next two bits should be 10 (guessing 10 is data response action)
    parameter = response[5:8]  # Should be same as sent i.e. 740
    data_length = response[8:10]  # length of reponse - should be 06
    data = response[10:16]  # The returned data
    checksum = response[16:18]

    print("Reponse processing:")
    print(f"  Address: {addr}, action: {action}, parameter: {parameter}")
    print(f"  Data length: {data_length}, data: {data}")
    print(f"  Checksum {checksum}")
    validate_response(addr, action, parameter, data_length, data)

    validate_pressure()
    pressure = process_pressure(data)
    return pressure


################################################################################
# Get Pressure (main method)
def get_pressure(device):
    try:
        with serial.Serial(device, 9600, timeout=1) as ser:
            command = get_pressure_read_command()
            ser.write(command.encode("ascii"))
            response = ser.read(64)  # Adjust as needed
            if not response:
                print(f"No response from pressure gauge on {device}")
                return None
                
            print(f"Response from {device}:", response.decode("ascii", errors="replace"))

            pressure = process_response(response)
            print(f"Pressure is {pressure}")
            return float(pressure)
    except Exception as e:
        print(f"Error reading pressure from {device}: {e}")
        return None


class Instrument(BaseInstrument):

    def __init__(self):
        pass

    def go_to_setpoint(self, state):
        setpoint = state.status["setpoint"]
        print(f"Setting upstream pressure to {setpoint} - not supported!")

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        # Get device address from state config
        device = state.config.get("DEVICE_ADDRESS")
        if device is None:
            print("WARNING: DEVICE_ADDRESS not in state.config, falling back to /dev/ttyUSB0")
            device = "/dev/ttyUSB0"

        # Get the pressure
        measurement = get_pressure(device)
        if measurement is not None:
            state.measurement = measurement
            return {"pressure": measurement}
        else:
            return {"pressure": 0.0}

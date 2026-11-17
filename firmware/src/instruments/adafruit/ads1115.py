"""
TI ADS1115 ADC (Raspberry Pi HAT) reading four 4-20 mA current-loop signals:
input/output ammeters and input/output voltmeters with 4-20 mA transmitter outputs.
https://www.ti.com/product/ADS1115
https://docs.circuitpython.org/projects/ads1x15/en/latest/

Each 4-20 mA loop is read as the voltage across a precision burden resistor on one
ADS1115 input, converted back to mA, then scaled to the meter's engineering unit.
Loop currents outside the 4-20 mA band (open loop, transmitter fault) are reported
as a failed measurement (None), which sets the instrument status to `error`.

ADDRESS is the ADS1115's I2C address (e.g. "0x48"); it defaults to 0x48 if unset.
All variables are sensors only: none of them can be set.
"""

# System imports
import math
import threading
import time
from typing import ClassVar

# Instrument specific imports
# `board` and `busio` (Adafruit Blinka) only import on supported hardware, so they
# are imported in `connect_ads1115` instead, keeping simulation runnable anywhere.
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# Local imports
from src.instrument import BaseInstrument


# ======================================================================================
# Instrument Class
# --------------------------------------------------------------------------------------
class Instrument(BaseInstrument):
    # sensor: ADS1115 input (A0-A3) and the meter's reading at 4 mA and at 20 mA.
    # Check each meter's datasheet/nameplate for its 4 mA and 20 mA values.
    available_variables: ClassVar[dict[str, dict]] = {
        "input_current": {
            "sensor": {"channel": 3, "eng_min": 0.0, "eng_max": 13.0},  # A
            "actuator": None,
        },
        "output_current": {
            "sensor": {"channel": 2, "eng_min": 0.0, "eng_max": 200.0},  # A
            "actuator": None,
        },
        "input_voltage": {
            "sensor": {"channel": 1, "eng_min": 0.0, "eng_max": 300.0},  # V
            "actuator": None,
        },
        "output_voltage": {
            "sensor": {"channel": 0, "eng_min": 0.0, "eng_max": 200.0},  # V
            "actuator": None,
        },
    }

    def initialise(self):
        self.ads = None
        self.inputs = {}
        # Measurement ticks for different variables share one I2C bus and ADC
        self.lock = threading.Lock()
        self.sim_start = time.time()
        if self.config["SIMULATE"]:
            return
        self.i2c_address = parse_i2c_address(None)
        # If it can't connect now, it tries again on each measurement
        self.connect()

    def connect(self):
        try:
            self.ads, self.inputs = connect_ads1115(self.i2c_address)
            print(f"Connected to ADS1115 at I2C address {hex(self.i2c_address)}")
            return True
        except Exception as e:
            self.ads, self.inputs = None, {}
            print(
                f"Could not connect to ADS1115 at I2C address {hex(self.i2c_address)}: {e}\n"
                "Check that I2C is enabled (raspi-config), the HAT is seated, and "
                "'i2cdetect -y 1' shows the address."
            )
            return False

    def simulate(self, variable):
        # With a setpoint or an external actuator, converge towards it as usual
        if (
            self.setpoints.get(variable) is not None
            or variable in self.config["EXTERNAL_ACTUATORS"]
        ):
            return self.default_sim(variable)
        # Otherwise, a slowly varying 4-20 mA signal, run through the same conversion
        # as the real readings
        sensor = self.available_variables[variable]["sensor"]
        t = time.time() - self.sim_start
        ma = 12.0 + 7.5 * math.sin(t / 6.0 + sensor["channel"] * 1.3)
        return ma_to_engineering(ma, sensor)

    def get_measurement(self, variable):
        sensor = self.available_variables[variable]["sensor"]
        with self.lock:
            if self.ads is None and not self.connect():
                return None
            try:
                voltage = self.inputs[sensor["channel"]].voltage
            except Exception as e:
                print(f"Error reading ADS1115 channel A{sensor['channel']}: {e}")
                return None

        ma = voltage_to_ma(voltage)
        fault = loop_fault(ma)
        if fault:
            print(f"Loop fault on '{variable}' (A{sensor['channel']}): {ma:.2f} mA, {fault}")
            return None
        return ma_to_engineering(ma, sensor)

    def go_to_setpoint(self, variable, setpoint):
        # Never called: every variable has `actuator: None`
        raise NotImplementedError(
            f"ADS1115 has no actuator: '{variable}' cannot be set to {setpoint}."
        )


# ======================================================================================

# ======================================================================================
# ADS1115 configuration and helper functions
# --------------------------------------------------------------------------------------
DEFAULT_I2C_ADDRESS = 0x48  # ADDR pin tied to GND, the default on most HATs

# Precision burden resistor (ohms) across each input: V = I * R.
# With GAIN = 1 (+/-4.096 V full scale) and the ADS1115 powered from 3.3 V, keep
# 20 mA * R below ~3.3 V. For a 5 V supply and a 250 ohm resistor, use GAIN = 2/3.
BURDEN_RESISTOR_OHMS = 160.0
GAIN = 1

# Loop current outside this band is a fault, not a reading:
# below 4 mA usually means an open loop, above 20 mA a transmitter fault.
LOW_FAULT_MA = 3.8
HIGH_FAULT_MA = 20.5


# --------------------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------------------
def parse_i2c_address(address):
    """
    Returns the I2C address as an int, from e.g. "0x48", "72" or 72.
    """
    if address in (None, ""):
        return DEFAULT_I2C_ADDRESS
    if isinstance(address, int):
        return address
    return int(str(address).strip(), 0)


def connect_ads1115(i2c_address):
    """
    Opens the ADS1115 and returns it, with an AnalogIn for each of its 4 inputs.
    Raises an exception if it can't be opened.
    """
    import board
    import busio

    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c, address=i2c_address, gain=GAIN)
    inputs = {channel: AnalogIn(ads, channel) for channel in range(4)}
    return ads, inputs


def voltage_to_ma(voltage):
    return voltage / BURDEN_RESISTOR_OHMS * 1000.0


def ma_to_engineering(ma, sensor):
    span = sensor["eng_max"] - sensor["eng_min"]
    return sensor["eng_min"] + (ma - 4.0) / 16.0 * span


def loop_fault(ma):
    """
    Returns a description of the loop fault, or None if the current is in range.
    """
    if ma < LOW_FAULT_MA:
        return "LOW (open loop?)"
    if ma > HIGH_FAULT_MA:
        return "HIGH (transmitter fault?)"
    return None


# ======================================================================================

"""
TI ADS1115 ADC (Raspberry Pi HAT) reading four 4-20 mA current-loop signals:
input/output ammeters and input/output voltmeters with 4-20 mA transmitter outputs.
https://www.ti.com/product/ADS1115
https://docs.circuitpython.org/projects/ads1x15/en/latest/

Each 4-20 mA loop is read as the voltage across a precision burden resistor on one
ADS1115 input, converted back to mA, then scaled to the meter's engineering unit,
using the variable's range (VARIABLE_RANGES, from min and max in comodo.yaml) as the
meter's readings at 4 mA and at 20 mA. Readings are clamped to that range.
Loop currents at the NAMUR NE43 failure levels (open loop, transmitter fault) are
reported as a failed measurement (None), which sets the instrument status to `error`.

ADDRESS is the I2C bus device (e.g. "/dev/i2c-1"), and DEVICE_ID the ADS1115's I2C address
on it (e.g. "0x48"), which defaults to 0x48 if unset.
All variables are sensors only: none of them can be set.
In simulation, the input voltage is fixed at mains (MAINS_VOLTAGE), and the other variables
follow the "power" simulation input. If no input is available, a default signal is used.
"""

# System imports
import math
import re
import time
from typing import ClassVar

# Instrument specific imports
# `adafruit_extended_bus` (Adafruit Blinka) only imports on supported hardware, so it
# is imported in `connect_ads1115` instead, keeping simulation runnable anywhere.
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# Local imports
from src.instrument import BaseInstrument


# ======================================================================================
# Instrument Class
# --------------------------------------------------------------------------------------
class Instrument(BaseInstrument):
    # sensor: ADS1115 input (A0-A3) of each meter.
    # The meter's readings at 4 mA and at 20 mA are the variable's min and max in comodo.yaml
    # (check each meter's datasheet/nameplate for them).
    available_variables: ClassVar[dict[str, dict]] = {
        "input_current": {"sensor": {"channel": 3}},  # A
        "output_current": {"sensor": {"channel": 2}},  # A
        "input_voltage": {"sensor": {"channel": 1}},  # V
        "output_voltage": {"sensor": {"channel": 0}},  # V
    }

    def initialise(self):
        self.ads = None
        self.inputs = {}
        self.sim_start = time.time()
        # The readings are scaled with each variable's range
        missing = [
            variable
            for variable in self.config["ACTIVE_VARIABLES"]
            if variable not in self.config["VARIABLE_RANGES"]
        ]
        if missing:
            raise ValueError(
                f"Missing the range (min and max) of {', '.join(missing)}: "
                "they are the meter's readings at 4 mA and at 20 mA."
            )
        if self.config["SIMULATE"]:
            return
        self.i2c_bus = parse_i2c_bus(self.config["ADDRESS"])
        self.i2c_address = parse_i2c_address(self.config["DEVICE_ID"])
        # If it can't connect now, it tries again on each measurement
        self.connect()

    def connect(self):
        try:
            self.ads, self.inputs = connect_ads1115(self.i2c_bus, self.i2c_address)
            print(f"Connected to ADS1115 at {self.where()}")
            return True
        except Exception as e:
            self.ads, self.inputs = None, {}
            print(
                f"Could not connect to ADS1115 at {self.where()}: {e}\n"
                "Check that I2C is enabled (raspi-config), the HAT is seated, and "
                f"'i2cdetect -y {self.i2c_bus}' shows the address."
            )
            return False

    def where(self):
        return f"I2C bus {self.i2c_bus}, address {hex(self.i2c_address)}"

    def simulate(self, variable):
        variable_range = self.config["VARIABLE_RANGES"][variable]
        if variable == "input_voltage":
            # Mains, before the power controller: fixed
            return min(max(MAINS_VOLTAGE, variable_range["min"]), variable_range["max"])
        # Other variables: a 4-20 mA signal, run through the same conversion as the real readings
        # If a simulation input is provided (and measured)
        power = self.simulation_input("power")
        if isinstance(power, (int, float)) and not isinstance(power, bool):
            # Voltage and current both scale with the square root of the power,
            # as a fraction of the simulation input's range
            power_range = self.config["SIMULATION_INPUTS"]["power"]
            fraction = (power - power_range["min"]) / (
                power_range["max"] - power_range["min"]
            )
            ma = 4.0 + 16.0 * math.sqrt(min(max(fraction, 0.0), 1.0))
        else:
            # If no simulation input is available, use a default signal
            sensor = self.available_variables[variable]["sensor"]
            t = time.time() - self.sim_start
            ma = 12.0 + 7.5 * math.sin(t / 6.0 + sensor["channel"] * 1.3)
        return ma_to_engineering(ma, variable_range)

    def get_measurement(self, variable):
        sensor = self.available_variables[variable]["sensor"]
        if self.ads is None and not self.connect():
            return None
        try:
            voltage = self.inputs[sensor["channel"]].voltage
        except Exception as e:
            # Reconnect on the next measurement, in case the connection was lost
            self.ads, self.inputs = None, {}
            print(
                f"Error reading ADS1115 channel A{sensor['channel']}: {e}. Reconnecting."
            )
            return None

        ma = voltage_to_ma(voltage)
        fault = loop_fault(ma)
        if fault:
            print(
                f"Loop fault on '{variable}' (A{sensor['channel']}): {ma:.2f} mA, {fault}"
            )
            return None
        return ma_to_engineering(ma, self.config["VARIABLE_RANGES"][variable])

    def go_to_setpoint(self, variable, setpoint):
        # No actuators available
        pass


# ======================================================================================

# ======================================================================================
# ADS1115 configuration and helper functions
# --------------------------------------------------------------------------------------
DEFAULT_I2C_ADDRESS = 0x48  # ADDR pin tied to GND, the default on most HATs
MAINS_VOLTAGE = 230.0  # V, the simulated input voltage

# Precision burden resistor (ohms) across each input: V = I * R.
# With GAIN = 1 (+/-4.096 V full scale) and the ADS1115 powered from 3.3 V, keep
# 20 mA * R below ~3.3 V. For a 5 V supply and a 250 ohm resistor, use GAIN = 2/3.
BURDEN_RESISTOR_OHMS = 160.0
GAIN = 1

# Loop currents at the NAMUR NE43 failure levels are a fault, not a reading:
# at or below 3.6 mA usually means an open loop, at or above 21 mA a transmitter fault.
# In between, readings outside 4-20 mA are clamped to the variable's range.
LOW_FAULT_MA = 3.6
HIGH_FAULT_MA = 21.0


# --------------------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------------------
def parse_i2c_bus(address):
    """
    Returns the I2C bus number from its device, e.g. 1 from "/dev/i2c-1".
    """
    match = re.fullmatch(r"/dev/i2c-(\d+)", str(address).strip())
    if match is None:
        raise ValueError(
            f"Invalid ADS1115 address '{address}'. Expected an I2C bus device, e.g. /dev/i2c-1."
        )
    return int(match.group(1))


def parse_i2c_address(address):
    """
    Returns the I2C address as an int, from e.g. "0x48", "72" or 72.
    """
    if address in (None, ""):
        return DEFAULT_I2C_ADDRESS
    if isinstance(address, int):
        return address
    return int(str(address).strip(), 0)


def connect_ads1115(i2c_bus, i2c_address):
    """
    Opens the ADS1115 on the I2C bus, and returns it with an AnalogIn for each of its 4 inputs.
    Raises an exception if it can't be opened.
    """
    from adafruit_extended_bus import ExtendedI2C

    i2c = ExtendedI2C(i2c_bus)
    ads = ADS.ADS1115(i2c, address=i2c_address, gain=GAIN)
    inputs = {channel: AnalogIn(ads, channel) for channel in range(4)}
    return ads, inputs


def voltage_to_ma(voltage):
    return voltage / BURDEN_RESISTOR_OHMS * 1000.0


def ma_to_engineering(ma, variable_range):
    """
    Returns the reading for the loop current, scaled linearly from 4-20 mA to the
    variable's range (min at 4 mA, max at 20 mA), and clamped to it.
    """
    ma = min(max(ma, 4.0), 20.0)
    span = variable_range["max"] - variable_range["min"]
    return variable_range["min"] + (ma - 4.0) / 16.0 * span


def loop_fault(ma):
    """
    Returns a description of the loop fault, or None if the current is in range.
    """
    if ma <= LOW_FAULT_MA:
        return "LOW (open loop?)"
    if ma >= HIGH_FAULT_MA:
        return "HIGH (transmitter fault?)"
    return None


# ======================================================================================

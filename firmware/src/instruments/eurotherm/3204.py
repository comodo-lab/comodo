"""
Eurotherm 3204 Temperature Controller interface.

Modbus RTU over serial.
"""

# System imports
from typing import ClassVar

# Instrument specific imports
import serial
from pymodbus.client import ModbusSerialClient

# Local imports
from src.instrument import BaseInstrument


# ======================================================================================
# Instrument Class
# --------------------------------------------------------------------------------------
class Instrument(BaseInstrument):
    available_variables: ClassVar[dict[str, dict]] = {
        "temperature": {
            "sensor": 0,
            "actuator": 1,
        },
    }

    def initialise(self):
        if self.config["SIMULATE"]:
            self.client = None
        else:
            self.client = ModbusSerialClient(
                port=self.config["ADDRESS"],
                baudrate=BAUDRATE,
                bytesize=BYTESIZE,
                parity=PARITY,
                stopbits=STOPBITS,
                timeout=TIMEOUT,
            )
            # If it can't connect now, the client tries again on each read or write
            if self.client.connect():
                print(
                    f"Connected to Eurotherm 3204 on {self.config['ADDRESS']} (device {DEVICE_ID})"
                )
            else:
                print(
                    f"Could not connect to Eurotherm 3204 on {self.config['ADDRESS']}"
                )

    def simulate(self, variable):
        return self.default_sim(variable)

    def get_measurement(self, variable):
        return read_register(self.client, self.available_variables[variable]["sensor"])

    def go_to_setpoint(self, variable, setpoint):
        write_register(
            self.client,
            self.available_variables[variable]["actuator"],
            setpoint,
        )


# ======================================================================================

# ======================================================================================
# 3204 configuration and helper functions
# --------------------------------------------------------------------------------------
DEVICE_ID = 1  # Modbus address of the controller
MODBUS_REGISTER_COUNT = 1
BAUDRATE = 9600
BYTESIZE = serial.EIGHTBITS
PARITY = serial.PARITY_NONE
STOPBITS = serial.STOPBITS_ONE
TIMEOUT = 1  # seconds


# --------------------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------------------
def read_register(client, register):
    """
    Returns the register's value, or None if it can't be read.
    """
    try:
        result = client.read_holding_registers(
            address=register, count=MODBUS_REGISTER_COUNT, device_id=DEVICE_ID
        )
        if result.isError():
            raise ValueError(result)
        return float(result.registers[0])
    except Exception as e:
        print(f"Error reading register {register}: {e}")
        return None


def write_register(client, register, value):
    """
    Writes the value to the register, raising an exception if it can't be written.
    """
    result = client.write_register(
        address=register, value=int(value), device_id=DEVICE_ID
    )
    if result.isError():
        raise ValueError(f"Error writing register {register}: {result}")


# ======================================================================================

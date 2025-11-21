"""
Bronkhorst EL-FLOW Select Mass Flow Meter interface.
https://prod-bronkhorst-products-cdn-ccdwbfhmd0gfecfb.a02.azurefd.net/media/3u4iwfxh/917099-manual-el-flow-select.pdf
"""

import os
import fcntl
from contextlib import contextmanager

from sensor import BaseSensor
import propar
import time

ERROR_TIMEOUT = 10
REPETITION_TIME = 2

LOCK_FILE = os.environ.get("MASSFLOW_LOCK_FILE", "/lock/massflow.lock")

DELAY_TIME = 0.05  # Seconds to wait before accessing the instrument


@contextmanager
def serial_lock():
    """
    Cross-process lock using flock on a shared file.

    All propar calls to the same device must be wrapped in this.
    """
    fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


ERROR_TIMEOUT = 10  # Seconds to wait before retrying after an error
REPETITION_TIME = 2  # Seconds to wait before requesting another datapoint

# Generated from https://prod-bronkhorst-products-cdn-ccdwbfhmd0gfecfb.a02.azurefd.net/media/3u4iwfxh/917099-manual-el-flow-select.pdf
PARAMETER_MAPPING = {
    # Measurement and Control
    "8": {
        "name": "Flow_Rate_Measured",
        "type": "unsigned int",
        "access": "R",
        "range": "0 – 41942",
        "units": "%",
        "notes": "The value is a percentage of the full scale of the flow meter. 100% = 32000",
    },
    "9": {
        "name": "Flow_Rate_Setpoint",
        "type": "unsigned int",
        "access": "RW",
        "range": "0 – 32000",
        "units": "%",
        "notes": "The value is a percentage of the full scale of the flow meter. 100% = 32000",
    },
    "142": {
        "name": "Temperature",
        "type": "float",
        "access": "R",
        "range": "-250 - 500",
        "units": "°C",
        "notes": "Internal temperature in the instrument housing, approximation of the actual media temperature."
    },
    "143": {
        "name": "Pressure",
        "type": "float",
        "access": "RW",
        "range": "0 – 3.4E+38",
        "units": "bar",
        "notes": "In case an external pressure sensor is connected, this parameter returns the actual system pressure in bar(a). If there is no external pressure sensor, the default value of this parameter is equal to parameter Inlet pressure.",
    },
    # Advanced Measurement and Control
    "205": {
        "name": "Fmeasure",
        "type": "float",
        "access": "R",
        "range": "-3.4E+38 – 3.4E+38",
        "units": "From Capacity Unit",
        "notes": "The actual flow rate measured by the instrument, in the unit specified by the Capacity Unit parameter."
    },
    "206": {
        "name": "Fsetpoint",
        "type": "float",
        "access": "RW",
        "range": "0 – 3.4E+38",
        "units": "From Capacity Unit",
        "notes": "The flow rate setpoint for the instrument, in the unit specified by the Capacity Unit parameter."
    },
    "10": {
        "name": "Setpoint_Slope",
        "type": "unsigned int",
        "access": "RW",
        "range": "0 – 30000",
        "units": "s",
        "notes": "The time in seconds to go from 0-100% setpoint for flow rate adjustment. A value of 0 means no slope, i.e., the setpoint is reached immediately."
    },
    "122": {
        "name": "Counter_Value",
        "type": "float",
        "access": "RW",
        "range": "0 – 10000000",
        "unit": "From Counter Unit",
        "notes": "Current counter value in units selected with parameter Counter Unit."
    },
    "124": {
        "name": "Counter_Limit",
        "type": "float",
        "access": "RW",
        "range": "0 – 9999999",
        "unit": "From Counter Unit",
        "notes": "The limit for the counter. When the counter reaches this value, it will stop counting."
    },
    # Fluid Set
    "21": {
        "name": "Capacity_100_Percent",
        "type": "float",
        "access": "RW B",
        "range": "1E-10 – 1E+10",
        "unit": "From Capacity Unit",
        "notes": "The 100 % readout/control value (span), expressed in the Capacity Unit of the selected fluid",
    },
    # Advanced Fluid Set Parameters
    "178": {
        "name": "Inlet_Pressure",
        "type": "float",
        "access": "RW B",
        "range": "0 – 3.4E+38",
        "units": "bar",
        "notes": "Upstream pressure of the selected fluid in bar(a)."
    },
    "179": {
        "name": "Outlet_Pressure",
        "type": "float",
        "access": "RW B",
        "range": "0 – 3.4E+38",
        "units": "bar",
        "notes": "Downstream pressure of the selected fluid in bar(a)."
    },
    "181": {
        "name": "Fluid_Temperature",
        "type": "float",
        "access": "RW B",
        "range": "-250 – 500",
        "units": "°C",
        "notes": "The temperature of the selected fluid."
    },
}

# -------------------------------------------------------------------
# EL-Flow Select Functions
# -------------------------------------------------------------------


def read_parameter(channel):
    """
    Reads a parameter from the EL-Flow Select instrument.

    :param instrument: The propar instrument object.
    :param channel: The channel number to read.
    :return: The value of the parameter.
    """
    try:
        with serial_lock():
            try:
                # Register to /dev/ttyUSB2
                time.sleep(DELAY_TIME)
                print('Connecting to EL-Flow Select instrument')
                instrument = propar.instrument('/dev/ttyUSB2')
                print('Connected to EL-Flow Select instrument')
            except Exception as e:
                print(f'Error initializing propar.Instrument!\n{e}')
                return None
            # Wait for delay time before reading
            time.sleep(DELAY_TIME)
            print(f'Reading channel {channel}') 
            value = instrument.readParameter(int(channel))
            print(f' Value of channel is {value} with type {type(value)}')
        return value
    except Exception as e:
        print(f"Error reading channel {channel}: {e}")
        return None


def read_general(name):
    """
    Reads a general parameter from the EL-Flow Select instrument by name.

    :param instrument: The propar instrument object.
    :param name: The name of the parameter to read.
    :return: The value of the parameter if found, None otherwise.
    """
    for channel, info in PARAMETER_MAPPING.items():
        if info['name'] == name:
            if 'R' not in info['access']:
                print(f"Parameter {name} is not readable.")
                return None
            return read_parameter(int(channel))
    print(f"Parameter {name} not found in mapping.")
    return None


def write_param(channel, value):
    """
    Writes a parameter to the EL-Flow Select instrument.

    :param instrument: The propar instrument object.
    :param channel: The channel number to write.
    :param value: Value to write to channel
    :return: The value of the parameter if written, None if error.
    """
    try:
        with serial_lock():
            try:
                # Register to /dev/ttyUSB2
                time.sleep(DELAY_TIME)
                print('Connecting to EL-Flow Select instrument')
                instrument = propar.instrument('/dev/ttyUSB2')
                print('Connected to EL-Flow Select instrument')
            except Exception as e:
                print(f'Error initializing propar.Instrument!\n{e}')
            # Wait for delay time before writing
            time.sleep(DELAY_TIME)
            # TODO - Check this is the correct syntax for write to instrument
            write = instrument.writeParameter(int(channel), value)
        return write
    except Exception as e:
        print(f"Error writing {value} to channel {channel}: {e}")
        return None


def write_param_protected(channel, value):
    """
    Unlocks secured params for write

    :param instrument: The propar insturment object
    :param channel: The channel number to read.
    :param value: Value to write to channel
    :return: The value of the parameter if written, None if error.
    """
    try:
        try:
            # Register to /dev/ttyUSB2
            time.sleep(DELAY_TIME)
            print('Connecting to EL-Flow Select instrument')
            instrument = propar.instrument('/dev/ttyUSB2')
            print('Connected to EL-Flow Select instrument')
        except Exception as e:
            print(f'Error initializing propar.Instrument!\n{e}')
            return None
        # TODO - Check this is the correct syntax for write to instrument
        unlock = write_param(instrument, 7, 64)  # Unlock protected write
        if unlock is None:
            raise PermissionError('Could not unlock protected write param')

        write = write_param(instrument, channel, value)

        lock = write_param(instrument, 7, 82)  # Lock protected write
        if lock is None:
            raise PermissionError('Could not lock protected write param')
        return write

    except Exception as e:
        print(f"Error writing {value} to protected channel {channel}: {e}")
        return None


def write_general(instrument, name, value):
    """
    Writes a general parameter to the EL-Flow Select instrument by name.

    :param instrument: The propar instrument object.
    :param name: The name of the parameter to write.
    :param value: Value to write to channel
    :return: The value of the parameter if written, None if error.
    """
    for channel, info in PARAMETER_MAPPING.items():
        if info['name'] == name:
            if 'W' not in info['access']:
                print(f"Parameter {name} is not writable.")
                return None
            if 'B' in info['access']:
                return write_param_protected(instrument, int(channel), value)
            else:
                return write_param(instrument, int(channel), value)
    print(f"Parameter {name} not found in mapping.")
    return None


# -------------------------------------------------------------------
# Main Function
# -------------------------------------------------------------------


@BaseSensor.register_sensor("massflow")
class MassFlow(BaseSensor):

    def __init__(self):
        return

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        flow_rate = (read_general("Flow_Rate_Measured") / 41942) * 100  # Convert to percentage
        if flow_rate is None:
            print("Failed to read Flow_Rate_Measured.")
            return None

        state.measurement = flow_rate
        return flow_rate

    def go_to_setpoint(self, setpoint):
        print('Not addded yet - testing')
        return None
    # def go_to_setpoint(self, setpoint):
    #     if self.instrument is None:
    #         print("Instrument not initialized.")
    #         return None

    #     if not (0 <= setpoint <= 100):
    #         print("Setpoint must be between 0 and 100%.")
    #         return None

    #     # Convert percentage to instrument scale (0-32000)
    #     instrument_setpoint = (setpoint / 100) * 32000
    #     result = write_general(self.instrument, "Flow_Rate_Setpoint", int(instrument_setpoint))
    #     if result is None:
    #         print("Failed to write Flow_Rate_Setpoint.")
    #         return None

    #     print(f"Set Flow_Rate_Setpoint to {setpoint}% ({int(instrument_setpoint)} in instrument scale).")
    #     return result


@BaseSensor.register_sensor("massflow_temp")
class MassFlowTemp(BaseSensor):

    def __init__(self):
        return

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        temperature = read_general("Temperature")
        if temperature is None:
            print("Failed to read Temperature.")
            return None

        state.measurement = temperature
        return temperature

    def go_to_setpoint(self, setpoint):
        print("MassFlowTemp does not support setting a setpoint.")
        return None


@BaseSensor.register_sensor("massflow_pressure_upstream")
class MassFlowPressureUpstream(BaseSensor):

    def __init__(self):
        return

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        pressure = read_general("Inlet_Pressure")
        if pressure is None:
            print("Failed to read Inlet_Pressure.")
            return None

        state.measurement = pressure
        return pressure

    def go_to_setpoint(self, setpoint):
        print("MassFlowPressureUpstream does not support setting a setpoint.")
        return None


@BaseSensor.register_sensor("massflow_pressure_downstream")
class MassFlowPressureDownstream(BaseSensor):

    def __init__(self):
        return

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        pressure = read_general("Outlet_Pressure")
        if pressure is None:
            print("Failed to read Outlet_Pressure.")
            return None

        state.measurement = pressure
        return pressure

    def go_to_setpoint(self, setpoint):
        print("MassFlowPressureDownstream does not support setting a setpoint.")
        return None


@BaseSensor.register_sensor("massflow_fluid_temp")
class MassFlowFluidTemp(BaseSensor):

    def __init__(self):
        return

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        temperature = read_general("Fluid_Temperature")
        if temperature is None:
            print("Failed to read Fluid_Temperature.")
            return None

        state.measurement = temperature
        return temperature

    def go_to_setpoint(self, setpoint):
        print("MassFlowFluidTemp does not support setting a setpoint.")
        return None

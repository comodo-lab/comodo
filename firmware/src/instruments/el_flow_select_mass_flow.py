"""
Bronkhorst EL-FLOW Select Mass Flow Meter interface.
https://prod-bronkhorst-products-cdn-ccdwbfhmd0gfecfb.a02.azurefd.net/media/3u4iwfxh/917099-manual-el-flow-select.pdf
"""

from src.instrument import BaseInstrument

import propar
import json
import os

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
        "notes": "Internal temperature in the instrument housing, approximation of the actual media temperature.",
    },
    "143": {
        "name": "Pressure",
        "type": "float",
        "access": "RW",
        "range": "0 – 3.4E+38",
        "units": "bar",
        "notes": "In case an external pressure instrument is connected, this parameter returns the actual system pressure in bar(a). If there is no external pressure instrument, the default value of this parameter is equal to parameter Inlet pressure.",
    },
    # Advanced Measurement and Control
    "205": {
        "name": "Fmeasure",
        "type": "float",
        "access": "R",
        "range": "-3.4E+38 – 3.4E+38",
        "units": "From Capacity Unit",
        "notes": "The actual flow rate measured by the instrument, in the unit specified by the Capacity Unit parameter.",
    },
    "206": {
        "name": "Fsetpoint",
        "type": "float",
        "access": "RW",
        "range": "0 – 3.4E+38",
        "units": "From Capacity Unit",
        "notes": "The flow rate setpoint for the instrument, in the unit specified by the Capacity Unit parameter.",
    },
    "10": {
        "name": "Setpoint_Slope",
        "type": "unsigned int",
        "access": "RW",
        "range": "0 – 30000",
        "units": "s",
        "notes": "The time in seconds to go from 0-100% setpoint for flow rate adjustment. A value of 0 means no slope, i.e., the setpoint is reached immediately.",
    },
    "12": {
        "name": "Control_Mode",
        "type": "unsigned int",
        "access": "RW",
        "range": "0 – 255",
        "notes": "0 = Analog, 1 = RS232/Bus, 3 = Valve fully closed, 4 = Valve fully open.",
    },
    "122": {
        "name": "Counter_Value",
        "type": "float",
        "access": "RW",
        "range": "0 – 10000000",
        "unit": "From Counter Unit",
        "notes": "Current counter value in units selected with parameter Counter Unit.",
    },
    "124": {
        "name": "Counter_Limit",
        "type": "float",
        "access": "RW",
        "range": "0 – 9999999",
        "unit": "From Counter Unit",
        "notes": "The limit for the counter. When the counter reaches this value, it will stop counting.",
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
        "notes": "Upstream pressure of the selected fluid in bar(a).",
    },
    "179": {
        "name": "Outlet_Pressure",
        "type": "float",
        "access": "RW B",
        "range": "0 – 3.4E+38",
        "units": "bar",
        "notes": "Downstream pressure of the selected fluid in bar(a).",
    },
    "181": {
        "name": "Fluid_Temperature",
        "type": "float",
        "access": "RW B",
        "range": "-250 – 500",
        "units": "°C",
        "notes": "The temperature of the selected fluid.",
    },
}

# -------------------------------------------------------------------
# EL-Flow Select Functions
# -------------------------------------------------------------------


def read_parameter(instrument, channel):
    """
    Reads a parameter from the EL-Flow Select instrument.

    :param instrument: The propar instrument object.
    :param channel: The channel number to read.
    :return: The value of the parameter.
    """
    try:
        return instrument.readParameter(channel)
    except Exception as e:
        print(f"Error reading channel {channel}: {e}")
        return None


def read_general(instrument, name):
    """
    Reads a general parameter from the EL-Flow Select instrument by name.

    :param instrument: The propar instrument object.
    :param name: The name of the parameter to read.
    :return: The value of the parameter if found, None otherwise.
    """
    for channel, info in PARAMETER_MAPPING.items():
        if info["name"] == name:
            if "R" not in info["access"]:
                print(f"Parameter {name} is not readable.")
                return None
            return read_parameter(instrument, int(channel))
    print(f"Parameter {name} not found in mapping.")
    return None


def write_param(instrument, channel, value):
    """
    Writes a parameter to the EL-Flow Select instrument.

    :param instrument: The propar instrument object.
    :param channel: The channel number to write.
    :param value: Value to write to channel
    :return: The result of the write operation, or None if error.
    """
    try:
        return instrument.writeParameter(channel, value)
    except Exception as e:
        print(f"Error writing value {value} to parameter {channel}: {e}")
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
        if info["name"] == name:
            if "W" not in info["access"]:
                print(f"Parameter {name} is not writable.")
                return None
            return write_param(instrument, int(channel), value)
    print(f"Parameter {name} not found in mapping.")
    return None


def read_all(instrument):
    """
    Reads all parameters from the EL-Flow Select instrument,
    add them to a dictionary and returns it.

    Will create the data structure in the form:
    {
        "Flow_Rate_Measured": value,
        ...
    }

    :param instrument: The propar instrument object.
    :return: A dictionary of all parameter values.
    """
    data = {}
    for channel, info in PARAMETER_MAPPING.items():
        if 'R' in info['access']:
            value = read_parameter(instrument, int(channel))
            data[info['name']] = value
    return data


# -------------------------------------------------------------------
# Main Function
# -------------------------------------------------------------------


class Instrument(BaseInstrument):
    def __init__(self):
        self.simulated_setpoint = 0.0
        self.simulated_measurement = 0.0

    def initialise(self, state):
        try:
            # Get device address from state config
            device = state.config.get("DEVICE_ADDRESS")
            if device is None:
                print("WARNING: DEVICE_ADDRESS not in state.config, falling back to /dev/ttyUSB2")
                device = "/dev/ttyUSB2"

            print(f"Initializing propar.Instrument on {device}")
            try:
                self.instrument = propar.instrument(device)
            except AttributeError:
                self.instrument = propar.Instrument(device)
            except Exception as inner_e:
                print(f"Failed to create propar instrument on {device}: {inner_e}")
                self.instrument = None
                return

            if self.instrument is None:
                print(f"propar.instrument({device}) returned None without raising.")
                return

            # Verify connection by reading a parameter
            print("Verifying connection to mass flow...")
            mode = read_parameter(self.instrument, 12)
            if mode is None or (isinstance(mode, str) and "<ERR" in mode):
                 print(f"Connection verification failed. Mode read back: {mode}")
                 self.instrument = None
                 return

            # Must be in Analog mode (0) — Bus mode (1) rejects RS232 setpoint writes.
            print(f"Current Control_Mode: {mode}. Setting to 0 (Analog)...")
            write_param(self.instrument, 12, 0)
            mode = read_parameter(self.instrument, 12)
            if mode != 0:
                print(f"WARNING: Control_Mode readback = {mode}, expected 0 (Analog). Setpoint writes may fail.")
            else:
                print("Control_Mode confirmed: 0 (Analog)")

            # Slope 0 = immediate response (no ramp)
            write_param(self.instrument, 10, 0)
            slope = read_parameter(self.instrument, 10)
            if slope != 0:
                print(f"WARNING: Setpoint_Slope readback = {slope}, expected 0.")
            else:
                print("Setpoint_Slope confirmed: 0 (immediate)")

            print(f"Mass flow initialised on {device}")
        except Exception as e:
            print(f"Error during mass flow initialization sequence!\n{e}")
            self.instrument = None

    def simulate_initialise(self, state):
        pass

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        if self.instrument is None:
            print("Instrument not initialized.")
            return None

        data = read_all(self.instrument)
        
        # Calculate actual flow as a percentage (0-100%)
        # Bronkhorst scale: 100% = 32000
        raw_flow = data.get("Flow_Rate_Measured")
        if raw_flow is not None:
            data["mass_flow"] = (float(raw_flow) / 32000) * 100
        else:
            print("WARNING: Flow_Rate_Measured read back as None (communication error?)")
            data["mass_flow"] = 0.0
            
        return data

    def go_to_setpoint(self, state):
        if self.instrument is None:
            print("Instrument not initialized.")
            return None

        setpoint =  state.status["setpoint"]
        if setpoint is None:
            return None
            
        if not (0 <= setpoint <= 100):
            print(f"Setpoint {setpoint} out of range (0-100%).")
            return None

        # Convert percentage to instrument scale (0-32000)
        instrument_setpoint = int((setpoint / 100) * 32000)

        result = write_general(
            self.instrument, "Flow_Rate_Setpoint", instrument_setpoint
        )
        if result is None:
            print("Failed to write Flow_Rate_Setpoint.")
            return None

        # Verify write
        read_back = self.instrument.readParameter(9)
        print(
            f"Set Flow_Rate_Setpoint to {setpoint}% ({instrument_setpoint}). "
            f"Instrument reports: {read_back} ({(float(read_back)/32000)*100 if read_back is not None else 'N/A'}%)"
        )
        return result

    def simulate_go_to_setpoint(self,state):        
        setpoint =  state.status["setpoint"]
        if not (0 <= setpoint <= 100):
            print("Setpoint must be between 0 and 100%.")
            return None

        self.simulated_setpoint = setpoint
        print(f"(Simulated) Setting Flow_Rate_Setpoint to {setpoint}%.")

    def simulate_get_measurement(self, state):
        # Simple simulation: measurement approaches setpoint
        if self.simulated_measurement < self.simulated_setpoint:
            self.simulated_measurement += 0.1
        elif self.simulated_measurement > self.simulated_setpoint:
            self.simulated_measurement -= 0.1
        state.measurement = self.simulated_measurement
        return {"mass_flow": self.simulated_measurement} 

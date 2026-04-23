"""
Diagnostic script for Bronkhorst EL-FLOW Select mass flow controller.

Usage:
    python utils/check_mass_flow.py [PORT] [OPTIONS]

    PORT                Serial port (default: /dev/ttyUSB2)

Options:
    --set-bus           Force control mode to Bus/RS232 (mode 1)
    --set-flow=N        Write a flow setpoint of N% (0-100), then read back
    --read-all          Read and print all known parameters

Examples:
    python utils/check_mass_flow.py
    python utils/check_mass_flow.py /dev/ttyUSB0
    python utils/check_mass_flow.py /dev/ttyUSB2 --set-bus
    python utils/check_mass_flow.py /dev/ttyUSB2 --set-flow=5
    python utils/check_mass_flow.py /dev/ttyUSB2 --set-bus --set-flow=5 --read-all
"""

import sys

# --- Parameter map (subset of EL-FLOW Select parameters) ---
PARAMS = {
    8:   ("Flow_Rate_Measured",   "R",   "%",    "0-41942 (100% = 32000)"),
    9:   ("Flow_Rate_Setpoint",   "RW",  "%",    "0-32000 (100% = 32000)"),
    10:  ("Setpoint_Slope",       "RW",  "s",    "0-30000, 0 = immediate"),
    12:  ("Control_Mode",         "RW",  "-",    "0=Analog 1=Bus 3=Closed 4=Open"),
    21:  ("Capacity_100_Percent", "RW",  "unit", "Full-scale flow value"),
    142: ("Temperature",          "R",   "C",    "Housing temperature"),
    143: ("Pressure",             "RW",  "bar",  "System pressure"),
    178: ("Inlet_Pressure",       "RW",  "bar",  "Upstream pressure"),
    179: ("Outlet_Pressure",      "RW",  "bar",  "Downstream pressure"),
    181: ("Fluid_Temperature",    "RW",  "C",    "Fluid temperature"),
    205: ("Fmeasure",             "R",   "unit", "Actual flow in capacity units"),
    206: ("Fsetpoint",            "RW",  "unit", "Setpoint in capacity units"),
}

CONTROL_MODES = {0: "Analog", 1: "Bus/RS232", 3: "Valve closed", 4: "Valve open"}
SEP = "-" * 60


def connect(port):
    try:
        import propar
    except ImportError:
        print("ERROR: 'propar' package not installed. Run: pip install propar")
        sys.exit(1)

    print(f"Connecting to {port}...")
    try:
        instrument = propar.instrument(port)
    except AttributeError:
        instrument = propar.Instrument(port)
    except Exception as e:
        print(f"ERROR: Could not open {port}: {e}")
        sys.exit(1)

    print("Connected.\n")
    return instrument


def read_param(instrument, channel):
    try:
        return instrument.readParameter(channel)
    except Exception as e:
        return f"<ERR: {e}>"


def write_param(instrument, channel, value):
    try:
        result = instrument.writeParameter(channel, value)
        return True, result
    except Exception as e:
        return False, str(e)


def check_connection(instrument):
    print(SEP)
    print("CONNECTION CHECK")
    print(SEP)
    flow = read_param(instrument, 8)
    if isinstance(flow, str) and "<ERR" in flow:
        print(f"FAIL -- could not read Flow_Rate_Measured (param 8): {flow}")
        return False
    print(f"OK   -- Flow_Rate_Measured (param 8) = {flow}")
    return True


def check_control_mode(instrument, force_bus=False):
    print(SEP)
    print("CONTROL MODE")
    print(SEP)
    mode = read_param(instrument, 12)
    if isinstance(mode, str) and "<ERR" in mode:
        print(f"FAIL -- could not read Control_Mode: {mode}")
        return

    mode_name = CONTROL_MODES.get(mode, f"Unknown ({mode})")
    label = "OK  " if mode == 1 else "WARN"
    print(f"{label} -- Control_Mode = {mode} ({mode_name})")

    if mode != 1:
        if force_bus:
            print("      Writing Control_Mode = 1 (Bus)...")
            ok, result = write_param(instrument, 12, 1)
            readback = read_param(instrument, 12)
            if ok and readback == 1:
                print(f"OK   -- Control_Mode set to 1 (Bus/RS232). Readback: {readback}")
            else:
                print(f"FAIL -- Write attempted but readback = {readback}. Result: {result}")
        else:
            print("      Device is NOT in Bus mode -- setpoint writes will be ignored.")
            print("      Run with --set-bus to force Bus mode.")


def check_flow_state(instrument):
    print(SEP)
    print("FLOW STATE")
    print(SEP)

    raw_measured = read_param(instrument, 8)
    raw_setpoint = read_param(instrument, 9)

    if not (isinstance(raw_measured, str) and "<ERR" in raw_measured):
        pct = (float(raw_measured) / 32000) * 100
        print(f"     Flow_Rate_Measured (8)  : {raw_measured:6}  = {pct:.2f}%")
    else:
        print(f"FAIL -- Flow_Rate_Measured: {raw_measured}")

    if not (isinstance(raw_setpoint, str) and "<ERR" in raw_setpoint):
        pct = (float(raw_setpoint) / 32000) * 100
        print(f"     Flow_Rate_Setpoint (9)  : {raw_setpoint:6}  = {pct:.2f}%")
    else:
        print(f"FAIL -- Flow_Rate_Setpoint: {raw_setpoint}")

    slope = read_param(instrument, 10)
    print(f"     Setpoint_Slope     (10) : {slope} s")

    fmeasure  = read_param(instrument, 205)
    fsetpoint = read_param(instrument, 206)
    capacity  = read_param(instrument, 21)
    print(f"     Fmeasure          (205) : {fmeasure}")
    print(f"     Fsetpoint         (206) : {fsetpoint}")
    print(f"     Capacity 100%     (21)  : {capacity}")


def test_setpoint_write(instrument, target_pct):
    print(SEP)
    print(f"SETPOINT WRITE TEST -- target: {target_pct}%")
    print(SEP)

    if not (0 <= target_pct <= 100):
        print(f"SKIP -- {target_pct}% is out of range (0-100%)")
        return

    instrument_value = int((target_pct / 100) * 32000)
    print(f"     Writing {instrument_value} (= {target_pct}%) to Flow_Rate_Setpoint (9)...")

    ok, result = write_param(instrument, 9, instrument_value)
    readback = read_param(instrument, 9)

    if not ok:
        print(f"FAIL -- Write error: {result}")
        return

    if isinstance(readback, str) and "<ERR" in readback:
        print(f"FAIL -- Readback error: {readback}")
        return

    readback_pct = (float(readback) / 32000) * 100
    if readback == instrument_value:
        print(f"OK   -- Readback matches: {readback} = {readback_pct:.2f}%")
    else:
        print(f"WARN -- Readback mismatch: wrote {instrument_value}, got {readback} ({readback_pct:.2f}%)")
        print("        This usually means the device is not in Bus control mode (mode 1).")

    fsp = read_param(instrument, 206)
    print(f"     Fsetpoint (206) after write: {fsp}")


def read_all_params(instrument):
    print(SEP)
    print("ALL PARAMETERS")
    print(SEP)
    for channel in sorted(PARAMS):
        name, access, units, notes = PARAMS[channel]
        if "R" in access:
            value = read_param(instrument, channel)
            print(f"  [{channel:3d}] {name:<28s} = {str(value):<14s} ({units})  {notes}")


def main():
    args = sys.argv[1:]

    port = "/dev/ttyUSB2"
    if args and not args[0].startswith("--"):
        port = args[0]
        args = args[1:]

    force_bus = "--set-bus" in args
    show_all  = "--read-all" in args

    target_flow = None
    for arg in args:
        if arg.startswith("--set-flow="):
            try:
                target_flow = float(arg.split("=", 1)[1])
            except ValueError:
                print(f"ERROR: invalid --set-flow value: {arg}")
                sys.exit(1)

    print(f"\nBronkhorst EL-FLOW Select -- diagnostic")
    print(f"Port: {port}\n")

    instrument = connect(port)

    if not check_connection(instrument):
        print("\nDevice not responding. Check:")
        print("  1. USB cable connected")
        print("  2. Correct port (ls /dev/ttyUSB*)")
        print("  3. propar installed (pip install propar)")
        sys.exit(1)

    check_control_mode(instrument, force_bus=force_bus)
    check_flow_state(instrument)

    if target_flow is not None:
        test_setpoint_write(instrument, target_flow)

    if show_all:
        read_all_params(instrument)

    print(SEP)
    print("Done.\n")


if __name__ == "__main__":
    main()

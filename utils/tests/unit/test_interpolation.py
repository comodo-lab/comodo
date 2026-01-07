from utils.interpolation import (
    split_setpoints,
)


def test_split_setpoints():
    setpoints = [
        {
            "time": 0,
            "pressure": 0,
            "temperature": 0,
            "displacement 1": 0,
            "displacement 2": 0,
        },
        {
            "time": 1,
            "pressure": 2,
            "temperature": 3,
            "displacement 1": 4,
            "displacement 2": 5,
        },
        {
            "time": 3,
            "pressure": 0,
            "temperature": 0,
            "displacement 1": 0,
            "displacement 2": 0,
        },
    ]
    resolution = 0.5
    result = split_setpoints(setpoints, resolution)
    assert result == [
        {
            "duration": 0.0,
            "pressure": 0.0,
            "temperature": 0.0,
            "displacement 1": 0.0,
            "displacement 2": 0.0,
        },
        {
            "duration": 0.5,
            "pressure": 1.0,
            "temperature": 1.5,
            "displacement 1": 2.0,
            "displacement 2": 2.5,
        },
        {
            "duration": 0.5,
            "pressure": 2.0,
            "temperature": 3.0,
            "displacement 1": 4.0,
            "displacement 2": 5.0,
        },
        {
            "duration": 0.5,
            "pressure": 1.5,
            "temperature": 2.25,
            "displacement 1": 3.0,
            "displacement 2": 3.75,
        },
        {
            "duration": 0.5,
            "pressure": 1.0,
            "temperature": 1.5,
            "displacement 1": 2.0,
            "displacement 2": 2.5,
        },
        {
            "duration": 0.5,
            "pressure": 0.5,
            "temperature": 0.75,
            "displacement 1": 1.0,
            "displacement 2": 1.25,
        },
        {
            "duration": 0.5,
            "pressure": 0.0,
            "temperature": 0.0,
            "displacement 1": 0.0,
            "displacement 2": 0.0,
        },
    ]

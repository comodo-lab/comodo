# Auto generated from comodo.yaml.schema by pythongen.py version: 0.0.1
# Generation date: 2025-12-14T20:56:04
# Schema: ExperimentSchema
#
# id: https://example.org/experiment-schema
# description:
# license: https://creativecommons.org/publicdomain/zero/1.0/

import dataclasses
import re
from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    time
)
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Union
)

from jsonasobj2 import (
    JsonObj,
    as_dict
)
from linkml_runtime.linkml_model.meta import (
    EnumDefinition,
    PermissibleValue,
    PvFormulaOptions
)
from linkml_runtime.utils.curienamespace import CurieNamespace
from linkml_runtime.utils.enumerations import EnumDefinitionImpl
from linkml_runtime.utils.formatutils import (
    camelcase,
    sfx,
    underscore
)
from linkml_runtime.utils.metamodelcore import (
    bnode,
    empty_dict,
    empty_list
)
from linkml_runtime.utils.slot import Slot
from linkml_runtime.utils.yamlutils import (
    YAMLRoot,
    extended_float,
    extended_int,
    extended_str
)
from rdflib import (
    Namespace,
    URIRef
)

from linkml_runtime.linkml_model.types import Float, String

metamodel_version = "1.7.0"
version = None

# Namespaces
EX = CurieNamespace('ex', 'https://example.org/')
LINKML = CurieNamespace('linkml', 'https://w3id.org/linkml/')
DEFAULT_ = EX


# Types

# Class references
class GlobalSettingsId(extended_str):
    pass


class InstrumentId(extended_str):
    pass


class SensorId(extended_str):
    pass


class VisualisationId(extended_str):
    pass


class GraphId(VisualisationId):
    pass


class GaugeId(VisualisationId):
    pass


@dataclass(repr=False)
class Experiment(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["Experiment"]
    class_class_curie: ClassVar[str] = "ex:Experiment"
    class_name: ClassVar[str] = "Experiment"
    class_model_uri: ClassVar[URIRef] = EX.Experiment

    global_set: Optional[Union[str, GlobalSettingsId]] = None
    instruments: Optional[Union[dict[Union[str, InstrumentId], Union[dict, "Instrument"]], list[Union[dict, "Instrument"]]]] = empty_dict()
    visualisations: Optional[Union[dict[Union[str, VisualisationId], Union[dict, "Visualisation"]], list[Union[dict, "Visualisation"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.global_set is not None and not isinstance(self.global_set, GlobalSettingsId):
            self.global_set = GlobalSettingsId(self.global_set)

        self._normalize_inlined_as_dict(slot_name="instruments", slot_type=Instrument, key_name="id", keyed=True)

        self._normalize_inlined_as_dict(slot_name="visualisations", slot_type=Visualisation, key_name="id", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class GlobalSettings(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["GlobalSettings"]
    class_class_curie: ClassVar[str] = "ex:GlobalSettings"
    class_name: ClassVar[str] = "GlobalSettings"
    class_model_uri: ClassVar[URIRef] = EX.GlobalSettings

    id: Union[str, GlobalSettingsId] = None
    error_timeout: Optional[str] = None
    material: Optional[str] = None
    sample_id: Optional[str] = None
    operator: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, GlobalSettingsId):
            self.id = GlobalSettingsId(self.id)

        if self.error_timeout is not None and not isinstance(self.error_timeout, str):
            self.error_timeout = str(self.error_timeout)

        if self.material is not None and not isinstance(self.material, str):
            self.material = str(self.material)

        if self.sample_id is not None and not isinstance(self.sample_id, str):
            self.sample_id = str(self.sample_id)

        if self.operator is not None and not isinstance(self.operator, str):
            self.operator = str(self.operator)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Instrument(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["Instrument"]
    class_class_curie: ClassVar[str] = "ex:Instrument"
    class_name: ClassVar[str] = "Instrument"
    class_model_uri: ClassVar[URIRef] = EX.Instrument

    id: Union[str, InstrumentId] = None
    sensors: Optional[Union[dict[Union[str, SensorId], Union[dict, "Sensor"]], list[Union[dict, "Sensor"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, InstrumentId):
            self.id = InstrumentId(self.id)

        self._normalize_inlined_as_dict(slot_name="sensors", slot_type=Sensor, key_name="id", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Sensor(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["Sensor"]
    class_class_curie: ClassVar[str] = "ex:Sensor"
    class_name: ClassVar[str] = "Sensor"
    class_model_uri: ClassVar[URIRef] = EX.Sensor

    id: Union[str, SensorId] = None
    address: Optional[str] = None
    measurement_interval: Optional[str] = None
    sensor: Optional[Union[dict, "SensorConfig"]] = None
    actuator: Optional[Union[dict, "ActuatorConfig"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, SensorId):
            self.id = SensorId(self.id)

        if self.address is not None and not isinstance(self.address, str):
            self.address = str(self.address)

        if self.measurement_interval is not None and not isinstance(self.measurement_interval, str):
            self.measurement_interval = str(self.measurement_interval)

        if self.sensor is not None and not isinstance(self.sensor, SensorConfig):
            self.sensor = SensorConfig(**as_dict(self.sensor))

        if self.actuator is not None and not isinstance(self.actuator, ActuatorConfig):
            self.actuator = ActuatorConfig(**as_dict(self.actuator))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class SensorConfig(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["SensorConfig"]
    class_class_curie: ClassVar[str] = "ex:SensorConfig"
    class_name: ClassVar[str] = "SensorConfig"
    class_model_uri: ClassVar[URIRef] = EX.SensorConfig

    type: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    unit: Optional[str] = None
    correction_multiplier: Optional[float] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.type is not None and not isinstance(self.type, str):
            self.type = str(self.type)

        if self.min is not None and not isinstance(self.min, float):
            self.min = float(self.min)

        if self.max is not None and not isinstance(self.max, float):
            self.max = float(self.max)

        if self.unit is not None and not isinstance(self.unit, str):
            self.unit = str(self.unit)

        if self.correction_multiplier is not None and not isinstance(self.correction_multiplier, float):
            self.correction_multiplier = float(self.correction_multiplier)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class ActuatorConfig(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["ActuatorConfig"]
    class_class_curie: ClassVar[str] = "ex:ActuatorConfig"
    class_name: ClassVar[str] = "ActuatorConfig"
    class_model_uri: ClassVar[URIRef] = EX.ActuatorConfig

    type: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    unit: Optional[str] = None
    correction_multiplier: Optional[float] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.type is not None and not isinstance(self.type, str):
            self.type = str(self.type)

        if self.min is not None and not isinstance(self.min, float):
            self.min = float(self.min)

        if self.max is not None and not isinstance(self.max, float):
            self.max = float(self.max)

        if self.unit is not None and not isinstance(self.unit, str):
            self.unit = str(self.unit)

        if self.correction_multiplier is not None and not isinstance(self.correction_multiplier, float):
            self.correction_multiplier = float(self.correction_multiplier)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Visualisation(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["Visualisation"]
    class_class_curie: ClassVar[str] = "ex:Visualisation"
    class_name: ClassVar[str] = "Visualisation"
    class_model_uri: ClassVar[URIRef] = EX.Visualisation

    id: Union[str, VisualisationId] = None
    title: Optional[str] = None
    vis_type: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, VisualisationId):
            self.id = VisualisationId(self.id)

        if self.title is not None and not isinstance(self.title, str):
            self.title = str(self.title)

        self.vis_type = str(self.class_name)

        super().__post_init__(**kwargs)


    def __new__(cls, *args, **kwargs):

        type_designator = "vis_type"
        if not type_designator in kwargs:
            return super().__new__(cls,*args,**kwargs)
        else:
            type_designator_value = kwargs[type_designator]
            target_cls = cls._class_for("class_name", type_designator_value)


            if target_cls is None:
                raise ValueError(f"Wrong type designator value: class {cls.__name__} "
                                 f"has no subclass with ['class_name']='{kwargs[type_designator]}'")
            return super().__new__(target_cls,*args,**kwargs)



@dataclass(repr=False)
class Graph(Visualisation):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["Graph"]
    class_class_curie: ClassVar[str] = "ex:Graph"
    class_name: ClassVar[str] = "Graph"
    class_model_uri: ClassVar[URIRef] = EX.Graph

    id: Union[str, GraphId] = None
    y_values: Optional[Union[str, list[str]]] = empty_list()
    vis_type: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, GraphId):
            self.id = GraphId(self.id)

        if not isinstance(self.y_values, list):
            self.y_values = [self.y_values] if self.y_values is not None else []
        self.y_values = [v if isinstance(v, str) else str(v) for v in self.y_values]

        self.vis_type = str(self.class_name)

        super().__post_init__(**kwargs)
        self.vis_type = str(self.class_name)


@dataclass(repr=False)
class Gauge(Visualisation):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["Gauge"]
    class_class_curie: ClassVar[str] = "ex:Gauge"
    class_name: ClassVar[str] = "Gauge"
    class_model_uri: ClassVar[URIRef] = EX.Gauge

    id: Union[str, GaugeId] = None
    value: Optional[Union[str, list[str]]] = empty_list()
    vis_type: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, GaugeId):
            self.id = GaugeId(self.id)

        if not isinstance(self.value, list):
            self.value = [self.value] if self.value is not None else []
        self.value = [v if isinstance(v, str) else str(v) for v in self.value]

        self.vis_type = str(self.class_name)

        super().__post_init__(**kwargs)
        self.vis_type = str(self.class_name)


# Enumerations


# Slots
class slots:
    pass

slots.id = Slot(uri=EX.id, name="id", curie=EX.curie('id'),
                   model_uri=EX.id, domain=None, range=URIRef)

slots.global_set = Slot(uri=EX.global_set, name="global_set", curie=EX.curie('global_set'),
                   model_uri=EX.global_set, domain=None, range=Optional[Union[str, GlobalSettingsId]])

slots.instruments = Slot(uri=EX.instruments, name="instruments", curie=EX.curie('instruments'),
                   model_uri=EX.instruments, domain=None, range=Optional[Union[dict[Union[str, InstrumentId], Union[dict, Instrument]], list[Union[dict, Instrument]]]])

slots.sensors = Slot(uri=EX.sensors, name="sensors", curie=EX.curie('sensors'),
                   model_uri=EX.sensors, domain=None, range=Optional[Union[dict[Union[str, SensorId], Union[dict, Sensor]], list[Union[dict, Sensor]]]])

slots.sensor = Slot(uri=EX.sensor, name="sensor", curie=EX.curie('sensor'),
                   model_uri=EX.sensor, domain=None, range=Optional[Union[dict, SensorConfig]])

slots.actuator = Slot(uri=EX.actuator, name="actuator", curie=EX.curie('actuator'),
                   model_uri=EX.actuator, domain=None, range=Optional[Union[dict, ActuatorConfig]])

slots.error_timeout = Slot(uri=EX.error_timeout, name="error_timeout", curie=EX.curie('error_timeout'),
                   model_uri=EX.error_timeout, domain=None, range=Optional[str])

slots.material = Slot(uri=EX.material, name="material", curie=EX.curie('material'),
                   model_uri=EX.material, domain=None, range=Optional[str])

slots.sample_id = Slot(uri=EX.sample_id, name="sample_id", curie=EX.curie('sample_id'),
                   model_uri=EX.sample_id, domain=None, range=Optional[str])

slots.operator = Slot(uri=EX.operator, name="operator", curie=EX.curie('operator'),
                   model_uri=EX.operator, domain=None, range=Optional[str])

slots.address = Slot(uri=EX.address, name="address", curie=EX.curie('address'),
                   model_uri=EX.address, domain=None, range=Optional[str])

slots.measurement_interval = Slot(uri=EX.measurement_interval, name="measurement_interval", curie=EX.curie('measurement_interval'),
                   model_uri=EX.measurement_interval, domain=None, range=Optional[str])

slots.type = Slot(uri=EX.type, name="type", curie=EX.curie('type'),
                   model_uri=EX.type, domain=None, range=Optional[str])

slots.vis_type = Slot(uri=EX.vis_type, name="vis_type", curie=EX.curie('vis_type'),
                   model_uri=EX.vis_type, domain=None, range=Optional[str])

slots.min = Slot(uri=EX.min, name="min", curie=EX.curie('min'),
                   model_uri=EX.min, domain=None, range=Optional[float])

slots.max = Slot(uri=EX.max, name="max", curie=EX.curie('max'),
                   model_uri=EX.max, domain=None, range=Optional[float])

slots.unit = Slot(uri=EX.unit, name="unit", curie=EX.curie('unit'),
                   model_uri=EX.unit, domain=None, range=Optional[str])

slots.correction_multiplier = Slot(uri=EX.correction_multiplier, name="correction_multiplier", curie=EX.curie('correction_multiplier'),
                   model_uri=EX.correction_multiplier, domain=None, range=Optional[float])

slots.visualisations = Slot(uri=EX.visualisations, name="visualisations", curie=EX.curie('visualisations'),
                   model_uri=EX.visualisations, domain=None, range=Optional[Union[dict[Union[str, VisualisationId], Union[dict, Visualisation]], list[Union[dict, Visualisation]]]])

slots.title = Slot(uri=EX.title, name="title", curie=EX.curie('title'),
                   model_uri=EX.title, domain=None, range=Optional[str])

slots.y_values = Slot(uri=EX.y_values, name="y_values", curie=EX.curie('y_values'),
                   model_uri=EX.y_values, domain=None, range=Optional[Union[str, list[str]]])

slots.value = Slot(uri=EX.value, name="value", curie=EX.curie('value'),
                   model_uri=EX.value, domain=None, range=Optional[Union[str, list[str]]])

slots.Graph_vis_type = Slot(uri=EX.vis_type, name="Graph_vis_type", curie=EX.curie('vis_type'),
                   model_uri=EX.Graph_vis_type, domain=Graph, range=Optional[str])

slots.Gauge_vis_type = Slot(uri=EX.vis_type, name="Gauge_vis_type", curie=EX.curie('vis_type'),
                   model_uri=EX.Gauge_vis_type, domain=Gauge, range=Optional[str])


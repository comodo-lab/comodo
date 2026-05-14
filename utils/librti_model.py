# Auto generated from librti.yaml.schema by pythongen.py version: 0.0.1
# Generation date: 2025-12-14T20:35:55
# Schema: LibrtiSchema
#
# id: https://example.org/librti-schema
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
EX = CurieNamespace('ex', 'https://example.org/librti/')
LINKML = CurieNamespace('linkml', 'https://w3id.org/linkml/')
DEFAULT_ = EX


# Types

# Class references
class InstrumentId(extended_str):
    pass


class InstrumentId(extended_str):
    pass


class EmulatorId(extended_str):
    pass


class ModelComponentId(extended_str):
    pass


class MaterialModelMaterial(extended_str):
    pass


class ConditionMaterial(extended_str):
    pass


class VisualisationId(extended_str):
    pass


class GraphId(VisualisationId):
    pass


class GaugeId(VisualisationId):
    pass


@dataclass(repr=False)
class LibrtiSystem(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["LibrtiSystem"]
    class_class_curie: ClassVar[str] = "ex:LibrtiSystem"
    class_name: ClassVar[str] = "LibrtiSystem"
    class_model_uri: ClassVar[URIRef] = EX.LibrtiSystem

    global_set: Optional[Union[dict, "GlobalSettings"]] = None
    instruments: Optional[Union[dict[Union[str, InstrumentId], Union[dict, "Instrument"]], list[Union[dict, "Instrument"]]]] = empty_dict()
    emulators: Optional[Union[dict[Union[str, EmulatorId], Union[dict, "Emulator"]], list[Union[dict, "Emulator"]]]] = empty_dict()
    visualisations: Optional[Union[dict[Union[str, VisualisationId], Union[dict, "Visualisation"]], list[Union[dict, "Visualisation"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.global_set is not None and not isinstance(self.global_set, GlobalSettings):
            self.global_set = GlobalSettings(**as_dict(self.global_set))

        self._normalize_inlined_as_dict(slot_name="instruments", slot_type=Instrument, key_name="id", keyed=True)

        self._normalize_inlined_as_dict(slot_name="emulators", slot_type=Emulator, key_name="id", keyed=True)

        self._normalize_inlined_as_dict(slot_name="visualisations", slot_type=Visualisation, key_name="id", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class GlobalSettings(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["GlobalSettings"]
    class_class_curie: ClassVar[str] = "ex:GlobalSettings"
    class_name: ClassVar[str] = "GlobalSettings"
    class_model_uri: ClassVar[URIRef] = EX.GlobalSettings

    version: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.version is not None and not isinstance(self.version, str):
            self.version = str(self.version)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Instrument(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["Instrument"]
    class_class_curie: ClassVar[str] = "ex:Instrument"
    class_name: ClassVar[str] = "Instrument"
    class_model_uri: ClassVar[URIRef] = EX.Instrument

    id: Union[str, InstrumentId] = None
    instruments: Optional[Union[dict[Union[str, InstrumentId], Union[dict, "Instrument"]], list[Union[dict, "Instrument"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, InstrumentId):
            self.id = InstrumentId(self.id)

        self._normalize_inlined_as_dict(slot_name="instruments", slot_type=Instrument, key_name="id", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Instrument(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["Instrument"]
    class_class_curie: ClassVar[str] = "ex:Instrument"
    class_name: ClassVar[str] = "Instrument"
    class_model_uri: ClassVar[URIRef] = EX.Instrument

    id: Union[str, InstrumentId] = None
    address: Optional[str] = None
    measurement_interval: Optional[str] = None
    instrument: Optional[Union[dict, "InstrumentConfig"]] = None
    actuator: Optional[Union[dict, "ActuatorConfig"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, InstrumentId):
            self.id = InstrumentId(self.id)

        if self.address is not None and not isinstance(self.address, str):
            self.address = str(self.address)

        if self.measurement_interval is not None and not isinstance(self.measurement_interval, str):
            self.measurement_interval = str(self.measurement_interval)

        if self.instrument is not None and not isinstance(self.instrument, InstrumentConfig):
            self.instrument = InstrumentConfig(**as_dict(self.instrument))

        if self.actuator is not None and not isinstance(self.actuator, ActuatorConfig):
            self.actuator = ActuatorConfig(**as_dict(self.actuator))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class InstrumentConfig(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["InstrumentConfig"]
    class_class_curie: ClassVar[str] = "ex:InstrumentConfig"
    class_name: ClassVar[str] = "InstrumentConfig"
    class_model_uri: ClassVar[URIRef] = EX.InstrumentConfig

    type: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    unit: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.type is not None and not isinstance(self.type, str):
            self.type = str(self.type)

        if self.min is not None and not isinstance(self.min, float):
            self.min = float(self.min)

        if self.max is not None and not isinstance(self.max, float):
            self.max = float(self.max)

        if self.unit is not None and not isinstance(self.unit, str):
            self.unit = str(self.unit)

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

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.type is not None and not isinstance(self.type, str):
            self.type = str(self.type)

        if self.min is not None and not isinstance(self.min, float):
            self.min = float(self.min)

        if self.max is not None and not isinstance(self.max, float):
            self.max = float(self.max)

        if self.unit is not None and not isinstance(self.unit, str):
            self.unit = str(self.unit)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Emulator(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["Emulator"]
    class_class_curie: ClassVar[str] = "ex:Emulator"
    class_name: ClassVar[str] = "Emulator"
    class_model_uri: ClassVar[URIRef] = EX.Emulator

    id: Union[str, EmulatorId] = None
    outputs: Optional[Union[Union[dict, "EmulatorOutput"], list[Union[dict, "EmulatorOutput"]]]] = empty_list()
    components: Optional[Union[dict[Union[str, ModelComponentId], Union[dict, "ModelComponent"]], list[Union[dict, "ModelComponent"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, EmulatorId):
            self.id = EmulatorId(self.id)

        if not isinstance(self.outputs, list):
            self.outputs = [self.outputs] if self.outputs is not None else []
        self.outputs = [v if isinstance(v, EmulatorOutput) else EmulatorOutput(**as_dict(v)) for v in self.outputs]

        self._normalize_inlined_as_dict(slot_name="components", slot_type=ModelComponent, key_name="id", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class EmulatorOutput(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["EmulatorOutput"]
    class_class_curie: ClassVar[str] = "ex:EmulatorOutput"
    class_name: ClassVar[str] = "EmulatorOutput"
    class_model_uri: ClassVar[URIRef] = EX.EmulatorOutput

    quantity: Optional[str] = None
    unit: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.quantity is not None and not isinstance(self.quantity, str):
            self.quantity = str(self.quantity)

        if self.unit is not None and not isinstance(self.unit, str):
            self.unit = str(self.unit)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class ModelComponent(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["ModelComponent"]
    class_class_curie: ClassVar[str] = "ex:ModelComponent"
    class_name: ClassVar[str] = "ModelComponent"
    class_model_uri: ClassVar[URIRef] = EX.ModelComponent

    id: Union[str, ModelComponentId] = None
    material_models: Optional[Union[dict[Union[str, MaterialModelMaterial], Union[dict, "MaterialModel"]], list[Union[dict, "MaterialModel"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ModelComponentId):
            self.id = ModelComponentId(self.id)

        self._normalize_inlined_as_dict(slot_name="material_models", slot_type=MaterialModel, key_name="material", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class MaterialModel(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["MaterialModel"]
    class_class_curie: ClassVar[str] = "ex:MaterialModel"
    class_name: ClassVar[str] = "MaterialModel"
    class_model_uri: ClassVar[URIRef] = EX.MaterialModel

    material: Union[str, MaterialModelMaterial] = None
    model_ref: Optional[str] = None
    parameters: Optional[Union[str, list[str]]] = empty_list()
    update_policy: Optional[str] = None
    updated_from: Optional[Union[dict, "UpdateSource"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.material):
            self.MissingRequiredField("material")
        if not isinstance(self.material, MaterialModelMaterial):
            self.material = MaterialModelMaterial(self.material)

        if self.model_ref is not None and not isinstance(self.model_ref, str):
            self.model_ref = str(self.model_ref)

        if not isinstance(self.parameters, list):
            self.parameters = [self.parameters] if self.parameters is not None else []
        self.parameters = [v if isinstance(v, str) else str(v) for v in self.parameters]

        if self.update_policy is not None and not isinstance(self.update_policy, str):
            self.update_policy = str(self.update_policy)

        if self.updated_from is not None and not isinstance(self.updated_from, UpdateSource):
            self.updated_from = UpdateSource(**as_dict(self.updated_from))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class UpdateSource(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["UpdateSource"]
    class_class_curie: ClassVar[str] = "ex:UpdateSource"
    class_name: ClassVar[str] = "UpdateSource"
    class_model_uri: ClassVar[URIRef] = EX.UpdateSource

    source: Optional[str] = None
    condition: Optional[Union[dict, "Condition"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.source is not None and not isinstance(self.source, str):
            self.source = str(self.source)

        if self.condition is not None and not isinstance(self.condition, Condition):
            self.condition = Condition(**as_dict(self.condition))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Condition(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = EX["Condition"]
    class_class_curie: ClassVar[str] = "ex:Condition"
    class_name: ClassVar[str] = "Condition"
    class_model_uri: ClassVar[URIRef] = EX.Condition

    material: Union[str, ConditionMaterial] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.material):
            self.MissingRequiredField("material")
        if not isinstance(self.material, ConditionMaterial):
            self.material = ConditionMaterial(self.material)

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
                   model_uri=EX.global_set, domain=None, range=Optional[Union[dict, GlobalSettings]])

slots.version = Slot(uri=EX.version, name="version", curie=EX.curie('version'),
                   model_uri=EX.version, domain=None, range=Optional[str])

slots.instruments = Slot(uri=EX.instruments, name="instruments", curie=EX.curie('instruments'),
                   model_uri=EX.instruments, domain=None, range=Optional[Union[dict[Union[str, InstrumentId], Union[dict, Instrument]], list[Union[dict, Instrument]]]])

slots.instruments = Slot(uri=EX.instruments, name="instruments", curie=EX.curie('instruments'),
                   model_uri=EX.instruments, domain=None, range=Optional[Union[dict[Union[str, InstrumentId], Union[dict, Instrument]], list[Union[dict, Instrument]]]])

slots.instrument = Slot(uri=EX.instrument, name="instrument", curie=EX.curie('instrument'),
                   model_uri=EX.instrument, domain=None, range=Optional[Union[dict, InstrumentConfig]])

slots.actuator = Slot(uri=EX.actuator, name="actuator", curie=EX.curie('actuator'),
                   model_uri=EX.actuator, domain=None, range=Optional[Union[dict, ActuatorConfig]])

slots.address = Slot(uri=EX.address, name="address", curie=EX.curie('address'),
                   model_uri=EX.address, domain=None, range=Optional[str])

slots.measurement_interval = Slot(uri=EX.measurement_interval, name="measurement_interval", curie=EX.curie('measurement_interval'),
                   model_uri=EX.measurement_interval, domain=None, range=Optional[str])

slots.type = Slot(uri=EX.type, name="type", curie=EX.curie('type'),
                   model_uri=EX.type, domain=None, range=Optional[str])

slots.min = Slot(uri=EX.min, name="min", curie=EX.curie('min'),
                   model_uri=EX.min, domain=None, range=Optional[float])

slots.max = Slot(uri=EX.max, name="max", curie=EX.curie('max'),
                   model_uri=EX.max, domain=None, range=Optional[float])

slots.unit = Slot(uri=EX.unit, name="unit", curie=EX.curie('unit'),
                   model_uri=EX.unit, domain=None, range=Optional[str])

slots.emulators = Slot(uri=EX.emulators, name="emulators", curie=EX.curie('emulators'),
                   model_uri=EX.emulators, domain=None, range=Optional[Union[dict[Union[str, EmulatorId], Union[dict, Emulator]], list[Union[dict, Emulator]]]])

slots.outputs = Slot(uri=EX.outputs, name="outputs", curie=EX.curie('outputs'),
                   model_uri=EX.outputs, domain=None, range=Optional[Union[Union[dict, EmulatorOutput], list[Union[dict, EmulatorOutput]]]])

slots.quantity = Slot(uri=EX.quantity, name="quantity", curie=EX.curie('quantity'),
                   model_uri=EX.quantity, domain=None, range=Optional[str])

slots.components = Slot(uri=EX.components, name="components", curie=EX.curie('components'),
                   model_uri=EX.components, domain=None, range=Optional[Union[dict[Union[str, ModelComponentId], Union[dict, ModelComponent]], list[Union[dict, ModelComponent]]]])

slots.material_models = Slot(uri=EX.material_models, name="material_models", curie=EX.curie('material_models'),
                   model_uri=EX.material_models, domain=None, range=Optional[Union[dict[Union[str, MaterialModelMaterial], Union[dict, MaterialModel]], list[Union[dict, MaterialModel]]]])

slots.material = Slot(uri=EX.material, name="material", curie=EX.curie('material'),
                   model_uri=EX.material, domain=None, range=URIRef)

slots.model_ref = Slot(uri=EX.model_ref, name="model_ref", curie=EX.curie('model_ref'),
                   model_uri=EX.model_ref, domain=None, range=Optional[str])

slots.parameters = Slot(uri=EX.parameters, name="parameters", curie=EX.curie('parameters'),
                   model_uri=EX.parameters, domain=None, range=Optional[Union[str, list[str]]])

slots.update_policy = Slot(uri=EX.update_policy, name="update_policy", curie=EX.curie('update_policy'),
                   model_uri=EX.update_policy, domain=None, range=Optional[str])

slots.updated_from = Slot(uri=EX.updated_from, name="updated_from", curie=EX.curie('updated_from'),
                   model_uri=EX.updated_from, domain=None, range=Optional[Union[dict, UpdateSource]])

slots.source = Slot(uri=EX.source, name="source", curie=EX.curie('source'),
                   model_uri=EX.source, domain=None, range=Optional[str])

slots.condition = Slot(uri=EX.condition, name="condition", curie=EX.curie('condition'),
                   model_uri=EX.condition, domain=None, range=Optional[Union[dict, Condition]])

slots.visualisations = Slot(uri=EX.visualisations, name="visualisations", curie=EX.curie('visualisations'),
                   model_uri=EX.visualisations, domain=None, range=Optional[Union[dict[Union[str, VisualisationId], Union[dict, Visualisation]], list[Union[dict, Visualisation]]]])

slots.title = Slot(uri=EX.title, name="title", curie=EX.curie('title'),
                   model_uri=EX.title, domain=None, range=Optional[str])

slots.vis_type = Slot(uri=EX.vis_type, name="vis_type", curie=EX.curie('vis_type'),
                   model_uri=EX.vis_type, domain=None, range=Optional[str])

slots.y_values = Slot(uri=EX.y_values, name="y_values", curie=EX.curie('y_values'),
                   model_uri=EX.y_values, domain=None, range=Optional[Union[str, list[str]]])

slots.value = Slot(uri=EX.value, name="value", curie=EX.curie('value'),
                   model_uri=EX.value, domain=None, range=Optional[Union[str, list[str]]])

slots.Graph_vis_type = Slot(uri=EX.vis_type, name="Graph_vis_type", curie=EX.curie('vis_type'),
                   model_uri=EX.Graph_vis_type, domain=Graph, range=Optional[str])

slots.Gauge_vis_type = Slot(uri=EX.vis_type, name="Gauge_vis_type", curie=EX.curie('vis_type'),
                   model_uri=EX.Gauge_vis_type, domain=Gauge, range=Optional[str])


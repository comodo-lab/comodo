---
title: 'comodo: A Python framework for experiment control and automation'
tags:
  - experiments
  - automation
  - telemetry
  - Python
  - firmware
authors:
  - name: Francisco Herrerías-Azcué
    orcid: 0000-0002-5906-221X
    equal-contrib: true
    corresponding: true
    affiliation: '1'
  - name: Oliver J. Woolland
    orcid: 0000-0002-4565-9760
    equal-contrib: true
    affiliation: '1'
affiliations:
 - name: University of Manchester
   index: 1
   ror: 027m9bs27
date: 23 November 2026
bibliography: paper.bib

---

# Summary

`comodo` is a software stack that allows you to control, monitor, design and oversee laboratory experiments.
Users can specify a desired experiment timeline and simply trigger its automatic execution and data gathering.

It employs a distributed architecture;
Users interact with the experiment via a web interface.
A server-hosted controller module performs orchestration and executes the experiment;
Edge-hardware-hosted firmware controls the instruments.

The components of `comodo` communicate with each other via MQTT messages, both for control and data exchange.
This allows for automated recording of lab data and metadata, which we implement using influxdB.
Since the data is recorded live, it can be easily queried and further processed.

The software stack is run and deployed using Docker Compose.
This provides a repeatable, versionable setup, and makes it easy to run.
It also enables the components to communicate internally.

# Statement of need

Laboratory experiments remain the bedrock of scientific endeavour and discovery.
Despite this noble status, the reality of experimental undertaking can be unglamorous and inefficient.
Early career researchers often spend long hours running experiments.
Data is not always collected, let alone preserved, or analysed.
The collection of metadata and provenance is not consistent and not widely practised.
Many more hours are then spent trying to re-run an experiment to confirm a result.

Many experiments are run manually, often through multiple manufacturer provided interfaces.
When automation is implemented, it is often with scripts only useful for their specific setup.
This tends to be very time consuming, it often results in duplicate work, and is rarely thoroughly tested or efficient.
What's more important, it removes scientists from their primary purpose.

`comodo` proposes a generalised framework for automating the running of laboratory experiments, using modern technologies and architectures.
It is designed to be easily extendable and commune with the hardware used in bespoke experimental setups.
At the same time, it is meant to completely take care of the control, automation, and data gathering layers.
This greatly reduces the complexity and time needed to digitally enable any laboratory.
As a result, it gives time back to the researchers to focus on designing experiments and interpreting results.

# State of the field

The automation of scientific experiments has been explored for several decades.
As experimental setups become increasingly complex, there is a growing need for software that simplifies the integration of laboratory equipment.
Being able to abstract hardware-specific interfaces and enable automation of experimental procedures becomes more and more important.

Several approaches have emerged to address different aspects of this problem.

At the instrument level, hardware abstraction layers provide common interfaces for interacting with equipment from different manufacturers.
This allows experimental procedures to be developed independently of specific hardware implementations [PyVISA, QCoDeS, PyMeasure, PyLabRobot, Instrumental].

At a higher level, efforts have focused on describing experimental procedures independently of their execution.
Such approaches facilitate the reproducibility, portability and execution of experimental protocols across compatible systems [Autoprotocol, SiLA 2, Antha, XDL].

Similarly, orchestration tools allow researchers to define sequences of operations, coordinate different instruments and automate data acquisition and processing [HELAO, ChemOS, Clarity, MAHOS].

These approaches address important individual aspects, but do not necessarily provide a complete infrastructure for controlling and automating scientific experiments.
Such infrastructure must bring together hardware integration, experiment configuration, execution and coordination, data acquisition, user interaction and operational monitoring.

A number of frameworks providing this more comprehensive functionality predate comodo.
Each adopts a different architectural approach and makes different trade-offs between flexibility, complexity and ease of use.

[EPICS](https://github.com/epics-base/epics-base), for example, is a mature and widely used solution for generalised experiment control in scientific facilities.
It provides a comprehensive infrastructure for distributed control, remote operation, automatic sequencing and monitoring.
However, its extensive capabilities and flexibility come with an associated configuration and learning overhead.
Although EPICS can support small installations, its architecture and ecosystem are arguably more elaborate than necessary for relatively simple laboratory experiments.
This can make it less accessible to smaller research groups seeking a lightweight solution.

[Bluesky](https://github.com/bluesky/bluesky) is another option, targeting experimental data acquisition and orchestration.
It provides facilities for controlling experiments, coordinating instrumentation, and collecting structured data and metadata.
However, its primary interface is programmatic.
Experiment procedures are expressed as Python plans, and extending the system often requires familiarity with concepts such as devices, callbacks and event-based data handling.
While this provides considerable flexibility, it places a programming burden on experimental scientists.
As a consequence, it may make the framework less accessible to users who primarily want to configure and execute experiments rather than develop software.

[Qudi-Core](https://github.com/Ulm-IQO/qudi-core) takes a similar modular approach.
It allows users to coordinate measurements across instruments, including distributed hardware.
It separates experiment functionality into three layers: graphical user interfaces, control logic and hardware interfaces.
This provides a well-defined and extensible architecture, with existing modules that can be reused across experiments.
However, extending the framework typically requires users to develop Python modules that conform to its architecture.
Consequently, implementing new experimental procedures can still require substantial programming effort.

[PLACE](https://github.com/palab/place) offers another modular approach to laboratory automation.
It provides a server-based architecture, with a browser interface for configuring and executing experiments.
Experimental procedures are described using structured JSON data.
Data acquisition and communication with instruments are handled through Python modules.
This separates the experiment description from the underlying hardware implementation.
However, supporting new experimental setups still requires the development of appropriate Python modules, and the framework relies on its own server and module architecture.


All of the above existing frameworks already provide complete, powerful tools for experiment control.
Each of them make architectural choices that reflect their design goals and target use cases.
These choices involve trade-offs between configurability, programming effort, deployment complexity and operational monitoring.

We believe there is room for an alternative approach that places a different emphasis on these trade-offs.

With `comodo`, we take an opinionated stance in regards to experiment control.
Rather than providing a general-purpose programming environment for defining experimental procedures, we reduce experiment descriptions to timelines of setpoints.
This limits the range of experiments that can be described, but significantly simplifies configuration and execution for a broad class of experiments.

We make similarly deliberate choices in the underlying infrastructure.
We adopt a containerised approach to deployment, prioritising portability, isolation and reproducibility across different computing environments.
Communication between components is based on MQTT, an established messaging protocol widely used in Internet of Things applications.
This provides a lightweight and decoupled communication mechanism, allowing components to operate independently.
Importantly, it is open and transparent, which also facilitates integration with external systems, including broader Digital Twin infrastructures.

Together, these choices aim to provide an accessible and lightweight infrastructure, that does not require users to develop extensive experiment control software.


# Software design

`comodo` is designed to be able to conform to any network / deployment topology that may be required by the specifics of a deployment scenario.

## Event driven

yes, it is

## Decentralisation

`comodo` is designed as a decentralised stack of smaller software components which each perform a specific task.
Communication between these elements is via MQTT messages, small text messages relayed by a central broker.
The messages may contain command and control messages (e.g. instruments/furnace/temperature/setpoint 350) and telemetry data (e.g. instruments/furnace/temperature/measurement 274).

This decentralised design has several advantages.
- Each component may be deployed where it makes the most sense to do so, e.g. experiment control on a centralised machine, instrument control on dedicated edge hardware where the instrument sits.
- Each component may be made robust to failures of other components.
- Messages can be centrally monitored for correctness and stored for later recall.
- Storage and presentation of data can be handled by off the the shelf components.

## Stage machines

To achieve the decentralisation, and further beneficial characteristics, each software module in `comodo` is conceived as a state machine, keeping it's own internal account of it's state and what actions it can and cannot undertake.

Each module's state is streamed out and other components may react to it.

## Control loops

round and round we go

## Flexibility / Extensibility

`comodo` is designed to be a generic solution for running laboratory experiments.
The stack is configured with a central configuration file which sets up the full runtime environment.
This experiment file is controlled by a schema which prevents invalid configurations.

The central config file controls which instruments are expected and deployed, with firmware being created ad-hoc by taking a standard firmware core and adding an instrument specific plug-in, written to a standard template.

To allow the broadest possible range of experiments to be run, the broadest possible definition of an experiment has been pursued.
An experiment in `comodo` is defined as 'a list of time steps, with the value of each input given at each step'.
This can be visualised as a table, with specified instruments as the columns and time steps as the rows, and this input is exposed to users via the experiment config UI.

## Transparency

`comodo` is a tool for working openly on scientific experiments, all telemetry is stored and made visible to members of the research group involved.
Further, the later application of machine learning may allow additional insights to be derived.

## Robustness

Rather than employing a bespoke experiment control system per laboratory experiment, `comodo` allows users to apply specialisations of battle tested components.
Further each component tries to be able to stand alone and function sensibly when others are not available.
The whole stack is monitored for errors and drift, with various components empowered to take action if a problem is detected.


# Research Impact

`comodo` has been deployed successfully in this work @author:mcfe and is soon to be deployed on a second experiment.

# Acknowledgements

We acknowledge contributions from William Smith who worked hard to deploy this software in the GDPS laboratory.

# References

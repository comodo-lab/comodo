---
title: 'Comodo-Lab: A Python framework for experiment control and automation'
tags:
  - Python
  - experiments
  - firmware
  - provenance
  - telemetry
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
date: 9 Novermber 2026
bibliography: paper.bib

---

# Summary

`comodo` is a software stack for specifying, executing and
developing laboratory experiments. It employs a distributed
architecture; a server-hosted controller module performs orchestration and 
executes the experiment, edge-hardware hosted firmware controls instruments and
users interact with the experiment via a web interface.

The components of `comodo` communicate with each other via MQTT
messages. In addition to providing experiment command and control this
allows the automated recording of lab data and metadata, arranging it
for later queries or the application of machine learning.

`comodo` is designed for users of laboratories employing bespoke
experimental setups, where proprietary software from a single
manufacturer cannot provide a complete solution. 

`comodo` is run and deployed using Docker Compose, this provides a
repeatable setup and easy running. It also enables the components to
communicate internally.

# Statement of need

Laboratory experiments remain the bedrock of scientific endeavour and
discovery. Despite this noble status, the reality of experimental
undertaking can be unglamorous and inefficient. Early career
researchers often spend long hours running and maintaining
experiments. Data is not always preserved and often not analysed. The
collection of metadata and provenance is not standard and not widely
practiced.

Most significantly of all, many experiments are run manually or with
limited, manufacturer produced interfaces. Alternatively, some groups
create homebrewed automations, but this is time consuming and removes
scientists from their primary purpose.

There is a need for a generalised framework for running laboratory
experiments, using modern technologies and architectures, easily
extended to the hardware used in each unique experiment.


# Software design

`comodo` is designed to be able to conform to any network / deployment topology
that may be required by the specifics of a deployment scenario. 

## Event driven
 
yes, it is

## Decentralisation

`comodo` is designed as a decentralised stack of smaller software components 
which each perform a specific task. Communication between these elements is via 
MQTT messages, small text messages relayed by a central broker. The messages may 
contain command and control messages (e.g. instruments/furnace/temperature/setpoint 
350) and telemetry data (e.g. instruments/furnace/temperature/measurement 274).

This decentralised design has several advantages. 
- Each component may be deployed where it makes the most sense to do so, e.g. 
experiment control on a centralised machine, instrument control on dedicated edge
hardware where the instrument sits.
- Each component may be made robust to failures of other components. 
- Messages can be centrally monitored for correctness and stored for later recal
- Storage and presentation of data can be handled by off the the shelf components

## Stage machines

To achieve the decentralisation, and further benificial charcteristics, each 
software module in `comodo` is concieved as a state machine, keeping it's own
internal acount of it's state and what actions it can and cannot understake.

Each module's state is streamed out and other components may react to it.

## Control loops

round and round we go

## Flexibility / Extensibility

`comodo` is designed to be a generic solution for running laboratory experiments.
The stack is configured with a central configuration file which sets up the full
runtime environement. This experiment file is controlled by a schema which prevents
invalid configurations.

The central config file controls which instruments are expected and deployed,
with firmware being created ad-hoc by taking a standard firmware core and adding
an instrument specific plug-in, written to a standard template.

To allow the broadest possible range of experiments to be run, the broadest 
possible definition of an experiment has been pursued. An experiment in `comodo`
is defined as 'a list of time steps, with the value of each input given at each
step'. This can be visualised as a table, with specified instruments as the 
columns and time steps as the rows, and this input is exposed to users via the
experiment config UI.

## Transparency

`comodo` is a tool for working openly on scientific experiments, all telemetry is 
stored and made visiable to members of the research group involved. Further, the 
later application of machine learning may allow additional insights to be derived.

## Robustness

Rather than employing a bespoke experiment control system per laboratory experiment,
`comodo` allows users to apply specialisations of battle tested components. Further
each component tries to be able to stand alone and function sensibly when others
are not available. The whole stack is monitored for errors and drift, with various
components empowered to take action if a problem is detected.


# Research Impact

`comodo` has been deployed successfully in this work @author:mcfe
and is soon to be deployed on a second experiment.

# Acknowledgements

We acknowledge contributions from William Smith who worked hard to deploy this 
software in the GDPS laboratory.

# References

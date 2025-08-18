---
title: 'Comodo-Lab: A Python framework for experiment control and automation'
tags:
  - Python
  - experiments
  - firmware
  - provenance
  - telemetry
authors:
  - name: Oliver J. Woolland
    orcid: 0000-0002-4565-9760
    corresponding: true
    equal-contrib: true
    affiliation: '1'
  - name: Francisco Herrerías-Azcué
    orcid: 0000-0002-5906-221X
    equal-contrib: true
    affiliation: '1'
affiliations:
 - name: University of Manchester 
   index: 1
   ror: 027m9bs27
date: 15 August 2025
bibliography: paper.bib

---

# Summary

`Comodo-Lab` is a software package for running, managing and
developing laboratory experiments. It employs a distributed
architecture with users accessing the interface through their browser
locally, a server-hosted, controller module for orchestration and
edge-hardware hosted firmware for controlling the instruments.

The components of `Comodo-Lab` communicate with each other via MQTT
messages. In addition to providing experiment command and control this
allows the automated recording of lab data and metadata, arranging it
for later queries or the application of machine learning.

`Comodo-Lab` is designed for users of laboratories employing bespoke
experimental setups, where proprietary software from a single
manufacturer cannot provide a complete solution.

`Comodo-Lab` is run and deployed using Docker Compose, this provides a
repeatable setup and easy running. It also enables the components to
communicate internally.

`Comodo-Lab` has been deployed successfully in this work @author:mcfe
and is soon to be deployed on a second experiment.

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

# Acknowledgements

We acknowledge contributions from Brigitta Sipocz, Syrtis Major, and
Semyeong Oh, and support from Kathryn Johnston during the genesis of
this project.

# References

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

# Acknowledgements

We acknowledge contributions from Brigitta Sipocz, Syrtis Major, and
Semyeong Oh, and support from Kathryn Johnston during the genesis of
this project.

# References

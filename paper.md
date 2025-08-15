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

Even in an age of ever more powerful simulations, experiments remain the bedrock
of scientific endevour and discovery. Desipite this nobel status, the reality of 
experimental undertaking can be unglamourous and inefficient. Early career 
researchers often spend long hours running and maintaining experiments. Data is 
not always preserved and certainly not always analysed. The collection of 
metadata and provenance is not standard and not widely practiced. 

Most significantly of all, many experiments are run manually or with limited, 
manufacturer produced interfaces, or homebrewed automation. Dog eared LabVIEW 
scripts are passed from postdoc to postdoc with caveats and saftey warnings.

There is a need for a generalised framework for running laboratory experiments,
using modern technologies and architectures, easily extended to the hardware used
in each unique experiment.

# Statement of need

`Comodo-Lab` is a software package for running, managing and developing 
laboratory experiments. It employes a distributed architecture with users 
accessing the interface through their browser locally, a sever-hosted, 
controller module for orchestration and edge-hardware hosted firmware for 
controlling the instruments.

`Comodo-Lab` automates the recording of lab data and metadata, arranging it for 
later quiries or the application of machine learning.

`Comodo-Lab` is designed for laboratories employing bespoke experimental setups, 
where proprietary software from a single manufacturer cannot provide a complete
solution.

`Comodo-Lab` has been deployed succesfully in @author:fase and @author:mcfe.

# Design

`Comodo-Lab` is a distributed application. With a central server hosing a 
controller module. Firmware is deployed on edge hardware connected physically to
the instruments and users and design and launch experiments from a bespoke UI.

These components communicate via MQTT protocol messages. This enables the 
decoupling central to `Comodo-Lab`'s design and for new components to be easily
added. 

In addition to the core components there are several supporting services, these
are generally widely used open source software packages which provide standard
but powerful solutions to the challenges of laboratory experiments.

We will go into the individual components a little more here

### Core

- UI: A user facing front end for configuring and launching experiments, acessed 
through a web browser
- Controller: A server hosted application responsible for impementing the
experiment which has been specified and monitoring the status of the physical
equpiment
- Firmware: Low level software (often deployed on edge hardware e.g. 
microcontroller) responsible for converting generic instructios from the 
controller into machine level instructions. Also reports readings 

### Supporting 

- RabbitMQ: Broker for the MQTT messages
- Telegraf: Converts MQTT messages into entries
- InfluxDB: Stores entries in a time series database
- Grafana: Creates dashboards using the data stored in the database

# Implemetation and deployment

`Comodo-Lab` is run and deployed using Docker Compose, this provides a repeatable
setup and easy running. It also enables the components to communicate internally.

# Citations

Citations to entries in paper.bib should be in
[rMarkdown](http://rmarkdown.rstudio.com/authoring_bibliographies_and_citations.html)
format.

If you want to cite a software repository URL (e.g. something on GitHub without a preferred
citation) then you can do it with the example BibTeX entry below for @fidgit.

For a quick reference, the following citation commands can be used:
- `@author:2001`  ->  "Author et al. (2001)"
- `[@author:2001]` -> "(Author et al., 2001)"
- `[@author1:2001; @author2:2001]` -> "(Author1 et al., 2001; Author2 et al., 2002)"

# Figures

Figures can be included like this:
![Caption for example figure.\label{fig:example}](figure.png)
and referenced from text using \autoref{fig:example}.

Figure sizes can be customized by adding an optional second parameter:
![Caption for example figure.](figure.png){ width=20% }

# Acknowledgements

We acknowledge contributions from Brigitta Sipocz, Syrtis Major, and Semyeong
Oh, and support from Kathryn Johnston during the genesis of this project.

# References

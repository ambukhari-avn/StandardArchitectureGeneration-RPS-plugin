# PLC/SCADA Architecture — Mandatory Drawing Rules

Technical accuracy takes precedence over visual simplification. Simplify appearance
without changing the physical or logical topology. These rules supplement the
existing fixed image library, page fitting, navy heading tabs, joined A3 footer,
title block, scope colours, cable palette and line weights; preserve those settings.

## A. Architecture layout

1. Use top-to-bottom SCADA → Control → Field hierarchy. Include other standard layers only when required.
2. Maintain consistent equipment alignment, spacing and grouping.
3. Group equipment by functional system, control panel or network zone.
4. Use standard equipment pictures with captions beneath each item; obey the approved fixed-image policy.
5. Include no unnecessary equipment, communication rings or connections.
6. Maintain the established A3 footer, title block, scope colours and legend.

## B. Cable connectivity

1. Connect field instruments to their associated PLC I/O rack with hardwired signal connections where specified.
2. Group instruments sharing a destination I/O rack and show one representative hardwired connection from their group boundary to that rack.
3. Preserve each individual instrument-to-I/O relationship in the architecture data and connector metadata.
4. Never combine different destination I/O racks into a representative cable, even if they share a panel.
5. Label representative connections exactly “Typical Hardwired Signals — AI/DI/AO/DO.” This is a generic drawing convention, not proof that every listed signal type is used.
6. Add a note explaining that grouped lines represent multiple physical field connections.
7. Connect redundant controllers through their specified dedicated redundancy/synchronization interfaces.
8. Show separate synchronization links only when supported or required by the selected controller platform.
9. Connect PLCs, SCADA servers, workstations and network devices according to the specified physical topology.
10. Distinguish Ethernet, fibre optic, RS-485/Modbus, BACnet and hardwired links using the existing cable configuration. The `modbus` cable key is appropriate only for a specified RS-485/Modbus link; do not assume all Modbus is serial.
11. Never choose cable types from assumptions. Resolve missing interface information before building.
12. Show communication redundancy only when explicitly specified or technically validated.

## C. Cable routing and appearance

1. Use horizontal and vertical orthogonal segments; no diagonal cable routes. Small crossing hops are the established visual exception.
2. Attach lines continuously to equipment or group boundaries without gaps.
3. Minimize crossings and overlapping routes; use crossing hops where unavoidable.
4. Keep cables clear of equipment pictures, captions and headings.
5. Keep cable labels clear of intersections, equipment and other labels.
6. Maintain established cable colours and consistent weights.
7. Use shared visual trunks only where they accurately represent topology.
8. Keep redundant paths visually distinguishable.

## D. Equipment representation

1. Show CPUs, I/O racks, servers, workstations, firewalls and network switches as separate major equipment where applicable.
2. Represent multiple I/O modules as one rack unless module-level detail is requested.
3. Omit terminal blocks, DIN rails, cable cores and panel accessories from proposal architecture.
4. Include every major functional device required by the project.
5. Use consistent library pictures for equipment categories.
6. Add manufacturer/model captions only when specified. Library catalogue metadata does not authorize inventing a model.
7. Never invent equipment to fill space.

## E. Redundancy and topology

1. Show Primary and Secondary PLCs separately.
2. Identify redundancy links distinctly from normal communication links, using labels and interface information while retaining the configured cable type/colour.
3. Add dual switches, dual interfaces and redundant paths only when specified or required by an approved topology.
4. Never automatically create fibre rings.
5. Redundant PLCs do not imply redundant field I/O.
6. Do not imply redundancy where a single physical path creates a common failure point.
7. Put firewalls at actual security-zone boundaries.
8. Clearly identify existing and third-party system interfaces.

## F. Quality assurance before delivery

- Verify every required major device is represented, with correct groups and scope boundaries.
- Validate every logical source and destination, including all hidden individual field relationships.
- Check cable types against actual interfaces; confirm controller redundancy and physical network paths.
- Do not conceal different rack destinations in grouped lines.
- Confirm continuous clear routes and label positions, with no overlaps through equipment or headings.
- Preserve the A3 footer format, legend, scope colours and cable colours. Preserve supplied notes and add the mandatory grouping explanation when applicable.
- Build an editable Visio file with the supplied generator and inspect its preview.

Use project specifications and approved topology as evidence. Where controller
platform validation is necessary, consult current primary manufacturer documents
and record the source; do not invent technical compatibility. If essential
interface/topology facts are missing, ask a focused question. Automated structural
checks cannot establish physical platform compatibility or replace this review.

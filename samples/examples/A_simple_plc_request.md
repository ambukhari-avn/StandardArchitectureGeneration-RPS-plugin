ARCHITECTURE REQUEST — Water Treatment Plant Upgrade
(Edit any line, keep the [IDs], add new lines without an ID, delete lines to remove items. '-' means not stated.)

## Project
Client / Contractor: ACME Contracting
End User: City Water Authority
Project: Water Treatment Plant Upgrade
Document Title: PLC & SCADA System Architecture
Prepared By: AMB
Checked By: TBC
Approved By: TBC
Drawing Revision: R0

## Layers (top of drawing first)
- [L1] Level 1 | Control System | -
- [L0] Level 0 | Field Instruments | -

## Equipment
### [L0] Field Instruments
- [EQ-001] Pressure Transmitters | Qty: 4 | Category: instrument | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Pressure Transmitters — 4"
- [EQ-002] Temperature Transmitters | Qty: 3 | Category: instrument | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Temperature Transmitters — 3"
- [EQ-003] Flow Transmitters | Qty: 2 | Category: instrument | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Flow Transmitters — 2"
### [L1] Control System
- [EQ-004] PLC | Qty: 1 | Category: plc | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "PLC — 1"
- [EQ-005] Remote I/O Rack | Qty: 1 | Category: io | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Remote I/O Rack — 1"
- [EQ-006] Industrial Ethernet Switch | Qty: 1 | Category: switch | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: Ethernet | Notes: -
  Original: "Industrial Ethernet Switch — 1"
- [EQ-007] HMI Panel | Qty: 1 | Category: hmi | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "HMI Panel — 1"

## Connections
- [CN-001] EQ-001 Pressure Transmitters -> EQ-005 Remote I/O Rack | Protocol: Hardwired AI/DI/AO/DO | Medium: Copper (hardwired) | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: Field to control | Scope: - | Label: Typical Hardwired Signals — AI/DI/AO/DO | Via: -
- [CN-002] EQ-002 Temperature Transmitters -> EQ-005 Remote I/O Rack | Protocol: Hardwired AI/DI/AO/DO | Medium: Copper (hardwired) | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: Field to control | Scope: - | Label: Typical Hardwired Signals — AI/DI/AO/DO | Via: -
- [CN-003] EQ-003 Flow Transmitters -> EQ-005 Remote I/O Rack | Protocol: Hardwired AI/DI/AO/DO | Medium: Copper (hardwired) | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: Field to control | Scope: - | Label: Typical Hardwired Signals — AI/DI/AO/DO | Via: -
- [CN-004] EQ-006 Industrial Ethernet Switch -> EQ-005 Remote I/O Rack | Protocol: PROFINET | Medium: Copper Ethernet | Topology: Star | Redundancy: Single | Paths: - | Direction: - | Scope: - | Label: - | Via: -
- [CN-005] EQ-004 PLC -> EQ-006 Industrial Ethernet Switch | Protocol: - | Medium: Copper Ethernet | Topology: Star | Redundancy: Single | Paths: - | Direction: - | Scope: - | Label: - | Via: - | Units: 1-1
- [CN-006] EQ-007 HMI Panel -> EQ-006 Industrial Ethernet Switch | Protocol: PROFINET | Medium: Copper Ethernet | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: - | Scope: - | Label: - | Via: -

## Unresolved technical questions (generated; answer them in chat)
- none

## Notes

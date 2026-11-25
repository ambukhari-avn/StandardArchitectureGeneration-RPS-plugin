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
- [L2] Level 2 | SCADA / Supervisory | -
- [L1] Level 1 | Control System | -
- [L0] Level 0 | Field Instruments | -

## Equipment
### [L0] Field Instruments
- [EQ-001] Pressure Transmitters | Qty: 12 | Category: instrument | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Pressure Transmitters — 12"
- [EQ-002] Temperature Transmitters | Qty: 8 | Category: instrument | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Temperature Transmitters — 8"
- [EQ-003] Flow Transmitters | Qty: 6 | Category: instrument | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Flow Transmitters — 6"
### [L1] Control System
- [EQ-004] Redundant PLC CPUs | Qty: 2 | Category: plc | OEM: - | Model: - | Redundancy: Redundant pair | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Redundant PLC CPUs (hot standby) — 2"
- [EQ-005] Remote I/O Racks | Qty: 4 | Category: io | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Remote I/O Racks — 4"
- [EQ-006] Industrial Ethernet Switches | Qty: 2 | Category: switch | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: Ethernet | Notes: -
  Original: "Industrial Ethernet Switches — 2"
### [L2] SCADA / Supervisory
- [EQ-007] SCADA Servers | Qty: 2 | Category: server | OEM: - | Model: - | Redundancy: Redundant pair | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "SCADA Servers — 2 (redundant)"
- [EQ-008] Operator Workstation | Qty: 1 | Category: workstation | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Operator Workstation — 1"

## Connections
- [CN-001] EQ-001 Pressure Transmitters -> EQ-005 Remote I/O Racks | Protocol: Hardwired AI/DI/AO/DO | Medium: Copper (hardwired) | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: Field to control | Scope: - | Label: Typical Hardwired Signals — AI/DI/AO/DO | Via: -
- [CN-002] EQ-002 Temperature Transmitters -> EQ-005 Remote I/O Racks | Protocol: Hardwired AI/DI/AO/DO | Medium: Copper (hardwired) | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: Field to control | Scope: - | Label: Typical Hardwired Signals — AI/DI/AO/DO | Via: -
- [CN-003] EQ-003 Flow Transmitters -> EQ-005 Remote I/O Racks | Protocol: Hardwired AI/DI/AO/DO | Medium: Copper (hardwired) | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: Field to control | Scope: - | Label: Typical Hardwired Signals — AI/DI/AO/DO | Via: -
- [CN-004] EQ-006 Industrial Ethernet Switches -> EQ-005 Remote I/O Racks | Protocol: PROFINET | Medium: Copper Ethernet | Topology: Star | Redundancy: Redundant network | Paths: 2 | Direction: - | Scope: - | Label: - | Via: -
- [CN-005] EQ-004 Redundant PLC CPUs (primary <-> secondary) | Protocol: OEM redundancy synchronization | Medium: Fiber optic | Topology: Point-to-point | Redundancy: Redundant pair | Paths: 2 | Direction: - | Scope: - | Label: Redundancy Sync | Via: -
- [CN-006] EQ-004 Redundant PLC CPUs -> EQ-006 Industrial Ethernet Switches | Protocol: - | Medium: Copper Ethernet | Topology: Star | Redundancy: Single | Paths: - | Direction: - | Scope: - | Label: - | Via: - | Units: 1-1, 2-2
- [CN-007] EQ-006 Industrial Ethernet Switches -> EQ-007 SCADA Servers | Protocol: - | Medium: Copper Ethernet | Topology: Point-to-point | Redundancy: Dual independent paths | Paths: 1 | Direction: - | Scope: - | Label: - | Via: - | Units: 1-1, 2-2
- [CN-008] EQ-008 Operator Workstation -> EQ-006 Industrial Ethernet Switches | Protocol: Ethernet (TCP/IP) | Medium: Copper Ethernet | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: - | Scope: - | Label: - | Via: -

## Unresolved technical questions (generated; answer them in chat)
- none

## Notes

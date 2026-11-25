ARCHITECTURE REQUEST — Water Treatment Plant Upgrade
(Edit any line, keep the [IDs], add new lines without an ID, delete lines to remove items. '-' means not stated.)

## Project
Client / Contractor: ACME Contracting
End User: City Water Authority
Project: Water Treatment Plant Upgrade
Document Title: OT Network Architecture with DMZ
Prepared By: AMB
Checked By: TBC
Approved By: TBC
Drawing Revision: R0

## Layers (top of drawing first)
- [L4] Level 4 | Enterprise / Business Network | -
- [L3.5] Level 3.5 | DMZ — Demilitarized Zone | -
- [L2] Level 2 | SCADA / Supervisory | -
- [L1] Level 1 | Control | -

## Equipment
### [L1] Control
- [EQ-001] PLC | Qty: 1 | Category: plc | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "PLC — 1"
- [EQ-002] Industrial Ethernet Switch | Qty: 1 | Category: switch | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: Ethernet | Notes: -
  Original: "Industrial Ethernet Switch — 1"
### [L2] SCADA / Supervisory
- [EQ-003] SCADA Servers | Qty: 2 | Category: server | OEM: - | Model: - | Redundancy: Redundant pair | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "SCADA Servers — 2 (redundant)"
- [EQ-004] SCADA Switch | Qty: 1 | Category: switch | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "SCADA Switch — 1"
### [L3.5] DMZ — Demilitarized Zone
- [EQ-005] Firewall | Qty: 1 | Category: firewall | OEM: Fortinet | Model: FortiGate 100F | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Firewall — 1 (Fortinet FortiGate 100F)"
- [EQ-006] Historian Replica Server | Qty: 1 | Category: historian | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Historian Replica Server — 1"
### [L4] Enterprise / Business Network
- [EQ-007] ERP Server | Qty: 1 | Category: server | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "ERP Server — 1"
- [EQ-008] Corporate Switch | Qty: 1 | Category: switch | OEM: - | Model: - | Redundancy: - | Location: - | Scope: - | Interfaces: - | Notes: -
  Original: "Corporate Switch — 1"

## Connections
- [CN-001] EQ-001 PLC -> EQ-002 Industrial Ethernet Switch | Protocol: - | Medium: Copper Ethernet | Topology: Star | Redundancy: Single | Paths: - | Direction: - | Scope: - | Label: - | Via: - | Units: 1-1
- [CN-002] EQ-002 Industrial Ethernet Switch -> EQ-004 SCADA Switch | Protocol: - | Medium: Fiber optic | Topology: Point-to-point | Redundancy: Single | Paths: 1 | Direction: - | Scope: - | Label: - | Via: - | Units: 1-1
- [CN-003] EQ-003 SCADA Servers -> EQ-004 SCADA Switch | Protocol: Ethernet (TCP/IP) | Medium: Copper Ethernet | Topology: Star | Redundancy: Single-homed | Paths: - | Direction: - | Scope: - | Label: - | Via: - | Units: 1-1, 2-1
- [CN-004] EQ-005 Firewall -> EQ-004 SCADA Switch | Protocol: Ethernet (TCP/IP) | Medium: Copper Ethernet | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: - | Scope: - | Label: - | Via: - | Units: 1-1
- [CN-005] EQ-005 Firewall -> EQ-008 Corporate Switch | Protocol: Ethernet (TCP/IP) | Medium: Copper Ethernet | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: - | Scope: - | Label: - | Via: - | Units: 1-1
- [CN-006] EQ-006 Historian Replica Server -> EQ-005 Firewall | Protocol: OPC UA | Medium: Copper Ethernet | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: - | Scope: - | Label: - | Via: -
- [CN-007] EQ-007 ERP Server -> EQ-008 Corporate Switch | Protocol: Ethernet (TCP/IP) | Medium: Copper Ethernet | Topology: Point-to-point | Redundancy: Single | Paths: - | Direction: - | Scope: - | Label: - | Via: -

## Unresolved technical questions (generated; answer them in chat)
- none

## Notes

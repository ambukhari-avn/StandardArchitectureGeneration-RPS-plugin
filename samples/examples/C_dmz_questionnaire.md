# Example questionnaire — Test C: architecture with a DMZ

**Claude:** Step 1 — Project details: Client / Contractor, End User, Project, Document Title, Prepared By, Checked By, Approved By, Drawing Revision? (leave any blank for TBC)

**User:** Client / Contractor: ACME Contracting; End User: City Water Authority; Project: Water Treatment Plant Upgrade; Document Title: OT Network Architecture with DMZ; Prepared By: AMB; Checked By: (blank); Approved By: (blank); Drawing Revision: R0

**Claude:** Step 2 — Which Purdue layers does this architecture need? Level 0 Field Instruments, Level 1 Control, Level 2 SCADA / Supervisory, Level 3 Site Operations, Level 3.5 DMZ — Demilitarized Zone, Level 4 Enterprise / Business Network, Level 5 External / Corporate / Cloud Systems (rename or add custom layers if needed)

**User:** L1, L2, L3.5, L4

**Claude:** Step 3 — What equipment and quantities are required in Level 1 — Control?

**User:** 

    PLC — 1
    Industrial Ethernet Switch — 1

**Claude:** Recorded: EQ-001 PLC ×1; EQ-002 Industrial Ethernet Switch ×1

**Claude:** Step 3 — What equipment and quantities are required in Level 2 — SCADA / Supervisory?

**User:** 

    SCADA Servers — 2 (redundant)
    SCADA Switch — 1

**Claude:** Recorded: EQ-003 SCADA Servers ×2; EQ-004 SCADA Switch ×1

**Claude:** Step 3 — What equipment and quantities are required in Level 3.5 — DMZ — Demilitarized Zone?

**User:** 

    Firewall — 1 (Fortinet FortiGate 100F)
    Historian Replica Server — 1

**Claude:** Recorded: EQ-005 Firewall ×1; EQ-006 Historian Replica Server ×1

**Claude:** Step 3 — What equipment and quantities are required in Level 4 — Enterprise / Business Network?

**User:** 

    ERP Server — 1
    Corporate Switch — 1

**Claude:** Recorded: EQ-007 ERP Server ×1; EQ-008 Corporate Switch ×1

**Claude:** Step 4 — How are the PLC controllers PLC (EQ-001) connected to the industrial Ethernet switches (EQ-002 Industrial Ethernet Switch (x1))?  
  ( ) Single PLC to one switch  
  ( ) Redundant network configuration  
  ( ) Not Applicable  
  ( ) Other / Specify

**User:** Single PLC to one switch

**Claude:** Step 4 — Which physical medium connects the PLCs to the switches?  
  ( ) Copper Ethernet  
  ( ) Fiber optic  
  ( ) Other / Specify

**User:** Copper Ethernet

**Claude:** Step 4 — How does the Control network connect to the SCADA network?  
  ( ) Copper Ethernet  
  ( ) Fiber optic Ethernet  
  ( ) Dual redundant Ethernet paths  
  ( ) Through firewall / gateway  
  ( ) Not Applicable  
  ( ) Other / Specify

**User:** Fiber optic Ethernet

**Claude:** Step 4 — Which physical medium connects the SCADA servers and workstations (EQ-003 SCADA Servers (x2)) to the SCADA switch?  
  ( ) Copper Ethernet  
  ( ) Fiber optic  
  ( ) Not Applicable  
  ( ) Other / Specify

**User:** Copper Ethernet

**Claude:** Step 4 — What is the fiber optic network topology?  
  ( ) Point-to-point  
  ( ) Dual independent paths  
  ( ) Fiber optic ring  
  ( ) Other / Specify

**User:** Point-to-point

**Claude:** Step 4 — Which two networks or security zones does the firewall Firewall (EQ-005) connect?  
  ( ) Level 4 Enterprise / Business Network  
  ( ) Level 3.5 DMZ — Demilitarized Zone  
  ( ) Level 2 SCADA / Supervisory  
  ( ) Level 1 Control  
  ( ) Other / Specify

**User:** Level 2 SCADA / Supervisory, Level 4 Enterprise / Business Network

**Claude:** Step 4 — Which physical medium connects the firewall EQ-005 to those networks?  
  ( ) Copper Ethernet  
  ( ) Fiber optic  
  ( ) Other / Specify

**User:** Copper Ethernet

**Claude:** Step 4 — What does the Historian Replica Server (EQ-006) connect to?  
  ( ) EQ-008 Corporate Switch  
  ( ) EQ-004 SCADA Switch  
  ( ) EQ-002 Industrial Ethernet Switch  
  ( ) EQ-005 Firewall  
  ( ) EQ-007 ERP Server  
  ( ) EQ-003 SCADA Servers  
  ( ) EQ-001 PLC  
  ( ) Not Applicable  
  ( ) Other / Specify

**User:** EQ-005 Firewall

**Claude:** Step 4 — Which communication protocol does EQ-006 use to talk to EQ-005?  
  ( ) Ethernet (TCP/IP)  
  ( ) Modbus TCP  
  ( ) Modbus RTU  
  ( ) OPC UA  
  ( ) Other / Specify

**User:** OPC UA

**Claude:** Step 4 — Which physical medium links EQ-006 to EQ-005?  
  ( ) Copper Ethernet  
  ( ) Fiber optic  
  ( ) RS-485  
  ( ) RS-232  
  ( ) Wireless  
  ( ) Other / Specify

**User:** Copper Ethernet

**Claude:** Step 4 — What does the ERP Server (EQ-007) connect to?  
  ( ) EQ-008 Corporate Switch  
  ( ) EQ-004 SCADA Switch  
  ( ) EQ-002 Industrial Ethernet Switch  
  ( ) EQ-005 Firewall  
  ( ) EQ-006 Historian Replica Server  
  ( ) EQ-003 SCADA Servers  
  ( ) EQ-001 PLC  
  ( ) Not Applicable  
  ( ) Other / Specify

**User:** EQ-008 Corporate Switch

**Claude:** Step 4 — Which communication protocol does EQ-007 use to talk to EQ-008?  
  ( ) Ethernet (TCP/IP)  
  ( ) Modbus TCP  
  ( ) Modbus RTU  
  ( ) OPC UA  
  ( ) Other / Specify

**User:** Ethernet (TCP/IP)

**Claude:** Step 4 — Which physical medium links EQ-007 to EQ-008?  
  ( ) Copper Ethernet  
  ( ) Fiber optic  
  ( ) RS-485  
  ( ) RS-232  
  ( ) Wireless  
  ( ) Other / Specify

**User:** Copper Ethernet

**Claude:** Step 5 — review (below). Anything to change before I generate the drawing?

**User:** Generate it.


# Architecture request review

**Stage:** connectivity

## Project information
- Client / Contractor: ACME Contracting
- End User: City Water Authority
- Project: Water Treatment Plant Upgrade
- Document Title: OT Network Architecture with DMZ
- Prepared By: AMB
- Checked By: TBC
- Approved By: TBC
- Drawing Revision: R0

## Selected layers (top of drawing first)
- Level 4 **Enterprise / Business Network** (L4)
- Level 3.5 **DMZ — Demilitarized Zone** (L3.5)
- Level 2 **SCADA / Supervisory** (L2)
- Level 1 **Control** (L1)

## Equipment per layer
**Level 1 — Control**
- EQ-001 PLC — qty 1
- EQ-002 Industrial Ethernet Switch — qty 1

**Level 2 — SCADA / Supervisory**
- EQ-003 SCADA Servers — qty 2 (Redundant pair)
- EQ-004 SCADA Switch — qty 1

**Level 3.5 — DMZ — Demilitarized Zone**
- EQ-005 Firewall — qty 1 (Fortinet, FortiGate 100F)
- EQ-006 Historian Replica Server — qty 1

**Level 4 — Enterprise / Business Network**
- EQ-007 ERP Server — qty 1
- EQ-008 Corporate Switch — qty 1

## Connectivity summary
- CN-001 PLC ↔ Industrial Ethernet Switch: - / Copper Ethernet / Star / Single
- CN-002 Industrial Ethernet Switch ↔ SCADA Switch: - / Fiber optic / Point-to-point / Single
- CN-003 SCADA Servers ↔ SCADA Switch: Ethernet (TCP/IP) / Copper Ethernet / Star / Single-homed
- CN-004 Firewall ↔ SCADA Switch: Ethernet (TCP/IP) / Copper Ethernet / Point-to-point / Single
- CN-005 Firewall ↔ Corporate Switch: Ethernet (TCP/IP) / Copper Ethernet / Point-to-point / Single
- CN-006 Historian Replica Server ↔ Firewall: OPC UA / Copper Ethernet / Point-to-point / Single
- CN-007 ERP Server ↔ Corporate Switch: Ethernet (TCP/IP) / Copper Ethernet / Point-to-point / Single

## Unresolved technical questions
- none

## Additional notes
- (none)

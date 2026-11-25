# Example questionnaire — Test B: redundant PLC architecture

**Claude:** Step 1 — Project details: Client / Contractor, End User, Project, Document Title, Prepared By, Checked By, Approved By, Drawing Revision? (leave any blank for TBC)

**User:** Client / Contractor: ACME Contracting; End User: City Water Authority; Project: Water Treatment Plant Upgrade; Document Title: PLC & SCADA System Architecture; Prepared By: AMB; Checked By: (blank); Approved By: (blank); Drawing Revision: R0

**Claude:** Step 2 — Which Purdue layers does this architecture need? Level 0 Field Instruments, Level 1 Control, Level 2 SCADA / Supervisory, Level 3 Site Operations, Level 3.5 DMZ — Demilitarized Zone, Level 4 Enterprise / Business Network, Level 5 External / Corporate / Cloud Systems (rename or add custom layers if needed)

**User:** L0, L1, L2; rename L1 to "Control System"

**Claude:** Step 3 — What equipment and quantities are required in Level 0 — Field Instruments?

**User:** 

    Pressure Transmitters — 12
    Temperature Transmitters — 8
    Flow Transmitters — 6

**Claude:** Recorded: EQ-001 Pressure Transmitters ×12; EQ-002 Temperature Transmitters ×8; EQ-003 Flow Transmitters ×6

**Claude:** Step 3 — What equipment and quantities are required in Level 1 — Control System?

**User:** 

    Redundant PLC CPUs (hot standby) — 2
    Remote I/O Racks — 4
    Industrial Ethernet Switches — 2

**Claude:** Recorded: EQ-004 Redundant PLC CPUs ×2; EQ-005 Remote I/O Racks ×4; EQ-006 Industrial Ethernet Switches ×2

**Claude:** Step 3 — What equipment and quantities are required in Level 2 — SCADA / Supervisory?

**User:** 

    SCADA Servers — 2 (redundant)
    Operator Workstation — 1

**Claude:** Recorded: EQ-007 SCADA Servers ×2; EQ-008 Operator Workstation ×1

**Claude:** Step 4 — How are the field instruments connected to the Control system?  
  ( ) Hardwired AI/DI/AO/DO  
  ( ) Modbus RTU over RS-485  
  ( ) Modbus TCP over Ethernet  
  ( ) Fiber optic through a suitable interface  
  ( ) Mixed communication methods  
  ( ) Other / Specify

**User:** Hardwired AI/DI/AO/DO

**Claude:** Step 4 — How are the remote I/O racks connected to the PLC system?  
  ( ) PROFINET  
  ( ) EtherNet/IP  
  ( ) Modbus TCP  
  ( ) PROFIBUS  
  ( ) Local backplane / directly attached I/O  
  ( ) Other / Specify

**User:** PROFINET

**Claude:** Step 4 — What is the required remote I/O topology?  
  ( ) Star  
  ( ) Daisy-chain  
  ( ) Ring  
  ( ) Dual redundant network  
  ( ) Local backplane  
  ( ) Other / Specify

**User:** Dual redundant network

**Claude:** Step 4 — Which physical cable medium links the remote I/O racks (PROFINET, dual)?  
  ( ) Copper Ethernet  
  ( ) Fiber optic  
  ( ) Other / Specify

**User:** Copper Ethernet

**Claude:** Step 4 — A dual redundant network cannot be shown accurately with one rack picture. How should the I/O racks be drawn?  
  ( ) Show each rack (exact topology) — recommended  
  ( ) One representative rack with the quantity and topology written on its link  
  ( ) Other / Specify

**User:** One representative rack with the quantity and topology written on its link

**Claude:** Step 4 — How are the primary and secondary controllers of Redundant PLC CPUs (EQ-004) synchronized?  
  ( ) Dedicated OEM synchronization links  
  ( ) Ethernet-based synchronization  
  ( ) Fiber optic synchronization  
  ( ) OEM-standard configuration — to be verified  
  ( ) Other / Specify

**User:** Dedicated OEM synchronization links

**Claude:** Step 4 — How many physical synchronization links connect the two controllers of EQ-004?  
  ( ) 1  
  ( ) 2  
  ( ) Not known — to be verified  
  ( ) Other / Specify

**User:** 2

**Claude:** Step 4 — Which physical medium do the EQ-004 synchronization links use?  
  ( ) Fiber optic  
  ( ) Copper / OEM sync cable  
  ( ) Not known — to be verified  
  ( ) Other / Specify

**User:** Fiber optic

**Claude:** Step 4 — How are the PLC controllers Redundant PLC CPUs (EQ-004) connected to the industrial Ethernet switches (EQ-006 Industrial Ethernet Switches (x2))?  
  ( ) Each PLC connects to one dedicated switch  
  ( ) Both PLCs connect to both switches  
  ( ) Single PLC to one switch  
  ( ) Redundant network configuration  
  ( ) Not Applicable  
  ( ) Other / Specify

**User:** Each PLC connects to one dedicated switch

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

**User:** Dual redundant Ethernet paths

**Claude:** Step 4 — Which physical medium do the Control-to-SCADA links use?  
  ( ) Copper Ethernet  
  ( ) Fiber optic  
  ( ) Other / Specify

**User:** Copper Ethernet

**Claude:** Step 4 — What is the fiber optic network topology?  
  ( ) Point-to-point  
  ( ) Dual independent paths  
  ( ) Fiber optic ring  
  ( ) Other / Specify

**User:** Point-to-point

**Claude:** Step 4 — What does the Operator Workstation (EQ-008) connect to?  
  ( ) EQ-006 Industrial Ethernet Switches  
  ( ) EQ-007 SCADA Servers  
  ( ) EQ-004 Redundant PLC CPUs  
  ( ) EQ-005 Remote I/O Racks  
  ( ) Not Applicable  
  ( ) Other / Specify

**User:** EQ-006 Industrial Ethernet Switches

**Claude:** Step 4 — Which communication protocol does EQ-008 use to talk to EQ-006?  
  ( ) Ethernet (TCP/IP)  
  ( ) Modbus TCP  
  ( ) Modbus RTU  
  ( ) OPC UA  
  ( ) Other / Specify

**User:** Ethernet (TCP/IP)

**Claude:** Step 4 — Which physical medium links EQ-008 to EQ-006?  
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
- Document Title: PLC & SCADA System Architecture
- Prepared By: AMB
- Checked By: TBC
- Approved By: TBC
- Drawing Revision: R0

## Selected layers (top of drawing first)
- Level 2 **SCADA / Supervisory** (L2)
- Level 1 **Control System** (L1)
- Level 0 **Field Instruments** (L0)

## Equipment per layer
**Level 0 — Field Instruments**
- EQ-001 Pressure Transmitters — qty 12
- EQ-002 Temperature Transmitters — qty 8
- EQ-003 Flow Transmitters — qty 6

**Level 1 — Control System**
- EQ-004 Redundant PLC CPUs — qty 2 (Redundant pair)
- EQ-005 Remote I/O Racks — qty 4
- EQ-006 Industrial Ethernet Switches — qty 2

**Level 2 — SCADA / Supervisory**
- EQ-007 SCADA Servers — qty 2 (Redundant pair)
- EQ-008 Operator Workstation — qty 1

## Connectivity summary
- CN-001 Pressure Transmitters ↔ Remote I/O Racks: Hardwired AI/DI/AO/DO / Copper (hardwired) / Point-to-point / Single
- CN-002 Temperature Transmitters ↔ Remote I/O Racks: Hardwired AI/DI/AO/DO / Copper (hardwired) / Point-to-point / Single
- CN-003 Flow Transmitters ↔ Remote I/O Racks: Hardwired AI/DI/AO/DO / Copper (hardwired) / Point-to-point / Single
- CN-004 Industrial Ethernet Switches ↔ Remote I/O Racks: PROFINET / Copper Ethernet / Star / Redundant network
- CN-005 Redundant PLC CPUs primary ↔ secondary: OEM redundancy synchronization / Fiber optic / Point-to-point / Redundant pair
- CN-006 Redundant PLC CPUs ↔ Industrial Ethernet Switches: - / Copper Ethernet / Star / Single
- CN-007 Industrial Ethernet Switches ↔ SCADA Servers: - / Copper Ethernet / Point-to-point / Dual independent paths
- CN-008 Operator Workstation ↔ Industrial Ethernet Switches: Ethernet (TCP/IP) / Copper Ethernet / Point-to-point / Single

## Unresolved technical questions
- none

## Additional notes
- (none)

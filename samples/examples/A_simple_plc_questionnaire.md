# Example questionnaire — Test A: simple PLC architecture

**Claude:** Step 1 — Project details: Client / Contractor, End User, Project, Document Title, Prepared By, Checked By, Approved By, Drawing Revision? (leave any blank for TBC)

**User:** Client / Contractor: ACME Contracting; End User: City Water Authority; Project: Water Treatment Plant Upgrade; Document Title: PLC & SCADA System Architecture; Prepared By: AMB; Checked By: (blank); Approved By: (blank); Drawing Revision: R0

**Claude:** Step 2 — Which Purdue layers does this architecture need? Level 0 Field Instruments, Level 1 Control, Level 2 SCADA / Supervisory, Level 3 Site Operations, Level 3.5 DMZ — Demilitarized Zone, Level 4 Enterprise / Business Network, Level 5 External / Corporate / Cloud Systems (rename or add custom layers if needed)

**User:** L0, L1; rename L1 to "Control System"

**Claude:** Step 3 — What equipment and quantities are required in Level 0 — Field Instruments?

**User:** 

    Pressure Transmitters — 4
    Temperature Transmitters — 3
    Flow Transmitters — 2

**Claude:** Recorded: EQ-001 Pressure Transmitters ×4; EQ-002 Temperature Transmitters ×3; EQ-003 Flow Transmitters ×2

**Claude:** Step 3 — What equipment and quantities are required in Level 1 — Control System?

**User:** 

    PLC — 1
    Remote I/O Rack — 1
    Industrial Ethernet Switch — 1
    HMI Panel — 1

**Claude:** Recorded: EQ-004 PLC ×1; EQ-005 Remote I/O Rack ×1; EQ-006 Industrial Ethernet Switch ×1; EQ-007 HMI Panel ×1

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

**User:** Star

**Claude:** Step 4 — Which physical cable medium links the remote I/O racks (PROFINET, star)?  
  ( ) Copper Ethernet  
  ( ) Fiber optic  
  ( ) Other / Specify

**User:** Copper Ethernet

**Claude:** Step 4 — In the star, which switch or interface do the I/O racks connect to?  
  ( ) EQ-006 Industrial Ethernet Switch  
  ( ) Directly to the PLC network ports  
  ( ) Other / Specify

**User:** EQ-006 Industrial Ethernet Switch

**Claude:** Step 4 — How are the PLC controllers PLC (EQ-004) connected to the industrial Ethernet switches (EQ-006 Industrial Ethernet Switch (x1))?  
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

**Claude:** Step 4 — What does the HMI Panel (EQ-007) connect to?  
  ( ) EQ-006 Industrial Ethernet Switch  
  ( ) EQ-004 PLC  
  ( ) EQ-005 Remote I/O Rack  
  ( ) Not Applicable  
  ( ) Other / Specify

**User:** EQ-006 Industrial Ethernet Switch

**Claude:** Step 4 — Which communication protocol does EQ-007 use to talk to EQ-006?  
  ( ) PROFINET  
  ( ) EtherNet/IP  
  ( ) Modbus TCP  
  ( ) Other / Specify

**User:** PROFINET

**Claude:** Step 4 — Which physical medium links EQ-007 to EQ-006?  
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
- Level 1 **Control System** (L1)
- Level 0 **Field Instruments** (L0)

## Equipment per layer
**Level 0 — Field Instruments**
- EQ-001 Pressure Transmitters — qty 4
- EQ-002 Temperature Transmitters — qty 3
- EQ-003 Flow Transmitters — qty 2

**Level 1 — Control System**
- EQ-004 PLC — qty 1
- EQ-005 Remote I/O Rack — qty 1
- EQ-006 Industrial Ethernet Switch — qty 1
- EQ-007 HMI Panel — qty 1

## Connectivity summary
- CN-001 Pressure Transmitters ↔ Remote I/O Rack: Hardwired AI/DI/AO/DO / Copper (hardwired) / Point-to-point / Single
- CN-002 Temperature Transmitters ↔ Remote I/O Rack: Hardwired AI/DI/AO/DO / Copper (hardwired) / Point-to-point / Single
- CN-003 Flow Transmitters ↔ Remote I/O Rack: Hardwired AI/DI/AO/DO / Copper (hardwired) / Point-to-point / Single
- CN-004 Industrial Ethernet Switch ↔ Remote I/O Rack: PROFINET / Copper Ethernet / Star / Single
- CN-005 PLC ↔ Industrial Ethernet Switch: - / Copper Ethernet / Star / Single
- CN-006 HMI Panel ↔ Industrial Ethernet Switch: PROFINET / Copper Ethernet / Point-to-point / Single

## Unresolved technical questions
- none

## Additional notes
- (none)

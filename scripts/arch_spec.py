"""Structured architecture specification for the questionnaire workflow (Phases 2-6).

The AI runs the conversation; this module keeps the record, so every answer is stored once, every item has a stable id and nothing is
invented. One JSON file (architecture_spec.json) holds project details, selected layers, equipment records, connections, questionnaire
answers, notes and revision history. Standard library only.

    python scripts/arch_spec.py init spec.json
    python scripts/arch_spec.py project spec.json --client "ACME" --project "WTP Upgrade" ...
    python scripts/arch_spec.py layers spec.json --select L0 L1 L2 L3.5 [--rename L1="Control System"] [--custom "2.5|Utilities|Water & power"]
    python scripts/arch_spec.py add-equipment spec.json --layer L0 --text "Pressure Transmitters - 12"
    python scripts/arch_spec.py questions spec.json            (connectivity questions still open, in dependency order)
    python scripts/arch_spec.py answer spec.json io_protocol profinet
    python scripts/arch_spec.py connect spec.json --from EQ-004 --to EQ-007 --protocol "Modbus TCP" --medium "Copper Ethernet"
    python scripts/arch_spec.py validate spec.json
    python scripts/arch_spec.py review spec.json               (Step 5 review, markdown)
    python scripts/arch_spec.py request spec.json --out request.md        /  parse-request spec.json request.md [--apply]
    python scripts/arch_spec.py to-diagram spec.json --out diagram.json   (then build_diagram.py)

See docs/questionnaire-workflow.md.
"""
import argparse
import copy
import datetime
import hashlib
import json
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA = "avanceon-arch-spec/1"
TYPICAL_HW = "Typical Hardwired Signals — AI/DI/AO/DO"
OTHER, NA = "other", "na"


class SpecError(Exception):
    pass


# ---- layers -----------------------------------------------------------------------------------------------------------------------
STANDARD_LAYERS = [  # questionnaire key, builder id, level, default questionnaire name
    ("L0", "field", 0.0, "Field Instruments"),
    ("L1", "control", 1.0, "Control"),
    ("L2", "scada", 2.0, "SCADA / Supervisory"),
    ("L3", "operations", 3.0, "Site Operations"),
    ("L3.5", "dmz", 3.5, "DMZ — Demilitarized Zone"),
    ("L4", "enterprise", 4.0, "Enterprise / Business Network"),
    ("L5", "external", 5.0, "External / Corporate / Cloud Systems"),
]
STD_BY_KEY = {k: (k, i, lv, n) for k, i, lv, n in STANDARD_LAYERS}

PROJECT_FIELDS = [  # spec key, questionnaire label, diagram/footer key
    ("client", "Client / Contractor", "client"),
    ("end_user", "End User", "end_user"),
    ("project", "Project", "project"),
    ("doc_name", "Document Title", "doc_name"),
    ("prepared_by", "Prepared By", "prepared_by"),
    ("checked_by", "Checked By", "checked_by"),
    ("approved_by", "Approved By", "approved_by"),
    ("revision", "Drawing Revision", "revision"),
    ("sheet", "Sheet", "sheet"),
]

# ---- vocabularies (5.11: protocol, medium, topology and redundancy are different things) ------------------------------------------
PROTOCOLS = {
    "Hardwired AI/DI/AO/DO": ["hardwired", "hardwire", "hardwired ai/di/ao/do", "ai/di/ao/do", "4-20ma", "4-20 ma", "analog", "discrete"],
    "Modbus RTU": ["modbus rtu", "modbus serial", "modbus rs-485", "modbus rs485"],
    "Modbus TCP": ["modbus tcp", "modbus/tcp", "modbus tcp/ip"],
    "PROFINET": ["profinet", "pn"],
    "PROFIBUS DP": ["profibus", "profibus dp", "profibus-dp"],
    "PROFIBUS PA": ["profibus pa", "profibus-pa"],
    "EtherNet/IP": ["ethernet/ip", "ethernet ip", "enip", "cip"],
    "DNP3": ["dnp3", "dnp 3"],
    "IEC 60870-5-104": ["iec 104", "iec-104", "iec 60870-5-104", "iec104"],
    "IEC 61850": ["iec 61850", "61850"],
    "OPC UA": ["opc ua", "opc-ua", "opcua", "opc"],
    "BACnet/IP": ["bacnet", "bacnet/ip", "bacnet ip"],
    "BACnet MS/TP": ["bacnet ms/tp", "bacnet mstp", "ms/tp"],
    "HART": ["hart"],
    "Foundation Fieldbus": ["foundation fieldbus", "ff", "ff h1"],
    "Ethernet (TCP/IP)": ["ethernet", "tcp/ip", "tcp", "ip", "lan"],
    "OEM redundancy synchronization": ["oem sync", "redundancy sync", "synchronization", "sync"],
}
MEDIA = {
    "Copper (hardwired)": ["copper (hardwired)", "hardwired copper", "multicore", "instrument cable", "signal cable"],
    "Copper Ethernet": ["copper ethernet", "copper", "cat5", "cat5e", "cat6", "cat 6", "utp", "stp", "rj45", "ethernet cable"],
    "Fiber optic": ["fiber optic", "fibre optic", "fiber", "fibre", "fo", "optical", "singlemode", "single-mode", "multimode", "multi-mode", "sm fiber", "mm fiber"],
    "RS-485": ["rs-485", "rs485", "2-wire serial", "profibus cable"],
    "RS-232": ["rs-232", "rs232"],
    "Wireless": ["wireless", "radio", "wifi", "wi-fi", "lte", "4g", "5g", "gsm", "microwave", "satellite"],
    "Backplane": ["backplane", "local backplane", "local bus"],
    "OEM synchronization cable": ["oem sync cable", "sync cable", "dedicated sync cable"],
}
TOPOLOGIES = {
    "Point-to-point": ["point-to-point", "point to point", "p2p", "direct"],
    "Star": ["star"],
    "Daisy-chain": ["daisy-chain", "daisy chain", "daisy", "line", "linear", "chain"],
    "Ring": ["ring", "loop", "mrp ring", "fiber ring", "fibre ring"],
    "Bus / Multi-drop": ["bus", "multi-drop", "multidrop", "multi drop"],
    "Local backplane": ["local backplane", "backplane"],
    "Mesh": ["mesh"],
}
REDUNDANCY = {
    "Single": ["single", "none", "non-redundant", "simplex", "single path"],
    "Dual independent paths": ["dual independent", "dual independent paths", "dual paths", "two paths", "dual path", "dual"],
    "Redundant network": ["redundant network", "dual redundant network", "redundant", "prp", "hsr"],
    "Redundant pair": ["redundant pair", "hot standby", "hot-standby", "primary/secondary", "duplex", "1oo2"],
    "Dual-homed": ["dual-homed", "dual homed"],
    "Single-homed": ["single-homed", "single homed"],
}
VOCAB = {"protocol": PROTOCOLS, "medium": MEDIA, "topology": TOPOLOGIES, "redundancy": REDUNDANCY}
ETHERNET_PROTOCOLS = {"Modbus TCP", "PROFINET", "EtherNet/IP", "OPC UA", "BACnet/IP", "IEC 60870-5-104", "IEC 61850", "Ethernet (TCP/IP)"}
SERIAL_PROTOCOLS = {"Modbus RTU", "PROFIBUS DP", "PROFIBUS PA", "BACnet MS/TP", "HART", "Foundation Fieldbus"}


def classify_value(text):
    """Which vocabularies a free-text value belongs to: {"protocol": "PROFINET", ...}."""
    t = norm(text)
    hits = {}
    for field, table in VOCAB.items():
        for canon, aliases in table.items():
            if t == norm(canon) or t in aliases:
                hits[field] = canon
                break
    return hits


def canon(field, value):
    """Canonical spelling of a known value, or the user's text unchanged (free text is allowed and then only warned about)."""
    if value in (None, ""):
        return None
    hits = classify_value(value)
    return hits.get(field, str(value).strip())


# ---- equipment categories ------------------------------------------------------------------------------------------------------------
# Checked in order; the first match wins. Instrument switches ("pressure switch") are matched before network switches.
CATEGORY_RULES = [
    ("fo_panel", r"patch\s*panel|\bodf\b|\blilu\b|fib(?:er|re)\s*(?:optic\s*)?(?:termination|panel|box)|\bfo\s*(?:pp|panel)"),
    ("io", r"\bi\s*/\s*o\b|\bio\s+(?:rack|module|panel|drop|station|card)|\brio\b|remote\s*io\b|\bet\s?200|\bi/o\b"),
    ("instrument", r"transmitter|\bsensor|analy[sz]er|flow\s*meter|flowmeter|\bmeter\b|detector|\bvalve|actuator|positioner|gauge|"
                   r"thermocouple|\brtd\b|probe|solenoid|push\s*button|limit\s*switch|(?:level|pressure|temperature|flow|proximity|float)\s+switch|"
                   r"\binstrument|\b(?:pt|tt|ft|lt|pit|tit|fit|lit|dpt|dpit|mov|xv|fcv|pcv|lcv)\b"),
    ("firewall", r"fire\s*wall|\bngfw\b|\butm\b"),
    ("dcs", r"\bdcs\b|distributed\s+control"),
    ("existing_scada", r"(?:existing|third[\s-]*party|legacy|client)\s+scada"),
    ("rtu", r"\brtu\b|remote\s+terminal"),
    ("plc", r"\bplc|controller|\bcpu\b|\bs7[\s-]?\d|controllogix|compactlogix|\bm580\b|\bm340\b|\bpac\b"),
    ("hmi", r"\bhmi\b|operator\s+panel|touch\s*panel|panel\s*pc"),
    ("gateway", r"gateway|protocol\s+converter|serial\s+(?:server|converter|device\s+server)|anybus|prosoft|\bconverter\b"),
    ("media_converter", r"media\s+converter|\bsfp\b|transceiver"),
    ("router", r"router|\blte\b|\b4g\b|\b5g\b|modem|cellular"),
    ("wireless", r"wireless|access\s*point|\bwap\b|\bradio\b|wi-?fi|microwave"),
    ("switch", r"switch"),
    ("historian", r"historian"),
    ("eng_workstation", r"engineering\s+(?:work\s*station|station|pc|laptop)|\bews\b|engineering\s+client"),
    ("laptop", r"laptop|notebook"),
    ("server", r"server|\bvm\b|virtual\s+machine|\bnas\b|domain\s+controller"),
    ("workstation", r"work\s*station|\bows\b|operator\s+(?:station|client)|\bclient\b|\bpc\b|desktop|thin\s+client"),
    ("printer", r"printer"),
    ("video_wall", r"video\s*wall|large\s+screen|display\s+wall"),
    ("ups", r"\bups\b|uninterruptible"),
    ("kvm", r"\bkvm\b"),
    ("time_server", r"\bgps\b|\bntp\b|time\s+server|clock"),
]
CATEGORIES = [c for c, _ in CATEGORY_RULES] + ["other"]
DEFAULT_NAMES = {"plc": "PLC", "io": "Remote I/O", "switch": "Ethernet Switch", "server": "Server", "workstation": "Workstation",
                 "firewall": "Firewall", "gateway": "Gateway", "rtu": "RTU", "hmi": "HMI", "router": "Router", "instrument": "Instrument"}
NON_COMM = {"instrument", "fo_panel", "video_wall", "kvm", "ups"}           # no network question unless the user gives an interface
SCADA_ENDPOINTS = {"server", "historian", "workstation", "eng_workstation", "laptop", "printer", "time_server"}
CONTROLLERS = {"plc", "rtu", "dcs"}
TWO_SIDED = {"gateway", "media_converter", "firewall"}

OEMS = ["Siemens", "Schneider Electric", "Schneider", "Rockwell Automation", "Rockwell", "Allen-Bradley", "ABB", "Emerson", "Honeywell",
        "Yokogawa", "GE", "Mitsubishi", "Omron", "Hirschmann", "Moxa", "Cisco", "Fortinet", "Palo Alto", "Phoenix Contact",
        "Endress+Hauser", "Endress + Hauser", "E+H", "Rosemount", "Krohne", "VEGA", "Dell", "HPE", "HP", "Lenovo", "AVEVA", "Wonderware",
        "Inductive Automation", "Belden", "RuggedCom", "Ruggedcom", "Westermo", "WAGO", "Beckhoff", "B&R", "Danfoss", "Eaton", "APC",
        "Hach", "Fisher", "Foxboro", "Teltonika", "Red Lion", "ProSoft", "HMS", "Advantech", "Weidmuller", "Turck", "Pepperl+Fuchs",
        "Bently Nevada", "SEL", "Check Point", "Sophos", "Juniper", "Aruba", "Ubiquiti", "Sierra Wireless", "Johnson Controls"]
INTERFACE_WORDS = [  # (pattern, canonical)
    (r"profinet", "PROFINET"), (r"profibus\s*pa", "PROFIBUS PA"), (r"profibus", "PROFIBUS DP"), (r"ethernet\s*/\s*ip", "EtherNet/IP"),
    (r"modbus\s*tcp", "Modbus TCP"), (r"modbus\s*rtu", "Modbus RTU"), (r"rs[\s-]?485", "RS-485"), (r"rs[\s-]?232", "RS-232"),
    (r"dnp\s?3", "DNP3"), (r"iec\s*61850", "IEC 61850"), (r"iec\s*(?:60870-5-)?104", "IEC 60870-5-104"), (r"opc\s*ua", "OPC UA"),
    (r"bacnet", "BACnet"), (r"\bhart\b", "HART"), (r"4\s*-\s*20\s*ma", "4-20 mA"), (r"foundation\s+fieldbus", "Foundation Fieldbus"),
    (r"devicenet", "DeviceNet"), (r"controlnet", "ControlNet"), (r"canopen", "CANopen"), (r"\bsfp\b", "SFP"),
    (r"fib(?:er|re)|\bfo\b", "Fiber optic"), (r"(?<!/)\bethernet\b(?!\s*/\s*ip)", "Ethernet"), (r"wi-?fi", "Wi-Fi"), (r"\blte\b|\b4g\b", "LTE"),
]
PAIR_WORDS = r"redundan|hot[\s-]*standby|duplex|primary\s*(?:/|and|&)\s*(?:secondary|standby|backup)|\b1oo2\b|\bhot\s*/\s*hot\b"
OTHER_SCOPE = r"client\s+scope|by\s+(?:the\s+)?(?:client|others|owner|end\s*user)|\bexisting\b|third[\s-]*party|free\s+issue|\bfim\b|" \
              r"owner[\s-]+supplied|not\s+in\s+(?:avanceon\s+)?scope|out\s+of\s+scope|\bothers'?\s+scope"


def norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def categorize(name):
    t = norm(name)
    for cat, pattern in CATEGORY_RULES:
        if re.search(pattern, t):
            return cat
    return "other"


# ---- spec file ----------------------------------------------------------------------------------------------------------------------
def new_spec():
    return {"schema": SCHEMA, "stage": "project", "project": {k: None for k, _, _ in PROJECT_FIELDS}, "layers": [], "equipment": [],
            "connections": [], "answers": {}, "layout": {}, "images": {}, "notes": [], "counters": {"EQ": 0, "CN": 0, "C": 0},
            "history": [{"at": now(), "action": "init", "detail": "specification created"}], "request": {}}


def load(path):
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)
    if spec.get("schema") != SCHEMA:
        raise SpecError("%s is not an architecture specification (%s)" % (path, SCHEMA))
    return spec


def save(spec, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(spec, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def log(spec, action, detail):
    spec.setdefault("history", []).append({"at": now(), "action": action, "detail": detail})


def next_id(spec, prefix):
    spec["counters"][prefix] = spec["counters"].get(prefix, 0) + 1                   # never reused, even after a deletion
    return "%s-%03d" % (prefix, spec["counters"][prefix]) if prefix != "C" else "C%d" % spec["counters"][prefix]


def eq(spec, eid):
    for e in spec["equipment"]:
        if e["id"] == eid:
            return e
    raise SpecError("no equipment %s" % eid)


def layer(spec, key):
    for l in spec["layers"]:
        if l["key"] == key or l["id"] == key:
            return l
    raise SpecError("layer %s is not selected" % key)


def layer_level(spec, key):
    return layer(spec, key)["level"]


# ---- Step 1: project -----------------------------------------------------------------------------------------------------------------
def set_project(spec, **values):
    changed = []
    for k, label, _ in PROJECT_FIELDS:
        if k in values and values[k] is not None:
            v = str(values[k]).strip()
            v = None if v == "" or v.upper() == "TBC" else v
            if spec["project"].get(k) != v:
                spec["project"][k] = v
                changed.append("%s=%s" % (label, v or "TBC"))
    if changed:
        log(spec, "project", "; ".join(changed))
    return changed


# ---- Step 2: layers ------------------------------------------------------------------------------------------------------------------
def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", norm(text)).strip("_") or "layer"


def select_layers(spec, keys, renames=None, custom=None, force=False):
    """Select exactly these layers (any combination, none added automatically). renames: {key: name}; custom: [(level, name, desc)]."""
    renames, custom = renames or {}, custom or []
    old = {l["key"]: l for l in spec["layers"]}
    chosen = []
    for k in keys:
        k = k.strip().upper().replace("LEVEL", "L").replace(" ", "")
        if not k.startswith("L") and not k.startswith("C"):
            k = "L" + k
        if k in STD_BY_KEY:
            key, bid, lv, name = STD_BY_KEY[k]
            prev = old.get(key, {})
            chosen.append({"key": key, "id": bid, "level": lv, "name": prev.get("name", name), "desc": prev.get("desc", ""), "custom": False})
        elif k in old and old[k].get("custom"):
            chosen.append(dict(old[k]))
        else:
            raise SpecError("unknown layer %s (standard: %s; custom layers are added with --custom)" % (k, ", ".join(STD_BY_KEY)))
    for level, name, desc in custom:
        try:
            lv = float(str(level).lower().replace("level", "").strip())
        except ValueError:
            raise SpecError("custom layer %r needs a numeric level such as 2.5" % name)
        key = next_id(spec, "C")
        bid = "custom_" + slug(name)
        while any(c["id"] == bid for c in chosen):
            bid += "_x"
        chosen.append({"key": key, "id": bid, "level": lv, "name": name.strip(), "desc": (desc or "").strip(), "custom": True})
    for c in chosen:
        if c["key"] in renames:
            c["name"] = renames[c["key"]].strip()
    unknown = set(renames) - {c["key"] for c in chosen}
    if unknown:
        raise SpecError("cannot rename unselected layer(s): %s" % ", ".join(sorted(unknown)))
    dropped = [k for k in old if k not in {c["key"] for c in chosen}]
    used = [e for e in spec["equipment"] if e["layer"] in dropped]
    if used and not force:
        raise SpecError("layer(s) %s still hold equipment (%s); move or remove it first, or use --force to delete it" %
                        (", ".join(dropped), ", ".join(e["id"] for e in used)))
    for e in used:
        remove_equipment(spec, e["id"])
    if len({c["key"] for c in chosen}) != len(chosen):
        raise SpecError("a layer is listed twice")
    spec["layers"] = sorted(chosen, key=lambda c: c["level"])                          # stored lowest first (question order)
    spec["stage"] = "equipment" if spec["stage"] in ("project", "layers") else spec["stage"]
    log(spec, "layers", ", ".join("%s %s" % (c["key"], c["name"]) for c in spec["layers"]))
    return spec["layers"]


def level_label(lv):
    return "Level %s" % (("%g" % lv) if isinstance(lv, (int, float)) else lv)


# ---- Step 3: equipment ---------------------------------------------------------------------------------------------------------------
QTY_PATTERNS = [
    r"\b(?:qty|quantity|nos?\.?|no\.\s*of)\s*[:=]?\s*(\d+)\b",
    r"\b(\d+)\s*(?:nos?\.?|units?|pcs|sets?|off|numbers?)(?=\W|$)",
    r"(?:\s[-–—]|[–—:=])\s*(\d+)\s*(?:\([^)]*\))?\s*$",
    r"\s[x×]\s*(\d+)\s*$",
    r"^\s*(\d+)\s*[x×]\s+",
    r"^\s*(\d+)\s+(?=[A-Za-z])",
    r"\((\d+)\)\s*$",
]
FIELD_KEYS = {"oem": "oem", "make": "oem", "manufacturer": "oem", "brand": "oem", "vendor": "oem", "model": "model", "part": "model",
              "part number": "model", "location": "location", "panel": "location", "scope": "scope", "interface": "interfaces",
              "interfaces": "interfaces", "notes": "notes", "note": "notes", "qty": "quantity", "quantity": "quantity",
              "redundancy": "redundancy", "category": "category", "type": "category"}


def _split_lines(text):
    out = []
    for raw in re.split(r"[\r\n;]+", text or ""):
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^(?:level\s*[\d.]+|l\s*[\d.]+)\s*[:\-—]?\s*(?:[A-Za-z /&—-]*)?:?\s*$", line, re.I) and len(line) < 60 \
                and not re.search(r"\d+\s*$", re.sub(r"^(?:level|l)\s*[\d.]+", "", line, flags=re.I)):
            continue                                                                    # a "Level 0:" heading line
        line = re.sub(r"^\s*(?:[-*•▪>]+|\d+[.)])\s+", "", line)
        if line:
            out.append(line)
    return out


def parse_line(line):
    """One equipment description -> fields. Only what is written is captured; missing quantities and models stay empty."""
    rec = {"source_text": line, "name": None, "quantity": None, "oem": None, "model": None, "redundancy": None, "location": None,
           "scope": None, "interfaces": [], "notes": None, "category": None}
    body = line
    parts = [p.strip() for p in line.split("|")]
    if len(parts) > 1:                                                                 # "Name | OEM: Siemens | Model: ..."
        body = parts[0]
        for p in parts[1:]:
            m = re.match(r"^([A-Za-z ]+?)\s*[:=]\s*(.+)$", p)
            key = FIELD_KEYS.get(norm(m.group(1))) if m else None
            if key == "interfaces":
                rec["interfaces"] = [s.strip() for s in re.split(r"[,/]| and ", m.group(2)) if s.strip()]
            elif key == "quantity":
                rec["quantity"] = int(re.sub(r"\D", "", m.group(2)) or 0) or None
            elif key:
                rec[key] = m.group(2).strip()
            else:
                rec["notes"] = "; ".join(x for x in (rec["notes"], p) if x)
    work = body
    for key in ("oem", "model", "location", "notes"):                                  # inline "model: X" inside the name part
        m = re.search(r"\b%s\s*[:=]\s*([^,()]+)" % ("make|oem|manufacturer|brand" if key == "oem" else key), work, re.I)
        if m and not rec[key]:
            rec[key] = m.group(1).strip()
            work = (work[:m.start()] + work[m.end():]).strip(" ,")
    paren_notes = [m.group(1).strip() for m in re.finditer(r"\(([^)]*)\)", work) if not re.fullmatch(r"\s*\d+\s*", m.group(1))]
    if rec["quantity"] is None:
        for pat in QTY_PATTERNS:
            m = re.search(pat, work, re.I)
            if m:
                rec["quantity"] = int(m.group(1))
                work = (work[:m.start()] + " " + work[m.end():]).strip()
                break
    low = norm(line)
    if re.search(PAIR_WORDS, low):
        rec["redundancy"] = rec["redundancy"] or "Redundant pair"
    if re.search(OTHER_SCOPE, low):
        rec["scope"] = rec["scope"] or ("other: " + re.search(OTHER_SCOPE, low).group(0))
    elif re.search(r"avanceon\s+scope|by\s+avanceon", low):
        rec["scope"] = rec["scope"] or "avanceon"
    if not rec["location"]:
        m = re.search(r"\b(?:located\s+(?:in|at)|inside|in|at)\s+((?:the\s+)?[\w\-/. ]*?\b(?:panel|room|cabinet|building|station|site|mcc|kiosk|"
                      r"shelter|enclosure|cubicle|control\s+room)\b(?:\s+[A-Z0-9][\w\-]*)?)", line, re.I)
        if m:
            rec["location"] = m.group(1).strip()
    if not rec["oem"]:
        for o in OEMS:
            if re.search(r"(?<![\w])%s(?![\w])" % re.escape(o), line, re.I):
                rec["oem"] = o
                break
    if rec["oem"] and not rec["model"]:                                                # a part number written after the maker's name
        after = re.split(re.escape(rec["oem"]), body, flags=re.I)
        tail = re.split(r"[()|,;]|\s[-\u2013\u2014]\s", after[1])[0] if len(after) > 1 else ""
        toks = tail.split()
        hit = next((i for i, t in enumerate(toks[:4]) if re.search(r"\d", t) and not re.match(r"(?i)rs-?\d|4-20|iec|\d{1,2}$", t)), None)
        if hit is not None and not any(re.search(PAIR_WORDS + r"|\bx\b|qty", t.lower()) for t in toks[:hit + 1]):
            end = hit + 1
            while end < len(toks) and (re.search(r"\d", toks[end]) or re.fullmatch(r"[A-Z]{2,4}", toks[end])) \
                    and not re.match(r"(?i)rs-?\d|4-20", toks[end]):
                end += 1
            rec["model"] = " ".join(toks[:end]).strip(" -:")
    found = []
    for pat, name in INTERFACE_WORDS:
        if re.search(pat, low) and name not in found and name not in rec["interfaces"]:
            found.append(name)
    rec["interfaces"] = rec["interfaces"] + found
    name = re.sub(r"\([^)]*\)", " ", work)
    name = re.sub(r"\s+[-–—:]\s*$", "", re.sub(r"\s+", " ", name)).strip(" ,;-–—:")
    for part in (rec["model"], rec["oem"], rec["location"]):                          # captured separately, not repeated in the name
        if part:
            name = re.sub(r"(?i)\s*\b(?:in|at|inside|located in|located at)?\s*" + re.escape(part) + r"\b", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" ,;-\u2013\u2014:")
    rec["name"] = name or None
    paren_notes = [n for n in paren_notes if n and not (rec["oem"] and rec["oem"].lower() in n.lower())
                   and not re.fullmatch(r"(?i)\s*(?:%s)\w*\s*" % PAIR_WORDS, n)]
    if paren_notes:
        rec["notes"] = "; ".join(x for x in [rec["notes"]] + paren_notes if x)
    rec["category"] = rec["category"] if rec["category"] in CATEGORIES else next((c for c in (categorize(x) for x in (rec["name"], rec["model"], body) if x) if c != "other"), "other")
    if not rec["name"]:
        rec["name"] = DEFAULT_NAMES.get(rec["category"], "Equipment")
    return rec


def add_equipment(spec, layer_key, text):
    """Parse a layer's free text into equipment records. Returns (added, duplicates). Lines already recorded are not added twice."""
    lay = layer(spec, layer_key)
    added, dupes = [], []
    for line in _split_lines(text):
        rec = parse_line(line)
        same = [e for e in spec["equipment"] if e["layer"] == lay["key"] and norm(e["name"]) == norm(rec["name"])
                and (e.get("model") or "") == (rec["model"] or "")]
        if same:
            dupes.append((line, same[0]["id"]))
            continue
        rec.update(id=next_id(spec, "EQ"), layer=lay["key"], flags=[])
        rec["systems"] = systems_for(rec)
        rec["flags"] = equipment_flags(rec)
        spec["equipment"].append(rec)
        added.append(rec)
    if added:
        log(spec, "equipment", "%s: added %s" % (lay["key"], ", ".join("%s %s" % (r["id"], r["name"]) for r in added)))
    return added, dupes


def is_pair(rec):
    return bool(rec.get("redundancy")) and bool(re.search(PAIR_WORDS + r"|redundant pair", norm(rec["redundancy"])))


def systems_for(rec):
    """Independent systems a record represents: two redundant CPUs are one redundant controller system (4.3)."""
    q = rec.get("quantity")
    if q is None:
        return None
    if is_pair(rec) and rec["category"] in CONTROLLERS | {"server", "historian"}:
        return 1 if q == 2 else None                                                    # 4 'redundant' CPUs: ask, do not guess
    return q


def equipment_flags(rec):
    flags = []
    if rec.get("quantity") is None:
        flags.append("quantity not stated")
    if is_pair(rec) and rec["category"] in CONTROLLERS | {"server", "historian"} and rec.get("quantity") not in (None, 2):
        flags.append("redundant with quantity %s: confirm how many redundant systems this is" % rec["quantity"])
    if rec["category"] == "other":
        flags.append("category not recognised: confirm what this equipment is")
    return flags


EDITABLE = ("name", "category", "quantity", "systems", "oem", "model", "redundancy", "location", "scope", "interfaces", "notes", "layer")


def edit_equipment(spec, eid, **changes):
    e = eq(spec, eid)
    done = []
    for k, v in changes.items():
        if k not in EDITABLE or v is None:
            continue
        if k == "layer":
            v = layer(spec, v)["key"]
        if k in ("quantity", "systems"):
            v = None if str(v).strip().upper() in ("", "-", "TBC", "NONE") else int(v)
        if k == "interfaces" and isinstance(v, str):
            v = [s.strip() for s in v.split(",") if s.strip()]
        if k == "category" and v not in CATEGORIES:
            raise SpecError("category must be one of: %s" % ", ".join(CATEGORIES))
        if isinstance(v, str) and v.strip() in ("", "-"):
            v = None
        if e.get(k) != v:
            done.append("%s: %r -> %r" % (k, e.get(k), v))
            e[k] = v
    if "systems" not in changes and any(d.startswith(("quantity", "redundancy", "category")) for d in done):
        e["systems"] = systems_for(e)
    e["flags"] = equipment_flags(e)
    if done:
        log(spec, "edit-equipment", "%s %s" % (eid, "; ".join(done)))
    return done


def remove_equipment(spec, eid):
    eq(spec, eid)
    spec["equipment"] = [e for e in spec["equipment"] if e["id"] != eid]
    gone = [c["id"] for c in spec["connections"] if eid in (c["source"], c["destination"]) or eid in (c.get("via") or [])
            or eid in (c.get("nodes") or [])]
    spec["connections"] = [c for c in spec["connections"] if c["id"] not in gone]
    spec["answers"] = {k: v for k, v in spec["answers"].items() if eid not in k}
    log(spec, "remove-equipment", "%s (and connections %s)" % (eid, ", ".join(gone) or "none"))
    return gone


def units(rec):
    return max(1, rec.get("quantity") or 1)


# ---- Step 4: connectivity question engine --------------------------------------------------------------------------------------
def C(value, label):
    return {"value": value, "label": label}


OTHER_C, NA_C = C(OTHER, "Other / Specify"), C(NA, "Not Applicable")
MEDIUM_CHOICES = [C("copper", "Copper Ethernet"), C("fibre", "Fiber optic"), OTHER_C]
MEDIUM_MAP = {"copper": "Copper Ethernet", "fibre": "Fiber optic", "rs485": "RS-485", "rs232": "RS-232", "wireless": "Wireless",
              "backplane": "Backplane", "oem": "OEM synchronization cable"}


def recs(spec, cats, layers=None):
    cats = {cats} if isinstance(cats, str) else set(cats)
    return [e for e in spec["equipment"] if e["category"] in cats and (layers is None or e["layer"] in layers)]


def layer_keys(spec, builder_ids):
    return {l["key"] for l in spec["layers"] if l["id"] in builder_ids}


def touching(spec, eid, manual_only=False):
    return [c for c in spec["connections"] if eid in (c["source"], c["destination"]) or eid in (c.get("nodes") or [])
            and (not manual_only or not c.get("origin"))]


def manual_between(spec, a_ids, b_ids):
    a_ids, b_ids = set(a_ids), set(b_ids)
    for c in spec["connections"]:
        if c.get("origin"):
            continue
        ends = {c["source"], c["destination"]} | set(c.get("nodes") or [])
        if ends & a_ids and ends & b_ids:
            return c
    return None


def describe(recs_):
    return ", ".join("%s %s%s" % (r["id"], r["name"], " (x%d)" % r["quantity"] if r.get("quantity") else "") for r in recs_)


def control_layers(spec):
    return layer_keys(spec, {"control"}) or {l["key"] for l in spec["layers"] if 0.5 < l["level"] < 2}


def scada_layers(spec):
    return layer_keys(spec, {"scada"}) or {l["key"] for l in spec["layers"] if 1.5 < l["level"] < 3}


class Q(dict):
    pass


def _q(key, step, prompt, choices, about, multi=False, why=""):
    return Q(key=key, step=step, prompt=prompt, choices=choices + ([] if any(c["value"] == OTHER for c in choices) else [OTHER_C]),
             multi=multi, about=about, why=why)


def plan(spec):
    """Every relationship instance that the current equipment makes relevant, in the 5.10 dependency order. Each instance yields
    either its next open question or (when its answers are complete) the connections it confirms."""
    A = spec["answers"]
    out = []                                                                       # [(question or None, [connection specs])]
    ctl, scl = control_layers(spec), scada_layers(spec)
    instruments = recs(spec, "instrument")
    io = recs(spec, "io")
    plcs = recs(spec, "plc")
    ctrl_targets = io or recs(spec, CONTROLLERS)

    # 1. field instruments -> I/O or control system (5.2)
    pending_instr = [r for r in instruments if not manual_between(spec, [r["id"]], [e["id"] for e in spec["equipment"] if e["id"] != r["id"]])]
    if pending_instr and (io or recs(spec, CONTROLLERS | {"gateway"})):
        g = A.get("instrument_to_control")
        if not g:
            out.append((_q("instrument_to_control", 1, "How are the field instruments connected to the Control system?",
                           [C("hardwired", "Hardwired AI/DI/AO/DO"), C("modbus_rtu", "Modbus RTU over RS-485"),
                            C("modbus_tcp", "Modbus TCP over Ethernet"), C("fibre_interface", "Fiber optic through a suitable interface"),
                            C("mixed", "Mixed communication methods")], [r["id"] for r in pending_instr],
                           why="field instruments (%s) and control/I/O equipment are present" % describe(pending_instr)), []))
        else:
            for r in pending_instr:
                out.append(_instrument(spec, r, g["value"], A))
    # 2. I/O racks -> PLC (5.3)
    pending_io = [r for r in io if not manual_between(spec, [r["id"]], [p["id"] for p in plcs + recs(spec, "switch")])]
    if pending_io and plcs:
        out.extend(_io(spec, pending_io, plcs, A, ctl))
    # 3. redundant PLC synchronisation (5.4)
    for p in plcs + recs(spec, {"dcs"}):
        if not is_pair(p):
            continue
        if any(c for c in spec["connections"] if not c.get("origin") and c["source"] == p["id"] == c["destination"]):
            continue
        out.append(_sync(spec, p, A))
    # 4. PLC -> industrial Ethernet switches (5.5)
    sws = recs(spec, "switch", ctl) or recs(spec, "switch", scl)
    for p in plcs:
        if sws and not manual_between(spec, [p["id"]], [s["id"] for s in sws]):
            out.append(_plc_switch(spec, p, sws, A))
    # 5. control network -> SCADA network (5.6)
    src = recs(spec, "switch", ctl) or recs(spec, CONTROLLERS, ctl)
    dst = recs(spec, "switch", scl) or recs(spec, SCADA_ENDPOINTS, scl)
    linked = any(c for c in spec["connections"] if c.get("origin") != "ctlscada"
                 and {c["source"], c["destination"]} & {e["id"] for e in src} and {c["source"], c["destination"]} & {e["id"] for e in dst})
    if src and dst and set(e["id"] for e in src) != set(e["id"] for e in dst) and not linked:
        out.append(_control_scada(spec, src, dst, A))
    # 6. SCADA equipment -> its switches (5.6)
    ssw = recs(spec, "switch", scl)
    ends = [e for e in recs(spec, SCADA_ENDPOINTS, scl) if not manual_between(spec, [e["id"]], [s["id"] for s in ssw])]
    if ssw and ends:
        out.append(_scada_lan(spec, ssw, ends, A))
    # 7. fibre optic network (5.7)
    out.extend(_fibre(spec, A))
    # 8. firewall / DMZ (5.8)
    for f in recs(spec, "firewall"):
        out.append(_firewall(spec, f, A))
    # 9. everything else that communicates (5.9), lowest layer first. Asked only once the structured steps above are settled,
    # because their answers usually connect the same equipment (the dependency order of 5.10).
    if any(q for q, _ in out):
        return out
    order = {l["key"]: l["level"] for l in spec["layers"]}
    handled = {k.split(":")[1] for k in A if ":" in k}
    for r in sorted(spec["equipment"], key=lambda e: (order.get(e["layer"], 0), e["id"])):
        if r["category"] in NON_COMM and not (r.get("interfaces") and r["category"] not in ("instrument", "fo_panel")):
            continue
        if r["category"] in ("io", "firewall"):
            continue
        need = 2 if r["category"] in TWO_SIDED else 1
        have = [c for c in spec["connections"] if r["id"] in (c["source"], c["destination"]) or r["id"] in (c.get("nodes") or [])
                or r["id"] in (c.get("via") or [])]
        mine = [c for c in have if (c.get("origin") or "").startswith("link:%s:" % r["id"])]
        others = len(have) - len(mine)
        if r["category"] == "plc" and (r["id"] in handled):
            continue
        for side in range(1, need + 1):
            if others >= side:
                continue
            if A.get("link:%s:%d:target" % (r["id"], side), {}).get("value") == NA:
                break
            out.append(_link(spec, r, side, A))
    return out


def _ans(A, key):
    return (A.get(key) or {}).get("value")


def _target_question(spec, key, step, what, candidates, about):
    return _q(key, step, "Which equipment are the %s connected to?" % what,
              [C(c["id"], "%s %s" % (c["id"], c["name"])) for c in candidates] + [NA_C], about)


def _instrument(spec, r, method, A):
    if method == "mixed":
        method = _ans(A, "instrument_method:" + r["id"])
        if not method:
            return (_q("instrument_method:" + r["id"], 1, "How are the %s (%s) connected to the Control system?" % (r["name"], r["id"]),
                       [C("hardwired", "Hardwired AI/DI/AO/DO"), C("modbus_rtu", "Modbus RTU over RS-485"),
                        C("modbus_tcp", "Modbus TCP over Ethernet"), C("fibre_interface", "Fiber optic through a suitable interface"), NA_C],
                       [r["id"]]), [])
    if method in (OTHER, NA):
        return (None, [])
    if method == "fibre_interface":
        iface = _ans(A, "instrument_interface:" + r["id"])
        if not iface:
            cands = recs(spec, {"gateway", "media_converter", "io", "rtu"})
            return (_q("instrument_interface:" + r["id"], 1,
                       "Which communication interface puts the %s (%s) on the fiber optic link? (An analog transmitter cannot connect "
                       "directly to fiber.)" % (r["name"], r["id"]), [C(c["id"], "%s %s" % (c["id"], c["name"])) for c in cands] + [NA_C],
                       [r["id"]]), [])
        if iface in (OTHER, NA):
            return (None, [])
        local = _ans(A, "instrument_local:" + r["id"])
        if not local:
            return (_q("instrument_local:" + r["id"], 1, "How are the %s connected to %s?" % (r["name"], iface),
                       [C("hardwired", "Hardwired AI/DI/AO/DO"), C("modbus_rtu", "Modbus RTU over RS-485")], [r["id"], iface]), [])
        tgt = _single_target(spec, "instrument_target:" + r["id"], A, [c for c in recs(spec, {"io"} | CONTROLLERS) if c["id"] != iface])
        if isinstance(tgt, Q):
            return (tgt, [])
        conns = [_conn_from_method(r["id"], iface, local, "instrument:" + r["id"])]
        if tgt:
            conns.append(dict(source=iface, destination=tgt, protocol=None, medium="Fiber optic", topology="Point-to-point",
                              redundancy=None, paths=None, direction=None, scope=None, label=None, pattern="first-to-first",
                              origin="instrument:%s:fibre" % r["id"]))
        return (None, conns)
    cands = recs(spec, "io") or recs(spec, CONTROLLERS)
    if method in ("modbus_rtu",):
        cands = cands + recs(spec, "gateway")
    if method == "modbus_tcp":
        cands = cands + recs(spec, "switch") + recs(spec, "gateway")
    tgt = _single_target(spec, "instrument_target:" + r["id"], A, cands, what="%s (%s)" % (r["name"], r["id"]))
    if isinstance(tgt, Q):
        return (tgt, [])
    return (None, [_conn_from_method(r["id"], tgt, method, "instrument:" + r["id"])] if tgt else [])


def _single_target(spec, key, A, cands, what=None):
    if not cands:
        return None
    if len(cands) == 1 and not A.get(key):
        return cands[0]["id"]
    v = _ans(A, key)
    if not v:
        return _target_question(spec, key, 1, what or key.split(":")[1], cands, [key.split(":")[1]])
    return None if v in (OTHER, NA) else v


def _conn_from_method(src, dst, method, origin):
    base = dict(source=src, destination=dst, topology=None, redundancy="Single", paths=None, direction=None, scope=None, label=None,
                origin=origin, pattern="each-to-first")
    if method == "hardwired":
        base.update(protocol="Hardwired AI/DI/AO/DO", medium="Copper (hardwired)", topology="Point-to-point", label=TYPICAL_HW,
                    pattern="group", direction="Field to control")
    elif method == "modbus_rtu":
        base.update(protocol="Modbus RTU", medium="RS-485")
    elif method == "modbus_tcp":
        base.update(protocol="Modbus TCP", medium="Copper Ethernet")
    else:
        base.update(protocol=None, medium=None)
    return base


IO_PROTOCOLS = {"profinet": "PROFINET", "ethernet_ip": "EtherNet/IP", "modbus_tcp": "Modbus TCP", "profibus": "PROFIBUS DP"}


def _io(spec, pending, plcs, A, ctl):
    out = []
    proto = _ans(A, "io_protocol")
    if not proto:
        return [(_q("io_protocol", 2, "How are the remote I/O racks connected to the PLC system?",
                    [C("profinet", "PROFINET"), C("ethernet_ip", "EtherNet/IP"), C("modbus_tcp", "Modbus TCP"), C("profibus", "PROFIBUS"),
                     C("backplane", "Local backplane / directly attached I/O")], [r["id"] for r in pending],
                    why="I/O equipment (%s) and PLC equipment (%s) are present" % (describe(pending), describe(plcs))), [])]
    if proto in (OTHER, NA):
        return []
    topo = "backplane" if proto == "backplane" else _ans(A, "io_topology")
    if not topo:
        return [(_q("io_topology", 2, "What is the required remote I/O topology?",
                    [C("star", "Star"), C("daisy", "Daisy-chain"), C("ring", "Ring"), C("dual", "Dual redundant network"),
                     C("backplane", "Local backplane")], [r["id"] for r in pending],
                    why="the topology is not assumed from the protocol"), [])]
    if topo in (OTHER, NA):
        return []
    medium = "backplane" if topo == "backplane" else _ans(A, "io_medium")
    if not medium:
        ch = [C("copper", "Copper Ethernet"), C("fibre", "Fiber optic")] if proto != "profibus" else \
            [C("rs485", "PROFIBUS copper cable (RS-485)"), C("fibre", "Fiber optic (optical link modules)")]
        return [(_q("io_medium", 2, "Which physical cable medium links the remote I/O racks (%s, %s)?" %
                    (IO_PROTOCOLS.get(proto, proto), topo), ch, [r["id"] for r in pending]), [])]
    if medium in (OTHER, NA):
        return []
    hub = None
    if topo == "star":
        sw = recs(spec, "switch", ctl)
        hub = _ans(A, "io_star_hub")
        if not hub:
            return [(_q("io_star_hub", 2, "In the star, which switch or interface do the I/O racks connect to?",
                        [C(s["id"], "%s %s" % (s["id"], s["name"])) for s in sw] + [C("plc", "Directly to the PLC network ports")],
                        [r["id"] for r in pending]), [])]
        if hub in (OTHER, NA):
            return []
    for r in pending:
        owner = plcs[0]["id"] if len(plcs) == 1 else _ans(A, "io_owner:" + r["id"])
        if not owner:
            out.append((_target_question(spec, "io_owner:" + r["id"], 2, "%s (%s) — which PLC system do they belong to" % (r["name"], r["id"]),
                                         plcs, [r["id"]]).__class__(key="io_owner:" + r["id"], step=2,
                        prompt="Which PLC system do the %s (%s) belong to?" % (r["name"], r["id"]),
                        choices=[C(p["id"], "%s %s" % (p["id"], p["name"])) for p in plcs] + [OTHER_C], multi=False, about=[r["id"]],
                        why=""), []))
            continue
        if owner in (OTHER, NA):
            continue
        c = dict(source=owner, destination=r["id"], protocol=None if proto == "backplane" else IO_PROTOCOLS.get(proto, proto),
                 medium=MEDIUM_MAP.get(medium, medium), topology={"star": "Star", "daisy": "Daisy-chain", "ring": "Ring",
                 "dual": "Star", "backplane": "Local backplane"}[topo], redundancy="Redundant network" if topo == "dual" else "Single",
                 paths=2 if topo == "dual" else None, direction=None, scope=None, label=None, origin="io:" + r["id"],
                 pattern={"star": "each-to-first", "daisy": "chain", "ring": "ring", "dual": "all-to-all", "backplane": "none"}[topo])
        if topo == "star" and hub not in (None, "plc"):
            c["source"] = hub
        if topo == "dual":
            sw = recs(spec, "switch", ctl)
            if sw:
                c["source"] = sw[0]["id"]
        out.append((None, [c]))
    return out


def _sync(spec, p, A):
    k = p["id"]
    how = _ans(A, "plc_sync:" + k)
    if not how:
        return (_q("plc_sync:" + k, 3, "How are the primary and secondary controllers of %s (%s) synchronized?" % (p["name"], k),
                   [C("dedicated", "Dedicated OEM synchronization links"), C("ethernet", "Ethernet-based synchronization"),
                    C("fibre", "Fiber optic synchronization"), C("oem_tbv", "OEM-standard configuration — to be verified")], [k],
                   why="%s is a redundant controller pair" % k), [])
    if how in (OTHER, NA):
        return (None, [])
    paths = _ans(A, "plc_sync_paths:" + k)
    if not paths:
        return (_q("plc_sync_paths:" + k, 3, "How many physical synchronization links connect the two controllers of %s?" % k,
                   [C("1", "1"), C("2", "2"), C("unknown", "Not known — to be verified")], [k]), [])
    medium = {"ethernet": "copper", "fibre": "fibre"}.get(how) or _ans(A, "plc_sync_medium:" + k)
    if not medium:
        return (_q("plc_sync_medium:" + k, 3, "Which physical medium do the %s synchronization links use?" % k,
                   [C("fibre", "Fiber optic"), C("copper", "Copper / OEM sync cable"), C("unknown", "Not known — to be verified")], [k]), [])
    med = {"copper": "Copper Ethernet" if how == "ethernet" else "OEM synchronization cable", "fibre": "Fiber optic"}.get(medium)
    label = "Redundancy Sync" + (" (to be verified)" if how == "oem_tbv" or paths == "unknown" or medium == "unknown" else "")
    return (None, [dict(source=k, destination=k, protocol="OEM redundancy synchronization" if how != "ethernet" else "Ethernet (TCP/IP)",
                        medium=med, topology="Point-to-point", redundancy="Redundant pair",
                        paths=int(paths) if paths in ("1", "2") else None, direction=None, scope=None, label=label, pattern="pair",
                        origin="sync:" + k)])


def _units_of(recs_):
    return [(r["id"], i) for r in recs_ for i in range(1, units(r) + 1)]


def _plc_switch(spec, p, sws, A):
    k = p["id"]
    how = _ans(A, "plc_switch:" + k)
    su = _units_of(sws)
    if not how:
        ch = []
        if units(p) >= 2 and len(su) >= 2:
            ch.append(C("each_dedicated", "Each PLC connects to one dedicated switch"))
            ch.append(C("both_to_both", "Both PLCs connect to both switches"))
        ch += [C("single_to_one", "Single PLC to one switch"), C("redundant_network", "Redundant network configuration"), NA_C]
        return (_q("plc_switch:" + k, 4, "How are the PLC controllers %s (%s) connected to the industrial Ethernet switches (%s)?" %
                   (p["name"], k, describe(sws)), ch, [k] + [s["id"] for s in sws]), [])
    if how in (OTHER, NA):
        return (None, [])
    med = _ans(A, "plc_switch_medium")
    if not med:
        return (_q("plc_switch_medium", 4, "Which physical medium connects the PLCs to the switches?", MEDIUM_CHOICES, [k]), [])
    if med in (OTHER, NA):
        return (None, [])
    pu = list(range(1, units(p) + 1))
    if how == "each_dedicated":
        pairs = [((k, u), su[i]) for i, u in enumerate(pu) if i < len(su)]
    elif how in ("both_to_both", "redundant_network"):
        pairs = [((k, u), s) for u in pu for s in su[:2]]
    else:
        pairs = [((k, 1), su[0])]
    return (None, _pairs_to_conns(pairs, dict(protocol=None, medium=MEDIUM_MAP[med], topology="Star",
                                               redundancy="Redundant network" if how in ("redundant_network", "both_to_both") else "Single",
                                               paths=None, direction=None, scope=None, label=None), "plcsw:" + k))


def _pairs_to_conns(pairs, fields, origin):
    by = {}
    for (a, ua), (b, ub) in pairs:
        by.setdefault((a, b), []).append([ua, ub])
    return [dict(fields, source=a, destination=b, links=links, pattern="links", origin=origin) for (a, b), links in by.items()]


def _control_scada(spec, src, dst, A):
    how = _ans(A, "control_scada")
    about = [e["id"] for e in src + dst]
    if not how:
        return (_q("control_scada", 5, "How does the Control network connect to the SCADA network?",
                   [C("copper", "Copper Ethernet"), C("fibre", "Fiber optic Ethernet"), C("dual", "Dual redundant Ethernet paths"),
                    C("via_firewall", "Through firewall / gateway"), NA_C], about,
                   why="control (%s) and SCADA (%s) equipment are present" % (describe(src), describe(dst))), [])
    if how in (OTHER, NA):
        return (None, [])
    med = how if how in ("copper", "fibre") else _ans(A, "control_scada_medium")
    if not med:
        return (_q("control_scada_medium", 5, "Which physical medium do the Control-to-SCADA links use?", MEDIUM_CHOICES, about), [])
    if med in (OTHER, NA):
        return (None, [])
    su, du = _units_of(src), _units_of(dst)
    f = dict(protocol=None, medium=MEDIUM_MAP[med], topology="Point-to-point", redundancy="Single", paths=1, direction=None, scope=None,
             label=None)
    if how == "dual":
        f.update(redundancy="Dual independent paths", paths=2)
        if len(su) >= 2 and len(du) >= 2:
            return (None, _pairs_to_conns([(su[0], du[0]), (su[1], du[1])], dict(f, paths=1), "ctlscada"))
        return (None, _pairs_to_conns([(su[0], du[0])], dict(f, label="2 × redundant paths"), "ctlscada"))
    if how == "via_firewall":
        fws = recs(spec, "firewall")
        fw = fws[0]["id"] if len(fws) == 1 else _ans(A, "control_scada_firewall")
        if not fw:
            return (_q("control_scada_firewall", 5, "Which firewall / gateway separates the Control and SCADA networks?",
                       [C(x["id"], "%s %s" % (x["id"], x["name"])) for x in fws + recs(spec, "gateway")], about,
                       why="no firewall is recorded yet" if not fws else ""), [])
        if fw in (OTHER, NA):
            return (None, [])
        return (None, _pairs_to_conns([(su[0], (fw, 1)), ((fw, 1), du[0])], f, "ctlscada"))
    return (None, _pairs_to_conns([(su[0], du[0])], f, "ctlscada"))


def _scada_lan(spec, ssw, ends, A):
    su = _units_of(ssw)
    about = [e["id"] for e in ends]
    homing = "single_first" if len(su) < 2 else _ans(A, "scada_homing")
    if not homing:
        return (_q("scada_homing", 6, "Are the SCADA servers and workstations single-homed or dual-homed to the %d SCADA switches?" % len(su),
                   [C("single_first", "Single-homed — all to Switch 1"), C("single_split", "Single-homed — split between the switches"),
                    C("dual", "Dual-homed — each to both switches")], about), [])
    if homing in (OTHER, NA):
        return (None, [])
    med = _ans(A, "scada_lan_medium")
    if not med:
        return (_q("scada_lan_medium", 6, "Which physical medium connects the SCADA servers and workstations (%s) to the SCADA switch%s?" %
                   (describe(ends), "es" if len(su) > 1 else ""), [C("copper", "Copper Ethernet"), C("fibre", "Fiber optic"), NA_C], about), [])
    if med in (OTHER, NA):
        return (None, [])
    pairs, n = [], 0
    for e in ends:
        for u in range(1, units(e) + 1):
            if homing == "dual":
                pairs += [((e["id"], u), s) for s in su[:2]]
            else:
                pairs.append(((e["id"], u), su[n % len(su)] if homing == "single_split" else su[0]))
            n += 1
    return (None, _pairs_to_conns(pairs, dict(protocol="Ethernet (TCP/IP)", medium=MEDIUM_MAP[med], topology="Star",
                                               redundancy="Dual-homed" if homing == "dual" else "Single-homed", paths=None, direction=None,
                                               scope=None, label=None), "scadalan"))


def _fibre(spec, A):
    panels = recs(spec, "fo_panel")
    fibre_conns = [c for c in spec["connections"] if c.get("medium") == "Fiber optic"]
    fibre_kit = [e for e in spec["equipment"] if "Fiber optic" in (e.get("interfaces") or []) or "SFP" in (e.get("interfaces") or [])]
    if not (panels or fibre_conns or fibre_kit):
        return []
    out = []
    topo = _ans(A, "fibre_topology")
    if not topo:
        return [(_q("fibre_topology", 7, "What is the fiber optic network topology?",
                    [C("p2p", "Point-to-point"), C("dual", "Dual independent paths"), C("ring", "Fiber optic ring")],
                    [e["id"] for e in panels + fibre_kit], why="fiber optic equipment or links are present"), [])]
    if topo == "ring" and not any(c.get("pattern") == "ring" for c in spec["connections"]):
        nodes = _ans(A, "fibre_ring_nodes")
        if not nodes:
            cands = [e for e in spec["equipment"] if e["category"] not in ("instrument", "fo_panel", "video_wall", "ups", "kvm")]
            out.append((_q("fibre_ring_nodes", 7, "Which equipment is on the fiber optic ring, in connection order?",
                           [C(e["id"], "%s %s" % (e["id"], e["name"])) for e in cands], [e["id"] for e in cands], multi=True), []))
        elif nodes not in (OTHER, NA):
            ids = [n.strip() for n in nodes.split(",") if n.strip()]
            out.append((None, [dict(source=ids[0], destination=ids[-1], nodes=ids, protocol=None, medium="Fiber optic", topology="Ring",
                                    redundancy="Redundant network", paths=None, direction=None, scope=None, label="Fiber Optic Ring",
                                    pattern="ring", origin="fibrering")]))
    for p in panels:
        v = _ans(A, "fo_panel_links:" + p["id"])
        if v is None:
            cands = [c for c in spec["connections"] if c.get("medium") == "Fiber optic" and c.get("pattern") != "ring"]
            out.append((_q("fo_panel_links:" + p["id"], 7, "Which fiber optic links pass through the patch panel %s (%s)? (Patch panels are "
                            "not connected to unrelated equipment.)" % (p["name"], p["id"]),
                            [C(c["id"], "%s %s → %s" % (c["id"], (_get(spec, c["source"]) or {}).get("name", c["source"]),
                                                         (_get(spec, c["destination"]) or {}).get("name", c["destination"])))
                             for c in cands] + [NA_C], [p["id"]],
                            multi=True), []))
    return out


def _firewall(spec, f, A):
    k = f["id"]
    others = [c for c in spec["connections"] if (k in (c["source"], c["destination"])) and not (c.get("origin") or "").startswith("fw:")]
    if len(others) >= 2:
        return (None, [])
    zones = _ans(A, "firewall_zones:" + k)
    if not zones:
        return (_q("firewall_zones:" + k, 8, "Which two networks or security zones does the firewall %s (%s) connect?" % (f["name"], k),
                   [C(l["key"], "%s %s" % (level_label(l["level"]), l["name"])) for l in sorted(spec["layers"], key=lambda l: -l["level"])],
                   [k], multi=True, why="firewalls are never assumed from the DMZ layer; only the zones you name are connected"), [])
    if zones in (OTHER, NA):
        return (None, [])
    med = _ans(A, "firewall_medium:" + k)
    if not med:
        return (_q("firewall_medium:" + k, 8, "Which physical medium connects the firewall %s to those networks?" % k, MEDIUM_CHOICES, [k]), [])
    if med in (OTHER, NA):
        return (None, [])
    pairs = []
    for z in [z.strip() for z in zones.split(",") if z.strip()]:
        cands = [e for e in recs(spec, "switch", {z}) if e["id"] != k] or [e for e in spec["equipment"] if e["layer"] == z and e["id"] != k
                                                                           and e["category"] not in NON_COMM]
        if not cands:
            continue                                         # nothing else in that zone yet: validate() reports it
        tgt = cands[0]["id"] if len(cands) == 1 else _ans(A, "firewall_link:%s:%s" % (k, z))
        if not tgt:
            return (_q("firewall_link:%s:%s" % (k, z), 8, "On the %s side, which equipment does firewall %s connect to?" % (layer(spec, z)["name"], k),
                       [C(e["id"], "%s %s" % (e["id"], e["name"])) for e in cands], [k]), [])
        if tgt not in (OTHER, NA):
            pairs.append(((k, 1), (tgt, 1)))
    return (None, _pairs_to_conns(pairs, dict(protocol="Ethernet (TCP/IP)", medium=MEDIUM_MAP[med], topology="Point-to-point",
                                               redundancy="Single", paths=None, direction=None, scope=None, label=None), "fw:" + k))


LINK_PROTOCOLS = {
    "gateway": ["Modbus RTU", "Modbus TCP", "PROFIBUS DP", "PROFINET", "EtherNet/IP", "DNP3", "IEC 60870-5-104", "OPC UA", "BACnet/IP"],
    "rtu": ["DNP3", "IEC 60870-5-104", "Modbus TCP", "Modbus RTU"],
    "dcs": ["OPC UA", "Modbus TCP", "Modbus RTU", "IEC 60870-5-104", "DNP3"],
    "existing_scada": ["OPC UA", "Modbus TCP", "IEC 60870-5-104", "DNP3"],
    "hmi": ["PROFINET", "EtherNet/IP", "Modbus TCP"],
    "plc": ["PROFINET", "EtherNet/IP", "Modbus TCP", "Modbus RTU"],
    "router": ["Ethernet (TCP/IP)"], "wireless": ["Ethernet (TCP/IP)"],
}
LINK_MEDIA = [C("copper", "Copper Ethernet"), C("fibre", "Fiber optic"), C("rs485", "RS-485"), C("rs232", "RS-232"), C("wireless", "Wireless")]


def _link(spec, r, side, A):
    k = "link:%s:%d" % (r["id"], side)
    tgt = _ans(A, k + ":target")
    if not tgt:
        order = {l["key"]: l["level"] for l in spec["layers"]}
        mine = order.get(r["layer"], 0)
        cands = [e for e in spec["equipment"] if e["id"] != r["id"] and e["category"] not in ("instrument", "fo_panel", "video_wall", "ups", "kvm")]
        cands.sort(key=lambda e: (e["category"] != "switch", abs(order.get(e["layer"], 0) - mine), e["id"]))
        what = "%s (%s)" % (r["name"], r["id"]) + (" — the %s side" % ("first" if side == 1 else "second") if r["category"] in TWO_SIDED else "")
        return (_q(k + ":target", 9, "What does the %s connect to?" % what,
                   [C(e["id"], "%s %s" % (e["id"], e["name"])) for e in cands[:8]] + [NA_C], [r["id"]],
                   why="%s is communication equipment with no confirmed connection" % r["id"]), [])
    if tgt in (OTHER, NA):
        return (None, [])
    proto = _ans(A, k + ":protocol")
    if not proto:
        ch = LINK_PROTOCOLS.get(r["category"], ["Ethernet (TCP/IP)", "Modbus TCP", "Modbus RTU", "OPC UA"])
        return (_q(k + ":protocol", 9, "Which communication protocol does %s use to talk to %s?" % (r["id"], tgt),
                   [C(p, p) for p in ch], [r["id"], tgt]), [])
    med = _ans(A, k + ":medium")
    if not med:
        return (_q(k + ":medium", 9, "Which physical medium links %s to %s?" % (r["id"], tgt), LINK_MEDIA, [r["id"], tgt]), [])
    if med in (OTHER, NA):
        return (None, [])
    return (None, [dict(source=r["id"], destination=tgt, protocol=canon("protocol", proto) if proto != OTHER else None,
                        medium=MEDIUM_MAP.get(med, med), topology="Point-to-point", redundancy="Single", paths=None, direction=None,
                        scope=None, label=None, pattern="first-to-first", origin=k)])


def questions(spec):
    return [q for q, _ in plan(spec) if q]


def materialize(spec):
    """Create or refresh the connections that complete answers confirm. Connections the user edited by hand are never overwritten."""
    wanted = {}
    for _ in range(4):                                       # answers can unlock later steps (e.g. fibre panels after fibre links exist)
        wanted = {}
        for q, conns in plan(spec):
            for c in conns:
                wanted.setdefault(c["origin"], []).append(c)
        changed = _sync_conns(spec, wanted)
        if not changed:
            break
    _apply_fo_panels(spec)
    return wanted


def _sig(c):
    keep = {k: v for k, v in c.items() if k not in ("id", "origin", "auto", "sig")}
    return hashlib.sha1(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:12]


def _sync_conns(spec, wanted):
    changed = False
    keep = []
    manual_origins = {c["origin"] for c in spec["connections"] if c.get("origin") and not c.get("auto")}
    for c in spec["connections"]:
        if c.get("auto") and c["origin"] not in wanted and c["origin"] != "fopanel":
            changed = True                                    # its answer was withdrawn, is being re-asked, or is now Other / N/A
            spec.setdefault("retired_ids", {}).setdefault(c["origin"], []).append(c["id"])
            continue
        keep.append(c)
    spec["connections"] = keep
    for origin, conns in wanted.items():
        if origin in manual_origins:
            continue
        existing = [c for c in spec["connections"] if c.get("origin") == origin and c.get("auto")]
        if sorted(_sig(c) for c in existing) == sorted(_sig(c) for c in conns):
            continue
        ids = [c["id"] for c in existing]
        retired = spec.get("retired_ids", {}).pop(origin, [])
        ids += [i for i in sorted(retired) if not any(x["id"] == i for x in spec["connections"])]   # keep identifiers (6.4)
        spec["connections"] = [c for c in spec["connections"] if c not in existing]
        for i, c in enumerate(conns):
            c = dict(c, id=ids[i] if i < len(ids) else next_id(spec, "CN"), auto=True)
            c.setdefault("via", [])
            spec["connections"].append(c)
        changed = True
    return changed


def _apply_fo_panels(spec):
    for p in recs(spec, "fo_panel"):
        v = _ans(spec["answers"], "fo_panel_links:" + p["id"])
        if not v or v in (OTHER, NA):
            continue
        for cid in [x.strip() for x in v.split(",") if x.strip()]:
            for c in spec["connections"]:
                if c["id"] == cid and p["id"] not in c.setdefault("via", []):
                    c["via"].append(p["id"])


def answer(spec, key, value, text=None):
    """Record an answer (value is a choice value, comma-separated for multi-select, or 'other' with text) and materialize."""
    qs = {q["key"]: q for q in questions(spec)}
    if key not in qs and key in spec["answers"]:                 # changing an earlier answer (6.2 / 6.4): validate against its question
        trial = copy.deepcopy(spec)
        del trial["answers"][key]
        qs.update({q["key"]: q for q in questions(trial)})
    if key not in qs and key not in spec["answers"]:
        raise SpecError("no open question %s (open: %s)" % (key, ", ".join(qs) or "none"))
    q = qs.get(key)
    if q:
        allowed = {c["value"] for c in q["choices"]} | {OTHER, NA}
        vals = [v.strip() for v in str(value).split(",")] if q["multi"] else [str(value).strip()]
        bad = [v for v in vals if v not in allowed]
        if bad:
            raise SpecError("%s: %s is not a choice (choices: %s). Use 'other' with --text for anything else." %
                            (key, ", ".join(bad), ", ".join(sorted(allowed))))
        if key.startswith("firewall_zones:") and value not in (OTHER, NA) and len(vals) != 2:
            raise SpecError("a firewall connects two networks or zones: choose exactly two (or 'other' with --text)")
    spec["answers"][key] = {"value": str(value).strip(), "text": text, "at": now()}
    log(spec, "answer", "%s = %s%s" % (key, value, " (%s)" % text if text else ""))
    materialize(spec)
    spec["stage"] = "connectivity"
    return spec["answers"][key]


def unanswer(spec, key):
    if key not in spec["answers"]:
        raise SpecError("%s has no answer" % key)
    del spec["answers"][key]
    for k in [k for k in spec["answers"] if k.startswith(key.split(":")[0] + "_") and key.split(":")[0] in ("io_protocol",)]:
        pass
    log(spec, "unanswer", key)
    materialize(spec)


CONN_FIELDS = ("source", "destination", "protocol", "medium", "topology", "redundancy", "paths", "direction", "scope", "label", "pattern",
               "via", "nodes", "relation", "links")


def connect(spec, **f):
    for k in ("source", "destination"):
        eq(spec, f[k])
    c = {k: f.get(k) for k in CONN_FIELDS}
    for k in ("protocol", "medium", "topology", "redundancy"):
        c[k] = canon(k, c[k])
    c["paths"] = int(c["paths"]) if c.get("paths") not in (None, "", "-") else None
    c["via"] = [v for v in (c.get("via") or []) if v]
    c["pattern"] = c.get("pattern") or ("ring" if c.get("nodes") else "first-to-first")
    c.update(id=next_id(spec, "CN"), origin=None, auto=False)
    spec["connections"].append(c)
    log(spec, "connect", "%s %s -> %s" % (c["id"], c["source"], c["destination"]))
    return c


def edit_connection(spec, cid, **f):
    c = next((c for c in spec["connections"] if c["id"] == cid), None)
    if not c:
        raise SpecError("no connection %s" % cid)
    done = []
    for k, v in f.items():
        if k not in CONN_FIELDS or v is None:
            continue
        if k in ("protocol", "medium", "topology", "redundancy"):
            v = canon(k, v)
        if k == "paths":
            v = None if str(v).strip() in ("", "-") else int(v)
        if k in ("via", "nodes") and isinstance(v, str):
            v = [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, str) and v.strip() in ("", "-"):
            v = None
        if c.get(k) != v:
            done.append("%s: %r -> %r" % (k, c.get(k), v))
            c[k] = v
    if done:
        c["auto"] = False                                    # now the user's: later answers do not overwrite it
        log(spec, "edit-connection", "%s %s" % (cid, "; ".join(done)))
    return done


def remove_connection(spec, cid):
    if not any(c["id"] == cid for c in spec["connections"]):
        raise SpecError("no connection %s" % cid)
    c = next(c for c in spec["connections"] if c["id"] == cid)
    spec["connections"] = [x for x in spec["connections"] if x["id"] != cid]
    if c.get("origin"):                                       # keep it gone: mark its origin answered as N/A by hand
        spec.setdefault("removed_origins", []).append(c["origin"])
    log(spec, "remove-connection", cid)


# ---- validation (5.11) ---------------------------------------------------------------------------------------------------------------
def cable_type(c):
    """Map protocol + medium to the approved cable palette. Returns (cable or None, reason)."""
    p, m = c.get("protocol"), c.get("medium")
    if m == "Copper (hardwired)" or p == "Hardwired AI/DI/AO/DO":
        return "hardwired", ""
    if p and p.startswith("BACnet"):
        return "bacnet", ""
    if m == "Fiber optic":
        return "fibre", ""
    if m == "Copper Ethernet":
        return "ethernet", ""
    if m == "RS-485" and p in ("Modbus RTU", None):
        return ("modbus", "") if p == "Modbus RTU" else (None, "RS-485 link with no protocol: the modbus colour is only for Modbus RTU")
    if m == "Backplane":
        return None, "local backplane (no cable drawn)"
    if m in ("RS-485", "RS-232", "Wireless", "OEM synchronization cable"):
        return None, "%s%s has no colour in the approved cable standard" % (m, " (%s)" % p if p else "")
    if m is None:
        return None, "physical medium not confirmed"
    return None, "medium %r is not in the approved cable standard" % m


def validate(spec):
    issues = []

    def add(sev, where, msg):
        issues.append({"severity": sev, "where": where, "message": msg})
    ids = {e["id"]: e for e in spec["equipment"]}
    keys = {l["key"] for l in spec["layers"]}
    if not spec["layers"]:
        add("error", "layers", "no layers selected")
    for e in spec["equipment"]:
        if e["layer"] not in keys:
            add("error", e["id"], "layer %s is not selected" % e["layer"])
        for f in e.get("flags", []):
            add("question", e["id"], "%s: %s" % (e["name"], f))
    for l in spec["layers"]:
        if not any(e["layer"] == l["key"] for e in spec["equipment"]):
            add("warning", l["key"], "layer %s has no equipment" % l["name"])
    for c in spec["connections"]:
        w = c["id"]
        for k in ("source", "destination"):
            if c.get(k) not in ids:
                add("error", w, "%s %s does not exist" % (k, c.get(k)))
        for k in c.get("via") or []:
            if k not in ids:
                add("error", w, "via %s does not exist" % k)
        for field in ("protocol", "medium", "topology", "redundancy"):
            v = c.get(field)
            if not v:
                continue
            hits = classify_value(v)
            if field not in hits and hits:
                other = sorted(hits)[0]
                add("error", w, "%s %r is a %s, not a %s: correct it" % (field, v, other, field))
            elif not hits and v not in VOCAB[field]:
                add("warning", w, "%s %r is not a recognised %s; check it" % (field, v, field))
        p, m, t = c.get("protocol"), c.get("medium"), c.get("topology")
        if p in ETHERNET_PROTOCOLS and m in ("RS-485", "RS-232", "Copper (hardwired)"):
            add("error", w, "%s runs over Ethernet, not %s" % (p, m))
        if p in SERIAL_PROTOCOLS and m == "Copper Ethernet":
            add("error", w, "%s is a serial/fieldbus protocol and cannot use Copper Ethernet directly (a gateway is needed)" % p)
        if p in SERIAL_PROTOCOLS and m == "Fiber optic":
            add("warning", w, "%s over fiber optic needs optical link modules or converters; record them" % p)
        if p == "Hardwired AI/DI/AO/DO" and m not in (None, "Copper (hardwired)"):
            add("error", w, "hardwired signals use copper (hardwired) cable, not %s" % m)
        if p == "Hardwired AI/DI/AO/DO" and t in ("Daisy-chain", "Ring", "Bus / Multi-drop"):
            add("error", w, "hardwired signals cannot use a %s topology" % t)
        if t == "Local backplane" and m not in (None, "Backplane"):
            add("error", w, "a local backplane topology has no %s cable" % m)
        if t == "Ring" and c.get("pattern") == "ring" and len(c.get("nodes") or []) < 3 and c.get("origin") != "io:" + c["destination"]:
            add("warning", w, "a ring needs at least three nodes")
        a, b = ids.get(c.get("source")), ids.get(c.get("destination"))
        if m == "Fiber optic" and any(x and x["category"] == "instrument" for x in (a, b)) and not c.get("via"):
            add("error", w, "an instrument cannot connect directly to fiber optic: name the communication interface")
        if m is None and c.get("pattern") != "none":
            add("question", w, "physical medium not confirmed")
        if t is None and c.get("pattern") not in ("pair", "none"):
            add("question", w, "topology not confirmed")
        if c.get("paths") is None and c.get("pattern") == "pair":
            add("question", w, "number of synchronization links not confirmed")
        cab, why = cable_type(c)
        if not cab and c.get("pattern") != "none" and m is not None:
            add("warning", w, "not drawn: %s" % why)
        if c.get("label") and "to be verified" in c["label"]:
            add("question", w, "%s" % c["label"])
    for k, v in spec["answers"].items():
        if k.startswith("firewall_zones:") and v.get("value") not in (OTHER, NA):
            for z in v["value"].split(","):
                if z in keys and not any(e["layer"] == z and e["id"] != k.split(":")[1] and e["category"] not in NON_COMM
                                         for e in spec["equipment"]):
                    add("question", k, "the firewall's %s side has no equipment to connect to yet" % layer(spec, z)["name"])
        if v.get("value") == OTHER:
            if not v.get("text"):
                add("question", k, "'Other / Specify' chosen without details")
            add("question", k, "Other: %s — record the resulting connection with 'connect'" % (v.get("text") or ""))
    for q in questions(spec):
        add("question", q["key"], "open: " + q["prompt"])
    return issues


# ---- Step 5: review and editable request ----------------------------------------------------------------------------------------
def _v(x):
    if x in (None, "", []):
        return "-"
    if isinstance(x, list):
        return ", ".join("-".join(map(str, i)) if isinstance(i, list) else str(i) for i in x)
    return str(x)


def project_lines(spec):
    return ["%s: %s" % (label, spec["project"].get(k) or "TBC") for k, label, _ in PROJECT_FIELDS if k != "sheet" or spec["project"].get(k)]


def equipment_line(e):
    return "- [%s] %s | Qty: %s | Category: %s | OEM: %s | Model: %s | Redundancy: %s | Location: %s | Scope: %s | Interfaces: %s | Notes: %s" % (
        e["id"], e["name"], _v(e.get("quantity")), e["category"], _v(e.get("oem")), _v(e.get("model")), _v(e.get("redundancy")),
        _v(e.get("location")), _v(e.get("scope")), _v(e.get("interfaces")), _v(e.get("notes")))


def connection_line(spec, c):
    name = {e["id"]: e["name"] for e in spec["equipment"]}
    ends = "%s %s -> %s %s" % (c["source"], name.get(c["source"], "?"), c["destination"], name.get(c["destination"], "?"))
    if c.get("source") == c.get("destination"):
        ends = "%s %s (primary <-> secondary)" % (c["source"], name.get(c["source"], "?"))
    extra = ""
    if c.get("nodes"):
        extra += " | Nodes: %s" % ", ".join(c["nodes"])
    if c.get("links"):
        extra += " | Units: %s" % ", ".join("%d-%d" % tuple(l) for l in c["links"])
    return "- [%s] %s | Protocol: %s | Medium: %s | Topology: %s | Redundancy: %s | Paths: %s | Direction: %s | Scope: %s | Label: %s | Via: %s%s" % (
        c["id"], ends, _v(c.get("protocol")), _v(c.get("medium")), _v(c.get("topology")), _v(c.get("redundancy")), _v(c.get("paths")),
        _v(c.get("direction")), _v(c.get("scope")), _v(c.get("label")), _v(c.get("via")), extra)


def request_text(spec):
    P = spec["project"]
    out = ["ARCHITECTURE REQUEST — %s" % (P.get("project") or "TBC"),
           "(Edit any line, keep the [IDs], add new lines without an ID, delete lines to remove items. '-' means not stated.)", "",
           "## Project"] + project_lines(spec) + ["", "## Layers (top of drawing first)"]
    for l in sorted(spec["layers"], key=lambda l: -l["level"]):
        out.append("- [%s] %s | %s | %s" % (l["key"], level_label(l["level"]), l["name"], l.get("desc") or "-"))
    out += ["", "## Equipment"]
    for l in spec["layers"]:
        out.append("### [%s] %s" % (l["key"], l["name"]))
        for e in [e for e in spec["equipment"] if e["layer"] == l["key"]]:
            out.append(equipment_line(e))
            out.append('  Original: "%s"' % e.get("source_text", "").replace('"', "'"))
    out += ["", "## Connections"] + [connection_line(spec, c) for c in spec["connections"]]
    out += ["", "## Unresolved technical questions (generated; answer them in chat)"]
    out += ["- %s: %s" % (i["where"], i["message"]) for i in validate(spec) if i["severity"] in ("question", "error")] or ["- none"]
    out += ["", "## Notes"] + ["- %s" % n for n in spec["notes"]]
    return "\n".join(out) + "\n"


def review_text(spec):
    """Step 5 review, markdown. Project, layers, equipment per layer, connectivity summary, unresolved questions, notes."""
    issues = validate(spec)
    out = ["# Architecture request review", "", "**Stage:** %s" % spec["stage"], "", "## Project information"]
    out += ["- " + l for l in project_lines(spec)]
    out += ["", "## Selected layers (top of drawing first)"]
    out += ["- %s **%s** (%s)" % (level_label(l["level"]), l["name"], l["key"]) for l in sorted(spec["layers"], key=lambda l: -l["level"])]
    out += ["", "## Equipment per layer"]
    for l in spec["layers"]:
        out.append("**%s — %s**" % (level_label(l["level"]), l["name"]))
        rows = [e for e in spec["equipment"] if e["layer"] == l["key"]]
        if not rows:
            out.append("- (none)")
        for e in rows:
            bits = [x for x in (e.get("oem"), e.get("model"), e.get("redundancy"), e.get("location"),
                                ("scope: " + e["scope"]) if e.get("scope") else None) if x]
            out.append("- %s %s — qty %s%s%s" % (e["id"], e["name"], e.get("quantity") or "TBC",
                                                      " (%s)" % ", ".join(bits) if bits else "",
                                                      " ⚠ " + "; ".join(e["flags"]) if e.get("flags") else ""))
        out.append("")
    out += ["## Connectivity summary"]
    name = {e["id"]: e["name"] for e in spec["equipment"]}
    for c in spec["connections"]:
        cab, why = cable_type(c)
        ends = "%s ↔ %s" % (name.get(c["source"], c["source"]), name.get(c["destination"], c["destination"])) \
            if c["source"] != c["destination"] else "%s primary ↔ secondary" % name.get(c["source"])
        if c.get("nodes"):
            ends = " → ".join(name.get(n, n) for n in c["nodes"]) + " (ring)"
        out.append("- %s %s: %s / %s / %s / %s%s%s" % (c["id"], ends, _v(c.get("protocol")), _v(c.get("medium")), _v(c.get("topology")),
                                                      _v(c.get("redundancy")), " via " + ", ".join(c["via"]) if c.get("via") else "",
                                                      "" if cab else " — *%s*" % why))
    if not spec["connections"]:
        out.append("- (none confirmed yet)")
    out += ["", "## Unresolved technical questions"]
    out += ["- **%s** %s: %s" % (i["severity"], i["where"], i["message"]) for i in issues if i["severity"] in ("error", "question")] or ["- none"]
    warn = [i for i in issues if i["severity"] == "warning"]
    if warn:
        out += ["", "## Warnings"] + ["- %s: %s" % (i["where"], i["message"]) for i in warn]
    out += ["", "## Additional notes"] + (["- %s" % n for n in spec["notes"]] or ["- (none)"])
    return "\n".join(out) + "\n"


def _fields(parts):
    d = {}
    for p in parts:
        m = re.match(r"^\s*([A-Za-z /]+?)\s*:\s*(.*)$", p)
        if m:
            d[norm(m.group(1))] = None if m.group(2).strip() in ("-", "") else m.group(2).strip()
    return d


def parse_request(spec, text):
    """Read an edited request back. Returns a list of change dicts; apply_changes() applies them. Generated sections are ignored."""
    changes, section, lay = [], None, None
    seen_eq, seen_cn, seen_l = set(), set(), set()
    plabels = {norm(label): k for k, label, _ in PROJECT_FIELDS}
    names = {"client / contractor": "client"}
    plabels.update(names)
    new_notes = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            h = norm(line[3:])
            section = "project" if h.startswith("project") else "layers" if h.startswith("layers") else "equipment" if h.startswith(
                "equipment") else "connections" if h.startswith("connections") else "notes" if h.startswith("notes") else "skip"
            continue
        if section == "equipment" and line.startswith("### "):
            m = re.match(r"### \[([^\]]+)\]", line)
            lay = m.group(1) if m else None
            continue
        if not line.strip() or section in (None, "skip") or line.strip().startswith("Original:"):
            continue
        if section == "project":
            m = re.match(r"^([^:]+):\s*(.*)$", line)
            if m and norm(m.group(1)) in plabels:
                k = plabels[norm(m.group(1))]
                v = m.group(2).strip()
                v = None if v.upper() in ("TBC", "-", "") else v
                if spec["project"].get(k) != v:
                    changes.append({"kind": "project", "field": k, "old": spec["project"].get(k), "new": v})
        elif section == "layers":
            m = re.match(r"^- \[([^\]]+)\]\s*(.*)$", line)
            if not m:
                continue
            parts = [p.strip() for p in m.group(2).split("|")]
            key = m.group(1).strip()
            seen_l.add(key)
            lvl = parts[0] if parts else None
            name = parts[1] if len(parts) > 1 else None
            desc = parts[2] if len(parts) > 2 and parts[2] != "-" else ""
            cur = next((l for l in spec["layers"] if l["key"] == key), None)
            if not cur:
                changes.append({"kind": "layer-add", "key": key, "level": lvl, "name": name, "desc": desc})
            else:
                if name and name != cur["name"]:
                    changes.append({"kind": "layer-rename", "key": key, "old": cur["name"], "new": name})
                if (desc or "") != (cur.get("desc") or ""):
                    changes.append({"kind": "layer-desc", "key": key, "old": cur.get("desc"), "new": desc})
        elif section == "equipment":
            m = re.match(r"^- (?:\[(EQ-\d+)\]\s*)?(.*)$", line)
            if not m:
                continue
            eid, body = m.group(1), m.group(2)
            parts = [p.strip() for p in body.split("|")]
            f = _fields(parts[1:])
            vals = {"name": parts[0], "quantity": f.get("qty"), "category": f.get("category"), "oem": f.get("oem"), "model": f.get("model"),
                    "redundancy": f.get("redundancy"), "location": f.get("location"), "scope": f.get("scope"),
                    "interfaces": [s.strip() for s in f["interfaces"].split(",")] if f.get("interfaces") else [], "notes": f.get("notes")}
            if eid:
                seen_eq.add(eid)
                try:
                    cur = eq(spec, eid)
                except SpecError:
                    changes.append({"kind": "error", "message": "%s is not in the specification" % eid})
                    continue
                diff = {}
                for k, v in vals.items():
                    curv = cur.get(k)
                    if k == "quantity":
                        v = None if v in (None, "TBC") else int(re.sub(r"\D", "", v) or 0) or None
                    if (curv or None) != (v or None) and not (k == "interfaces" and (curv or []) == (v or [])):
                        diff[k] = (curv, v)
                if lay and lay != cur["layer"]:
                    diff["layer"] = (cur["layer"], lay)
                if diff:
                    changes.append({"kind": "equipment-edit", "id": eid, "diff": diff})
            else:
                changes.append({"kind": "equipment-add", "layer": lay, "text": line[2:].strip()})
        elif section == "connections":
            m = re.match(r"^- (?:\[(CN-\d+)\]\s*)?(.*)$", line)
            if not m:
                continue
            cid, body = m.group(1), m.group(2)
            parts = [p.strip() for p in body.split("|")]
            ends = re.findall(r"EQ-\d+", parts[0])
            f = _fields(parts[1:])
            vals = {"protocol": f.get("protocol"), "medium": f.get("medium"), "topology": f.get("topology"), "redundancy": f.get("redundancy"),
                    "paths": f.get("paths"), "direction": f.get("direction"), "scope": f.get("scope"), "label": f.get("label"),
                    "via": [s.strip() for s in f["via"].split(",")] if f.get("via") else []}
            if ends:
                vals["source"] = ends[0]
                vals["destination"] = ends[1] if len(ends) > 1 else ends[0]
            if cid:
                seen_cn.add(cid)
                cur = next((c for c in spec["connections"] if c["id"] == cid), None)
                if not cur:
                    changes.append({"kind": "error", "message": "%s is not in the specification" % cid})
                    continue
                diff = {}
                for k, v in vals.items():
                    if k == "paths":
                        v = None if v is None else int(v)
                    curv = cur.get(k)
                    if (curv or None) != (v or None) and not (k == "via" and (curv or []) == (v or [])):
                        diff[k] = (curv, v)
                if diff:
                    changes.append({"kind": "connection-edit", "id": cid, "diff": diff})
            elif ends:
                changes.append({"kind": "connection-add", "fields": vals})
            else:
                changes.append({"kind": "error", "message": "connection line without equipment ids: %s" % line})
        elif section == "notes":
            if line.startswith("- "):
                new_notes.append(line[2:].strip())
    for e in spec["equipment"]:
        if e["id"] not in seen_eq:
            changes.append({"kind": "equipment-remove", "id": e["id"], "name": e["name"]})
    for c in spec["connections"]:
        if c["id"] not in seen_cn:
            changes.append({"kind": "connection-remove", "id": c["id"]})
    for l in spec["layers"]:
        if l["key"] not in seen_l:
            changes.append({"kind": "layer-remove", "key": l["key"]})
    if new_notes != spec["notes"]:
        changes.append({"kind": "notes", "old": spec["notes"], "new": new_notes})
    return changes


def describe_change(c):
    k = c["kind"]
    if k == "project":
        return "Project %s: %s -> %s" % (c["field"], c["old"] or "TBC", c["new"] or "TBC")
    if k in ("equipment-edit", "connection-edit"):
        return "%s: %s" % (c["id"], "; ".join("%s %s -> %s" % (f, _v(a), _v(b)) for f, (a, b) in c["diff"].items()))
    if k == "equipment-add":
        return "Add equipment to %s: %s" % (c["layer"], c["text"])
    if k == "equipment-remove":
        return "Remove %s %s (and its connections)" % (c["id"], c["name"])
    if k == "connection-add":
        return "Add connection %s -> %s" % (c["fields"].get("source"), c["fields"].get("destination"))
    if k == "connection-remove":
        return "Remove connection %s" % c["id"]
    if k.startswith("layer"):
        return "%s %s %s" % (k, c.get("key"), c.get("new") or c.get("name") or "")
    if k == "notes":
        return "Notes replaced (%d -> %d lines)" % (len(c["old"]), len(c["new"]))
    return c.get("message", k)


def apply_changes(spec, changes):
    errs = [c for c in changes if c["kind"] == "error"]
    if errs:
        raise SpecError("; ".join(c["message"] for c in errs))
    for c in changes:
        k = c["kind"]
        if k == "project":
            set_project(spec, **{c["field"]: c["new"] or ""})
        elif k == "layer-rename":
            layer(spec, c["key"])["name"] = c["new"]
        elif k == "layer-desc":
            layer(spec, c["key"])["desc"] = c["new"]
        elif k == "layer-add":
            keys = [l["key"] for l in spec["layers"] if not l.get("custom")]
            if c["key"] in STD_BY_KEY:
                select_layers(spec, keys + [c["key"]], renames={c["key"]: c["name"]} if c.get("name") else None)
            else:
                select_layers(spec, keys + [l["key"] for l in spec["layers"] if l.get("custom")],
                              custom=[(c["level"], c["name"] or c["key"], c.get("desc"))])
        elif k == "equipment-edit":
            edit_equipment(spec, c["id"], **{f: b for f, (a, b) in c["diff"].items()})
        elif k == "equipment-add":
            add_equipment(spec, c["layer"], c["text"])
        elif k == "connection-edit":
            edit_connection(spec, c["id"], **{f: (",".join(b) if isinstance(b, list) else b) for f, (a, b) in c["diff"].items()})
    for c in changes:                                        # removals last, so edits to other lines are not lost
        k = c["kind"]
        if k == "connection-remove" and any(x["id"] == c["id"] for x in spec["connections"]):
            remove_connection(spec, c["id"])
        elif k == "equipment-remove":
            remove_equipment(spec, c["id"])
        elif k == "connection-add":
            f = c["fields"]
            connect(spec, **{x: (f.get(x) if x != "via" else f.get("via")) for x in CONN_FIELDS if x in f})
        elif k == "notes":
            spec["notes"] = c["new"]
    for c in changes:
        if c["kind"] == "layer-remove":
            keep = [l["key"] for l in spec["layers"] if l["key"] != c["key"]]
            select_layers(spec, [k for k in keep if not k.startswith("C")] + [k for k in keep if k.startswith("C")])
    materialize(spec)
    log(spec, "request-edit", "%d change(s) applied from the edited request" % len(changes))


# ---- Step 6: specification -> diagram.json ---------------------------------------------------------------------------------------
COMPONENT_FOR = {"plc": "rack_plc", "io": "remote_i_o_drop", "switch": "ethernet_switch", "fo_panel": "fiber_optic_patch_panel",
                 "firewall": "firewall", "server": "rack_server", "historian": "historian_application_server",
                 "workstation": "client_operator_workstation", "eng_workstation": "engineering_workstation", "laptop": "laptop",
                 "router": "4g_lte_router", "wireless": "wireless_access_point", "ups": "ups", "printer": "printer",
                 "video_wall": "video_wall", "kvm": "kvm_switch", "time_server": "gps_nas_server", "gateway": "communication_processor",
                 "media_converter": "communication_processor", "dcs": "process_controller", "rtu": None, "hmi": None}
INSTRUMENT_COMPONENT = [(r"different|dp\b|dpt|dpit", "dp_transmitter_3_valve_manifold"), (r"pressure", "pressure_transmitter"),
                        (r"temperature|\btt\b|rtd|thermo", "temperature_transmitter_rtd_in_thermowell"),
                        (r"coriolis", "coriolis_flowmeter"), (r"vortex", "vortex_flowmeter"), (r"ultrasonic\s+flow", "clamp_on_ultrasonic_flowmeter"),
                        (r"flow", "electromagnetic_flowmeter"), (r"level\s+switch", "level_switch"), (r"ultrasonic\s+level", "ultrasonic_level_transmitter"),
                        (r"level", "radar_level_transmitter"), (r"ph|orp", "ph_orp_sensor_transmitter"), (r"chlorine", "chlorine_analyzer_sensor"),
                        (r"turbidity", "turbidity_meter"), (r"h2s", "h2s_analyzer"), (r"gas", "gas_detector"), (r"flame", "flame_detector"),
                        (r"vibration", "vibration_sensor"), (r"proximity", "proximity_sensor"), (r"valve|mov|actuator", "mov_motor_operated_valve"),
                        (r"power\s+meter|energy", "power_meter"), (r"push\s*button|e-?stop", "emergency_stop_push_button")]
OEM_COMPONENT = {("hmi", "siemens"): "hmi_panel_siemens", ("hmi", "schneider"): "hmi_panel_schneider", ("rtu", "siemens"): "rtu_siemens",
                 ("rtu", "abb"): "rtu_abb", ("rtu", "schneider"): "rtu_schneider"}


def _known_components():
    ids = set()
    for f in ("components.json", "fixed_components.json"):
        try:
            with open(os.path.join(ROOT, "data", f), encoding="utf-8") as fh:
                ids |= {c["id"] for c in json.load(fh)["components"]}
        except (OSError, ValueError, KeyError):
            pass
    return ids


def component_for(e, known):
    cat = e["category"]
    if cat == "instrument":
        t = norm(e["name"])
        for pat, cid in INSTRUMENT_COMPONENT:
            if re.search(pat, t):
                return cid if cid in known else None
        return None
    oem = norm(e.get("oem") or "").split(" ")[0] if e.get("oem") else ""
    cid = OEM_COMPONENT.get((cat, oem)) or COMPONENT_FOR.get(cat)
    return cid if cid in known else None


def singular(name):
    words = name.split()
    if not words:
        return name
    w = words[-1]
    if re.search(r"(?:ches|shes|sses|xes)$", w, re.I):
        w = w[:-2]
    elif re.search(r"[^su]s$", w, re.I) and not re.search(r"(?:ss|is|us|os)$", w, re.I) and len(w) > 3:
        w = w[:-1]
    return " ".join(words[:-1] + [w])


def unit_ids(e):
    return ["%s-%d" % (e["id"], i) for i in range(1, units(e) + 1)]


def to_diagram(spec):
    """A buildable diagram.json from the specification. Returns (diagram, warnings). The AI still sources pictures (web first) and may
    refine grouping; topology, quantities and cable types come only from the specification."""
    issues = [i for i in validate(spec) if i["severity"] == "error"]
    warnings = []
    known = _known_components()
    P = spec["project"]
    d = {"project": {fk: P.get(k) for k, _, fk in PROJECT_FIELDS if P.get(k)}, "notes": list(spec["notes"])}
    if P.get("doc_name"):
        d["title"] = P["doc_name"].upper()
    lays = sorted(spec["layers"], key=lambda l: -l["level"])
    d["layers"] = [l["id"] for l in lays]
    custom = [l for l in lays if l.get("custom")]
    if custom:
        d["custom_layers"] = [{"id": l["id"], "level": l["level"], "name": l["name"], "desc": l.get("desc", "")} for l in custom]
    d["layer_headers"] = {l["id"]: {"name": l["name"], **({"description": l["desc"]} if l.get("desc") else {})} for l in lays if not l.get("custom")}
    lid = {l["key"]: l["id"] for l in spec["layers"]}
    shapes, lines, rings = [], [], []
    owner = {}                                                         # io record -> plc record (from confirmed I/O connections)
    for c in spec["connections"]:
        a, b = _get(spec, c["source"]), _get(spec, c["destination"])
        if a and b and {a["category"], b["category"]} >= {"io"} and (a["category"] in CONTROLLERS or b["category"] in CONTROLLERS):
            io_, plc = (b, a) if b["category"] == "io" else (a, b)
            owner[io_["id"]] = plc["id"]
        elif a and b and "io" in (a["category"], b["category"]) and c.get("origin", "").startswith("io:"):
            owner.setdefault(c["destination"], next((x["id"] for x in recs(spec, "plc")), None))
    field_target = {}
    for c in spec["connections"]:
        a, b = _get(spec, c["source"]), _get(spec, c["destination"])
        if a and b and a["category"] == "instrument" and b["category"] != "instrument":
            field_target.setdefault(a["id"], owner.get(b["id"], b["id"]))
    groups = {}

    def group(gid, layer_id, label, scope="avanceon", parent=None, **kw):
        if gid not in groups:
            g = {"id": gid, "kind": "group", "label": label, "scope": scope}
            g.update({"parent": parent} if parent else {"layer": layer_id})
            g.update(kw)
            groups[gid] = g
            shapes.append(g)
        return gid
    plcs = recs(spec, CONTROLLERS)
    for e in spec["equipment"]:
        lay = lid[e["layer"]]
        scope = "other" if (e.get("scope") or "").startswith("other") else "avanceon"
        cat = e["category"]
        if cat in ("existing_scada", "dcs") and not e.get("quantity"):
            group("G-" + e["id"], lay, e["name"], scope="other")       # an existing system summary, no invented device picture
            continue
        if cat == "plc" or (cat in ("rtu", "dcs") and lay == "control"):
            parent = group("G-SYS-" + e["id"], lay, "%s" % e["name"], scope=scope, columns=1)
        elif cat == "io":
            sys_ = owner.get(e["id"])
            if sys_ and _get(spec, sys_) and lid[_get(spec, sys_)["layer"]] == lay:
                parent = group("G-IO-" + sys_, lay, "I/O Racks", parent=group("G-SYS-" + sys_, lay, _get(spec, sys_)["name"], columns=1),
                               solid=True, row=1, scope=scope)
            else:
                parent = group("G-IO-" + e["layer"], lay, "I/O Racks", solid=True, scope=scope)
        elif cat == "instrument":
            tgt = field_target.get(e["id"])
            label = "Field Instruments" + (" — %s" % _get(spec, tgt)["name"] if tgt and len(plcs) > 1 and _get(spec, tgt) else "")
            parent = group("G-FIELD-%s%s" % (tgt or e["layer"], "-other" if scope == "other" else ""), lay, label, scope=scope)
        elif scope == "other":
            parent = group("G-OTHER-" + e["layer"], lay, "Client / Existing Scope", scope="other")
        elif lay == "scada" or cat in SCADA_ENDPOINTS | {"switch", "video_wall", "firewall"}:
            parent = group("G-" + lay, lay, "", scope=scope)
        else:
            parent = group("G-" + lay, lay, "Control Network" if lay == "control" else "", scope=scope)
        n = units(e)
        cid = component_for(e, known)
        for i, uid in enumerate(unit_ids(e), 1):
            s = {"id": uid, "parent": parent, "label": singular(e["name"]) if n > 1 else e["name"]}
            if cat == "instrument":
                s["label"] = e["name"]
                s["sublabel"] = "(Qty %s)" % (e["quantity"] if e.get("quantity") else "TBC")
            elif is_pair(e) and n == 2:
                s["sublabel"] = "(Primary)" if i == 1 else ("(Secondary)" if cat in CONTROLLERS else "(Standby)")
            elif n > 1:
                s["label"] = "%s %d" % (singular(e["name"]), i)
            if e.get("oem") or e.get("model"):
                s["sublabel"] = ((s.get("sublabel") + " ") if s.get("sublabel") else "") + " ".join(x for x in (e.get("oem"), e.get("model")) if x)
            if cid:
                s["component"] = cid
            if cat == "plc" or cat == "io":
                s["row"] = 0 if cat == "plc" else None
                if s["row"] is None:
                    del s["row"]
            img = spec.get("images", {}).get(e["id"])
            if img:
                s.update({k: v for k, v in img.items() if k in ("image", "image_source", "oem", "model", "image_override", "background")})
            shapes.append(s)
            if cat == "instrument":
                break                                                  # one representative picture per instrument type, quantity in caption
        if e.get("quantity") is None:
            warnings.append("%s %s: quantity not stated; drawn once with 'Qty TBC'" % (e["id"], e["name"]))
    for g in groups.values():                                          # one row of equipment per box unless it is crowded
        kids = [x for x in shapes if x.get("parent") == g["id"]]
        if "columns" not in g:
            g["columns"] = max(1, min(8, len(kids)))
    for c in spec["connections"]:
        cab, why = cable_type(c)
        if c.get("pattern") == "none":
            continue
        if not cab:
            warnings.append("%s not drawn: %s" % (c["id"], why))
            continue
        a, b = _get(spec, c["source"]), _get(spec, c["destination"])
        if not a or not b:
            continue
        common = {"cable": cab}
        if c.get("label"):
            common["label"] = c["label"]
        if c.get("pattern") == "ring":
            nodes = c.get("nodes") or ([unit_ids(a)[0]] + unit_ids(b))
            nodes = [unit_ids(_get(spec, n))[0] if _get(spec, n) else n for n in nodes] if c.get("nodes") else nodes
            if c.get("origin", "").startswith("io:"):
                existing = next((r for r in rings if r.get("_src") == c["source"]), None)
                if existing:
                    existing["nodes"] += [n for n in unit_ids(b) if n not in existing["nodes"]]
                    continue
            rings.append({"id": "ring-" + c["id"], "label": c.get("label") or "Fiber Optic Ring", "cable": cab, "nodes": nodes, "_src": c["source"]})
            continue
        if c.get("pattern") == "pair":
            u = unit_ids(a)
            if len(u) >= 2:
                for _ in range(c.get("paths") or 1):
                    lines.append(dict(common, **{"from": u[0], "to": u[1], "direct": True, "label": c.get("label") or "Redundancy Sync"}))
                    break                                              # the label carries the number of links; one drawn line
                if (c.get("paths") or 1) > 1:
                    lines[-1]["label"] = "%s (%d links)" % (lines[-1]["label"], c["paths"])
            continue
        if c.get("pattern") == "group":
            ga = next((s["parent"] for s in shapes if s.get("id") in unit_ids(a)), None)
            tgt = owner.get(b["id"]) if b["category"] == "io" else None
            gb = "G-IO-" + tgt if tgt and "G-IO-" + tgt in groups else next((s["parent"] for s in shapes if s.get("id") in unit_ids(b)), None)
            for u in unit_ids(b)[:1]:
                lines.append(dict(common, **{"from": unit_ids(a)[0], "to": u}))
            continue
        if c.get("pattern") == "chain":
            existing = next((l for l in lines if l.get("_chain") == c["source"]), None)
            if existing:
                existing["chain"] += [u for u in unit_ids(b) if u not in existing["chain"]]
            else:
                lines.append(dict(common, chain=[unit_ids(a)[0]] + unit_ids(b), _chain=c["source"]))
            continue
        if c.get("pattern") == "links":
            pairs = [("%s-%d" % (a["id"], x), "%s-%d" % (b["id"], y)) for x, y in c["links"]]
        elif c.get("pattern") == "each-to-first":
            pairs = [(unit_ids(a)[0], u) for u in unit_ids(b)] if a["category"] != "instrument" else [(unit_ids(a)[0], unit_ids(b)[0])]
        elif c.get("pattern") == "all-to-all":
            pairs = [(x, y) for x in unit_ids(a) for y in unit_ids(b)]
        else:
            pairs = [(unit_ids(a)[0], unit_ids(b)[0])]
        if a["category"] == "instrument":
            pairs = [(unit_ids(a)[0], y) for _, y in pairs]
        for i, (x, y) in enumerate(pairs):
            hops = [x] + ["%s-%d" % (v, min(i + 1, units(_get(spec, v)))) for v in c.get("via") or [] if _get(spec, v)] + [y]
            for p, q in zip(hops, hops[1:]):
                lines.append(dict(common, **{"from": p, "to": q}))
    for l in lines:
        l.pop("_chain", None)
    for r in rings:
        r.pop("_src", None)
    seen, uniq = set(), []
    for l in lines:
        key = json.dumps(l, sort_keys=True)
        if key not in seen:
            seen.add(key)
            uniq.append(l)
    d["shapes"], d["lines"] = shapes, uniq
    if rings:
        d["rings"] = rings
    for i in issues:
        warnings.insert(0, "ERROR %s: %s" % (i["where"], i["message"]))
    return d, warnings


def _get(spec, eid):
    return next((e for e in spec["equipment"] if e["id"] == eid), None)


# ---- 6.4 revisions --------------------------------------------------------------------------------------------------------------
def snapshot(spec):
    return copy.deepcopy({k: spec[k] for k in ("project", "layers", "equipment", "connections", "notes")})


def changes_since_baseline(spec):
    """What changed since the drawing was last generated: the affected equipment and connections, everything else untouched."""
    base = spec.get("baseline")
    if not base:
        return None
    out = {"project": [], "layers": [], "equipment": {"added": [], "removed": [], "changed": []},
           "connections": {"added": [], "removed": [], "changed": []}, "notes": base["notes"] != spec["notes"]}
    for k, label, _ in PROJECT_FIELDS:
        if base["project"].get(k) != spec["project"].get(k):
            out["project"].append("%s: %s -> %s" % (label, base["project"].get(k) or "TBC", spec["project"].get(k) or "TBC"))
    bl = {l["key"]: l for l in base["layers"]}
    cl = {l["key"]: l for l in spec["layers"]}
    out["layers"] += ["added %s %s" % (k, cl[k]["name"]) for k in cl if k not in bl]
    out["layers"] += ["removed %s %s" % (k, bl[k]["name"]) for k in bl if k not in cl]
    out["layers"] += ["renamed %s: %s -> %s" % (k, bl[k]["name"], cl[k]["name"]) for k in cl if k in bl and bl[k]["name"] != cl[k]["name"]]
    for kind, fields in (("equipment", EDITABLE), ("connections", CONN_FIELDS)):
        b = {x["id"]: x for x in base[kind]}
        c = {x["id"]: x for x in spec[kind]}
        out[kind]["added"] = [i for i in c if i not in b]
        out[kind]["removed"] = [i for i in b if i not in c]
        for i in c:
            if i in b:
                d = ["%s %s -> %s" % (f, _v(b[i].get(f)), _v(c[i].get(f))) for f in fields if (b[i].get(f) or None) != (c[i].get(f) or None)]
                if d:
                    out[kind]["changed"].append({"id": i, "diff": d})
    out["unchanged_equipment"] = len([i for i in {x["id"] for x in spec["equipment"]} if i not in out["equipment"]["added"]
                                      and i not in [x["id"] for x in out["equipment"]["changed"]]])
    return out


def changes_text(spec):
    ch = changes_since_baseline(spec)
    if ch is None:
        return "No drawing has been generated from this specification yet.\n"
    name = {e["id"]: e["name"] for e in spec["baseline"]["equipment"] + spec["equipment"]}
    for c in spec["baseline"]["connections"] + spec["connections"]:
        name[c["id"]] = "%s -> %s" % (name.get(c["source"], c["source"]), name.get(c["destination"], c["destination"]))
    lines = ["Changes since the last generated drawing (%s):" % (spec["baseline_revision"] or "R?")]
    for p in ch["project"]:
        lines.append("- project: " + p)
    for l in ch["layers"]:
        lines.append("- layer " + l)
    for kind in ("equipment", "connections"):
        for i in ch[kind]["added"]:
            lines.append("- %s added: %s %s" % (kind, i, name.get(i, "")))
        for i in ch[kind]["removed"]:
            lines.append("- %s removed: %s %s" % (kind, i, name.get(i, "")))
        for c in ch[kind]["changed"]:
            lines.append("- %s changed: %s %s: %s" % (kind, c["id"], name.get(c["id"], ""), "; ".join(c["diff"])))
    if ch["notes"]:
        lines.append("- notes changed")
    if len(lines) == 1:
        lines.append("- nothing")
    lines.append("Unchanged equipment kept as is: %d record(s), same ids." % ch["unchanged_equipment"])
    return "\n".join(lines) + "\n"


def revise(spec, revision=None, note=None):
    if revision:
        set_project(spec, revision=revision)
    spec["stage"] = "modify"
    log(spec, "revise", "%s%s" % (revision or spec["project"].get("revision") or "", " - " + note if note else ""))


# ---- command line -------------------------------------------------------------------------------------------------------------------
def _print_questions(qs, as_json):
    if as_json:
        print(json.dumps(qs, indent=1, ensure_ascii=False))
        return
    if not qs:
        print("No open connectivity questions.")
        return
    for q in qs:
        print("[%s] (step %d%s) %s" % (q["key"], q["step"], ", choose any" if q["multi"] else "", q["prompt"]))
        if q.get("why"):
            print("    because: %s" % q["why"])
        for c in q["choices"]:
            print("    %-16s %s" % (c["value"], c["label"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init")
    s.add_argument("spec")
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("project")
    s.add_argument("spec")
    for k, _, _ in PROJECT_FIELDS:
        s.add_argument("--" + k.replace("_", "-"), dest=k)
    sub.add_parser("catalog")
    s = sub.add_parser("layers")
    s.add_argument("spec")
    s.add_argument("--select", nargs="+", required=True)
    s.add_argument("--rename", action="append", default=[], help='KEY="New name"')
    s.add_argument("--custom", action="append", default=[], help='"LEVEL|Name|Description"')
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("add-equipment")
    s.add_argument("spec")
    s.add_argument("--layer", required=True)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--text")
    g.add_argument("--file")
    s = sub.add_parser("edit-equipment")
    s.add_argument("spec")
    s.add_argument("id")
    for k in EDITABLE:
        s.add_argument("--" + k)
    s = sub.add_parser("remove-equipment")
    s.add_argument("spec")
    s.add_argument("id")
    s = sub.add_parser("questions")
    s.add_argument("spec")
    s.add_argument("--json", action="store_true")
    s.add_argument("--next", action="store_true", help="only the next question")
    s = sub.add_parser("answer")
    s.add_argument("spec")
    s.add_argument("key")
    s.add_argument("value")
    s.add_argument("--text")
    s = sub.add_parser("unanswer")
    s.add_argument("spec")
    s.add_argument("key")
    s = sub.add_parser("connect")
    s.add_argument("spec")
    s.add_argument("--from", dest="source", required=True)
    s.add_argument("--to", dest="destination", required=True)
    for k in ("protocol", "medium", "topology", "redundancy", "paths", "direction", "scope", "label", "pattern", "relation"):
        s.add_argument("--" + k)
    s.add_argument("--via", default="")
    s.add_argument("--nodes", default="")
    s = sub.add_parser("edit-connection")
    s.add_argument("spec")
    s.add_argument("id")
    for k in ("protocol", "medium", "topology", "redundancy", "paths", "direction", "scope", "label", "pattern", "via", "nodes"):
        s.add_argument("--" + k)
    s.add_argument("--from", dest="source")
    s.add_argument("--to", dest="destination")
    s = sub.add_parser("remove-connection")
    s.add_argument("spec")
    s.add_argument("id")
    s = sub.add_parser("note")
    s.add_argument("spec")
    s.add_argument("text", nargs="?")
    s.add_argument("--remove", type=int)
    s = sub.add_parser("image")
    s.add_argument("spec")
    s.add_argument("id")
    for k in ("image", "image_source", "oem", "model"):
        s.add_argument("--" + k.replace("_", "-"), dest=k)
    s = sub.add_parser("stage")
    s.add_argument("spec")
    s.add_argument("name", choices=["project", "layers", "equipment", "connectivity", "review", "generated", "modify"])
    s = sub.add_parser("revise")
    s.add_argument("spec")
    s.add_argument("--revision")
    s.add_argument("--note")
    for name in ("validate", "review", "show", "history", "changes"):
        s = sub.add_parser(name)
        s.add_argument("spec")
        s.add_argument("--json", action="store_true")
    s = sub.add_parser("request")
    s.add_argument("spec")
    s.add_argument("--out", required=True)
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("parse-request")
    s.add_argument("spec")
    s.add_argument("request")
    s.add_argument("--apply", action="store_true")
    s = sub.add_parser("to-diagram")
    s.add_argument("spec")
    s.add_argument("--out", required=True)
    s.add_argument("--allow-errors", action="store_true")
    a = ap.parse_args(argv)
    try:
        return run(a)
    except SpecError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2


def run(a):
    if a.cmd == "catalog":
        for k, bid, lv, name in STANDARD_LAYERS:
            print("%-5s %-10s %s" % (k, level_label(lv), name))
        return 0
    if a.cmd == "init":
        if os.path.exists(a.spec) and not a.force:
            raise SpecError("%s exists; use it, or --force to start again" % a.spec)
        save(new_spec(), a.spec)
        print("created %s" % a.spec)
        return 0
    spec = load(a.spec)
    out = None
    if a.cmd == "project":
        out = set_project(spec, **{k: getattr(a, k) for k, _, _ in PROJECT_FIELDS})
        spec["stage"] = "layers" if spec["stage"] == "project" else spec["stage"]
        print("\n".join(project_lines(spec)))
    elif a.cmd == "layers":
        ren = {}
        for r in a.rename:
            k, _, v = r.partition("=")
            ren[k.strip().upper()] = v.strip().strip('"')
        cus = []
        for c in a.custom:
            bits = [b.strip() for b in c.split("|")] + ["", ""]
            cus.append((bits[0], bits[1], bits[2]))
        for l in sorted(select_layers(spec, a.select, ren, cus, a.force), key=lambda l: -l["level"]):
            print("%-5s %-10s %s" % (l["key"], level_label(l["level"]), l["name"]))
    elif a.cmd == "add-equipment":
        text = a.text if a.text is not None else open(a.file, encoding="utf-8").read()
        added, dupes = add_equipment(spec, a.layer, text)
        for e in added:
            print(equipment_line(e) + ("  [%s]" % "; ".join(e["flags"]) if e["flags"] else ""))
        for line, eid in dupes:
            print("already recorded as %s (not added again): %s" % (eid, line))
    elif a.cmd == "edit-equipment":
        print("\n".join(edit_equipment(spec, a.id, **{k: getattr(a, k) for k in EDITABLE})) or "no change")
        materialize(spec)
    elif a.cmd == "remove-equipment":
        print("removed %s; connections removed: %s" % (a.id, ", ".join(remove_equipment(spec, a.id)) or "none"))
        materialize(spec)
    elif a.cmd == "questions":
        qs = questions(spec)
        _print_questions(qs[:1] if a.next else qs, a.json)
        return 0
    elif a.cmd == "answer":
        answer(spec, a.key, a.value, a.text)
        print("recorded %s = %s" % (a.key, a.value))
        qs = questions(spec)
        print("open questions: %d%s" % (len(qs), " (next: %s)" % qs[0]["key"] if qs else ""))
    elif a.cmd == "unanswer":
        unanswer(spec, a.key)
        print("cleared %s" % a.key)
    elif a.cmd == "connect":
        c = connect(spec, source=a.source, destination=a.destination, protocol=a.protocol, medium=a.medium, topology=a.topology,
                    redundancy=a.redundancy, paths=a.paths, direction=a.direction, scope=a.scope, label=a.label, pattern=a.pattern,
                    relation=a.relation, via=[v.strip() for v in a.via.split(",") if v.strip()],
                    nodes=[v.strip() for v in a.nodes.split(",") if v.strip()] or None)
        print(connection_line(spec, c))
        for i in validate(spec):
            if i["where"] == c["id"] and i["severity"] in ("error", "warning"):
                print("%s: %s" % (i["severity"].upper(), i["message"]))
    elif a.cmd == "edit-connection":
        print("\n".join(edit_connection(spec, a.id, **{k: getattr(a, k) for k in CONN_FIELDS if hasattr(a, k)})) or "no change")
    elif a.cmd == "remove-connection":
        remove_connection(spec, a.id)
        print("removed %s" % a.id)
    elif a.cmd == "note":
        if a.remove is not None:
            spec["notes"].pop(a.remove - 1)
        elif a.text:
            spec["notes"].append(a.text)
        print("\n".join("%d. %s" % (i + 1, n) for i, n in enumerate(spec["notes"])) or "no notes")
        log(spec, "note", "notes now %d" % len(spec["notes"]))
    elif a.cmd == "image":
        eq(spec, a.id)
        spec.setdefault("images", {})[a.id] = {k: getattr(a, k) for k in ("image", "image_source", "oem", "model") if getattr(a, k)}
        log(spec, "image", a.id)
    elif a.cmd == "stage":
        spec["stage"] = a.name
        log(spec, "stage", a.name)
        print("stage: %s" % a.name)
    elif a.cmd == "validate":
        issues = validate(spec)
        if a.json:
            print(json.dumps(issues, indent=1, ensure_ascii=False))
        else:
            for i in issues:
                print("%-8s %-24s %s" % (i["severity"].upper(), i["where"], i["message"]))
            print("%d error(s), %d question(s), %d warning(s)" % tuple(sum(i["severity"] == s for i in issues) for s in ("error", "question", "warning")))
        return 1 if any(i["severity"] == "error" for i in issues) else 0
    elif a.cmd == "review":
        sys.stdout.write(review_text(spec))
        return 0
    elif a.cmd == "show":
        print(json.dumps(spec, indent=1, ensure_ascii=False))
        return 0
    elif a.cmd == "changes":
        sys.stdout.write(changes_text(spec))
        return 0
    elif a.cmd == "revise":
        revise(spec, a.revision, a.note)
        print("revision %s; edit the specification, then run to-diagram and rebuild" % (spec["project"].get("revision") or "TBC"))
    elif a.cmd == "history":
        for h in spec.get("history", []):
            print("%s  %-18s %s" % (h["at"], h["action"], h["detail"]))
        return 0
    elif a.cmd == "request":
        prev = spec.get("request", {}).get("sha")
        if os.path.exists(a.out) and not a.force:
            with open(a.out, encoding="utf-8") as fh:
                cur = hashlib.sha1(fh.read().encode()).hexdigest()
            if prev and cur != prev:
                raise SpecError("%s has edits that are not in the specification yet. Run parse-request first (or --force to discard them)." % a.out)
        text = request_text(spec)
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        spec.setdefault("request", {})["sha"] = hashlib.sha1(text.encode()).hexdigest()
        print("wrote %s" % a.out)
    elif a.cmd == "parse-request":
        with open(a.request, encoding="utf-8") as fh:
            text = fh.read()
        changes = parse_request(spec, text)
        for c in changes:
            print("- " + describe_change(c))
        if not changes:
            print("no differences")
        if not a.apply:
            return 0
        apply_changes(spec, changes)
        new = request_text(spec)
        with open(a.request, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new)
        spec.setdefault("request", {})["sha"] = hashlib.sha1(new.encode()).hexdigest()
        print("applied %d change(s); %s rewritten from the specification" % (len(changes), a.request))
    elif a.cmd == "to-diagram":
        d, warnings = to_diagram(spec)
        errs = [w for w in warnings if w.startswith("ERROR")]
        for w in warnings:
            print(("" if w.startswith("ERROR") else "warning: ") + w)
        if errs and not a.allow_errors:
            raise SpecError("correct the specification errors above first (they are flagged, not silently replaced)")
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, indent=1, ensure_ascii=False)
        if spec.get("baseline"):
            sys.stdout.write(changes_text(spec))
        spec.setdefault("revisions", []).append({"revision": spec["project"].get("revision") or "R0", "at": now(),
                                                 "changes": changes_since_baseline(spec)})
        spec["baseline"] = snapshot(spec)
        spec["baseline_revision"] = spec["project"].get("revision") or "R0"
        spec["stage"] = "generated"
        log(spec, "to-diagram", a.out)
        print("wrote %s (%d shapes, %d lines)" % (a.out, len(d["shapes"]), len(d["lines"])))
    save(spec, a.spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())

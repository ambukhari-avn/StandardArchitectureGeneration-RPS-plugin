"""Acceptance scenarios A-D (Phase 11), run through the real questionnaire. Used by tests/test_acceptance.py and to regenerate the
examples in samples/examples/ (questionnaire transcript, review, editable request, specification, diagram.json, Visio and preview).

    python scripts/examples.py [out_folder]          (default samples/examples; the preview needs Pillow)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import arch_spec as A  # noqa: E402

PROJECT = dict(client="ACME Contracting", end_user="City Water Authority", project="Water Treatment Plant Upgrade",
               doc_name="PLC & SCADA System Architecture", prepared_by="AMB", checked_by="", approved_by="",
               revision="R0")


class Run:
    """Drives the questionnaire like the AI would and records a readable transcript."""

    def __init__(self, title):
        self.spec = A.new_spec()
        self.log = ["# Example questionnaire — %s" % title, ""]

    def say(self, who, text):
        self.log.append("**%s:** %s" % (who, text))
        self.log.append("")

    def project(self, **kw):
        self.say("Claude", "Step 1 — Project details: Client / Contractor, End User, Project, Document Title, Prepared By, Checked By, "
                           "Approved By, Drawing Revision? (leave any blank for TBC)")
        A.set_project(self.spec, **kw)
        self.say("User", "; ".join("%s: %s" % (l, kw.get(k) or "(blank)") for k, l, _ in A.PROJECT_FIELDS if k in kw))

    def layers(self, keys, renames=None):
        self.say("Claude", "Step 2 — Which Purdue layers does this architecture need? " +
                 ", ".join("%s %s" % (A.level_label(lv), n) for _, _, lv, n in A.STANDARD_LAYERS) + " (rename or add custom layers if needed)")
        A.select_layers(self.spec, keys, renames)
        self.say("User", ", ".join(keys) + "".join('; rename %s to "%s"' % kv for kv in (renames or {}).items()))

    def equipment(self, key, text):
        lay = A.layer(self.spec, key)
        self.say("Claude", "Step 3 — What equipment and quantities are required in %s — %s?" % (A.level_label(lay["level"]), lay["name"]))
        self.say("User", "\n\n    " + text.replace("\n", "\n    "))
        added, _ = A.add_equipment(self.spec, key, text)
        self.say("Claude", "Recorded: " + "; ".join("%s %s ×%s" % (e["id"], e["name"], e["quantity"] or "TBC") for e in added))

    def answer(self, key, value, text=None):
        q = next((q for q in A.questions(self.spec) if q["key"] == key), None)
        if q is None:
            raise A.SpecError("question %s is not open (open: %s)" % (key, [x["key"] for x in A.questions(self.spec)]))
        choices = {c["value"]: c["label"] for c in q["choices"]}
        self.say("Claude", "Step 4 — %s  \n  " % q["prompt"] + "  \n  ".join("( ) " + c["label"] for c in q["choices"]))
        A.answer(self.spec, key, value, text)
        self.say("User", ", ".join(choices.get(v, v) for v in value.split(",")))

    def picture(self, eid, name):
        """Offline examples only: a bundled picture stands in for the web-first image the AI would source."""
        self.spec.setdefault("images", {})[eid] = {"fixture": name}

    def finish(self):
        assert not A.questions(self.spec), [q["key"] for q in A.questions(self.spec)]
        self.say("Claude", "Step 5 — review (below). Anything to change before I generate the drawing?")
        self.say("User", "Generate it.")
        return self


INSTRUMENTS = "Pressure Transmitters — 12\nTemperature Transmitters — 8\nFlow Transmitters — 6"


def case_a():
    """Test A: simple PLC (PT, TT, FT, one PLC, one I/O rack, one Ethernet switch, one HMI)."""
    r = Run("Test A: simple PLC architecture")
    r.project(**PROJECT)
    r.layers(["L0", "L1"], {"L1": "Control System"})
    r.equipment("L0", INSTRUMENTS.replace("— 12", "— 4").replace("— 8", "— 3").replace("— 6", "— 2"))
    r.equipment("L1", "PLC — 1\nRemote I/O Rack — 1\nIndustrial Ethernet Switch — 1\nHMI Panel — 1")
    r.picture("EQ-001", "pressure_transmitter.png")
    r.picture("EQ-003", "flow_transmitter.png")
    r.answer("instrument_to_control", "hardwired")
    r.answer("io_protocol", "profinet")
    r.answer("io_topology", "star")
    r.answer("io_medium", "copper")
    r.answer("io_star_hub", "EQ-006")
    r.answer("plc_switch:EQ-004", "single_to_one")
    r.answer("plc_switch_medium", "copper")
    r.answer("link:EQ-007:1:target", "EQ-006")
    r.answer("link:EQ-007:1:protocol", "PROFINET")
    r.answer("link:EQ-007:1:medium", "copper")
    return r.finish()


def case_b():
    """Test B: redundant PLC (2 redundant CPUs, 4 RIO, 2 switches, 2 SCADA servers, 1 OWS, field instruments)."""
    r = Run("Test B: redundant PLC architecture")
    r.project(**PROJECT)
    r.layers(["L0", "L1", "L2"], {"L1": "Control System"})
    r.equipment("L0", INSTRUMENTS)
    r.equipment("L1", "Redundant PLC CPUs (hot standby) — 2\nRemote I/O Racks — 4\nIndustrial Ethernet Switches — 2")
    r.equipment("L2", "SCADA Servers — 2 (redundant)\nOperator Workstation — 1")
    r.picture("EQ-001", "pressure_transmitter.png")
    r.picture("EQ-003", "flow_transmitter.png")
    r.answer("instrument_to_control", "hardwired")
    r.answer("io_protocol", "profinet")
    r.answer("io_topology", "dual")
    r.answer("io_medium", "copper")
    r.answer("io_display", "representative")
    r.answer("plc_sync:EQ-004", "dedicated")
    r.answer("plc_sync_paths:EQ-004", "2")
    r.answer("plc_sync_medium:EQ-004", "fibre")
    r.answer("plc_switch:EQ-004", "each_dedicated")
    r.answer("plc_switch_medium", "copper")
    r.answer("control_scada", "dual")
    r.answer("control_scada_medium", "copper")
    r.answer("fibre_topology", "p2p")
    r.answer("link:EQ-008:1:target", "EQ-006")
    r.answer("link:EQ-008:1:protocol", "Ethernet (TCP/IP)")
    r.answer("link:EQ-008:1:medium", "copper")
    return r.finish()


def case_c():
    """Test C: with a DMZ (control, SCADA, DMZ equipment, enterprise systems, firewall only as requested)."""
    r = Run("Test C: architecture with a DMZ")
    r.project(**dict(PROJECT, doc_name="OT Network Architecture with DMZ"))
    r.layers(["L1", "L2", "L3.5", "L4"])
    r.equipment("L1", "PLC — 1\nIndustrial Ethernet Switch — 1")
    r.equipment("L2", "SCADA Servers — 2 (redundant)\nSCADA Switch — 1")
    r.equipment("L3.5", "Firewall — 1 (Fortinet FortiGate 100F)\nHistorian Replica Server — 1")
    r.equipment("L4", "ERP Server — 1\nCorporate Switch — 1")
    r.answer("plc_switch:EQ-001", "single_to_one")
    r.answer("plc_switch_medium", "copper")
    r.answer("control_scada", "fibre")
    r.answer("scada_lan_medium", "copper")
    r.answer("fibre_topology", "p2p")
    r.answer("firewall_zones:EQ-005", "L2,L4")
    r.answer("firewall_medium:EQ-005", "copper")
    r.answer("link:EQ-006:1:target", "EQ-005")
    r.answer("link:EQ-006:1:protocol", "OPC UA")
    r.answer("link:EQ-006:1:medium", "copper")
    r.answer("link:EQ-007:1:target", "EQ-008")
    r.answer("link:EQ-007:1:protocol", "Ethernet (TCP/IP)")
    r.answer("link:EQ-007:1:medium", "copper")
    return r.finish()


def case_d():
    """Test D: generate B, then 'Add one operator workstation and change the PLC network connection to dual redundant Ethernet.'"""
    r = case_b()
    r.spec["baseline"] = A.snapshot(r.spec)
    r.spec["baseline_revision"] = "R0"
    r.log += ["---", "", "# Revision request", ""]
    r.say("User", "Add one operator workstation and change the PLC network connection to dual redundant Ethernet.")
    A.revise(r.spec, "R1", "client comments")
    A.edit_equipment(r.spec, "EQ-008", quantity="2")
    A.materialize(r.spec)
    A.answer(r.spec, "plc_switch:EQ-004", "redundant_network")
    r.say("Claude", "Revision R1. Changes:\n\n" + A.changes_text(r.spec))
    return r


CASES = {"A_simple_plc": case_a, "B_redundant_plc": case_b, "C_dmz": case_c, "D_revision": case_d}


def write(name, run, folder, build=True, preview=True, previous=None):
    import build_diagram as B
    os.makedirs(folder, exist_ok=True)
    spec = run.spec
    path = lambda ext: os.path.join(folder, "%s%s" % (name, ext))
    with open(path("_questionnaire.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(run.log) + "\n\n" + A.review_text(spec))
    with open(path("_request.md"), "w", encoding="utf-8") as fh:
        fh.write(A.request_text(spec))
    for eid, img in spec.get("images", {}).items():                   # bundled fixtures, relative to the output folder
        if img.get("fixture"):
            img.update(image=os.path.relpath(os.path.join(ROOT, "samples", "pictures", img["fixture"]), folder),
                       image_source="Bundled example picture (stands in for a web-sourced manufacturer image)")
    d, warnings = A.to_diagram(spec)
    if previous is not None:                                           # a revision keeps the presentation choices of the last drawing
        A.merge_previous(d, previous)
    problems = A.verify_diagram(spec, d)                               # the drawing must show exactly the confirmed specification
    if problems:
        raise A.SpecError("diagram does not match the specification: " + "; ".join(problems))
    spec["baseline"] = A.snapshot(spec)
    A.save(spec, path("_architecture_spec.json"))
    with open(path("_diagram.json"), "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1, ensure_ascii=False)
    if not build:
        return None
    r = B.build(d, os.path.join(ROOT, "base", "base.vsdx"), path(".vsdx"), spec_dir=folder)
    if preview:
        import dev_preview
        dev_preview.render(r["page"], path("_preview.png"))
    r["diagram"] = d
    return r


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "samples", "examples")
    built = {}
    for name, fn in CASES.items():
        r = write(name, fn(), out, previous=built["B_redundant_plc"]["diagram"] if name == "D_revision" else None)
        built[name] = r
        print("%s: built, %d shapes, %d lines, qa: %s" % (name, r["shapes"], r["lines"], "; ".join(r["qa"]) or "no defects"))

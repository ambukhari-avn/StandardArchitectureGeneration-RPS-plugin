"""Offline instrument picture library (v1.7.2): draws front-facing illustrations of common field instruments and ISA-5.1 tag
balloons as transparent PNGs in data/instruments/, and writes data/instrument_pictures.json (ids, files, SHA-256).

These are offline fallbacks only: the web-first image policy is unchanged (real manufacturer pictures come first). An instrument with
no picture at all is drawn as its ISA-5.1 balloon (PT, TT, ...) and never as an unrelated generic equipment icon.

    python scripts/instrument_art.py          (maintainers; needs Pillow. The builder itself does not.)
"""
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "data", "instruments")
S = 4                      # supersampling
W = H = 600 * S            # drawn at 2400 px, saved at 600 px

STEEL, STEEL_D, STEEL_L = (196, 202, 210), (96, 104, 114), (232, 236, 240)
BLUE, BLUE_D = (31, 95, 168), (18, 58, 104)
DISPLAY, DIGITS = (30, 42, 51), (124, 252, 154)
YELLOW, YELLOW_D = (240, 196, 40), (150, 112, 10)
RED = (200, 40, 40)
BLACK = (40, 40, 44)
OUTLINE = (70, 76, 86)
LW = 7 * S // 2


def font(size):
    for f in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def vgrad(d, box, c0, c1, horizontal=True):
    """Cylinder-like shading: light in the middle, darker at the edges."""
    x0, y0, x1, y1 = [int(v) for v in box]
    n = (x1 - x0) if horizontal else (y1 - y0)
    for i in range(max(1, n)):
        t = abs(i / max(1, n - 1) - .4) / .6
        c = tuple(int(c0[k] + (c1[k] - c0[k]) * min(1, t)) for k in range(3))
        if horizontal:
            d.line([(x0 + i, y0), (x0 + i, y1)], fill=c)
        else:
            d.line([(x0, y0 + i), (x1, y0 + i)], fill=c)


def box(d, b, fill=STEEL, edge=STEEL_D, r=40, shade=True, horizontal=True):
    x0, y0, x1, y1 = b
    if shade:
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle(b, r, fill=255)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        vgrad(ImageDraw.Draw(layer), b, STEEL_L if fill == STEEL else tuple(min(255, c + 45) for c in fill), edge if fill == STEEL else
              tuple(max(0, c - 55) for c in fill), horizontal)
        d._image.paste(layer, (0, 0), mask)
    else:
        d.rounded_rectangle(b, r, fill=fill)
    d.rounded_rectangle(b, r, outline=OUTLINE, width=LW)


def disc(d, c, rad, fill=STEEL):
    x, y = c
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse([x - rad, y - rad, x + rad, y + rad], fill=255)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vgrad(ImageDraw.Draw(layer), [x - rad, y - rad, x + rad, y + rad], tuple(min(255, k + 40) for k in fill),
          tuple(max(0, k - 70) for k in fill))
    d._image.paste(layer, (0, 0), mask)
    d.ellipse([x - rad, y - rad, x + rad, y + rad], outline=OUTLINE, width=LW)


def display(d, b, text="12.5"):
    d.rounded_rectangle(b, 18, fill=DISPLAY, outline=BLACK, width=LW // 2)
    x0, y0, x1, y1 = b
    f = font(int((y1 - y0) * .55))
    tw = d.textlength(text, font=f)
    d.text(((x0 + x1 - tw) / 2, y0 + (y1 - y0) * .18), text, fill=DIGITS, font=f)


def head(d, cx, cy, r, text="12.5", glands=True):
    """Dual-compartment transmitter head seen from the front: round housing with a display window."""
    if glands:
        for sx in (-1, 1):
            box(d, [cx + sx * r * .95 - r * .28, cy - r * .16, cx + sx * r * .95 + r * .28, cy + r * .16], r=12, horizontal=False)
    disc(d, (cx, cy), r)
    disc(d, (cx, cy), int(r * .78), fill=(214, 219, 226))
    display(d, [cx - r * .5, cy - r * .3, cx + r * .5, cy + r * .3], text)


def pipe(d, y, h, x0=170, x1=W - 170):
    box(d, [x0, y - h / 2, x1, y + h / 2], r=10, horizontal=False)


def flange(d, x, y, h, w=110):
    box(d, [x - w / 2, y - h / 2, x + w / 2, y + h / 2], r=14, horizontal=True)
    for k in (-.36, 0, .36):
        d.ellipse([x - 16, y + k * h - 16, x + 16, y + k * h + 16], fill=STEEL_D)


def nut(d, cx, y0, w, h):
    d.polygon([(cx - w / 2, y0), (cx + w / 2, y0), (cx + w / 2 + 30, y0 + h / 2), (cx + w / 2, y0 + h), (cx - w / 2, y0 + h),
               (cx - w / 2 - 30, y0 + h / 2)], fill=STEEL, outline=OUTLINE)
    d.line([(cx - w / 4, y0), (cx - w / 4, y0 + h)], fill=STEEL_D, width=LW // 2)
    d.line([(cx + w / 4, y0), (cx + w / 4, y0 + h)], fill=STEEL_D, width=LW // 2)


# ---- instruments -------------------------------------------------------------------------------------------------------------------
def pressure_transmitter(d):
    head(d, W / 2, 760, 470, "4.20")
    box(d, [W / 2 - 150, 1180, W / 2 + 150, 1450], r=20)
    box(d, [W / 2 - 330, 1420, W / 2 + 330, 1820], r=50)
    d.text((W / 2 - 150, 1540), "PT", fill=BLUE_D, font=font(170))
    nut(d, W / 2, 1830, 260, 200)
    box(d, [W / 2 - 70, 2030, W / 2 + 70, 2300], r=10)


def dp_transmitter(d):
    head(d, W / 2, 640, 420, "0.82")
    box(d, [W / 2 - 130, 1030, W / 2 + 130, 1220], r=20)
    box(d, [W / 2 - 420, 1200, W / 2 + 420, 1600], r=50)
    box(d, [W / 2 - 560, 1640, W / 2 + 560, 1900], fill=BLUE, r=30)          # 3-valve manifold
    for x in (W / 2 - 360, W / 2, W / 2 + 360):
        box(d, [x - 40, 1900, x + 40, 2080], r=10)
        box(d, [x - 140, 2060, x + 140, 2130], fill=BLACK, r=20, shade=False)
    for x in (W / 2 - 300, W / 2 + 300):
        box(d, [x - 55, 2130, x + 55, 2350], r=10)


def temperature_transmitter(d):
    head(d, W / 2, 700, 430, "85.6")
    box(d, [W / 2 - 110, 1100, W / 2 + 110, 1300], r=14)
    nut(d, W / 2, 1300, 300, 190)
    box(d, [W / 2 - 75, 1490, W / 2 + 75, 2330], r=30)                      # thermowell
    d.text((W / 2 - 115, 1610), "T", fill=BLUE_D, font=font(220))


def electromagnetic_flowmeter(d):
    head(d, W / 2, 560, 360, "152")
    box(d, [W / 2 - 110, 900, W / 2 + 110, 1080], r=14)
    pipe(d, 1600, 520, 250, W - 250)
    flange(d, 330, 1600, 900)
    flange(d, W - 330, 1600, 900)
    box(d, [W / 2 - 560, 1080, W / 2 + 560, 2120], fill=BLUE, r=120)
    d.text((W / 2 - 160, 1460), "FT", fill=(235, 242, 250), font=font(260))


def coriolis_flowmeter(d):
    pipe(d, 1900, 360, 200, W - 200)
    flange(d, 300, 1900, 700)
    flange(d, W - 300, 1900, 700)
    d.rounded_rectangle([W / 2 - 700, 900, W / 2 + 700, 1780], 300, fill=STEEL_L, outline=OUTLINE, width=LW)
    box(d, [W / 2 - 700, 900, W / 2 + 700, 1780], r=300)
    head(d, W / 2, 520, 330, "98.1")
    box(d, [W / 2 - 100, 830, W / 2 + 100, 930], r=10)


def vortex_flowmeter(d):
    head(d, W / 2, 600, 400, "64.3")
    box(d, [W / 2 - 100, 980, W / 2 + 100, 1380], r=14)
    pipe(d, 1780, 560, 300, W - 300)
    flange(d, 420, 1780, 960)
    flange(d, W - 420, 1780, 960)
    box(d, [W / 2 - 380, 1380, W / 2 + 380, 2180], r=60)


def clamp_on_flowmeter(d):
    pipe(d, 1750, 380, 120, W - 120)
    for x in (W / 2 - 500, W / 2 + 300):
        box(d, [x - 110, 1480, x + 300, 1560], fill=BLUE, r=18)
        box(d, [x - 140, 1540, x + 330, 1960], fill=BLACK, r=20, shade=False)
    box(d, [W / 2 - 520, 300, W / 2 + 520, 1100], r=50)
    display(d, [W / 2 - 360, 420, W / 2 + 360, 760], "12.0")
    for k in range(4):
        d.ellipse([W / 2 - 330 + k * 200, 850, W / 2 - 230 + k * 200, 950], fill=BLUE)
    d.line([(W / 2 - 300, 1100), (W / 2 - 300, 1480)], fill=BLACK, width=26)
    d.line([(W / 2 + 400, 1100), (W / 2 + 400, 1480)], fill=BLACK, width=26)


def radar_level(d):
    head(d, W / 2, 620, 420, "3.42")
    box(d, [W / 2 - 110, 1010, W / 2 + 110, 1180], r=14)
    box(d, [W / 2 - 560, 1180, W / 2 + 560, 1360], r=20)                     # process flange
    d.polygon([(W / 2 - 230, 1360), (W / 2 + 230, 1360), (W / 2 + 500, 2250), (W / 2 - 500, 2250)], fill=STEEL, outline=OUTLINE)
    vgrad(d, [W / 2 - 220, 1380, W / 2 + 220, 1600], STEEL_L, STEEL_D)
    d.line([(W / 2 - 500, 2250), (W / 2 + 500, 2250)], fill=OUTLINE, width=LW)


def ultrasonic_level(d):
    head(d, W / 2, 640, 430, "2.10")
    box(d, [W / 2 - 110, 1040, W / 2 + 110, 1220], r=14)
    nut(d, W / 2, 1220, 420, 220)
    box(d, [W / 2 - 330, 1440, W / 2 + 330, 2140], fill=BLACK, r=60, shade=False)
    d.ellipse([W / 2 - 260, 2060, W / 2 + 260, 2220], fill=(90, 90, 96), outline=OUTLINE, width=LW)


def submersible_probe(d):
    d.line([(W / 2, 120), (W / 2, 900)], fill=BLACK, width=70)
    box(d, [W / 2 - 170, 880, W / 2 + 170, 2150], r=80)
    box(d, [W / 2 - 170, 2080, W / 2 + 170, 2300], fill=BLACK, r=60, shade=False)
    d.text((W / 2 - 115, 1380), "L", fill=BLUE_D, font=font(220))


def level_switch(d):
    box(d, [W / 2 - 330, 300, W / 2 + 330, 1000], r=80)
    d.ellipse([W / 2 - 90, 560, W / 2 + 90, 740], fill=(60, 200, 90), outline=OUTLINE, width=LW)
    nut(d, W / 2, 1000, 320, 200)
    box(d, [W / 2 - 110, 1200, W / 2 + 110, 1700], r=20)
    for x in (W / 2 - 160, W / 2 + 60):
        box(d, [x, 1680, x + 100, 2350], r=40)


def pressure_switch(d):
    box(d, [W / 2 - 520, 350, W / 2 + 520, 1500], fill=BLUE, r=70)
    box(d, [W / 2 - 360, 520, W / 2 + 360, 1180], r=40)
    d.text((W / 2 - 150, 660), "PS", fill=BLUE_D, font=font(260))
    box(d, [W / 2 + 520, 800, W / 2 + 760, 980], r=20)                      # conduit
    box(d, [W / 2 - 110, 1500, W / 2 + 110, 1780], r=14)
    nut(d, W / 2, 1780, 300, 200)
    box(d, [W / 2 - 70, 1980, W / 2 + 70, 2300], r=10)


def temperature_switch(d):
    box(d, [W / 2 - 520, 300, W / 2 + 520, 1300], fill=BLUE, r=70)
    box(d, [W / 2 - 360, 470, W / 2 + 360, 1050], r=40)
    d.text((W / 2 - 150, 580), "TS", fill=BLUE_D, font=font(260))
    nut(d, W / 2, 1300, 300, 190)
    box(d, [W / 2 - 70, 1490, W / 2 + 70, 2330], r=30)


def flow_switch(d):
    box(d, [W / 2 - 520, 300, W / 2 + 520, 1200], fill=BLUE, r=70)
    box(d, [W / 2 - 360, 450, W / 2 + 360, 980], r=40)
    d.text((W / 2 - 150, 540), "FS", fill=BLUE_D, font=font(260))
    nut(d, W / 2, 1200, 320, 190)
    pipe(d, 1900, 420, 200, W - 200)
    box(d, [W / 2 - 40, 1390, W / 2 + 40, 1950], r=10)
    box(d, [W / 2 - 220, 1880, W / 2 + 220, 1990], r=20)                     # paddle


def analyzer(d, tag="AT", colour=BLUE):
    box(d, [W / 2 - 700, 250, W / 2 + 700, 1650], fill=colour, r=60)
    box(d, [W / 2 - 560, 380, W / 2 + 560, 1100], r=30)
    display(d, [W / 2 - 460, 470, W / 2 + 460, 900], "7.02")
    d.text((W / 2 - 160, 930), tag, fill=BLUE_D, font=font(150))
    for k in range(3):
        d.ellipse([W / 2 - 330 + k * 250, 1250, W / 2 - 190 + k * 250, 1390], fill=STEEL_L, outline=OUTLINE, width=LW)
    for x in (W / 2 - 300, W / 2 + 300):
        d.line([(x, 1650), (x, 2300)], fill=(80, 140, 200), width=60)
    box(d, [W / 2 - 150, 1700, W / 2 + 150, 2300], r=60)                     # sensor


def gas_detector(d, tag="GD"):
    box(d, [W / 2 - 560, 350, W / 2 + 560, 1450], fill=YELLOW, r=90)
    display(d, [W / 2 - 360, 520, W / 2 + 360, 900], "0.0")
    d.text((W / 2 - 150, 1010), tag, fill=(70, 50, 0), font=font(190))
    for x in (W / 2 - 560, W / 2 + 560):
        box(d, [x - 140, 750, x + 140, 930], r=20)
    box(d, [W / 2 - 180, 1450, W / 2 + 180, 1700], r=20)
    box(d, [W / 2 - 260, 1690, W / 2 + 260, 2200], fill=BLACK, r=70, shade=False)
    for k in range(-2, 3):
        d.line([(W / 2 + k * 80, 2020), (W / 2 + k * 80, 2170)], fill=(120, 120, 120), width=24)


def flame_detector(d):
    box(d, [W / 2 - 580, 500, W / 2 + 580, 1900], fill=RED, r=120)
    d.ellipse([W / 2 - 330, 820, W / 2 + 330, 1480], fill=DISPLAY, outline=BLACK, width=LW)
    d.ellipse([W / 2 - 170, 980, W / 2 + 170, 1320], fill=(70, 110, 160))
    box(d, [W / 2 - 160, 1900, W / 2 + 160, 2250], r=20)


def vibration_sensor(d):
    nut(d, W / 2, 1650, 420, 260)
    box(d, [W / 2 - 260, 750, W / 2 + 260, 1660], r=60)
    box(d, [W / 2 - 110, 450, W / 2 + 110, 760], fill=BLACK, r=30, shade=False)
    d.line([(W / 2, 450), (W / 2, 120)], fill=BLACK, width=70)
    d.text((W / 2 - 115, 1030), "V", fill=BLUE_D, font=font(240))


def proximity_sensor(d):
    box(d, [W / 2 - 220, 500, W / 2 + 220, 2100], r=40)
    for y in range(560, 2060, 70):
        d.line([(W / 2 - 220, y), (W / 2 + 220, y + 30)], fill=STEEL_D, width=12)
    nut(d, W / 2, 900, 460, 160)
    nut(d, W / 2, 1650, 460, 160)
    box(d, [W / 2 - 220, 2080, W / 2 + 220, 2250], fill=BLUE, r=30)
    d.line([(W / 2, 500), (W / 2, 120)], fill=BLACK, width=60)


def power_meter(d):
    box(d, [W / 2 - 760, 420, W / 2 + 760, 2050], fill=(70, 74, 80), r=50)
    box(d, [W / 2 - 640, 540, W / 2 + 640, 1500], r=30)
    display(d, [W / 2 - 540, 640, W / 2 + 540, 1150], "415V")
    d.text((W / 2 - 330, 1200), "kWh  PF", fill=BLUE_D, font=font(170))
    for k in range(4):
        box(d, [W / 2 - 560 + k * 300, 1640, W / 2 - 380 + k * 300, 1880], fill=BLUE, r=20)


def mov(d):
    box(d, [W / 2 - 520, 220, W / 2 + 520, 1100], fill=BLUE, r=80)          # electric actuator
    display(d, [W / 2 - 280, 380, W / 2 + 280, 620], "OPEN")
    d.ellipse([W / 2 - 610, 520, W / 2 - 380, 880], fill=RED, outline=OUTLINE, width=LW)    # handwheel side
    box(d, [W / 2 - 150, 1100, W / 2 + 150, 1380], r=20)                     # yoke
    pipe(d, 1850, 520, 150, W - 150)
    flange(d, 250, 1850, 900)
    flange(d, W - 250, 1850, 900)
    box(d, [W / 2 - 460, 1380, W / 2 + 460, 2280], r=200)                   # valve body


def control_valve(d):
    d.chord([W / 2 - 620, 150, W / 2 + 620, 1250], 180, 360, fill=STEEL, outline=OUTLINE, width=LW)
    box(d, [W / 2 - 620, 690, W / 2 + 620, 800], r=20)
    box(d, [W / 2 - 70, 800, W / 2 + 70, 1350], r=10)                       # stem
    box(d, [W / 2 + 120, 950, W / 2 + 520, 1250], fill=BLUE, r=30)          # positioner
    pipe(d, 1850, 500, 150, W - 150)
    flange(d, 250, 1850, 880)
    flange(d, W - 250, 1850, 880)
    d.ellipse([W / 2 - 480, 1350, W / 2 + 480, 2300], fill=STEEL, outline=OUTLINE, width=LW)


def estop(d):
    box(d, [W / 2 - 600, 700, W / 2 + 600, 2250], fill=YELLOW, r=80)
    d.ellipse([W / 2 - 480, 280, W / 2 + 480, 1240], fill=RED, outline=(110, 20, 20), width=LW)
    d.ellipse([W / 2 - 300, 440, W / 2 + 300, 800], fill=(235, 90, 90))
    d.text((W / 2 - 360, 1600), "STOP", fill=(70, 50, 0), font=font(240))


ILLUSTRATIONS = {  # component id -> (drawing, caption used for new ids)
    "pressure_transmitter": (pressure_transmitter, "Pressure transmitter"),
    "pit_pressure_indicating_transmitter": (pressure_transmitter, None),
    "dp_transmitter_3_valve_manifold": (dp_transmitter, "DP transmitter with 3-valve manifold"),
    "dpit_differential_pressure_indicating_transmitter": (dp_transmitter, None),
    "temperature_transmitter_rtd_in_thermowell": (temperature_transmitter, "Temperature transmitter (RTD in thermowell)"),
    "tit_temperature_indicating_transmitter": (temperature_transmitter, None),
    "electromagnetic_flowmeter": (electromagnetic_flowmeter, "Electromagnetic flowmeter"),
    "flowmeters_electromagnetic": (electromagnetic_flowmeter, None),
    "fit_flow_indicating_transmitter": (electromagnetic_flowmeter, None),
    "coriolis_flowmeter": (coriolis_flowmeter, "Coriolis flowmeter"),
    "vortex_flowmeter": (vortex_flowmeter, "Vortex flowmeter"),
    "clamp_on_ultrasonic_flowmeter": (clamp_on_flowmeter, "Clamp-on ultrasonic flowmeter"),
    "radar_level_transmitter": (radar_level, "Radar level transmitter"),
    "lt_level_transmitter": (radar_level, None),
    "ultrasonic_level_transmitter": (ultrasonic_level, "Ultrasonic level transmitter"),
    "submersible_level_probe": (submersible_probe, "Submersible level probe"),
    "level_switch": (level_switch, "Level switch"),
    "ls_level_switch": (level_switch, None),
    "ps_pressure_switch": (pressure_switch, "Pressure switch"),
    "ts_temperature_switch": (temperature_switch, "Temperature switch"),
    "fs_flow_switch": (flow_switch, "Flow switch"),
    "ph_orp_sensor_transmitter": (lambda d: analyzer(d, "pH"), "pH / ORP sensor and transmitter"),
    "chlorine_analyzer_sensor": (lambda d: analyzer(d, "Cl2"), "Chlorine analyzer"),
    "chlorine_analyzer_analyzer_l0": (lambda d: analyzer(d, "Cl2"), None),
    "turbidity_meter": (lambda d: analyzer(d, "NTU"), "Turbidity meter"),
    "turbidity_analyzer": (lambda d: analyzer(d, "NTU"), None),
    "h2s_analyzer": (lambda d: gas_detector(d, "H2S"), "H2S analyzer"),
    "gas_detector": (gas_detector, "Gas detector"),
    "flame_detector": (flame_detector, "Flame detector"),
    "vibration_sensor": (vibration_sensor, "Vibration sensor"),
    "proximity_sensor": (proximity_sensor, "Proximity sensor"),
    "power_meter": (power_meter, "Power meter"),
    "mov_motor_operated_valve": (mov, "Motor operated valve"),
    "control_valve": (control_valve, "Control valve"),
    "analyzer": (analyzer, "Analyzer"),
}
BALLOON_TAGS = ["PT", "PIT", "PS", "DPT", "TT", "TIT", "TE", "TS", "FT", "FIT", "FE", "FS", "LT", "LIT", "LS", "AT", "AIT", "XV", "MOV",
                "FCV", "PCV", "LCV", "TCV", "HV", "GD", "FD", "VT", "ZS", "JT", "IT", "ST", "HS", "I"]


def balloon(tag):
    """ISA-5.1 field-mounted instrument bubble with its letters: used only when no picture exists at all."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = W * .40
    d.ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=(255, 255, 255, 255), outline=BLACK, width=16 * S // 2)
    f = font(int(r * (.78 if len(tag) <= 2 else .58)))
    tw = d.textlength(tag, font=f)
    bb = d.textbbox((0, 0), tag, font=f)
    d.text(((W - tw) / 2, (H - (bb[3] - bb[1])) / 2 - bb[1]), tag, fill=BLACK, font=f)
    return img


def render(fn):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fn(d)
    return img


def save(img, name):
    img = img.resize((W // S, H // S), Image.LANCZOS)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    path = os.path.join(OUT, name)
    img.save(path, optimize=True)
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    os.makedirs(OUT, exist_ok=True)
    entries, done = [], {}
    for cid, (fn, caption) in ILLUSTRATIONS.items():
        key = getattr(fn, "__name__", "") + (caption or "")
        name = cid + ".png"
        sha = save(render(fn), name)
        entries.append({"id": cid, "label": caption, "picture": "instruments/" + name, "sha256": sha, "illustration": True})
    balloons = []
    for tag in BALLOON_TAGS:
        name = "isa_%s.png" % tag.lower()
        balloons.append({"tag": tag, "picture": "instruments/" + name, "sha256": save(balloon(tag), name)})
    with open(os.path.join(ROOT, "data", "instrument_pictures.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"_note": "Offline instrument illustrations (v1.7.2), made by scripts/instrument_art.py. Fallbacks only: web-first "
                            "pictures come first. 'balloons' are ISA-5.1 tag bubbles used when an instrument has no picture at all; "
                            "an instrument is never drawn with the generic equipment icon.",
                   "components": entries, "balloons": balloons}, fh, indent=1)
        fh.write("\n")
    print("wrote %d illustrations and %d balloons to %s" % (len(entries), len(balloons), OUT))


if __name__ == "__main__":
    sys.exit(main())

"""Crops and side-by-side composites of the app screenshots for the report and slides (run after tools.trace_shots).
Run: python report/make_crops.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = Path(__file__).parent / "shots"
GREEN = (3, 82, 45)


def crop(name, box):
    return Image.open(S / f"{name}.png").convert("RGB").crop(box)


def side(parts, out, gap=24, labels=None):
    h = max(p.height for p in parts)
    w = sum(p.width for p in parts) + gap * (len(parts) - 1)
    top = 54 if labels else 0
    im = Image.new("RGB", (w, h + top), "white")
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 24)
    x = 0
    for i, p in enumerate(parts):
        im.paste(p, (x, top))
        if labels:
            d.text((x + 4, 8), labels[i], font=f, fill=GREEN)
        x += p.width + gap
    im.save(S / out)
    print(out, im.size)


# traced run 1: the patient's conversation, the approval card, and the agent/tool log
side([crop("trace1_whatsapp", (845, 185, 1330, 1000)), crop("trace1_whatsapp", (1370, 480, 1690, 1010))],
     "trace1_combo.png", labels=["What the patient sees", "Agent log, newest first"])
# traced run 2: the Health Advisor's reply and the agent/tool log
side([crop("trace2_health", (580, 240, 1250, 780)), crop("trace2_health", (1370, 480, 1690, 1010))],
     "trace2_combo.png", labels=["What the therapist sees", "Agent log, newest first"])
# the app's own token and cost meters
crop("trace_costs", (565, 100, 1345, 1020)).save(S / "costs_tokens.png")
# the user test: the therapist's own screen during the recorded call (camera thumbnails cropped out)
if (S / "usertest_raw_frame.png").is_file():   # frame from the recorded call; only the cropped version is in the repo
    crop("usertest_raw_frame", (0, 133, 1755, 1066)).save(S / "usertest_approval.png")
print("done")

# the three demos from the user test, replayed (tools.demo_runs + tools.demo_shots)
if (S / "demo1_whatsapp.png").is_file():
    side([crop("demo1_whatsapp", (845, 250, 1330, 860)), crop("demo1_whatsapp", (845, 860, 1330, 1470))],
         "demo1_combo.png", labels=["Valentina's WhatsApp", "(continued)"])
    side([crop("demo2_whatsapp", (845, 185, 1330, 1000)), crop("demo2_health", (580, 240, 1250, 830))],
         "demo2_combo.png", labels=["Javier's WhatsApp", "The Health Advisor, during and after the visit"])
    side([crop("demo3_daily", (565, 100, 1345, 640)), crop("demo3_ops", (580, 980, 1330, 1320))],
         "demo3_combo.png", labels=["Daily report", "\"How did the week go?\""])

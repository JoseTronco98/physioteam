"""Crops of the 2x screenshots (tools/hires_shots.py -> report/shots/hi) for the report and slides: each picture is cut
to its key moment so it stays readable. Coordinates are in 2x pixels.
Run: python report/make_crops.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = Path(__file__).parent / "shots"
HI = S / "hi"
GREEN = (3, 82, 45)


def crop(name, box):
    return Image.open(HI / f"{name}.png").convert("RGB").crop(box)


def side(parts, out, gap=40, labels=None):
    h = max(p.height for p in parts)
    w = sum(p.width for p in parts) + gap * (len(parts) - 1)
    top = 84 if labels else 0
    im = Image.new("RGB", (w, h + top), "white")
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 44)
    x = 0
    for i, p in enumerate(parts):
        im.paste(p, (x, top))
        if labels:
            d.text((x + 6, 14), labels[i], font=f, fill=GREEN)
        x += p.width + gap
    im.save(S / out)
    print(out, im.size)


def save(img, out):
    img.save(S / out)
    print(out, img.size)


# key moments (slides 6-8, report exhibits)
save(crop("t_approvals", (1205, 900, 2245, 1335)), "key_demo1_approval.png")             # Demo 1: the approval card
save(crop("d_health", (1160, 1140, 2500, 1495)), "key_demo2_drafts.png")                 # Demo 2: evaluation and plan drafted
save(crop("d_ops", (1170, 2170, 2500, 2612)), "key_demo3_week.png")                      # Demo 3: the weekly results answer
save(crop("r_wa_tom", (1700, 510, 2650, 1110)), "safety_injection.png")                  # prompt injection blocked
save(crop("r_wa_hector", (1700, 1120, 2640, 1840)), "safety_redflag.png")                # red flag: no advice, therapist answers
save(crop("t_costs", (1164, 1120, 2660, 1880)), "costs_tokens.png")                      # the app's own token meter

# report: the three demos (Exhibits 5-7), the PDFs (Exhibits 8-9)
side([crop("d_wa_valentina", (1690, 500, 2660, 1720)), crop("d_wa_valentina", (1690, 1720, 2660, 2940))],
     "demo1_combo.png", labels=["Valentina's WhatsApp", "(continued)"])
side([crop("d_wa_javier", (1690, 370, 2660, 2000)), crop("d_health", (1160, 480, 2500, 1660))],
     "demo2_combo.png", labels=["Javier's WhatsApp", "The Health Advisor, during and after the visit"])
side([crop("d_daily", (1130, 200, 2690, 1280)), crop("d_ops", (1170, 1975, 2645, 2615))],
     "demo3_combo.png", labels=["Daily report", "\"How did the week go?\""])
save(Image.open(HI / "d_pdf_eval.png").convert("RGB"), "demo2_pdf_eval_p1.png")
save(Image.open(HI / "d_pdf_plan.png").convert("RGB"), "demo2_pdf_plan_p1.png")
print("done")

# slide 6: the key moment of Demos 2 and 3, re-wrapped to a slide column (tools/hires_shots.py BUBBLES)
for n in ("b_demo2_drafts", "b_demo3_week"):
    save(Image.open(HI / f"{n}.png").convert("RGB"), f"{n.replace('b_', 'key_')}.png")

"""Offline Chinese teaching report and quantitative raster figures (Pillow)."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def figure(run, separation, path, vmax):
    image = Image.new("RGB", (1400, 760), "#f4f7fc")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    def font(size):
        return ImageFont.truetype(str(font_path), size) if font_path.exists() else ImageFont.load_default(size=size)
    def text(x, y, s, size=20, color="#15273d"):
        draw.text((x, y), s, fill=color, font=font(size))
    text(55, 25, f"Waveguide Lab | Theoretical directional coupler | centre spacing {separation:g} um", 28)
    text(55, 75, "1 transverse dimension + propagation | assumed index profile | no physical loss model", 20)
    text(90, 133, "Field intensity |psi|^2 [1/um]", 23)
    text(800, 133, "Half-space power / input power", 23)
    a, b, c, d = 90, 190, 690, 610
    mask = abs(run["x_um"]) <= 25
    density = (abs(run["fields"][:, mask]) ** 2).T[::-1]
    t = np.clip(density / vmax, 0, 1)
    stops = np.array([[8, 14, 37], [41, 48, 111], [20, 142, 172], [100, 215, 166], [255, 233, 124]])
    colors = np.stack([np.interp(t, np.linspace(0, 1, len(stops)), stops[:, i]) for i in range(3)], axis=-1)
    heat = Image.fromarray(colors.astype("uint8")).resize((c-a, d-b))
    image.paste(heat, (a, b))
    draw.rectangle((a,b,c,d), outline="#7b8798", width=1)
    zmax = run["z_um"][-1] / 1000
    for j in range(5):
        x = a + (c-a)*j/4
        draw.line((x,d,x,d+5),fill="#45576b")
        text(x-12,d+12,f"{zmax*j/4:.1f}",17)
        y = b + (d-b)*j/4
        text(35,y-12,f"{25-50*j/4:g}",17)
    text(245, 660, "Propagation z [mm]", 20)
    text(80, 160, "Transverse x [um]", 17)
    # shared absolute intensity legend across all separation candidates
    bar = np.linspace(0,1,300)[None,:]
    bar_rgb = np.stack([np.interp(bar,np.linspace(0,1,len(stops)),stops[:,i]) for i in range(3)],axis=-1)
    image.paste(Image.fromarray(bar_rgb.astype("uint8")).resize((300,12)),(300,710))
    text(240,703,"0",16)
    text(610,703,f"{vmax:.3f} 1/um",16)
    a,b,c,d = 800,190,1320,610
    draw.rectangle((a,b,c,d), fill="white", outline="#a4b1c1")
    for j in range(5):
        y=b+(d-b)*j/4
        draw.line((a,y,c,y),fill="#dce3ed")
        text(a-48,y-11,f"{1-j/4:.2f}",17)
        x=a+(c-a)*j/4
        text(x-12,d+12,f"{zmax*j/4:.1f}",17)
    for key,color in [("left_power","#2563eb"),("right_power","#e55c2a")]:
        pts=[(a+(c-a)*z/run["z_um"][-1],d-(d-b)*p) for z,p in zip(run["z_um"],run[key])]
        draw.line(pts,fill=color,width=4)
    text(845,660,"Propagation z [mm]",20)
    text(800,710,"Left half-space",18,"#2563eb")
    text(1050,710,"Right half-space",18,"#e55c2a")
    image.save(path)


def build_report_data(result, runs, separations):
    """Presentation data only; never re-solve or infer hardware quantities.

    Full-power curves retain numeric precision. Cropped intensity samples are
    rounded to 8 decimals for display; NPZ remains the authoritative raw field.
    """
    from dataclasses import replace
    from optics import Parameters, index_increment
    if not runs or len(runs) != len(separations) or len(runs) != len(result['scan']):
        raise ValueError('Report runs, separations and scan rows must match')
    vmax = max(float(np.max(abs(r['fields'])**2)) for r in runs)
    payload = []
    base = Parameters(**result['input']['parameters'])
    for i, (row, run, gap) in enumerate(zip(result['scan'], runs, separations)):
        x = run['x_um']
        # Keep the central display region, at most ~384 transverse samples.
        indices = np.flatnonzero(abs(x) <= min(25, base.window_um * .45))
        indices = indices[::max(1, int(np.ceil(len(indices)/384)))]
        p = replace(base, separation_um=gap)
        payload.append(dict(**row, z_mm=(run['z_um']/1000).tolist(),
                            left=run['left_power'].tolist(), right=run['right_power'].tolist(),
                            x_um=x[indices].tolist(),
                            intensity=np.round(abs(run['fields'][:,indices])**2,8).tolist(),
                            delta_n=index_increment(p,x[indices]).tolist(),
                            figure=f'spacing-{i}.png'))
    return dict(report_version=2, result=result, runs=payload, vmax=vmax)


def write_report(output, result, runs, separations):
    data = build_report_data(result, runs, separations)
    for i,(gap,run) in enumerate(zip(separations,runs)):
        figure(run,gap,output/f'spacing-{i}.png',data['vmax'])
    source = Path(__file__).parent
    template = (source/'report_template.html').read_text(encoding='utf-8')
    script = (source/'report_ui.js').read_text(encoding='utf-8')
    encoded = json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('<','\\u003c')
    page = template.replace('@@DATA@@',encoded).replace('@@SCRIPT@@',script)
    (output/'index.html').write_text(page,encoding='utf-8')

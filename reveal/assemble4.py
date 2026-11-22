# v4 montaj: kareler + sarki + yeni yazi tasarimi -> MP4 (H.264/AAC)
# blender -b --factory-startup --python assemble4.py -- <kare_klasoru> <sarki> <out.mp4> [onizleme_kare]
# Ortam: FONT1 (kalin baslik), FONT2 (etiket), RES (yuzde), END_FRAME
# v3'e gore: etiketler ortada ve kucuk/robota biniyordu -> sol alt, numarali, golgeli kutu;
# final yazisi robotun ustundeydi -> solda (robot build4'te saga kaydirildi); basta/sonda siyahtan gecis.
import bpy, os, sys

args = sys.argv[sys.argv.index('--') + 1:]
FR, SONG, OUT = args[0], args[1], args[2]
PREVIEW = args[3] if len(args) > 3 else None
FPS = 30
END = int(os.environ.get('END_FRAME', '1034'))
FONT1 = os.environ.get('FONT1', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf')
FONT2 = os.environ.get('FONT2', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf')
RES = int(os.environ.get('RES', '100'))
ICE, AMBER, RED = (0.55, 0.88, 1.0), (1.0, 0.72, 0.28), (1.0, 0.38, 0.32)

# (numara, metin, baslangic s, bitis s, renk)
LABELS = [
    ('01', 'TURRET  //  HOOD',    4.4,  8.0, ICE),
    ('02', 'FLOWER INTAKE',      10.8, 13.3, ICE),
    ('03', '4 SHOTS  //  0.3 S', 14.6, 16.4, AMBER),
    ('04', 'HIVE',               16.6, 19.9, RED),
    ('05', 'GROUND INTAKE',      20.2, 22.3, ICE),
    ('06', 'SHOT BLOCKER',       22.7, 24.8, ICE),
]
FLASHES = [(246, 0.22), (494, 0.22), (850, 0.22)]

sc = bpy.context.scene
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, END
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.render.resolution_percentage = RES
se = sc.sequence_editor_create()
strips = se.strips if hasattr(se, 'strips') else se.sequences

files = sorted(f for f in os.listdir(FR) if f.endswith('.png') and os.path.getsize(os.path.join(FR, f)) > 0)
nums = [int(f[1:5]) for f in files]
missing = sorted(set(range(1, END + 1)) - set(nums))
print('KARE', len(files), 'EKSIK', len(missing), missing[:20])
img = strips.new_image('frames', os.path.join(FR, files[0]), channel=1, frame_start=1)
for f in files[1:]:
    img.elements.append(f)
if hasattr(img, 'frame_final_duration'):
    img.frame_final_duration = min(len(files), END)

if SONG and os.path.exists(SONG):
    snd = strips.new_sound('music', SONG, channel=2, frame_start=1)
    for fr, v in ((1, 1.0), (END - 45, 1.0), (END, 0.0)):
        snd.volume = v; snd.keyframe_insert('volume', frame=fr)

f1o, f2o = bpy.data.fonts.load(FONT1), bpy.data.fonts.load(FONT2)

def text(name, txt, f0, f1, size, x, y, col, font, ch, align='LEFT', box=False, fade=8):
    try:
        s = strips.new_effect(name, 'TEXT', channel=ch, frame_start=f0, length=f1 - f0)
    except TypeError:
        s = strips.new_effect(name, 'TEXT', channel=ch, frame_start=f0, frame_end=f1)
    s.text = txt; s.font = font; s.font_size = size; s.color = (*col, 1.0); s.location = (x, y)
    for attr, val in (('align_x', align), ('anchor_x', align), ('anchor_y', 'CENTER')):
        if hasattr(s, attr):
            setattr(s, attr, val)
    if hasattr(s, 'use_shadow'):
        s.use_shadow = True
        for a, v in (('shadow_color', (0, 0, 0, 0.85)), ('shadow_blur', 0.4), ('shadow_offset', 0.03)):
            if hasattr(s, a):
                try: setattr(s, a, v)
                except Exception: pass
    if box and hasattr(s, 'use_box'):
        s.use_box = True
        if hasattr(s, 'box_color'): s.box_color = (0.0, 0.0, 0.0, 0.55)
        if hasattr(s, 'box_margin'): s.box_margin = 0.012
    s.blend_type = 'ALPHA_OVER'
    for fr, a in ((f0, 0.0), (f0 + fade, 1.0), (f1 - fade, 1.0), (f1, 0.0)):
        s.blend_alpha = a; s.keyframe_insert('blend_alpha', frame=fr)
    return s

ch = 3
for i, (num, txt, t0, t1, col) in enumerate(LABELS):
    f0, f1 = int(t0 * FPS), int(t1 * FPS)
    text(f'n{i}', num, f0, f1, 40, 0.055, 0.155, col, f1o, ch); ch += 1
    text(f'l{i}', txt, f0 + 3, f1, 70, 0.055, 0.095, (1, 1, 1), f2o, ch, box=True); ch += 1

# final: robot sagda (build4), yazi solda
t0, t1 = int(30.0 * FPS), END - 2
text('title', 'ZAĞANOS', t0, t1, 210, 0.065, 0.56, (1, 1, 1), f1o, ch, fade=12); ch += 1
text('sub', 'FTC #25577   ·   2026–27', t0 + 10, t1, 54, 0.068, 0.425, ICE, f2o, ch, fade=12); ch += 1

def color(name, f0, f1, col, blend, keys, chn):
    try:
        c = strips.new_effect(name, 'COLOR', channel=chn, frame_start=f0, length=f1 - f0)
    except TypeError:
        c = strips.new_effect(name, 'COLOR', channel=chn, frame_start=f0, frame_end=f1)
    c.color = col; c.blend_type = blend
    for f_, a in keys:
        c.blend_alpha = a; c.keyframe_insert('blend_alpha', frame=f_)

for i, (fr, k) in enumerate(FLASHES):
    color(f'flash{i}', fr, fr + 7, (1, 1, 1), 'ADD', ((fr, k), (fr + 2, k * 0.6), (fr + 6, 0.0)), ch); ch += 1
color('fadein', 1, 14, (0, 0, 0), 'ALPHA_OVER', ((1, 1.0), (13, 0.0)), ch); ch += 1
color('fadeout', END - 20, END + 1, (0, 0, 0), 'ALPHA_OVER', ((END - 20, 0.0), (END, 1.0)), ch); ch += 1

r = sc.render
if PREVIEW:
    r.image_settings.file_format = 'JPEG'
    for p in PREVIEW.split(','):
        sc.frame_set(int(p)); r.filepath = OUT.replace('.mp4', f'_{p}.jpg')
        bpy.ops.render.render(write_still=True)
    print('ONIZLEME', OUT)
else:
    if hasattr(r.image_settings, 'media_type'):
        r.image_settings.media_type = 'VIDEO'
    r.image_settings.file_format = 'FFMPEG'
    ff = r.ffmpeg
    ff.format = 'MPEG4'; ff.codec = 'H264'; ff.constant_rate_factor = 'HIGH'; ff.ffmpeg_preset = 'GOOD'
    ff.gopsize = 30; ff.audio_codec = 'AAC'; ff.audio_bitrate = 320; ff.audio_channels = 'STEREO'; ff.audio_mixrate = 48000
    r.filepath = OUT
    bpy.ops.render.render(animation=True)
    print('VIDEO', OUT)

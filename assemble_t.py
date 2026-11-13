# Sahneleri baslik ve sonuc yazilariyla tek videoda birlestir.
# Blender -b --factory-startup --python assemble_sim.py -- <physics_dir> <out.mp4> [onizleme_kare]
import bpy, os, sys

args = sys.argv[sys.argv.index('--') + 1:]
D, OUT = args[0], args[1]
PREVIEW = int(args[2]) if len(args) > 2 else None
FPS, HOLD = 30, 30
FONT = os.environ.get('FONT1', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf')
FONT2 = os.environ.get('FONT2', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf')
OK, BAD, INFO = (0.45, 1.0, 0.55), (1.0, 0.38, 0.30), (0.75, 0.85, 1.0)

SCENES = [
    ('vid/K00_CAD_b1', 'ŞU ANKİ CAD | 5 TOP YAN YANA', '{auto}', None, '4x yavaş | üstten | koyu: Bootleg, turuncu: Gecko'),
    ('vid/T253_b1', 'T253 | AYNI SAHNE', '{auto}', None, '4x yavaş | üstten | Bootleg duvarı geç, Gecko duvarı düz konik daralıyor'),
    ('vid/T193_b1', 'T193 | AYNI SAHNE', '{auto}', None, '4x yavaş | üstten'),
    ('vid/K00_CAD_c1', 'ŞU ANKİ CAD | 2 TOP TAM YAN YANA', '{auto}', None, '4x yavaş | üstten'),
    ('vid/T253_c1', 'T253 | AYNI SAHNE', '{auto}', None, '4x yavaş | üstten'),
    ('vid/T193_c1', 'T193 | AYNI SAHNE', '{auto}', None, '4x yavaş | üstten'),
]
END_LINES = [
    ('FUNNEL İTTİRİCİ OPTİMİZASYONU | 300 ADAY', 44, INFO),
    ('Yeni sahnelerde: şu anki CAD %90,7 | T253 %90,6 | T193 %90,4', 30, INFO),
    ('Fark gürültü içinde: şu anki CAD zaten en iyi seviyede', 30, OK),
    ('Videodaki fizik: Bootleg 0,70, Gecko 0,80, TPU 0,65, top 25,7 g', 26, INFO),
    ('Tutuşlar ölçülmedi; malzemeye göre seçilmiş değerler', 26, (0.7, 0.7, 0.7)),
]

sc = bpy.context.scene
sc.render.fps = FPS
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1280, 720, 100
sc.view_settings.view_transform = 'Standard'
se = sc.sequence_editor_create()
strips = se.strips if hasattr(se, 'strips') else se.sequences
font = bpy.data.fonts.load(FONT); font2 = bpy.data.fonts.load(FONT2)

def text(name, txt, f0, f1, size, x, y, col, fnt=font, ch=5, align='LEFT', box=False):
    try:
        s = strips.new_effect(name, 'TEXT', channel=ch, frame_start=f0, length=f1 - f0)
    except TypeError:
        s = strips.new_effect(name, 'TEXT', channel=ch, frame_start=f0, frame_end=f1)
    s.text = txt; s.font = fnt; s.font_size = size; s.color = (*col, 1.0); s.location = (x, y)
    for attr, val in (('align_x', align), ('anchor_x', align), ('anchor_y', 'CENTER')):
        if hasattr(s, attr):
            setattr(s, attr, val)
    if hasattr(s, 'use_shadow'):
        s.use_shadow = True
    if hasattr(s, 'use_box'):
        s.use_box = box
        if box:
            if hasattr(s, 'box_color'): s.box_color = (0.0, 0.0, 0.0, 0.72)
            if hasattr(s, 'box_margin'): s.box_margin = 0.012
    s.blend_type = 'ALPHA_OVER'
    for fr, a in ((f0, 0.0), (f0 + 6, 1.0), (f1 - 6, 1.0), (f1, 0.0)):
        s.blend_alpha = a; s.keyframe_insert('blend_alpha', frame=fr)
    return s

def color(name, f0, f1, ch=1):
    try:
        c = strips.new_effect(name, 'COLOR', channel=ch, frame_start=f0, length=f1 - f0)
    except TypeError:
        c = strips.new_effect(name, 'COLOR', channel=ch, frame_start=f0, frame_end=f1)
    c.color = (0.02, 0.025, 0.03)
    return c

f = 1
# giris
color('intro_bg', f, f + 75)
text('intro1', 'ZAĞANOS | T253 VE T193', f, f + 75, 66, 0.5, 0.56, (1, 1, 1), align='CENTER', ch=6)
text('intro2', 'RobotMontaj (7) | sadece Funnel İttirici duvarı değişiyor | gerçek POLLEN 25 g', f, f + 75, 34, 0.5, 0.44, INFO,
     fnt=font2, align='CENTER', ch=7)
f += 75
for i, (folder, title, result, col, note) in enumerate(SCENES):
    path = os.path.join(D, folder)
    files = sorted(x for x in os.listdir(path) if x.endswith('.png'))
    img = strips.new_image(folder, os.path.join(path, files[0]), channel=2, frame_start=f)
    for x in files[1:]:
        img.elements.append(x)
    n = len(files)
    img.frame_final_duration = n + HOLD          # son kare beklemede
    f1 = f + n + HOLD
    text(f't{i}', f'{i + 1}. {title}', f, f1, 38, 0.035, 0.92, (1, 1, 1), ch=5, box=True)
    text(f'n{i}', note, f, f1, 26, 0.035, 0.85, (0.75, 0.8, 0.85), fnt=font2, ch=6, box=True)
    if result == '{auto}':
        sp = os.path.join(path, 'sonuc.txt')
        result = open(sp).read().strip() if os.path.exists(sp) else ''
        col = BAD if 'kaldı' in result else OK
    text(f'r{i}', result, f + min(n // 2, 45), f1, 42, 0.035, 0.07, col, ch=7, box=True)
    f = f1
# kapanis
color('end_bg', f, f + 200)
for j, (txt, size, col) in enumerate(END_LINES):
    text(f'e{j}', txt, f + 4 * j, f + 200, size, 0.07, 0.88 - j * 0.105, col, fnt=font if j == 0 else font2, ch=5 + j)
f += 200
sc.frame_start, sc.frame_end = 1, f - 1

r = sc.render
if PREVIEW:
    r.image_settings.file_format = 'PNG'
    for fr in [int(x) for x in str(PREVIEW).split(',')] if isinstance(PREVIEW, str) else [PREVIEW]:
        sc.frame_set(fr); r.filepath = OUT.replace('.png', f'_{fr}.png')
        bpy.ops.render.render(write_still=True)
else:
    if hasattr(r.image_settings, 'media_type'):
        r.image_settings.media_type = 'VIDEO'
    r.image_settings.file_format = 'FFMPEG'
    ff = r.ffmpeg; ff.format = 'MPEG4'; ff.codec = 'H264'; ff.constant_rate_factor = 'HIGH'
    ff.ffmpeg_preset = 'GOOD'; ff.gopsize = 30; ff.audio_codec = 'NONE'
    r.filepath = OUT
    bpy.ops.render.render(animation=True)
print('VIDEO', OUT, f - 1)

# Instagram Reels dikey surum (1080x1920): "ZAGANOS PRESENTS / PLEASE ROTATE YOUR PHONE" karti + yatay film 90 derece cevrik.
# blender -b --factory-startup --python vertical.py -- <yatay.mp4> <out.mp4> [onizleme_kareleri]
# Ortam: FONT1 (kalin), FONT2 (etiket)
# Kart, filmin kendi siyah ZAGANOS kartinin (film kare 1-42) uzerine biner ve film kare 43'teki OVERLORD vurusunda kesilir;
# muzik filmle birlikte kaydigi icin senkron bozulmaz. Kartin ilk PRE karesi sessiz.
import bpy, os, sys, math
import numpy as np

args = sys.argv[sys.argv.index('--') + 1:]
MOV, OUT = args[0], args[1]
PREVIEW = args[2] if len(args) > 2 else None
FPS, PRE, HIT = 30, 45, 43                     # HIT: filmdeki OVERLORD flas karesi
CUT = PRE + HIT                               # kartin bittigi zaman cizelgesi karesi
FONT1 = os.environ.get('FONT1', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf')
FONT2 = os.environ.get('FONT2', FONT1)
ICE = (0.55, 0.88, 1.0)

sc = bpy.context.scene
r = sc.render
r.resolution_x, r.resolution_y, r.resolution_percentage = 1080, 1920, 100
r.fps = FPS
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
se = sc.sequence_editor_create()
strips = se.strips if hasattr(se, 'strips') else se.sequences

def new_movie(name, path, ch, start):
    try:
        return strips.new_movie(name, path, channel=ch, frame_start=start, fit_method='ORIGINAL')
    except TypeError:
        return strips.new_movie(name, path, channel=ch, frame_start=start)

# ---- film: saat yonunde 90 derece (telefon saat yonu tersine cevrilince dik gorunur); 1920x1080 -> 1080x1920 tam oturur
mv = new_movie('film', MOV, 2, PRE + 1)
mv.transform.rotation = -math.pi / 2
snd = strips.new_sound('audio', MOV, channel=1, frame_start=PRE + 1)
END = PRE + mv.frame_final_duration
sc.frame_start, sc.frame_end = 1, END

# ---- telefon ikonu (yuvarlak koseli cerceve + hoparlor yarigi), numpy ile PNG
W, H, R, S = 250, 460, 46, 15
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
px, py = np.abs(xx - W / 2 + 0.5), np.abs(yy - H / 2 + 0.5)
def rrect(bx, by, rad):
    qx, qy = px - bx + rad, py - by + rad
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - rad
d = rrect(W / 2 - 2, H / 2 - 2, R)
ring = np.clip(S / 2 - np.abs(d + S / 2) + 0.5, 0, 1)
slot = np.clip(0.5 - (np.hypot(np.maximum(np.abs(xx - W / 2) - 28, 0), np.abs(yy - 34)) - 5), 0, 1)
a = np.maximum(ring, slot)
rgba = np.zeros((H, W, 4), np.float32); rgba[..., :3] = 1.0; rgba[..., 3] = a
icon_path = os.path.join(os.path.dirname(os.path.abspath(OUT)), '_phone_icon.png')
im = bpy.data.images.new('phone', W, H, alpha=True)
im.pixels.foreach_set(rgba[::-1].ravel())           # Blender pikselleri alttan baslar
im.filepath_raw = icon_path; im.file_format = 'PNG'; im.save()

f1o, f2o = bpy.data.fonts.load(FONT1), bpy.data.fonts.load(FONT2)

def alpha_keys(s, keys):
    for fr, al in keys:
        s.blend_alpha = al; s.keyframe_insert('blend_alpha', frame=fr)

def effect(name, kind, ch, f0, f1):
    try:
        return strips.new_effect(name, kind, channel=ch, frame_start=f0, length=f1 - f0)
    except TypeError:
        return strips.new_effect(name, kind, channel=ch, frame_start=f0, frame_end=f1)

def text(name, txt, f0, f1, size, y, col, font, ch):
    s = effect(name, 'TEXT', ch, f0, f1)
    s.text = txt; s.font = font; s.font_size = size; s.color = (*col, 1.0); s.location = (0.5, y)
    for attr in ('align_x', 'anchor_x'):
        if hasattr(s, attr): setattr(s, attr, 'CENTER')
    if hasattr(s, 'anchor_y'): s.anchor_y = 'CENTER'
    s.blend_type = 'ALPHA_OVER'
    alpha_keys(s, ((f0, 0.0), (f0 + 7, 1.0), (f1 - 2, 1.0), (f1, 0.0)))
    return s

# siyah kart filmin uzerinde; film kare HIT'te (OVERLORD flasi) sert kesme
card = effect('card', 'COLOR', 3, 1, CUT)
card.color = (0.008, 0.01, 0.018); card.blend_type = 'ALPHA_OVER'

text('team', 'Z  A  Ğ  A  N  O  S', 4, CUT, 118, 0.75, (1, 1, 1), f1o, 4)
text('pres', 'P R E S E N T S', 11, CUT, 38, 0.705, ICE, f2o, 5)
text('rot1', 'PLEASE ROTATE', 20, CUT, 74, 0.34, (1, 1, 1), f1o, 6)
text('rot2', 'YOUR PHONE', 23, CUT, 74, 0.30, (1, 1, 1), f1o, 7)
text('rot3', 'F O R   F U L L   S C R E E N', 28, CUT, 32, 0.255, ICE, f2o, 8)

ph = strips.new_image('phone', icon_path, channel=9, frame_start=16)
if hasattr(ph, 'frame_final_duration'):
    ph.frame_final_duration = CUT - 16
ph.blend_type = 'ALPHA_OVER'
ph.transform.offset_y = 1920 * (0.525 - 0.5)
alpha_keys(ph, ((16, 0.0), (22, 1.0), (CUT - 2, 1.0), (CUT, 0.0)))
# saat yonu tersine 90 derece (izleyicinin telefonu cevirecegi yon), iki kez
for fr, ang in ((24, 0), (38, 90), (52, 90), (58, 0), (64, 0), (78, 90)):
    ph.transform.rotation = math.radians(ang); ph.transform.keyframe_insert('rotation', frame=fr)

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
    ff.gopsize = 30; ff.audio_codec = 'AAC'; ff.audio_bitrate = 256; ff.audio_channels = 'STEREO'; ff.audio_mixrate = 48000
    r.filepath = OUT
    bpy.ops.render.render(animation=True)
    print('VIDEO', OUT, END, 'kare')

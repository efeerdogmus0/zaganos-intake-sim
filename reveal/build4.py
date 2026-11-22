# v4: v3 sahnesi (reveal3.blend) uzerine duzeltme gecisi + kare render'i (GitHub Actions'ta).
# blender -b reveal3.blend --python build4.py -- <cikti_klasoru> <kareler: "1-1034" | "1,200,350"> [parca k/n]
# Ortam: ENGINE=EEVEE|CYCLES, RES=100 (yuzde, 1920x1080 tabani), SAMPLES
#
# v3'te gorulen hatalar ve bu gecisteki karsiliklari:
#  1) Butun karelerde mavi pus, dusuk kontrast (sis yogunlugu 0.025)      -> sis 0.011, pozlama -0.15
#  2) Hizli cekimlerde robot okunmuyor (11 s, 14 s lekeli)                 -> hareket bulaniklgi 0.5 -> 0.25
#  3) El kamerasi titremesi fazla (C_chase, E_strafe, J_go, H_*)           -> kamera yolu yumusatildi (titreme ~%35'e)
#  4) SHOT BLOCKER cekiminde robot kadrajdan tasiyor (23-25 s)             -> kamera geri cekildi
#  5) Final: ZAGANOS yazisi robotun ustune biniyor (30-34 s)               -> robot sag uce kaydirildi (lens kaydirma), yazi solda
#  6) Acilis 0-1 s siyah: bilerek korundu, ZAGANOS / OVERLORD giris yazisi oraya geliyor (EARLY_LIGHTS=1 eski davranis)
import bpy, sys, os, math

args = sys.argv[sys.argv.index('--') + 1:]
OUTD, FR = args[0], args[1]
PART = args[2] if len(args) > 2 else '0/1'
ENGINE = os.environ.get('ENGINE', 'EEVEE').upper()
RES = int(os.environ.get('RES', '100'))
SAMPLES = int(os.environ.get('SAMPLES', '64' if ENGINE == 'EEVEE' else '48'))
sc = bpy.context.scene
O = bpy.data.objects

# ---- 1) pus ve ton
pv = bpy.data.materials['FogMat'].node_tree.nodes['Principled Volume']
pv.inputs['Density'].default_value = 0.011
vs = sc.view_settings
vs.view_transform = 'AgX'
try:
    vs.look = 'AgX - Punchy'
except Exception as e:
    print('look', e)
vs.exposure = -0.15

# ---- 2) hareket bulanikligi
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.25

# ---- 3) kamera titremesini yumusat (her cekim ayri kamera; kareler tek tek anahtarli)
def fcurves_of(ob):
    ad = ob.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, 'fcurves') and len(getattr(act, 'fcurves', [])):
        return list(act.fcurves)
    out = []                                       # 4.4+ katmanli eylemler
    for layer in getattr(act, 'layers', []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += list(bag.fcurves)
    return out

def smooth(fc, keep=0.35, half=5):
    kp = fc.keyframe_points
    vals = [k.co[1] for k in kp]
    n = len(vals)
    for i, k in enumerate(kp):
        a, b = max(0, i - half), min(n, i + half + 1)
        m = sum(vals[a:b]) / (b - a)
        k.co[1] = keep * vals[i] + (1 - keep) * m
        k.handle_left[1] = k.handle_right[1] = k.co[1]
    fc.update()

cams = [o for o in O if o.type == 'CAMERA']
for c in cams:
    for fc in fcurves_of(c):
        if fc.data_path == 'location' and len(fc.keyframe_points) > 12:
            smooth(fc)

# ---- 4) shot blocker: kamerayi hedeften 1.35x uzaklastir
def pull_back(cam_name, k):
    cam, tg = O[cam_name], O[cam_name + '_tgt']
    cf = {fc.array_index: fc for fc in fcurves_of(cam) if fc.data_path == 'location'}
    tf = {fc.array_index: fc for fc in fcurves_of(tg) if fc.data_path == 'location'}
    for i in range(3):
        for kc in cf[i].keyframe_points:
            t = tf[i].evaluate(kc.co[0])
            kc.co[1] = t + (kc.co[1] - t) * k
            kc.handle_left[1] = kc.handle_right[1] = kc.co[1]
        cf[i].update()
pull_back('G_block', 1.7)

# ---- 5) final: robot kadrajin sagina (yazi sola gelecek)
O['I_hero'].data.shift_x = -0.17
O['I_hero'].data.dof.aperture_fstop = 3.5

# ---- 6) acilis: ilk saniye bilerek karanlik kaliyor (ZAGANOS / OVERLORD giris yazisi oraya geliyor)
for o in ([] if os.environ.get('EARLY_LIGHTS') != '1' else O):
    if o.type == 'LIGHT' and o.data.animation_data and o.data.animation_data.action:
        for fc in fcurves_of(o.data):
            for kp in fc.keyframe_points:
                if 16 <= kp.co[0] <= 115:            # tek kayma: anahtar sirasi bozulmaz
                    kp.co[0] -= 15; kp.handle_left[0] -= 15; kp.handle_right[0] -= 15
            fc.update()

# ---- render ayarlari
r = sc.render
r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, RES
r.image_settings.file_format = 'PNG'
r.image_settings.color_depth = '8'
if ENGINE == 'CYCLES':
    r.engine = 'CYCLES'
    cy = sc.cycles
    cy.device = 'CPU'; cy.samples = SAMPLES; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    try:
        cy.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    cy.volume_step_rate = 4.0; cy.max_bounces = 6; cy.caustics_reflective = cy.caustics_refractive = False
    r.use_persistent_data = True
else:
    r.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = SAMPLES

# ---- kareler
def parse(s):
    out = []
    for p in s.split(','):
        if '-' in p:
            a, b = map(int, p.split('-')); out += range(a, b + 1)
        elif p.strip():
            out.append(int(p))
    return out
frames = parse(FR)
k, n = map(int, PART.split('/'))
frames = frames[k::n]
os.makedirs(OUTD, exist_ok=True)
import time
for f in frames:
    fn = os.path.join(OUTD, f'f{f:04d}.png')
    if os.path.exists(fn) and os.path.getsize(fn) > 0:
        continue
    t = time.time()
    sc.frame_set(f)
    r.filepath = fn
    bpy.ops.render.render(write_still=True)
    print(f'KARE {f} {time.time() - t:.1f}s', flush=True)
print('BITTI', len(frames), flush=True)

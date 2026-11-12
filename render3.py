# sim3 kaydini (record3.py) tasarimin gercek geometrisiyle Blender'da ciz.
# Blender -b --factory-startup --python render3.py -- <physics_dir> <kayit.npz> <cikti_on_eki> [yavas=4] [yuzde=100] [top|side] [still k1,k2]
# top : ustten, robotun tum genisligi (robot ustte, toplar alttan gelir; sag = + taraf / Gecko tarafi)
# side: yandan yarim kesit (z > 0 kesilir)
import bpy, bmesh, sys, os, math, json
import numpy as np
from mathutils import Vector, Matrix, Quaternion

args = sys.argv[sys.argv.index('--') + 1:]
D, TRAJ, OUT = args[0], args[1], args[2]
SLOW = float(args[3]) if len(args) > 3 else 4.0
PCT = int(args[4]) if len(args) > 4 else 100
VIEW = args[5] if len(args) > 5 else 'top'
STILL = [int(x) for x in args[7].split(',')] if len(args) > 7 and args[6] == 'still' else None
FPS = 30
sys.path.insert(0, D)
import model as M, sim3 as S
from sim import rot
from sim2 import HOLE_AX, COS_A, WALL

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
tr = np.load(TRAJ, allow_pickle=True)
T = tr['t']; POS = tr['pos']; QUAT = tr['quat']; TH = tr['theta']; BR = float(tr['R'])
STATES = [str(s) for s in tr['states']]; TEND = [float(x) for x in tr['t_end']]
design = json.loads(str(tr['D']))
REGION = str(tr['region']) if 'region' in tr.files else 'region2.npz'
W = S.World(os.path.join(D, REGION))
W.set_design(design)
groups = W.groups; gi = groups[0]
reg = np.load(os.path.join(D, REGION), allow_pickle=True)
PART = {n: (v.astype(np.float64), f) for n, v, f in zip(reg['names'], reg['verts'], reg['faces'])}

def mat(name, col, metal=0.0, rough=0.5, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1)
    b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        if hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'BLENDED'
        else:
            m.blend_method = 'BLEND'
    return m

A = 0.5 if VIEW == 'top' else 1.0          # ustten bakista intake tekerleri yari saydam (alttaki top gorunsun)
MAT = {
    'alu': mat('alu', (0.62, 0.65, 0.70), 0.6, 0.38),
    'print': mat('print', (0.10, 0.32, 0.42), 0.0, 0.55),
    'dark': mat('dark', (0.06, 0.06, 0.07), 0.3, 0.5),
    'feed': mat('feed', (1.0, 0.42, 0.06), 0.0, 0.6),
    'gecko': mat('gecko', (1.0, 0.42, 0.06), 0.0, 0.6, A),
    'boot': mat('boot', (0.16, 0.20, 0.30), 0.0, 0.35, A),
    'tpu': mat('tpu', (0.35, 0.75, 1.0), 0.0, 0.5, A),
    'tpu2': mat('tpu2', (0.80, 0.40, 1.0), 0.0, 0.5, A),
    'fly': mat('fly', (0.95, 0.20, 0.10), 0.0, 0.5),
    'sushi': mat('sushi', (0.20, 0.85, 0.35), 0.0, 0.6),
    'new': mat('new', (0.95, 0.15, 0.75), 0.0, 0.4),
}
import re
def pick(name):
    if re.search(r'Print|Funnel|İttirici|Rampa|Koruma|Kapağı|TUTTURUCU|tutturucu', name): return MAT['print']
    if re.search(r'screw|Screw|nut|Nut|Motor|Bearing|race|Pulley|belt|Gear|Spur|Servo|Hex', name): return MAT['dark']
    return MAT['alu']

def add_mesh(name, v, f, material, cut=True):
    if cut:
        f = f[~(v[f][:, :, 1] > 0.09).all(1)] if VIEW == 'top' else f[~(v[f][:, :, 2] > 0.0).all(1)]
    if len(f) == 0:
        return None
    used = np.unique(f); remap = -np.ones(len(v), np.int64); remap[used] = np.arange(len(used))
    v2 = v[used]; f2 = remap[f]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(v2)); me.vertices.foreach_set('co', v2.astype(np.float32).ravel())
    me.loops.add(len(f2) * 3); me.loops.foreach_set('vertex_index', f2.astype(np.int32).ravel())
    me.polygons.add(len(f2))
    me.polygons.foreach_set('loop_start', np.arange(0, len(f2) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set('loop_total', np.full(len(f2), 3, np.int32))
    me.update(); me.validate()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob

def add_tris(name, tris, material, thick=0.0):
    tris = np.asarray(tris, dtype=np.float64)
    ob = add_mesh(name, tris.reshape(-1, 3), np.arange(len(tris) * 3).reshape(-1, 3), material)
    if ob is not None and thick > 0:
        sm = ob.modifiers.new('kalinlik', 'SOLIDIFY'); sm.thickness = thick; sm.offset = 0
    return ob

# --- donen gruplar icin pivotlar (yerel Z = mil ekseni)
pivots = {}
for g in groups:
    e = bpy.data.objects.new('PIV_' + g.name, None); sc.collection.objects.link(e)
    q = Vector((0, 0, 1)).rotation_difference(Vector(g.a).normalized())
    e.matrix_world = Matrix.Translation(Vector(g.c)) @ q.to_matrix().to_4x4()
    pivots[g.name] = e
bpy.context.view_layer.update()
def attach(ob, gname):
    if ob is not None:
        ob.parent = pivots[gname]; ob.matrix_parent_inverse = pivots[gname].matrix_world.inverted()

rot_parts = {n: g for g in groups for n in g.parts}
for n, (v, f) in PART.items():
    if n in S.World.VAR:
        continue
    g = rot_parts.get(n)
    if g is None:
        add_mesh(n, v, f, pick(n))
    elif g is gi:
        if n == 'IntakeShaft':
            attach(add_mesh(n, v, f, MAT['dark']), gi.name)
    else:
        m = MAT['fly'] if g.name == 'flywheel' else MAT['sushi'] if g.name.startswith('sushi') else MAT['feed']
        attach(add_mesh(n, v, f, m), g.name)

# --- tasarimin intake tekerleri: Gecko / Bootleg (CAD parcasinin kopyasi) ve mecanum makaralari
def biggest(prefix):
    c = [n for n in PART if n.startswith(prefix)]
    return max(c, key=lambda n: len(PART[n][1])) if c else None
SRC = {'G': biggest('48mm Gecko'), 'B': biggest('48mm Bootleg')}
for i, (z, rc, h, kind) in enumerate(W.cyl):
    v, f = PART[SRC[kind]]
    v = v.copy(); v[:, 2] += z - (v[:, 2].min() + v[:, 2].max()) / 2
    attach(add_mesh(f'Teker{i}', v, f, MAT['gecko' if kind == 'G' else 'boot'], cut=(VIEW != 'top')), gi.name)
rsrc = next(n for n in PART if 'Roller_TPU' in n)
vs, fs = PART[rsrc]; cs, es = M.pca_axis(vs)
ncad = sum(len(w) for w in W.cad_wheels)
for i, (c, e) in enumerate(W.rollers):
    e = np.asarray(e, float)
    if e @ es < 0:
        e = -e
    ax = np.cross(es, e); sn = np.linalg.norm(ax)
    Rm = rot(ax / sn, math.atan2(sn, float(es @ e))) if sn > 1e-9 else np.eye(3)
    v = (vs - cs) @ Rm.T + np.asarray(c, float)
    attach(add_mesh(f'Makara{i}', v, fs, MAT['tpu'] if i < ncad else MAT['tpu2'], cut=(VIEW != 'top')), gi.name)

# --- degisken parcalar: rampa, huni duvarlari, ek duvarlar
if W.ramp_tris is not None:
    add_tris('Rampa', W.ramp_tris, MAT['print'] if design.get('ramp', 'cad') == 'cad' else MAT['new'])
fun = design.get('funnel') or {}
for sg, key in ((-1, 'neg'), (1, 'pos')):
    spec = fun.get(key, 'cad'); cad = W.cad_fun[sg]
    if isinstance(spec, str):
        add_tris(f'Huni{sg}', cad, MAT['print'])
    else:
        add_tris(f'HuniArka{sg}', cad[cad[:, :, 0].min(1) > S.X_KEEP], MAT['print'])
        poly = [(S.X_MOUTH, sg * S.Z_PLATE)] + [(x, sg * w) for x, w in spec]
        if poly[-1][0] < S.X_KEEP:
            poly.append((S.X_KEEP, sg * S.CHAN))
        add_tris(f'HuniYeni{sg}', S.wall_tris(poly), MAT['new'], thick=0.004)
for i, w in enumerate(W.wall_polys):
    add_tris(f'Duvar{i}', S.wall_tris(w, 0.006, 0.064), MAT['new'], thick=0.004)

# --- zemin (robot cercevesinde akan saha zemini)
bpy.ops.mesh.primitive_plane_add(size=2.0, location=(-0.2, -0.0005, 0.0))
floor = bpy.context.object; floor.rotation_euler = (math.radians(-90), 0, 0)
fm = bpy.data.materials.new('floor'); fm.use_nodes = True
nt = fm.node_tree; bsdf = nt.nodes['Principled BSDF']
tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
ck = nt.nodes.new('ShaderNodeTexChecker'); ck.inputs['Scale'].default_value = 40
ck.inputs['Color1'].default_value = (0.045, 0.05, 0.06, 1); ck.inputs['Color2'].default_value = (0.03, 0.033, 0.04, 1)
nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], ck.inputs['Vector'])
nt.links.new(ck.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.9
floor.data.materials.append(fm)

# --- toplar: gercek POLLEN (1.8 mm PE kabuk, 26 delik)
pm = mat('pollen', (1.0, 0.80, 0.05), 0.0, 0.42)
me = bpy.data.meshes.new('pollen'); bmx = bmesh.new()
bmesh.ops.create_icosphere(bmx, subdivisions=6, radius=BR)
bmesh.ops.delete(bmx, geom=[v for v in bmx.verts if (np.array(v.co) / BR @ HOLE_AX.T).max() > COS_A], context='VERTS')
bmx.to_mesh(me); bmx.free()
nb = len(POS[-1])
balls = []
for i in range(nb):
    o = bpy.data.objects.new(f'Top{i}', me); sc.collection.objects.link(o)
    sm = o.modifiers.new('kabuk', 'SOLIDIFY'); sm.thickness = WALL; sm.offset = -1
    o.data.materials.append(pm)
    for p in o.data.polygons:
        p.use_smooth = True
    o.rotation_mode = 'QUATERNION'
    balls.append(o)

# --- zaman cizelgesi
ROBOT_V = float(os.environ.get('ROBOT_V', '0.5'))
nT = len(T)
P = np.full((nT, nb, 3), np.nan); Q = np.zeros((nT, nb, 4)); Q[:, :, 0] = 1
for k in range(nT):
    for i, p in enumerate(POS[k]):
        P[k, i] = p; Q[k, i] = QUAT[k][i]
for i in range(nb):
    if STATES[i] == 'cikti':            # cikan top kayitta donar: son hizla balistik devam
        fz = int(np.searchsorted(T, TEND[i])) - 1
        if 1 <= fz < nT - 1:
            v = (P[fz, i] - P[fz - 1, i]) / (T[fz] - T[fz - 1])
            dtz = T[fz:] - T[fz]
            P[fz:, i] = P[fz, i] + np.outer(dtz, v) + 0.5 * np.outer(dtz ** 2, M.G)
    elif STATES[i] == 'alindi':         # sadece intake kosusu: alinan top sahneden cikar
        P[T > TEND[i], i] = np.nan
nfr = int(T[-1] * SLOW * FPS) + 1
sc.frame_start, sc.frame_end = 1, nfr
sc.render.fps = FPS
gnames = [str(n) for n in tr['names']]
BASES = {nm: pivots[nm].matrix_world.to_quaternion() for nm in gnames}
for nm in gnames:
    pivots[nm].rotation_mode = 'QUATERNION'
for fr in range(1, nfr + 1):
    ts = (fr - 1) / (SLOW * FPS)
    k = int(np.clip(np.searchsorted(T, ts) - 1, 0, nT - 2))
    u = float(np.clip((ts - T[k]) / (T[k + 1] - T[k]), 0, 1))
    for gidx, nm in enumerate(gnames):
        th = TH[k][gidx] + (TH[k + 1][gidx] - TH[k][gidx]) * u
        pivots[nm].rotation_quaternion = BASES[nm] @ Quaternion((0, 0, 1), th)
        pivots[nm].keyframe_insert('rotation_quaternion', frame=fr)
    for i, o in enumerate(balls):
        p0, p1 = P[k, i], P[k + 1, i]
        if np.isnan(p0[0]) or np.isnan(p1[0]):
            o.scale = (0, 0, 0)
        else:
            o.location = Vector(p0 + (p1 - p0) * u); o.scale = (1, 1, 1)
            o.rotation_quaternion = Quaternion(Q[k, i]).slerp(Quaternion(Q[k + 1, i]), u)
        for dp in ('location', 'scale', 'rotation_quaternion'):
            o.keyframe_insert(dp, frame=fr)
    mp.inputs['Location'].default_value[0] = -ROBOT_V * ts
    mp.inputs['Location'].keyframe_insert('default_value', index=0, frame=fr)

# --- kamera ve isik
cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam)
cd.type = 'ORTHO'
if VIEW == 'top':
    cd.ortho_scale = 0.50
    cam.matrix_world = Matrix(((0, 1, 0, -0.190), (0, 0, 1, 1.2), (1, 0, 0, 0.0), (0, 0, 0, 1)))
else:
    cd.ortho_scale = 0.64
    cam.location = (-0.06, 0.165, 1.2); cam.rotation_euler = (0, 0, 0)
sc.camera = cam
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.035, 0.04, 0.05, 1)
for nm, loc, en, size in (('key', (0.25, 0.7, 1.1), 38, 1.4), ('fill', (-0.7, 0.25, 0.9), 16, 1.2), ('rim', (0.1, 0.9, -0.7), 22, 1.0)):
    ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = en; ld.size = size
    lo = bpy.data.objects.new(nm, ld); sc.collection.objects.link(lo); lo.location = loc
    lo.rotation_euler = (Vector((0, 0.15, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

r = sc.render
if os.environ.get('RENDER_ENGINE', 'EEVEE') == 'CYCLES':      # GPU'suz makine (GitHub Actions)
    r.engine = 'CYCLES'
    sc.cycles.device = 'CPU'; sc.cycles.samples = int(os.environ.get('CYCLES_SAMPLES', '24'))
    sc.cycles.use_denoising = True
else:
    r.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 16
r.resolution_x, r.resolution_y, r.resolution_percentage = 1280, 720, PCT
r.use_motion_blur = True; r.motion_blur_shutter = 0.4
sc.view_settings.view_transform = 'AgX'
r.image_settings.file_format = 'PNG'
os.makedirs(os.path.dirname(OUT), exist_ok=True)
if STILL:
    for fr in STILL:
        sc.frame_set(min(fr, nfr)); r.filepath = f'{OUT}{fr:04d}.png'
        bpy.ops.render.render(write_still=True)
else:
    ch = os.environ.get('FRAME_CHUNK')          # 'k/n': sahnenin k. dilimi (paralel render)
    if ch:
        k, n = map(int, ch.split('/'))
        a = 1 + (nfr * k) // n; b = (nfr * (k + 1)) // n
        if b < a:
            print('BITTI', nfr, 'bos dilim'); sys.exit(0)
        sc.frame_start, sc.frame_end = a, b
    print('KARE', sc.frame_start, sc.frame_end, 'toplam', nfr, flush=True)
    r.filepath = OUT
    bpy.ops.render.render(animation=True)
print('BITTI', nfr)

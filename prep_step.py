# Sifreli STEP (Actions'ta acilir) -> robot cercevesine hizali top yolu bolgesi (region npz).
# Hizalama: IntakeShaft merkezi/ekseni referans CAD'dekiyle (11.11 STEP) cakistirilir.
# python prep_step.py robot.step region2_v7.npz [karsilastirma_bolgesi.npz]
import sys, re
import numpy as np, trimesh, cascadio
from extract import dec, simplify
from extract2 import BOXES

step, out = sys.argv[1], sys.argv[2]
ref = sys.argv[3] if len(sys.argv) > 3 else None
cascadio.step_to_glb(step, 'robot.glb', tol_linear=0.0004, tol_angular=0.3, include_brep=True,
                     brep_types={'cylinder'}, include_materials=True)
scene = trimesh.load('robot.glb', force='scene')
parts = []
for node in scene.graph.nodes_geometry:
    T, gname = scene.graph[node]
    g = scene.geometry[gname]
    parts.append((dec(node), trimesh.transform_points(g.vertices, T), np.asarray(g.faces)))
print('parca', len(parts))

def center_axis(v):
    c = (v.min(0) + v.max(0)) / 2
    w, vec = np.linalg.eigh(np.cov((v - v.mean(0)).T)); return c, vec[:, -1]
iv = [v for n, v, f in parts if n == 'IntakeShaft'] or [v for n, v, f in parts if n.startswith('IntakeShaft')]
c, a = center_axis(np.vstack(iv))
print('IntakeShaft merkez (mm)', np.round(c * 1000, 2), 'eksen', np.round(a, 3))
assert abs(a[2]) > 0.99, 'intake mili z ekseninde degil: hizalama icin donme gerekiyor'
C_REF = np.array([-0.18215, 0.092, 0.0])
t = C_REF - c
parts = [(n, v + t, f) for n, v, f in parts]
fx = [v.mean(0)[0] for n, v, f in parts if n.startswith('FeederShaft')]
if fx and np.mean(fx) < C_REF[0]:          # feeder intake'in onunde kaldiysa robot y ekseni etrafinda 180 derece donuk
    print('180 derece donuk: duzeltiliyor')
    Rm = np.diag([-1.0, 1.0, -1.0])
    parts = [(n, (v - C_REF) @ Rm.T + C_REF, f) for n, v, f in parts]
allv = np.vstack([v for n, v, f in parts])
print('oteleme (mm)', np.round(t * 1000, 3), '| zemin min y (mm) %.1f' % (allv[:, 1].min() * 1000))

names, verts, faces = [], [], []
for n, v, f in parts:
    if not any((v.max(0) >= lo).all() and (v.min(0) <= hi).all() for lo, hi in BOXES):
        continue
    tri = v[f]; tmin, tmax = tri.min(1), tri.max(1)
    keep = np.zeros(len(f), bool)
    for lo, hi in BOXES:
        keep |= (tmax >= lo).all(1) & (tmin <= hi).all(1)
    if not keep.any():
        continue
    v2, f2 = simplify(v, f[keep])
    names.append(n); verts.append(v2.astype(np.float32)); faces.append(f2.astype(np.int32))
np.savez_compressed(out, names=np.array(names, dtype=object), verts=np.array(verts, dtype=object),
                    faces=np.array(faces, dtype=object))
print('bolge', len(names), 'parca ->', out)

if ref:   # top yolundaki (y<80 mm, intake-feeder) parcalarin referans bolgeye gore farki
    d = np.load(ref, allow_pickle=True)
    base = lambda n: re.sub(r'_\d+$', '', n)
    A = [(base(n), v.astype(float).min(0), v.astype(float).max(0), n) for n, v in zip(d['names'], d['verts'])]
    B = [(base(n), v.astype(float).min(0), v.astype(float).max(0), n) for n, v in zip(names, verts)]
    inp = lambda lo, hi: lo[1] < 0.08 and lo[0] < 0.06 and hi[0] > -0.26
    def um(X, Y):
        return [x for x in X if inp(x[1], x[2]) and not any(y[0] == x[0] and np.abs(y[1] - x[1]).max() < 5e-4 and
                                                            np.abs(y[2] - x[2]).max() < 5e-4 for y in Y)]
    print('\n--- top yolunda referansa gore DEGISEN/YENI parcalar:')
    for x in um(B, A):
        if not re.search(r'Roller_TPU|Original_Core', x[0]):
            print('  ', x[3], np.round(x[1] * 1000, 1), np.round(x[2] * 1000, 1))
    print('--- referansta olup artik olmayan/degisen:')
    for x in um(A, B):
        if not re.search(r'Roller_TPU|Original_Core', x[0]):
            print('  ', x[3], np.round(x[1] * 1000, 1), np.round(x[2] * 1000, 1))

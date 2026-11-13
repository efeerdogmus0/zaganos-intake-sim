# robot.glb -> region.npz: top yolunun cevresindeki parcalarin dunya koordinatli ucgenleri.
# Yogun ag (vida disleri vb.) 0.6 mm izgaraya oturtularak sadelestirilir.
# PYTHONPATH=pylib python3.13 extract.py robot.glb region.npz
import sys, re
import numpy as np
import trimesh

REGION_MIN = np.array([-0.27, -0.03, -0.10])
REGION_MAX = np.array([0.26, 0.37, 0.10])
SNAP = 0.0006

def dec(s):
    s = re.sub(r'\\X2\\([0-9A-F]+)\\X0\\',
               lambda m: ''.join(chr(int(m.group(1)[i:i + 4], 16)) for i in range(0, len(m.group(1)), 4)), s)
    s = re.sub(r'\\X\\([0-9A-F]{2})', lambda m: bytes([int(m.group(1), 16)]).decode('latin-1'), s)
    return s

def simplify(v, f):
    """Kose noktalarini SNAP izgarasina oturt, cakisanlari birlestir, bozuk ucgenleri at."""
    key = np.round(v / SNAP).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    nv = v[first]
    nf = inv[f]
    ok = (nf[:, 0] != nf[:, 1]) & (nf[:, 1] != nf[:, 2]) & (nf[:, 0] != nf[:, 2])
    nf = np.unique(np.sort(nf[ok], axis=1), axis=0) if False else nf[ok]
    return nv, nf

if __name__ == '__main__':
    scene = trimesh.load(sys.argv[1], force='scene')
    names, verts, faces = [], [], []
    tot0 = tot1 = 0
    for node in scene.graph.nodes_geometry:
        T, gname = scene.graph[node]
        g = scene.geometry[gname]
        v = trimesh.transform_points(g.vertices, T)
        if (v.max(0) < REGION_MIN).any() or (v.min(0) > REGION_MAX).any():
            continue
        f = np.asarray(g.faces)
        tri = v[f]
        keep = ((tri.max(1) >= REGION_MIN).all(1) & (tri.min(1) <= REGION_MAX).all(1))
        f = f[keep]
        if len(f) == 0:
            continue
        tot0 += len(f)
        v2, f2 = simplify(v, f)
        tot1 += len(f2)
        names.append(dec(node)); verts.append(v2.astype(np.float32)); faces.append(f2.astype(np.int32))
    print(f'{len(names)} parca, ucgen {tot0} -> {tot1}')
    np.savez_compressed(sys.argv[2], names=np.array(names, dtype=object),
                        verts=np.array(verts, dtype=object), faces=np.array(faces, dtype=object))

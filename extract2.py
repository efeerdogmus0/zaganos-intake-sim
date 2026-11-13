# robot.glb -> region2.npz: top yolunun tum genisligi.
#   A kutusu: orta kanal (|z| <= 0.10), intake'ten shooter cikisina kadar
#   B kutusu: on taraf tum genislik (|z| <= 0.215), intake + arka dayama bolgesi
# PYTHONPATH=pylib python3.13 extract2.py robot.glb region2.npz
import sys
import numpy as np
import trimesh
from extract import dec, simplify

BOXES = [(np.array([-0.27, -0.03, -0.10]), np.array([0.26, 0.37, 0.10])),
         (np.array([-0.27, -0.03, -0.215]), np.array([-0.09, 0.20, 0.215]))]

if __name__ == '__main__':
    scene = trimesh.load(sys.argv[1], force='scene')
    names, verts, faces = [], [], []
    tot0 = tot1 = 0
    for node in scene.graph.nodes_geometry:
        T, gname = scene.graph[node]
        g = scene.geometry[gname]
        v = trimesh.transform_points(g.vertices, T)
        vmin, vmax = v.min(0), v.max(0)
        if not any((vmax >= lo).all() and (vmin <= hi).all() for lo, hi in BOXES):
            continue
        f = np.asarray(g.faces)
        tri = v[f]
        tmin, tmax = tri.min(1), tri.max(1)
        keep = np.zeros(len(f), bool)
        for lo, hi in BOXES:
            keep |= (tmax >= lo).all(1) & (tmin <= hi).all(1)
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

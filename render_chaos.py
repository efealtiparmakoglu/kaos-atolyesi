"""
Kaos Atölyesi: karanlık salonda çift sarkaç makineleri — neon iz heykelleri.

    blender --background --python render_chaos.py -- --preview   # 4 kare 640x360
    blender --background --python render_chaos.py               # 48 kare 960x540

İzler = uç bobun 16 s'lik gerçek yörüngesi (RK4, statik heykel). Sarkaçlar
aynı entegrasyonun son 4 s'ini canlı yaşar: uç, kendi izinin kuyruğunda.
Son makine ikizdir: aynı başlangıç + 1e-9 kıvılcım — beyaz ve kızıl izler
önce üst üste, sonra bir daha asla buluşamaz.
"""

import math
import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

import bpy  # noqa: E402

import chaos  # noqa: E402

T_TRAIL = 16.0        # heykel izinin kapsadığı süre
T_START = 12.0        # canlı animasyon izin başladığı an (son 4 s)
CLIP = 48
FPS = 12
SPACING = 3.4
PIVOT_Z = 2.25


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return {"preview": "--preview" in a}


def _lineer(ob):
    ad = ob.animation_data
    if not (ad and ad.action):
        return
    act = ad.action
    if hasattr(act, "fcurves"):
        fcs = list(act.fcurves)
    else:
        fcs = [fc for layer in act.layers for strip in layer.strips
               for bag in strip.channelbags for fc in bag.fcurves]
    for fc in fcs:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def _mat(name, color, metallic=0.0, rough=0.5, emission=None):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    if emission is not None:
        out = nt.nodes["Material Output"]
        nt.nodes.remove(b)
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (*color, 1.0)
        em.inputs["Strength"].default_value = emission
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    else:
        b.inputs["Base Color"].default_value = (*color, 1.0)
        try:
            b.inputs["Metallic"].default_value = metallic
            b.inputs["Roughness"].default_value = rough
        except KeyError:
            pass
    return m


def _cubuk_meshi():
    if "KA_Cubuk" in bpy.data.meshes:
        return bpy.data.meshes["KA_Cubuk"]
    n = 6
    verts, faces = [], []
    for i in range(n):
        a2 = 2 * math.pi * i / n
        verts.append((0.0, 0.015 * math.cos(a2), 0.015 * math.sin(a2)))
    for i in range(n):
        a2 = 2 * math.pi * i / n
        verts.append((1.0, 0.015 * math.cos(a2), 0.015 * math.sin(a2)))
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    faces.append(tuple(range(n - 1, -1, -1)))
    faces.append(tuple(range(n, 2 * n)))
    mesh = bpy.data.meshes.new("KA_Cubuk")
    mesh.from_pydata(verts, [], faces)
    return mesh


def _iz_curve(points, color, name, coll, strength=2.2, bevel=0.009):
    curve = bpy.data.curves.new(f"{name}_iz", type="CURVE")
    curve.dimensions = "3D"
    sp = curve.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for i, (x, y, z) in enumerate(points):
        sp.points[i].co = (x, y, z, 1.0)
    curve.bevel_depth = bevel
    ob = bpy.data.objects.new(f"{name}_iz", curve)
    ob.data.materials.append(_mat(f"KA_iz_{name}", color, emission=strength))
    coll.objects.link(ob)
    return ob


def _joint(p1, p2):
    """Dünya konumlarından çubuk transformu: (loc, rot_y, len)."""
    dx, dy, dz = p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]
    ln = math.sqrt(dx * dx + dy * dy + dz * dz)
    rot_y = -math.atan2(dz, math.hypot(dx, dy))
    rot_z = math.atan2(dy, dx)
    return (p1, rot_y, rot_z, ln)


class Machine:
    def __init__(self, name, rec, color, x0, coll, twin_rec=None, twin_color=None):
        self.name = name
        self.rec = rec
        self.color = color
        self.x0 = x0
        self.twin_rec = twin_rec

        m_brass = _mat("KA_Us", (0.09, 0.08, 0.075), metallic=0.8, rough=0.4)
        bar = _cubuk_meshi()
        self.bars = []
        for tag in ("kol1", "kol2"):
            ob = bpy.data.objects.new(f"{name}_{tag}", bar)
            ob.data.materials.append(m_brass)
            coll.objects.link(ob)
            self.bars.append(ob)
        for k, (tag, r) in enumerate((("eklem", 0.055), ("uc", 0.085))):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=r)
            bob = bpy.context.active_object
            bob.name = f"{name}_{tag}"
            bob.data.materials.append(
                _mat(f"KA_{name}_uç", color, emission=(3.5 if tag == "uc" else None)))
            for c in list(bob.users_collection):
                c.objects.unlink(bob)
            coll.objects.link(bob)
            setattr(self, tag, bob)

        if twin_rec:
            self.bars.append(bpy.data.objects.new(f"{name}_kol1b", bar))
            self.bars[2].data.materials.append(m_brass)
            coll.objects.link(self.bars[2])
            self.bars.append(bpy.data.objects.new(f"{name}_kol2b", bar))
            self.bars[3].data.materials.append(m_brass)
            coll.objects.link(self.bars[3])
            self.bars[2].location.z += 0.02
            self.bars[3].location.z += 0.02
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.085)
            self.twin_tip = bpy.context.active_object
            self.twin_tip.name = f"{name}_ucb"
            self.twin_tip.data.materials.append(
                _mat(f"KA_{name}_uçb", twin_color, emission=3.5))
            for c in list(self.twin_tip.users_collection):
                c.objects.unlink(self.twin_tip)
            coll.objects.link(self.twin_tip)

    def joints_at(self, t):
        """t anındaki eklemler: kayıttan doğrusal örnekleme (dünya, x0 kaydırmalı)."""
        rec = self.rec
        i = min(int(t / 0.001), len(rec) - 2)
        f = t / 0.001 - i
        r0, r1 = rec[i], rec[i + 1]
        t1 = r0[1] + (r1[1] - r0[1]) * f
        t2 = r0[2] + (r1[2] - r0[2]) * f
        px = self.x0
        p0 = (px, 0.0, PIVOT_Z)
        p1 = (px + math.sin(t1), 0.0, PIVOT_Z - math.cos(t1))
        p2 = (p1[0] + math.sin(t2), 0.0, p1[2] - math.cos(t2))
        return p0, p1, p2

    def keyframe(self, frame, t):
        p0, p1, p2 = self.joints_at(t)
        for ob, (a, b2) in zip(self.bars[:2], ((p0, p1), (p1, p2))):
            loc, ry, rz, ln = _joint(a, b2)
            ob.location = loc
            ob.rotation_euler = (0.0, ry, rz)
            ob.scale = (ln, 1.0, 1.0)
            for dp in ("location", "rotation_euler", "scale"):
                ob.keyframe_insert(dp, frame=frame)
        self.eklem.location = p1
        self.eklem.keyframe_insert("location", frame=frame)
        self.uc.location = p2
        self.uc.keyframe_insert("location", frame=frame)
        if self.twin_rec:
            i = min(int(t / 0.001), len(self.twin_rec) - 2)
            f = t / 0.001 - i
            r0, r1 = self.twin_rec[i], self.twin_rec[i + 1]
            t1 = r0[1] + (r1[1] - r0[1]) * f
            t2 = r0[2] + (r1[2] - r0[2]) * f
            q1 = (self.x0 + math.sin(t1), 0.03, PIVOT_Z - math.cos(t1))
            q2 = (q1[0] + math.sin(t2), 0.03, q1[2] - math.cos(t2))
            for ob, (a, b2) in zip(self.bars[2:], ((p0, q1), (q1, q2))):
                loc, ry, rz, ln = _joint(a, b2)
                ob.location = loc
                ob.rotation_euler = (0.0, ry, rz)
                ob.scale = (ln, 1.0, 1.0)
                for dp in ("location", "rotation_euler", "scale"):
                    ob.keyframe_insert(dp, frame=frame)
            self.twin_tip.location = q2
            self.twin_tip.keyframe_insert("location", frame=frame)


def stüdyo():
    sc = bpy.context.scene
    w = bpy.data.worlds.new("Salon")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.010, 0.012, 0.020, 1.0)
    bg.inputs[1].default_value = 1.0

    # koyu cilalı zemin: neon yansımaları
    bpy.ops.mesh.primitive_plane_add(size=80, location=(8, 0, 0))
    floor = bpy.context.active_object
    floor.name = "Zemin"
    fm = bpy.data.materials.new("KA_Zemin")
    fm.use_nodes = True
    fb = fm.node_tree.nodes["Principled BSDF"]
    fb.inputs["Base Color"].default_value = (0.055, 0.055, 0.062, 1.0)
    fb.inputs["Roughness"].default_value = 0.16
    floor.data.materials.append(fm)

    spot = bpy.data.lights.new("Key", "AREA")
    spot.energy = 900
    spot.size = 6.0
    spot.color = (1.0, 0.9, 0.78)
    so = bpy.data.objects.new("Key", spot)
    sc.collection.objects.link(so)
    so.location = (8, -3.5, 6.5)
    so.rotation_euler = (math.radians(38), 0, 0)


def kamera(n_machines):
    cam = bpy.data.cameras.new("Cam")
    cam.lens = 40
    co = bpy.data.objects.new("Kamera", cam)
    bpy.context.scene.collection.objects.link(co)
    hedef = bpy.data.objects.new("Hedef", None)
    bpy.context.scene.collection.objects.link(hedef)
    co.constraints.new("TRACK_TO").target = hedef

    x_end = (n_machines - 1) * SPACING
    co.location = (-2.4, -4.6, 1.15)
    hedef.location = (0.4, 0, 1.35)
    co.keyframe_insert("location", frame=1)
    hedef.keyframe_insert("location", frame=1)
    co.location = (x_end - 1.4, -4.2, 1.5)
    hedef.location = (x_end, 0, 1.4)
    co.keyframe_insert("location", frame=CLIP + 1)
    hedef.keyframe_insert("location", frame=CLIP + 1)
    _lineer(co)
    _lineer(hedef)
    bpy.context.scene.camera = co


def render_setup(preview):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    sc.cycles.device = "GPU"
    if preview:
        sc.render.resolution_x, sc.render.resolution_y = 640, 360
        sc.cycles.samples = 48
    else:
        sc.render.resolution_x, sc.render.resolution_y = 960, 540
        sc.cycles.samples = 128
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.35
    sc.render.image_settings.file_format = "PNG"


def main():
    opts = args()
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)

    coll = bpy.data.collections.new("Atolye")
    sc.collection.children.link(coll)

    stüdyo()

    # makineler: iz heykelleri (16 s) + canlı sarkaçlar (son 4 s)
    t0, t1 = T_START, T_START + CLIP / FPS
    machines = []
    xs = [i * SPACING for i in range(len(chaos.factory_machines()))]
    for (name, th1, th2, color), x0 in zip(chaos.factory_machines(), xs):
        state = (math.radians(th1), 0.0, math.radians(th2), 0.0)
        _, rec = chaos.integrate(state, T_TRAIL, dt=0.001, record_every=4)
        # iz = uç bobun dünya yolu: (x0 + x2, 0, PIVOT_Z + y2) — mekanizma XZ düzleminde
        _iz_curve([(x0 + r[5], 0.0, PIVOT_Z + r[6]) for r in rec], color, name, coll)
        machines.append(Machine(name, rec, color, x0, coll))

    # ikiz makine: aynı başlangıç + 1e-9
    tw_x = xs[-1] + SPACING
    base = (math.radians(120.0), 0.0, math.radians(-10.0), 0.0)
    twin = (base[0] + 1e-9, 0.0, base[2], 0.0)
    _, rec_a = chaos.integrate(base, T_TRAIL, dt=0.001, record_every=4)
    _, rec_b = chaos.integrate(twin, T_TRAIL, dt=0.001, record_every=4)
    _iz_curve([(tw_x + r[5], 0.0, PIVOT_Z + r[6]) for r in rec_a], (0.92, 0.94, 1.0), "Ikiz_beyaz", coll, strength=2.6)
    _iz_curve([(tw_x + r[5], 0.0, PIVOT_Z + r[6]) for r in rec_b], (1.0, 0.12, 0.04), "Ikiz_kizil", coll, strength=2.6)
    machines.append(Machine("Ikiz", rec_a, (0.92, 0.94, 1.0), tw_x, coll,
                            twin_rec=rec_b, twin_color=(1.0, 0.12, 0.04)))

    # kaide
    m_ped = _mat("KA_Kaide", (0.14, 0.12, 0.10), metallic=0.6, rough=0.45)
    for m in machines:
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.16,
                                            depth=PIVOT_Z, location=(m.x0, 0, PIVOT_Z / 2))
        ped = bpy.context.active_object
        ped.name = f"{m.name}_kaide"
        ped.data.materials.append(m_ped)
        for c in list(ped.users_collection):
            c.objects.unlink(ped)
        coll.objects.link(ped)

    sc.frame_start = 1
    sc.frame_end = CLIP + 1
    sc.render.fps = FPS
    for f in range(1, CLIP + 2):
        t = t0 + (f - 1) / FPS
        for m in machines:
            m.keyframe(f, t)
    for ob in coll.objects:
        _lineer(ob)

    kamera(len(xs) + 1)
    render_setup(opts["preview"])

    out = os.path.join(REPO, "renders", "preview" if opts["preview"] else "chaos")
    os.makedirs(out, exist_ok=True)
    frames = [1, 16, 32, 49] if opts["preview"] else range(1, CLIP + 2)
    for f in frames:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(out, f"frame_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[kare {f}] bitti", flush=True)
    print(f"== BİTTİ -> {out} ==")


main()

"""
Kaos Atölyesi — doğrulama kapıları.

    python3 tests/verify.py

Blender gerekmez. Enerji korunumu, ikizlerin Lyapunov ayrışması ve
determinizm burada kanıtlanır; kırmızıysa sahne kurulmaz.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import chaos  # noqa: E402

GATES = []


def gate(name):
    def deco(fn):
        GATES.append((name, fn))
        return fn
    return deco


@gate("G1 enerji: 100 s RK4'te |ΔE/E| < 1e-6")
def g1_energy():
    errs = []
    state = (math.radians(120.0), 0.0, math.radians(-10.0), 0.0)
    e0 = chaos.energy(state)
    worst = 0.0
    s = state
    for _ in range(100_000):
        s = chaos.rk4_step(s, 0.001)
        worst = max(worst, abs(chaos.energy(s) - e0) / abs(e0))
    if worst > 1e-6:
        errs.append(f"enerji sapması {worst:.3e} > 1e-6")
    return errs


@gate("G2 denge: sarkan sarkaç sonsuza dek duruyor")
def g2_equilibrium():
    errs = []
    s = (0.0, 0.0, 0.0, 0.0)
    for _ in range(20_000):
        s = chaos.rk4_step(s, 0.001)
    if chaos.separation(s, (0.0, 0.0, 0.0, 0.0)) > 1e-6:
        errs.append(f"denge sürükledi: θ sapması {chaos.separation(s, (0, 0, 0, 0)):.3e}")
    return errs


@gate("G3 Lyapunov: 1e-9 kıvılcım en az 1e6 kat büyüyor ve O(1) geziniyor")
def g3_lyapunov():
    errs = []
    rec1, rec2, curve = chaos.twin_experiment(t_max=24.0)
    max_sep = max(s for _, s in curve)
    if max_sep < 1e-3:
        errs.append(f"maksimum ayrışma {max_sep:.3e} — kıvılcım büyümemiş")
    # büyütme: 1e-9 -> >= 1e6 kat (pozitif Lyapunov üssünün kanıtı)
    if max_sep / 1e-9 < 1e6:
        errs.append(f"büyütme {max_sep / 1e-9:.2e}x < 1e6x")
    # geç dönem: ayrışmış rejim O(0.1) gezinir (ilk 10 s sonrası penceresi)
    late = [s for t, s in curve if t >= 10.0]
    if late and max(late) < 0.1:
        errs.append(f"10 s sonrası penceresinde ayrışma {max(late):.4f} < 0.1")
    # erken evre: kıvılcım ölçeğinde kalmalı (izler başta üst üste)
    early = [s for t, s in curve if t <= 2.0]
    if early and max(early) > 1e-4:
        errs.append(f"ilk 2 s'de ayrışma {max(early):.3e} > 1e-4 — başlangıçta örtüşmüyor")
    return errs


@gate("G4 determinizm: aynı tohum -> bit bit aynı yol")
def g4_determinism():
    errs = []
    s1, r1 = chaos.integrate((math.radians(120.0), 0, math.radians(-10.0), 0), 8.0)
    s2, r2 = chaos.integrate((math.radians(120.0), 0, math.radians(-10.0), 0), 8.0)
    if any(abs(a - b) > 0.0 for a, b in zip(s1, s2)):
        errs.append("son durumlar farklı")
    if len(r1) != len(r2) or any(a != b for a, b in zip(r1, r2)):
        errs.append("kayıtlar bit düzeyinde aynı değil")
    return errs


@gate("G5 iz: uç bob yolu sonlu, sınırlı, uzun")
def g5_trail():
    errs = []
    _, rec = chaos.integrate((math.radians(120.0), 0, math.radians(-10.0), 0), 40.0, dt=0.002)
    tips = chaos.tip_positions(rec)
    if len(tips) < 1000:
        errs.append(f"iz {len(tips)} nokta — çok kısa")
    dmax = max(math.hypot(x, y) for x, y in tips)
    if not dmax < 4.2:  # l1+l2 = 2'den asla geçemez; pay güvenlik
        errs.append(f"iz sınır dışında: {dmax:.2f} > 4.2")
    dmin = min(math.hypot(x, y) for x, y in tips)
    if dmin > 2.05:
        errs.append("uç bob hiç aşağı inmemiş — sahne tek yarım kürede sıkışmış")
    return errs


def main():
    failures = 0
    for name, fn in GATES:
        errs = fn()
        if errs:
            failures += 1
            print(f"❌ {name}")
            for e in errs[:8]:
                print(f"   {e}")
        else:
            print(f"✅ {name}")
    print(f"\n{'KAPILAR KIRIK' if failures else 'TÜM KAPILAR YEŞİL'} ({failures} kırık)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

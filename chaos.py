"""
Kaos Atölyesi — çift sarkaç çekirdeği (saf matematik).

Blender'a bağımlılığı yok; tests/verify.py kapıları doğrudan bu modülü test eder.
Kural: her konum RK4'ün gerçek çözümüdür — keyframe hilesi yok, easing yok.
Hikâye: 1e-9 farklı başlayan ikizler önce aynı yerde, sonra bir daha asla
buluşamaz — Lyapunov ayrışması kapılarla kanıtlanır.
"""

import math

G = 9.81
M1 = M2 = 1.0
L1 = L2 = 1.0


def deriv(state):
    """Çift sarkaç Lagrange denklemleri: (th1, w1, th2, w2) -> türevleri."""
    t1, w1, t2, w2 = state
    d = t1 - t2
    den = 2.0 * M1 + M2 - M2 * math.cos(2.0 * d)
    a1 = (-G * (2.0 * M1 + M2) * math.sin(t1)
          - M2 * G * math.sin(t1 - 2.0 * t2)
          - 2.0 * math.sin(d) * M2 * (w2 * w2 * L2 + w1 * w1 * L1 * math.cos(d))
          ) / (L1 * den)
    a2 = (2.0 * math.sin(d) * (w1 * w1 * L1 * (M1 + M2)
                               + G * (M1 + M2) * math.cos(t1)
                               + w2 * w2 * L2 * M2 * math.cos(d))
          ) / (L2 * den)
    return (w1, a1, w2, a2)


def rk4_step(state, dt):
    k1 = deriv(state)
    k2 = deriv(tuple(s + 0.5 * dt * k for s, k in zip(state, k1)))
    k3 = deriv(tuple(s + 0.5 * dt * k for s, k in zip(state, k2)))
    k4 = deriv(tuple(s + dt * k for s, k in zip(state, k3)))
    return tuple(s + dt / 6.0 * (a + 2 * b + 2 * c + d)
                 for s, a, b, c, d in zip(state, k1, k2, k3, k4))


def integrate(state, t_total, dt=0.001, record_every=1):
    """state'i t_total süreye kadar entegre et; (son state, kayıt listesi).

    Kayıt: [(t, th1, th2, x1, y1, x2, y2)] — uç bobun (x2, y2) izi neon yol.
    """
    rec = []
    s = tuple(state)
    n = int(round(t_total / dt))
    for i in range(n + 1):
        t = i * dt
        if i % record_every == 0:
            x1 = L1 * math.sin(s[0]); y1 = -L1 * math.cos(s[0])
            x2 = x1 + L2 * math.sin(s[2]); y2 = y1 - L2 * math.cos(s[2])
            rec.append((t, s[0], s[2], x1, y1, x2, y2))
        if i < n:
            s = rk4_step(s, dt)
    return s, rec


def energy(state):
    """Toplam mekanik enerji (potansiyel sıfırı askı noktasında)."""
    t1, w1, t2, w2 = state
    v1sq = L1 * L1 * w1 * w1
    v2sq = L2 * L2 * w2 * w2 + L1 * L1 * w1 * w1 + 2.0 * L1 * L2 * w1 * w2 * math.cos(t1 - t2)
    ke = 0.5 * M1 * v1sq + 0.5 * M2 * v2sq
    pe = -(M1 + M2) * G * L1 * math.cos(t1) - M2 * G * L2 * math.cos(t2)
    return ke + pe


def tip_positions(rec):
    """Kayıttan uç bob izi: [(x2, y2)]."""
    return [(r[5], r[6]) for r in rec]


def separation(s1, s2):
    """Durum uzaklığı: yalnız AÇI farkları (θ1, θ2), 2pi sarmalı düzeltilmiş.

    Hızlar ayrı ölçeklidir — karıştırılırsa 'ayrışma' sahte şişer.
    """
    d = []
    for i in (0, 2):
        x = (s1[i] - s2[i]) % (2 * math.pi)
        if x > math.pi:
            x -= 2 * math.pi
        d.append(x)
    return math.hypot(*d)


def twin_experiment(theta1_deg=120.0, theta2_deg=-10.0, eps=1e-9, t_max=24.0, dt=0.001):
    """Aynı başlangıç + 1e-9 kıvılcım: (iz1, iz2, ayrılma eğrisi [(t, sep)]).

    chaos ikiz serüveninin tamamı bu deneyden çıkar.
    """
    base = (math.radians(theta1_deg), 0.0, math.radians(theta2_deg), 0.0)
    twin = (base[0] + eps, base[1], base[2], base[3])
    s1, rec1 = integrate(base, t_max, dt)
    s2, rec2 = integrate(twin, t_max, dt)
    curve = []
    step = max(1, len(rec1) // 240)
    for i in range(0, len(rec1), step):
        j = min(i, len(rec2) - 1)
        # durum uzaklığı: kayıtlardan açıları geri kur
        sep = separation((rec1[i][1], 0, rec1[i][2], 0), (rec2[j][1], 0, rec2[j][2], 0))
        curve.append((rec1[i][0], sep))
    return rec1, rec2, curve


def factory_machines():
    """Atölyedeki makineler: (ad, th1_deg, th2_deg, neon rengi)."""
    return [
        ("Kırmızı", 120.0, -10.0, (1.0, 0.16, 0.05)),
        ("Amber", 95.0, 25.0, (1.0, 0.55, 0.05)),
        ("Yeşil", 150.0, -35.0, (0.15, 1.0, 0.35)),
        ("Buz", 105.0, 8.0, (0.25, 0.75, 1.0)),
        ("Mor", 135.0, 60.0, (0.75, 0.25, 1.0)),
    ]

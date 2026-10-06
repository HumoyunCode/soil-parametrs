# -*- coding: utf-8 -*-
"""
ekin_tavsiya.py - Tuproq ma'lumotlari asosida ekin moslik indeksini hisoblash moduli.

Model (PhD tadqiqoti uchun gibrid faziy-kosinus modeli):
    mu_i      = faziy a'zolik funksiyasi, [0, 1]   (i = pH, gumus, tekstura)
    K_hard    = 0, agar mu_pH = 0, aks holda 1
    Sim_w     = sum(w_i * mu_i) / ( sqrt(sum(w_i * mu_i^2)) * sqrt(sum(w_i)) )
    Lambda    = min(mu_i)
    S_final   = K_hard * Sim_w * Lambda^gamma
"""
from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

# =====================================================================
# 1. SOZLAMALAR (Maqola uchun asoslanadigan parametrlar)
# =====================================================================

# Qaysi chuqurlik oralig'i olinadi (sm). Qatlam qalinligi bo'yicha vaznli o'rtacha.
CHUQURLIK_DAN = 0
CHUQURLIK_GACHA = 30

# Parametr vaznlari (yig'indisi 1 ga keltiriladi)
VAZNLAR = {"ph": 0.4, "gumus": 0.3, "tekstura": 0.3}

# Libix kuchi
GAMMA = 0.3  # [0.2 ; 0.5]

# pH trapesiyasi: a = b - PH_CHEKKA, d = c + PH_CHEKKA
PH_CHEKKA = 1.0

# Gumus: x_crit = GUMUS_KRIT_NISBAT * x_opt
GUMUS_KRIT_NISBAT = 0.5

# Tekstura bali: optimal sinfdan sinf-masofa -> ball
TEKSTURA_BALL = {0: 1.0, 1: 0.6, 2: 0.2}  # 2 va undan uzoq = 0.2

# pH shu qiymatdan yuqori bo'lsa sho'rlanish xavfi haqida ogohlantirish beriladi
PH_SHORLANISH_OGOHLANTIRISH = 8.2

# Tekstura sinflari (yengildan og'irga). USDA sinfi -> milliy sinf raqami
MILLIY_SINF_NOMI = {
    1: "qum",
    2: "yengil qumloq",
    3: "qumloq",
    4: "yengil qumoq",
    5: "o'rta qumoq",
    6: "og'ir qumoq",
    7: "gil",
}
USDA_MILLIY = {
    "sand": 1,
    "loamy sand": 2,
    "sandy loam": 3,
    "sandy clay loam": 4,
    "loam": 5,
    "silt loam": 5,
    "silt": 5,
    "clay loam": 6,
    "silty clay loam": 6,
    "sandy clay": 7,
    "silty clay": 7,
    "clay": 7,
}

# Ekinlar: jadvaldan.
#   ph     = (b, c)  optimal oraliq
#   gumus  = x_opt   (jadvaldagi pastki chegara)
#   tekstura = optimal milliy sinflar to'plami
EKINLAR: Dict[str, dict] = {
    "Kuzgi bug'doy": {"ph": (6.5, 7.5), "gumus": 1.2, "tekstura": {5, 6}},
    "G'o'za (paxta)": {"ph": (6.8, 8.0), "gumus": 1.0, "tekstura": {5}},
    "Makkajo'xori (don)": {"ph": (6.5, 7.5), "gumus": 1.5, "tekstura": {5}},
    "Mosh (takroriy)": {"ph": (6.5, 7.8), "gumus": 0.8, "tekstura": {4, 5}},
    "Yeryong'oq": {"ph": (6.0, 7.0), "gumus": 1.0, "tekstura": {2, 3, 4}},
    "Loviya": {"ph": (6.2, 7.2), "gumus": 1.2, "tekstura": {5}},
    "Soya": {"ph": (6.5, 7.5), "gumus": 1.5, "tekstura": {5}},
    "Kungaboqar": {"ph": (6.5, 8.0), "gumus": 1.0, "tekstura": {4, 5}},
    "Sabzi": {"ph": (6.0, 7.0), "gumus": 1.2, "tekstura": {3, 4}},
    "Kartoshka": {"ph": (5.5, 6.5), "gumus": 1.5, "tekstura": {4, 5}},
}

# =====================================================================
# 2. FAZIY A'ZOLIK FUNKSIYALARI
# =====================================================================


def trapesiya(x: float, a: float, b: float, c: float, d: float) -> float:
    """Ikki tomonlama chegaralangan parametr (pH). a<b<=c<d."""
    if not (a < b <= c < d):
        raise ValueError(f"Trapesiya chegaralari noto'g'ri: a={a}, b={b}, c={c}, d={d}")
    if x < a or x > d:
        return 0.0
    if x < b:
        return (x - a) / (b - a)
    if x <= c:
        return 1.0
    return (d - x) / (d - c)


def osuvchi(x: float, x_krit: float, x_opt: float) -> float:
    """O'suvchi parametr (gumus). x<=x_krit -> 0, x>=x_opt -> 1."""
    if not x_krit < x_opt:
        raise ValueError(f"x_krit < x_opt bo'lishi kerak: {x_krit}, {x_opt}")
    if x <= x_krit:
        return 0.0
    if x >= x_opt:
        return 1.0
    return (x - x_krit) / (x_opt - x_krit)


def vaznli_kosinus(mu: List[float], w: List[float]) -> float:
    """
    Vaznli kosinus o'xshashlik, ideal vektor R* = [1,...,1]:
        sum(w*mu*1) / ( sqrt(sum(w*mu^2)) * sqrt(sum(w*1^2)) )
    """
    if len(mu) != len(w):
        raise ValueError("mu va w uzunliklari teng emas")
    surat = sum(wi * mi for wi, mi in zip(w, mu))
    maxraj = math.sqrt(sum(wi * mi * mi for wi, mi in zip(w, mu))) * math.sqrt(sum(w))
    if maxraj == 0.0:
        return 0.0
    return min(1.0, surat / maxraj)  # suzuvchi nuqta xatosini kesish


# =====================================================================
# 3. TEKSTURA: USDA uchburchagi -> milliy sinf
# =====================================================================


def usda_sinf(qum: float, chang: float, gil: float) -> str:
    """USDA tekstura uchburchagi bo'yicha sinf (sand, silt, clay - %)."""
    sand, silt, clay = qum, chang, gil
    if silt + 1.5 * clay < 15:
        return "sand"
    if silt + 1.5 * clay >= 15 and silt + 2 * clay < 30:
        return "loamy sand"
    if (7 <= clay < 20 and sand > 52 and silt + 2 * clay >= 30) or (
        clay < 7 and silt < 50 and silt + 2 * clay >= 30
    ):
        return "sandy loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "loam"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "silt loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "sandy clay loam"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "clay loam"
    if 27 <= clay < 40 and sand <= 20:
        return "silty clay loam"
    if clay >= 35 and sand > 45:
        return "sandy clay"
    if clay >= 40 and silt >= 40:
        return "silty clay"
    if clay >= 40 and sand <= 45 and silt < 40:
        return "clay"
    raise ValueError(f"Tekstura sinfi aniqlanmadi: sand={sand}, silt={silt}, clay={clay}")


def tekstura_bali(sinf_raqami: int, optimal: set) -> float:
    masofa = min(abs(sinf_raqami - o) for o in optimal)
    return TEKSTURA_BALL.get(masofa, min(TEKSTURA_BALL.values()))


# =====================================================================
# 4. KIRISH MA'LUMOTLARINI O'QISH VA QATLAMLARNI BIRLASHTIRISH
# =====================================================================

_ALIAS = {
    "ph": ("phh2o", "ph", "pH"),
    "gumus": ("gumus", "humus"),
    "soc": ("soc",),
    "clay": ("clay", "gil", "loy"),
    "sand": ("sand", "qum"),
    "silt": ("silt", "chang"),
}


def _chuqurlik(kalit) -> Tuple[float, float]:
    sonlar = re.findall(r"\d+(?:[.,]\d+)?", str(kalit))
    if len(sonlar) != 2:
        raise ValueError(f"Chuqurlik kaliti tushunarsiz: {kalit!r} (masalan '0-5 cm' yoki '0-5cm')")
    a, b = (float(s.replace(",", ".")) for s in sonlar)
    if not a < b:
        raise ValueError(f"Chuqurlik noto'g'ri: {kalit!r}")
    return a, b


def _qiymat(qatlam: dict, nom: str) -> Optional[float]:
    """Qatlamdan qiymatni ajratib oladi (oddiy son yoki dict {'value': ...} bo'lsa ham qabul qiladi)."""
    for k in _ALIAS[nom]:
        if k in qatlam and qatlam[k] is not None:
            val = qatlam[k]
            if isinstance(val, dict) and "value" in val:
                val = val["value"]
            try:
                v = float(val)
                if math.isnan(v):
                    return None
                return v
            except (ValueError, TypeError):
                continue
    return None


def _qatlamlar(tuproq) -> List[Tuple[float, float, dict]]:
    """dict {'0-5 cm': {...}} yoki list [{'depth': '0-5 cm', ...}] qabul qiladi."""
    chiqish = []
    if isinstance(tuproq, dict):
        for k, v in tuproq.items():
            a, b = _chuqurlik(k)
            chiqish.append((a, b, v))
    else:
        for v in tuproq:
            kalit = v.get("depth", v.get("chuqurlik"))
            a, b = _chuqurlik(kalit)
            chiqish.append((a, b, v))
    chiqish.sort(key=lambda t: t[0])
    return chiqish


@dataclass
class Profil:
    ph: float
    gumus: float
    gil: float
    qum: float
    chang: float
    usda: str
    milliy_sinf: int
    ogohlantirishlar: List[str] = field(default_factory=list)
    ph_qatlamlar: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ph": round(self.ph, 2),
            "gumus": round(self.gumus, 2),
            "gil": round(self.gil, 1),
            "qum": round(self.qum, 1),
            "chang": round(self.chang, 1),
            "usda": self.usda,
            "milliy_sinf": self.milliy_sinf,
            "milliy_nom": MILLIY_SINF_NOMI.get(self.milliy_sinf, ""),
            "ogohlantirishlar": self.ogohlantirishlar,
            "ph_qatlamlar": self.ph_qatlamlar,
        }


def profil_tayyorla(tuproq, dan: float = CHUQURLIK_DAN, gacha: float = CHUQURLIK_GACHA) -> Profil:
    qatlamlar = [q for q in _qatlamlar(tuproq) if q[0] >= dan and q[1] <= gacha]
    if not qatlamlar:
        raise ValueError(f"{dan}-{gacha} sm oralig'ida qatlam topilmadi")
    # uzluksiz qoplanganini tekshirish
    joy = dan
    for a, b, _ in qatlamlar:
        if abs(a - joy) > 1e-9:
            raise ValueError(f"Qatlamlar orasida bo'shliq/ustma-ust tushish: {joy} sm dan {a} sm gacha")
        joy = b
    if abs(joy - gacha) > 1e-9:
        raise ValueError(f"Qatlamlar {gacha} sm gacha yetmaydi (oxirgisi {joy} sm)")

    ogoh: List[str] = []
    jami = gacha - dan
    yig = {"ph": 0.0, "gumus": 0.0, "clay": 0.0, "sand": 0.0, "silt": 0.0}
    for a, b, q in qatlamlar:
        vazn = (b - a) / jami
        belgi = f"{a:g}-{b:g} sm"
        v = {n: _qiymat(q, n) for n in ("ph", "gumus", "soc", "clay", "sand", "silt")}
        if v["gumus"] is None:
            if v["soc"] is None:
                raise ValueError(f"{belgi}: gumus ham, soc ham yo'q")
            # SOC (g/kg) -> gumus (%): soc/10 * 1.724 (Van Bemmelen koeffitsiyenti)
            v["gumus"] = v["soc"] / 10.0 * 1.724
            ogoh.append(f"{belgi}: gumus yo'q, soc dan hisoblandi (soc/10*1.724)")
        for n in ("ph", "clay", "sand", "silt"):
            if v[n] is None:
                raise ValueError(f"{belgi}: '{n}' qiymati yo'q")
        if not 3.0 <= v["ph"] <= 11.0:
            raise ValueError(f"{belgi}: pH={v['ph']} real oraliqdan tashqarida (3-11)")
        if not 0.0 <= v["gumus"] <= 30.0:
            raise ValueError(f"{belgi}: gumus={v['gumus']} % real oraliqdan tashqarida")
        for n in ("clay", "sand", "silt"):
            if not 0.0 <= v[n] <= 100.0:
                raise ValueError(f"{belgi}: {n}={v[n]} 0-100 oralig'idan tashqarida")
        s = v["clay"] + v["sand"] + v["silt"]
        if abs(s - 100.0) > 10.0:
            raise ValueError(f"{belgi}: clay+sand+silt={s:.1f}, 100 ga yaqin emas")
        if abs(s - 100.0) > 2.0:
            ogoh.append(f"{belgi}: clay+sand+silt={s:.1f} (100 ga normallashtirildi)")
        for n in yig:
            yig[n] += vazn * v[n]

    # Birlashgan tekstura yig'indisini 100 ga keltirish
    s = yig["clay"] + yig["sand"] + yig["silt"]
    gil, qum, chang = (yig[n] * 100.0 / s for n in ("clay", "sand", "silt"))

    usda = usda_sinf(qum, chang, gil)
    ph_q = {}
    for a, b, q in _qatlamlar(tuproq):
        p = _qiymat(q, "ph")
        if p is not None:
            ph_q[f"{a:g}-{b:g}"] = p
    yuqori = [k for k, p in ph_q.items() if p > PH_SHORLANISH_OGOHLANTIRISH]
    if yuqori:
        ogoh.append(
            f"pH > {PH_SHORLANISH_OGOHLANTIRISH} qatlamlar: {', '.join(yuqori)} sm. "
            "Sho'rlanish xavfi bor, EC o'lchanmagan (modelga kirmagan)"
        )
    return Profil(yig["ph"], yig["gumus"], gil, qum, chang, usda, USDA_MILLIY[usda], ogoh, ph_q)


# =====================================================================
# 5. EKINNI BAHOLASH
# =====================================================================


@dataclass
class EkinNatija:
    ekin: str
    mu_ph: float
    mu_gumus: float
    mu_tekstura: float
    k_hard: int
    sim: float
    libix: float
    s_final: float
    vaznli_ortacha: float  # diagnostika uchun (modelga kirmaydi)
    izoh: str = ""
    status: str = "suitable"  # optimal, moderate, low, rejected

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ekin": self.ekin,
            "mu_ph": round(self.mu_ph, 3),
            "mu_gumus": round(self.mu_gumus, 3),
            "mu_tekstura": round(self.mu_tekstura, 3),
            "k_hard": self.k_hard,
            "sim": round(self.sim, 3),
            "libix": round(self.libix, 3),
            "s_final": round(self.s_final, 3),
            "percent": round(self.s_final * 100.0, 1),
            "vaznli_ortacha": round(self.vaznli_ortacha, 3),
            "izoh": self.izoh,
            "status": self.status,
        }


def _vaznlar() -> Tuple[List[str], List[float]]:
    nomlar = ["ph", "gumus", "tekstura"]
    yig = sum(VAZNLAR[n] for n in nomlar)
    if yig <= 0:
        raise ValueError("Vaznlar yig'indisi musbat bo'lishi kerak")
    return nomlar, [VAZNLAR[n] / yig for n in nomlar]


def ekinni_ball(p: Profil, nom: str, talab: dict, gamma: float = GAMMA) -> EkinNatija:
    b, c = talab["ph"]
    mu_ph = trapesiya(p.ph, b - PH_CHEKKA, b, c, c + PH_CHEKKA)
    x_opt = talab["gumus"]
    mu_g = osuvchi(p.gumus, GUMUS_KRIT_NISBAT * x_opt, x_opt)
    mu_t = tekstura_bali(p.milliy_sinf, talab["tekstura"])

    mu = [mu_ph, mu_g, mu_t]
    _, w = _vaznlar()
    k_hard = 0 if mu_ph == 0.0 else 1
    sim = vaznli_kosinus(mu, w)
    libix = min(mu)
    s = k_hard * sim * (libix ** gamma)
    ortacha = sum(wi * mi for wi, mi in zip(w, mu))

    izoh = ""
    if k_hard == 0:
        izoh = f"pH={p.ph:.2f} ekin uchun yaroqsiz (qat'iy to'siq)"
        status = "rejected"
    else:
        nomlar = {0: "pH", 1: "gumus", 2: "tekstura"}
        i = mu.index(libix)
        if libix < 1.0:
            izoh = f"Cheklovchi omil: {nomlar[i]} (mu={libix:.2f})"
        else:
            izoh = "Barcha omillar optimal darajada"
        
        if s >= 0.80:
            status = "optimal"
        elif s >= 0.50:
            status = "moderate"
        else:
            status = "low"

    return EkinNatija(nom, mu_ph, mu_g, mu_t, k_hard, sim, libix, s, ortacha, izoh, status)


def profil_qatlamdan(qatlam: dict, depth_label: str = "Qatlam") -> Profil:
    """Yagona qatlam ma'lumotidan (masalan 0-5cm yoki 30-60cm) Profil obyektini tuzadi."""
    v = {n: _qiymat(qatlam, n) for n in ("ph", "gumus", "soc", "clay", "sand", "silt")}
    if v["gumus"] is None:
        if v["soc"] is not None:
            v["gumus"] = v["soc"] / 10.0 * 1.724
        else:
            v["gumus"] = 1.0
    if v["ph"] is None:
        v["ph"] = 7.5
    for n in ("clay", "sand", "silt"):
        if v[n] is None:
            v[n] = 33.3

    s = v["clay"] + v["sand"] + v["silt"]
    if s > 0:
        gil, qum, chang = (v[n] * 100.0 / s for n in ("clay", "sand", "silt"))
    else:
        gil, qum, chang = 20.0, 40.0, 40.0

    usda = usda_sinf(qum, chang, gil)
    milliy_sinf = USDA_MILLIY[usda]

    ogoh: List[str] = []
    if v["ph"] > PH_SHORLANISH_OGOHLANTIRISH:
        ogoh.append(
            f"pH ({v['ph']:.2f}) > {PH_SHORLANISH_OGOHLANTIRISH} ({depth_label}). "
            "Ushbu qatlamda ishqoriy sho'rlanish xavfi mavjud!"
        )
    return Profil(
        ph=v["ph"],
        gumus=v["gumus"],
        gil=gil,
        qum=qum,
        chang=chang,
        usda=usda,
        milliy_sinf=milliy_sinf,
        ogohlantirishlar=ogoh,
        ph_qatlamlar={depth_label: v["ph"]},
    )


def tavsiya_qatlam(qatlam: dict, depth_label: str = "Qatlam", gamma: float = GAMMA) -> dict:
    """Alohida bitta chuqurlik qatlami uchun ekinlar mosligini hisoblaydi."""
    p = profil_qatlamdan(qatlam, depth_label)
    natijalar = [ekinni_ball(p, nom, t, gamma) for nom, t in EKINLAR.items()]
    natijalar.sort(key=lambda r: (r.s_final, r.libix, r.sim, r.vaznli_ortacha), reverse=True)
    return {
        "profil": p,
        "natijalar": natijalar,
        "gamma": gamma,
        "profil_dict": p.to_dict(),
        "natijalar_list": [r.to_dict() for r in natijalar],
    }


def tavsiya_ber(tuproq, gamma: float = GAMMA) -> dict:
    """Asosiy funksiya. tuproq - dasturdan olingan ma'lumot (dict yoki list)."""
    if not 0.0 <= gamma <= 1.0:
        raise ValueError("gamma [0, 1] oralig'ida bo'lishi kerak")
    p = profil_tayyorla(tuproq)
    natijalar = [ekinni_ball(p, nom, t, gamma) for nom, t in EKINLAR.items()]
    natijalar.sort(key=lambda r: (r.s_final, r.libix, r.sim, r.vaznli_ortacha), reverse=True)
    return {
        "profil": p,
        "natijalar": natijalar,
        "gamma": gamma,
        # JSON API va frontend uchun qulay qism
        "profil_dict": p.to_dict(),
        "natijalar_list": [r.to_dict() for r in natijalar],
    }


def natijani_chiqar(res: dict) -> None:
    p: Profil = res["profil"]
    print(f"\nTuproq profili ({CHUQURLIK_DAN}-{CHUQURLIK_GACHA} sm, qalinlik bo'yicha vaznli o'rtacha)")
    print(f"  pH = {p.ph:.2f} | gumus = {p.gumus:.2f} % | gil = {p.gil:.1f} % | "
          f"qum = {p.qum:.1f} % | chang = {p.chang:.1f} %")
    print(f"  Tekstura: {p.usda} -> {MILLIY_SINF_NOMI[p.milliy_sinf]} ({p.milliy_sinf}-sinf)")
    print(f"  gamma = {res['gamma']}, vaznlar = {VAZNLAR}\n")
    bosh = f"{'No':>2}  {'Ekin':<20} {'mu_pH':>6} {'mu_gum':>7} {'mu_tek':>7} {'K':>2} " \
           f"{'Sim':>6} {'Lambda':>7} {'S_final':>8}  Izoh"
    print(bosh)
    print("-" * len(bosh) + "-" * 30)
    for i, r in enumerate(res["natijalar"], 1):
        print(f"{i:>2}  {r.ekin:<20} {r.mu_ph:>6.2f} {r.mu_gumus:>7.2f} {r.mu_tekstura:>7.2f} "
              f"{r.k_hard:>2} {r.sim:>6.3f} {r.libix:>7.3f} {r.s_final:>8.3f}  {r.izoh}")
    if p.ogohlantirishlar:
        print("\nOgohlantirishlar:")
        for o in p.ogohlantirishlar:
            print("  -", o)
    print("\nEslatma: tavsiya faqat pH, gumus va tekstura bo'yicha. Sho'rlanish (EC), NPK, "
          "iqlim va suv ta'minoti hisobga olinmagan.")


# =====================================================================
# 6. O'Z-O'ZINI TEKSHIRISH
# =====================================================================

DEMO = {
    "0-5 cm":    {"phh2o": 8.0, "gumus": 1.4, "clay": 22, "sand": 30, "silt": 48},
    "5-15 cm":   {"phh2o": 8.1, "gumus": 1.2, "clay": 23, "sand": 29, "silt": 48},
    "15-30 cm":  {"phh2o": 8.1, "gumus": 0.9, "clay": 24, "sand": 28, "silt": 48},
    "30-60 cm":  {"phh2o": 8.3, "gumus": 0.6, "clay": 25, "sand": 27, "silt": 48},
    "60-100 cm": {"phh2o": 8.4, "gumus": 0.4, "clay": 26, "sand": 26, "silt": 48},
}


def _yaqin(a, b, tol=1e-9):
    return abs(a - b) <= tol


def sinov() -> None:
    import random

    # 1. Trapesiya
    assert _yaqin(trapesiya(5.8, 5.8, 6.8, 8.0, 9.0), 0.0)
    assert _yaqin(trapesiya(6.3, 5.8, 6.8, 8.0, 9.0), 0.5)
    assert _yaqin(trapesiya(7.0, 5.8, 6.8, 8.0, 9.0), 1.0)
    assert _yaqin(trapesiya(8.5, 5.8, 6.8, 8.0, 9.0), 0.5)
    assert _yaqin(trapesiya(9.1, 5.8, 6.8, 8.0, 9.0), 0.0)
    # 2. O'suvchi
    assert _yaqin(osuvchi(0.5, 0.5, 1.0), 0.0)
    assert _yaqin(osuvchi(0.75, 0.5, 1.0), 0.5)
    assert _yaqin(osuvchi(2.0, 0.5, 1.0), 1.0)
    # 3. Kosinus: qo'lda hisoblangan misollar
    assert _yaqin(vaznli_kosinus([0.2, 0.2, 0.2], [1/3] * 3), 1.0)
    assert _yaqin(vaznli_kosinus([1, 1, 0.2], [1/3] * 3), 2.2 / 3 / math.sqrt(2.04 / 3), 1e-12)
    assert vaznli_kosinus([0, 0, 0], [0.4, 0.3, 0.3]) == 0.0
    # 4. Kosinus har doim [0,1] ichida (tasodifiy tekshiruv)
    rnd = random.Random(1)
    for _ in range(20000):
        mu = [rnd.random() for _ in range(3)]
        w = [rnd.random() + 1e-6 for _ in range(3)]
        s = sum(w)
        w = [x / s for x in w]
        v = vaznli_kosinus(mu, w)
        assert 0.0 <= v <= 1.0
    # 5. USDA uchburchagi: butun to'r bo'yicha sinf aniqlanishi
    for qum in range(0, 101):
        for gil in range(0, 101 - qum):
            usda_sinf(qum, 100 - qum - gil, gil)
    assert usda_sinf(90, 5, 5) == "sand"
    assert usda_sinf(40, 40, 20) == "loam"
    assert usda_sinf(20, 65, 15) == "silt loam"
    assert usda_sinf(33, 34, 33) == "clay loam"
    assert usda_sinf(20, 20, 60) == "clay"
    assert usda_sinf(65, 25, 10) == "sandy loam"
    for sinf in USDA_MILLIY:  # xarita to'liqligi
        assert sinf in USDA_MILLIY
    # 6. Qatlamlarni birlashtirish: (7*5 + 8*10 + 8*15) / 30
    t = {
        "0-5 cm": {"phh2o": 7, "gumus": 1, "clay": 20, "sand": 40, "silt": 40},
        "5-15 cm": {"phh2o": 8, "gumus": 1, "clay": 20, "sand": 40, "silt": 40},
        "15-30 cm": {"phh2o": 8, "gumus": 1, "clay": 20, "sand": 40, "silt": 40},
    }
    p = profil_tayyorla(t)
    assert _yaqin(p.ph, (7 * 5 + 8 * 10 + 8 * 15) / 30, 1e-12)
    assert p.usda == "loam" and p.milliy_sinf == 5
    # 7. Qo'lda hisob: g'o'za, pH 8.5, gumus 0.75, silt loam
    t = {
        "0-5 cm": {"phh2o": 8.5, "gumus": 0.75, "clay": 15, "sand": 20, "silt": 65},
        "5-15 cm": {"phh2o": 8.5, "gumus": 0.75, "clay": 15, "sand": 20, "silt": 65},
        "15-30 cm": {"phh2o": 8.5, "gumus": 0.75, "clay": 15, "sand": 20, "silt": 65},
    }
    res = tavsiya_ber(t)
    g = next(r for r in res["natijalar"] if r.ekin.startswith("G'o'za"))
    mu = [0.5, 0.5, 1.0]
    w = [0.4, 0.3, 0.3]
    kutilgan = (sum(a * b for a, b in zip(w, mu)) / math.sqrt(sum(a * b * b for a, b in zip(w, mu)))) * 0.5 ** 0.3
    assert _yaqin(g.s_final, kutilgan, 1e-12), (g.s_final, kutilgan)
    # 8. Qat'iy to'siq: bug'doy pH 8.6 -> rad
    t2 = {k: dict(v, phh2o=8.6) for k, v in t.items()}
    b = next(r for r in tavsiya_ber(t2)["natijalar"] if r.ekin.startswith("Kuzgi"))
    assert b.k_hard == 0 and b.s_final == 0.0
    # 9. Hamma natijalar [0,1] va saralangan
    r = tavsiya_ber(DEMO)["natijalar"]
    assert all(0.0 <= x.s_final <= 1.0 for x in r)
    assert all(r[i].s_final >= r[i + 1].s_final for i in range(len(r) - 1))
    # 10. Xato kirishlar to'g'ri rad etiladi
    for yomon in (
        {"0-5 cm": {"phh2o": 7, "gumus": 1, "clay": 20, "sand": 40, "silt": 40}},  # 30 smgacha yetmaydi
        {"0-5 cm": {"phh2o": 15, "gumus": 1, "clay": 20, "sand": 40, "silt": 40},
         "5-15 cm": t["5-15 cm"], "15-30 cm": t["15-30 cm"]},  # pH=15
        {"0-5 cm": {"phh2o": 7, "gumus": 1, "clay": 50, "sand": 40, "silt": 40},
         "5-15 cm": t["5-15 cm"], "15-30 cm": t["15-30 cm"]},  # yig'indi 130
    ):
        try:
            tavsiya_ber(yomon)
        except ValueError:
            pass
        else:
            raise AssertionError("Xato kirish rad etilmadi")
    print("Barcha sinovlar muvaffaqiyatli o'tdi.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sinov()
    elif len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            natijani_chiqar(tavsiya_ber(json.load(f)))
    else:
        natijani_chiqar(tavsiya_ber(DEMO))

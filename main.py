from fastapi import FastAPI
from pydantic import BaseModel
import psychrolib

psychrolib.SetUnitSystem(psychrolib.SI)

app = FastAPI()

P_ATM = 101325  # Pa


# -----------------------------
# INPUT MODELS
# -----------------------------
class PsychroInput(BaseModel):
    db: float
    rh: float


class CoolingInput(BaseModel):
    cfm: float
    ra_db: float
    ra_rh: float
    sa_db: float
    sa_rh: float


class MixingInput(BaseModel):
    total_cfm: float
    fa_pct: float
    ra_db: float
    ra_rh: float
    fa_db: float
    fa_rh: float


# -----------------------------
# COMMON CALC
# -----------------------------
def calc_air(Tdb, RH):
    RH = RH / 100

    W = psychrolib.GetHumRatioFromRelHum(Tdb, RH, P_ATM)
    h = psychrolib.GetMoistAirEnthalpy(Tdb, W) / 1000  # kJ/kg
    wb = psychrolib.GetTWetBulbFromRelHum(Tdb, RH, P_ATM)
    dp = psychrolib.GetTDewPointFromRelHum(Tdb, RH)
    v = psychrolib.GetMoistAirVolume(Tdb, W, P_ATM)
    rho = 1 / v

    return {
        "wb": round(wb, 2),
        "dp": round(dp, 2),
        "rh": round(RH * 100, 1),
        "w": round(W, 6),
        "h": round(h, 2),
        "v": round(v, 3),
        "rho": round(rho, 3),
    }


# -----------------------------
# TAB 1
# -----------------------------
@app.post("/psychro")
def psychro(data: PsychroInput):
    return calc_air(data.db, data.rh)


# -----------------------------
# TAB 2 (Cooling Analysis)
# -----------------------------
@app.post("/cooling")
def cooling(data: CoolingInput):

    ra = calc_air(data.ra_db, data.ra_rh)
    sa = calc_air(data.sa_db, data.sa_rh)

    # Convert CFM → m³/s
    m3s = data.cfm * 0.000471947

    # Use RA density
    rho = ra["rho"]
    m_dot = rho * m3s  # kg/s

    h1 = ra["h"]
    h2 = sa["h"]

    W1 = ra["w"]
    W2 = sa["w"]

    # Total load (kW)
    Qt = m_dot * (h1 - h2)

    # Sensible load (kW)
    Qs = m_dot * 1.02 * (data.ra_db - data.sa_db)

    # Latent load
    Ql = Qt - Qs

    SHR = Qs / Qt if Qt != 0 else 0

    # Condensate (kg/hr)
    m_cond = m_dot * (W1 - W2) * 3600

    return {
        "qt": round(Qt, 2),
        "qt_tr": round(Qt / 3.517, 2),
        "qs": round(Qs, 2),
        "ql": round(Ql, 2),
        "shr": round(SHR, 3),
        "cond": round(m_cond, 2),
        "dt": round(data.ra_db - data.sa_db, 2),
        "dh": round(h1 - h2, 2),

        # RA
        "ra_wb": ra["wb"],
        "ra_dp": ra["dp"],
        "ra_w": ra["w"],
        "ra_h": ra["h"],

        # SA
        "sa_wb": sa["wb"],
        "sa_dp": sa["dp"],
        "sa_w": sa["w"],
        "sa_h": sa["h"],
    }


# -----------------------------
# TAB 3 (Mixing)
# -----------------------------
@app.post("/mixing")
def mixing(data: MixingInput):

    ra = calc_air(data.ra_db, data.ra_rh)
    fa = calc_air(data.fa_db, data.fa_rh)

    fa_frac = data.fa_pct / 100
    ra_frac = 1 - fa_frac

    # Airflow split
    fa_cfm = data.total_cfm * fa_frac
    ra_cfm = data.total_cfm * ra_frac

    # Mixing (enthalpy & humidity)
    h_mix = ra_frac * ra["h"] + fa_frac * fa["h"]
    W_mix = ra_frac * ra["w"] + fa_frac * fa["w"]

    # Back calculate DB
    T_mix = (h_mix * 1000 - 2501000 * W_mix) / (1006 + 1860 * W_mix)

    wb = psychrolib.GetTWetBulbFromHumRatio(T_mix, W_mix, P_ATM)
    dp = psychrolib.GetTDewPointFromHumRatio(T_mix, W_mix, P_ATM)
    rh = psychrolib.GetRelHumFromHumRatio(T_mix, W_mix, P_ATM) * 100

    return {
        "ma_db": round(T_mix, 2),
        "ma_h": round(h_mix, 2),
        "ma_w": round(W_mix, 6),
        "ma_wb": round(wb, 2),
        "ma_dp": round(dp, 2),
        "ma_rh": round(rh, 1),
        "ra_cfm": round(ra_cfm, 0),
        "fa_cfm": round(fa_cfm, 0),
        "mix_dh": round(h_mix - ra["h"], 2),
    }

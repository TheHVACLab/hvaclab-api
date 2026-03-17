from fastapi import FastAPI
from pydantic import BaseModel
import psychrolib

app = FastAPI()

psychrolib.SetUnitSystem(psychrolib.SI)
P = 101325

# ---------- MODELS ----------
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


# ---------- TAB 1 ----------
@app.post("/psychro")
def psychro(data: PsychroInput):
    W = psychrolib.GetHumRatioFromRelHum(data.db, data.rh/100, P)
    h = psychrolib.GetMoistAirEnthalpy(data.db, W)/1000
    dp = psychrolib.GetTDewPointFromHumRatio(data.db, W, P)
    wb = psychrolib.GetTWetBulbFromHumRatio(data.db, W, P)

    return {
        "wb": round(wb,2),
        "dp": round(dp,2),
        "rh": data.rh,
        "w": round(W,5),
        "h": round(h,2)
    }


# ---------- TAB 2 ----------
@app.post("/cooling")
def cooling(data: CoolingInput):

    W1 = psychrolib.GetHumRatioFromRelHum(data.ra_db, data.ra_rh/100, P)
    W2 = psychrolib.GetHumRatioFromRelHum(data.sa_db, data.sa_rh/100, P)

    h1 = psychrolib.GetMoistAirEnthalpy(data.ra_db, W1)/1000
    h2 = psychrolib.GetMoistAirEnthalpy(data.sa_db, W2)/1000

    v1 = psychrolib.GetMoistAirVolume(data.ra_db, W1, P)
    rho = 1/v1
    m_dot = data.cfm * 0.0004719 * rho

    Qt = m_dot * (h1 - h2)
    Cp = 1.005 + 1.88 * W1
    Qs = m_dot * Cp * (data.ra_db - data.sa_db)
    Ql = Qt - Qs
    SHR = Qs/Qt if Qt != 0 else 0

    m_cond = max(0, m_dot * (W1 - W2) * 3600)

    return {
        "qt": round(Qt,2),
        "qt_tr": round(Qt/3.517,2),
        "qs": round(Qs,2),
        "ql": round(Ql,2),
        "shr": round(SHR,3),
        "cond": round(m_cond,2)
    }


# ---------- TAB 3 ----------
@app.post("/mixing")
def mixing(data: MixingInput):

    fa_frac = data.fa_pct/100
    fa_cfm = data.total_cfm * fa_frac
    ra_cfm = data.total_cfm - fa_cfm

    W_ra = psychrolib.GetHumRatioFromRelHum(data.ra_db, data.ra_rh/100, P)
    W_fa = psychrolib.GetHumRatioFromRelHum(data.fa_db, data.fa_rh/100, P)

    h_ra = psychrolib.GetMoistAirEnthalpy(data.ra_db, W_ra)/1000
    h_fa = psychrolib.GetMoistAirEnthalpy(data.fa_db, W_fa)/1000

    v_ra = psychrolib.GetMoistAirVolume(data.ra_db, W_ra, P)
    v_fa = psychrolib.GetMoistAirVolume(data.fa_db, W_fa, P)

    m_ra = ra_cfm * 0.0004719 * (1/v_ra)
    m_fa = fa_cfm * 0.0004719 * (1/v_fa)

    W_mix = (m_ra*W_ra + m_fa*W_fa)/(m_ra+m_fa)
    h_mix = (m_ra*h_ra + m_fa*h_fa)/(m_ra+m_fa)

    T_mix = psychrolib.GetTDryBulbFromEnthalpyAndHumRatio(h_mix*1000, W_mix)

    return {
        "ma_db": round(T_mix,2),
        "ma_h": round(h_mix,2),
        "ma_w": round(W_mix,5),
        "ra_cfm": round(ra_cfm),
        "fa_cfm": round(fa_cfm)
    }

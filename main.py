# =========================
# BACKEND (FastAPI) - FIXED
# =========================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psychrolib
import logging

psychrolib.SetUnitSystem(psychrolib.SI)

app = FastAPI()

# Logging
logging.basicConfig(level=logging.INFO)

# CORS (IMPORTANT)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# HEALTH CHECK
# -----------------------------
@app.get("/")
def home():
    return {"status": "HVAC API running"}

# -----------------------------
# COMMON CALC
# -----------------------------
def calc_air(Tdb, RH):
    if RH < 0 or RH > 100:
        raise HTTPException(status_code=400, detail="RH must be 0-100")

    RH = RH / 100

    W = psychrolib.GetHumRatioFromRelHum(Tdb, RH, P_ATM)
    h = psychrolib.GetMoistAirEnthalpy(Tdb, W) / 1000
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
# TAB 2
# -----------------------------
@app.post("/cooling")
def cooling(data: CoolingInput):

    if data.cfm <= 0:
        raise HTTPException(status_code=400, detail="Invalid airflow")

    ra = calc_air(data.ra_db, data.ra_rh)
    sa = calc_air(data.sa_db, data.sa_rh)

    m3s = data.cfm * 0.000471947

    rho = (ra["rho"] + sa["rho"]) / 2
    m_dot = rho * m3s

    h1 = ra["h"]
    h2 = sa["h"]

    W1 = ra["w"]
    W2 = sa["w"]

    Qt = m_dot * (h1 - h2)

    cp_air = 1.005
    Qs = m_dot * cp_air * (data.ra_db - data.sa_db)

    Ql = Qt - Qs

    SHR = Qs / Qt if Qt != 0 else 0

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

        "ra_wb": ra["wb"],
        "ra_dp": ra["dp"],
        "ra_w": ra["w"],
        "ra_h": ra["h"],

        "sa_wb": sa["wb"],
        "sa_dp": sa["dp"],
        "sa_w": sa["w"],
        "sa_h": sa["h"],
    }

# -----------------------------
# TAB 3
# -----------------------------
@app.post("/mixing")
def mixing(data: MixingInput):

    if data.total_cfm <= 0:
        raise HTTPException(status_code=400, detail="Invalid airflow")

    if data.fa_pct < 0 or data.fa_pct > 100:
        raise HTTPException(status_code=400, detail="FA% must be 0-100")

    ra = calc_air(data.ra_db, data.ra_rh)
    fa = calc_air(data.fa_db, data.fa_rh)

    fa_frac = data.fa_pct / 100
    ra_frac = 1 - fa_frac

    fa_cfm = data.total_cfm * fa_frac
    ra_cfm = data.total_cfm * ra_frac

    h_mix = ra_frac * ra["h"] + fa_frac * fa["h"]
    W_mix = ra_frac * ra["w"] + fa_frac * fa["w"]

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


# =========================
# FRONTEND FIX (IMPORTANT CHANGES ONLY)
# =========================

# Replace this in your HTML JS:
# const API="https://your-app-name.onrender.com";

# Replace ALL catch blocks with:
# catch(e){ showError(e.message || 'Operation failed') }

# Add button reset inside validation failures
# btn.innerText='Run Analysis'; btn.disabled=false;

# OPTIONAL: Add timeout
# fetch(url, { signal: AbortSignal.timeout(5000) })

# =========================
# RUN COMMAND (RENDER)
# =========================
# uvicorn hvac_backend:app --host 0.0.0.0 --port 10000

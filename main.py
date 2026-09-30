"""
Tuproq Parametrlari GIS Veb-Ilovasi (FastAPI Server)
PhD Ilmiy Tadqiqot Loyihasi: O'zbekiston hududlari bo'yicha SoilGrids qatlamlari
"""

import io
import csv
import json
import os
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import soil_service

app = FastAPI(
    title="O'zbekiston Tuproq Qatlamlari Tahlili (SoilGrids GIS)",
    description="Tuproq xususiyatlarini (pH, gumus, loy, qum, azot, CEC, zichlik) koordinatalar bo'yicha tahlil qilish tizimi",
    version="1.0.0"
)

# CORS sozlamalari
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Statik fayllarni ulash
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Bosh sahifani uzatish."""
    html_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>SoilGrids tizimi yuklanmoqda...</h1>")


@app.get("/api/soil")
async def get_soil_data(
    lat: float = Query(..., description="Kenglik (Latitude), masalan 41.3"),
    lon: float = Query(..., description="Uzunlik (Longitude), masalan 69.2")
):
    """Berilgan koordinatalar bo'yicha tuproq qatlamlari ma'lumotlarini qaytaradi."""
    try:
        profile = soil_service.get_soil_profile(lat=lat, lon=lon)
        return {
            "status": "success",
            "data": profile
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Xatolik yuz berdi: {str(e)}")


@app.get("/api/regions")
async def get_regions():
    """O'zbekistonning tezkor tanlanuvchi hududlar ro'yxati."""
    return {
        "status": "success",
        "regions": soil_service.UZBEKISTAN_REGIONS
    }


@app.get("/api/geojson/uzbekistan")
async def get_uzbekistan_geojson():
    """O'zbekiston xarita chegaralari GeoJSON fayli."""
    file_path = os.path.join(STATIC_DIR, "data", "uzbekistan.geojson")
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/json")
    raise HTTPException(status_code=404, detail="GeoJSON fayli topilmadi")


@app.get("/api/export/csv")
async def export_csv(
    lat: float = Query(..., description="Kenglik"),
    lon: float = Query(..., description="Uzunlik")
):
    """Tanlangan nuqta tuproq profili ma'lumotlarini CSV formatida yuklab beradi."""
    profile = soil_service.get_soil_profile(lat=lat, lon=lon)
    layers = profile.get("layers", {})
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Sarlavhalar
    writer.writerow([
        "Qatlam (Chuqurlik)", 
        "pH (H2O)", 
        "Organik uglerod (g/kg)", 
        "Gumus (%)", 
        "Loy / Gil (%)", 
        "Qum (%)", 
        "Chang / Soz (%)", 
        "Umumiy Azot (g/kg)", 
        "CEC (cmol(+)/kg)", 
        "Zichlik (g/sm3)"
    ])
    
    for depth in soil_service.DEPTHS:
        layer_data = layers.get(depth, {})
        writer.writerow([
            depth,
            layer_data.get("phh2o", {}).get("value", "-"),
            layer_data.get("soc", {}).get("value", "-"),
            layer_data.get("gumus", {}).get("value", "-"),
            layer_data.get("clay", {}).get("value", "-"),
            layer_data.get("sand", {}).get("value", "-"),
            layer_data.get("silt", {}).get("value", "-"),
            layer_data.get("nitrogen", {}).get("value", "-"),
            layer_data.get("cec", {}).get("value", "-"),
            layer_data.get("bdod", {}).get("value", "-")
        ])
    
    output.seek(0)
    filename = f"tuproq_profili_{lat:.4f}_{lon:.4f}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),  # UTF-8 with BOM for Excel
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

import asyncio, os, time
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import httpx

app = FastAPI(title="Norður – Veðurvakt Íslands")
app.mount("/static", StaticFiles(directory="static"), name="static")
PLACES = [
 {"name":"Reykjavík","lat":64.1466,"lon":-21.9426},
 {"name":"Akureyri","lat":65.6835,"lon":-18.0878},
 {"name":"Ísafjörður","lat":66.0748,"lon":-23.1353},
 {"name":"Egilsstaðir","lat":65.2669,"lon":-14.3948},
 {"name":"Vík","lat":63.4186,"lon":-19.0060},
 {"name":"Vestmannaeyjar","lat":63.4427,"lon":-20.2734}
]
URL="https://api.open-meteo.com/v1/forecast"
CACHE={"at":0,"data":None}
TTL=int(os.getenv("CACHE_TTL_SECONDS","900"))

async def fetch(client, place, model=None):
 params={"latitude":place["lat"],"longitude":place["lon"],
  "current":"temperature_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,pressure_msl",
  "hourly":"temperature_2m,precipitation,precipitation_probability,wind_speed_10m,wind_gusts_10m,pressure_msl",
  "daily":"weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,pressure_msl_mean",
  "forecast_days":10,"timezone":"Atlantic/Reykjavik","wind_speed_unit":"ms"}
 if model: params["models"]=model
 r=await client.get(URL,params=params,timeout=25); r.raise_for_status()
 return r.json()

@app.get("/")
async def home(): return FileResponse("static/index.html")

@app.get("/api/health")
async def health(): return {"ok":True,"service":"Nordur"}

@app.get("/api/dashboard")
async def dashboard():
 if CACHE["data"] and time.time()-CACHE["at"]<TTL: return CACHE["data"]
 async with httpx.AsyncClient() as client:
  results=await asyncio.gather(*(fetch(client,p) for p in PLACES),return_exceptions=True)
  points=[]
  for p,r in zip(PLACES,results):
   points.append({**p,"data":r if not isinstance(r,Exception) else None,"error":str(r) if isinstance(r,Exception) else None})
  models=[]
  for name,model in [("ECMWF IFS","ecmwf_ifs025"),("GFS","gfs_seamless"),("ICON","icon_seamless")]:
   try:
    x=await fetch(client,PLACES[0],model)
    models.append({"name":name,"current":x.get("current")})
   except Exception as e: models.append({"name":name,"error":str(e)})
 data={"generated_at":time.time(),"points":points,"models":models,
       "notice":"Sjálfvirkt áhættumat er ekki opinber veðurviðvörun."}
 CACHE.update(at=time.time(),data=data)
 return data

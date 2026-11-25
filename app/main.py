import asyncio, os, time, math
from datetime import datetime, timezone
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
IMO_WEATHER="https://api.vedur.is/weather"
IMO_CAP="https://api.vedur.is/cap/v1"
CACHE={"dashboard":{"at":0,"data":None},"alerts":{"at":0,"data":None},"observations":{"at":0,"data":None},"lows":{"at":0,"data":None}}
TTL=int(os.getenv("CACHE_TTL_SECONDS","900"))

async def get_json(client,url,params=None):
 r=await client.get(url,params=params,timeout=35,headers={"User-Agent":"Nordur-Vedurvakt/1.0 (public Iceland weather dashboard)"})
 r.raise_for_status()
 return r.json()

async def fetch(client, place, model=None):
 params={"latitude":place["lat"],"longitude":place["lon"],
  "current":"temperature_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,pressure_msl",
  "hourly":"temperature_2m,precipitation,precipitation_probability,wind_speed_10m,wind_gusts_10m,pressure_msl",
  "daily":"weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,pressure_msl_mean",
  "forecast_days":10,"timezone":"Atlantic/Reykjavik","wind_speed_unit":"ms"}
 if model: params["models"]=model
 return await get_json(client,URL,params)

def cache_ok(key):
 return CACHE[key]["data"] is not None and time.time()-CACHE[key]["at"]<TTL

@app.get("/")
async def home(): return FileResponse("static/index.html")

@app.get("/api/health")
async def health(): return {"ok":True,"service":"Nordur"}

@app.get("/api/dashboard")
async def dashboard():
 if cache_ok("dashboard"): return CACHE["dashboard"]["data"]
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
 data={"generated_at":time.time(),"points":points,"models":models}
 CACHE["dashboard"].update(at=time.time(),data=data)
 return data

@app.get("/api/alerts")
async def alerts():
 """Official active CAP alerts from the Icelandic Met Office."""
 if cache_ok("alerts"): return CACHE["alerts"]["data"]
 async with httpx.AsyncClient() as client:
  alerts_data=await get_json(client,f"{IMO_CAP}/capbroker/active/detailed/all")
  regions=await get_json(client,f"{IMO_CAP}/capcreator/forecast_regions")
 region_rows=regions if isinstance(regions,list) else regions.get("data",[]) if isinstance(regions,dict) else []
 region_names={str(r.get("id") or r.get("area_id")):r.get("name_is") or r.get("name_en") or r.get("name") for r in region_rows}
 alert_rows=alerts_data if isinstance(alerts_data,list) else alerts_data.get("messages",alerts_data.get("data",[])) if isinstance(alerts_data,dict) else []
 items=[]
 for a in alert_rows:
  info=a.get("info",{}) if isinstance(a.get("info"),dict) else {}
  area=a.get("area",{}) if isinstance(a.get("area"),dict) else {}
  area_id=a.get("area_id") or area.get("area_id") or area.get("id")
  items.append({
   "identifier":a.get("identifier"),"headline":a.get("headline_is") or info.get("headline_is") or info.get("headline") or a.get("event_is") or a.get("event") or "Veðurviðvörun",
   "description":a.get("description_is") or info.get("description_is") or info.get("description") or a.get("description_en") or "",
   "event":a.get("event_is") or info.get("event") or a.get("event_en"),"severity":a.get("severity") or info.get("severity"),
   "urgency":a.get("urgency") or info.get("urgency"),"certainty":a.get("certainty") or info.get("certainty"),
   "area":region_names.get(str(area_id),area.get("area_desc") or area.get("areaDesc") or f"Svæði {area_id}" if area_id else "Ísland"),
   "area_id":area_id,"onset":a.get("onset") or info.get("onset"),"expires":a.get("expires") or info.get("expires"),
   "sent":a.get("sent"),"polygon":a.get("polygon") or area.get("polygon") or [],
   "source":"Veðurstofa Íslands","url":"https://www.vedur.is/viðvaranir"
  })
 data={"generated_at":time.time(),"source":"Veðurstofa Íslands – CAP API","alerts":items,"count":len(items)}
 CACHE["alerts"].update(at=time.time(),data=data)
 return data

@app.get("/api/observations")
async def observations():
 """Latest automatic weather-station observations from IMO open API."""
 if cache_ok("observations"): return CACHE["observations"]["data"]
 async with httpx.AsyncClient() as client:
  stations_data=await get_json(client,f"{IMO_WEATHER}/stations",{"active":"true","station_type":"sj"})
  stations=stations_data if isinstance(stations_data,list) else stations_data.get("data",[]) if isinstance(stations_data,dict) else []
  # Select the closest two active automatic stations to each forecast town.
  selected={}
  for place in PLACES:
   candidates=[]
   for station in stations:
    lat=station.get("lat") or station.get("latitude")
    lon=station.get("lon") or station.get("longitude")
    sid=station.get("station") or station.get("station_id") or station.get("id")
    if lat is None or lon is None or sid is None: continue
    distance=(float(lat)-place["lat"])**2+(float(lon)-place["lon"])**2
    candidates.append((distance,station))
   for _,station in sorted(candidates,key=lambda x:x[0])[:2]:
    sid=station.get("station") or station.get("station_id") or station.get("id")
    selected[str(sid)]=station
  async def one(station):
   sid=station.get("station") or station.get("station_id") or station.get("id")
   return await get_json(client,f"{IMO_WEATHER}/observations/aws/10min/latest",{"parameters":"basic","station_id":sid,"format":"json"})
  results=await asyncio.gather(*(one(s) for s in selected.values()),return_exceptions=True)
 cleaned=[]
 for station,result in zip(selected.values(),results):
  if isinstance(result,Exception): continue
  rows=result if isinstance(result,list) else result.get("data",[]) if isinstance(result,dict) else []
  for x in rows:
   cleaned.append({
    "station":x.get("station"),"name":x.get("name") or station.get("name"),
    "time":x.get("time"),"temperature":x.get("t"),"wind":x.get("f"),
    "gust":x.get("fg"),"direction":x.get("d_txt"),"pressure":x.get("ps") or x.get("p"),
    "precipitation":x.get("r"),"latitude":station.get("lat"),"longitude":station.get("lon")
   })
 cleaned.sort(key=lambda x:(x["name"] or ""))
 result={"generated_at":time.time(),"source":"Veðurstofa Íslands – veðurathuganir","count":len(cleaned),"observations":cleaned}
 CACHE["observations"].update(at=time.time(),data=result)
 return result

@app.get("/api/pressure-lows")
async def pressure_lows():
 """Detect local sea-level pressure minima on a North Atlantic forecast grid."""
 if cache_ok("lows"): return CACHE["lows"]["data"]
 lats=[50,55,60,65,70,75]
 lons=[-45,-35,-25,-15,-5,5]
 pairs=[(lat,lon) for lat in lats for lon in lons]
 params={"latitude":",".join(str(x[0]) for x in pairs),
         "longitude":",".join(str(x[1]) for x in pairs),
         "hourly":"pressure_msl","forecast_days":3,"timezone":"UTC"}
 async with httpx.AsyncClient() as client:
  raw=await get_json(client,URL,params)
 series=raw if isinstance(raw,list) else [raw]
 times=series[0].get("hourly",{}).get("time",[])
 pressure=[]
 for idx,item in enumerate(series):
  vals=item.get("hourly",{}).get("pressure_msl",[])
  pressure.append(vals)
 detections=[]
 # Sample every six hours. A low must be lower than its surrounding grid cells.
 for ti in range(0,len(times),6):
  grid=[]
  for k,(lat,lon) in enumerate(pairs):
   vals=pressure[k] if k<len(pressure) else []
   value=vals[ti] if ti<len(vals) else None
   grid.append(value)
  lows=[]
  for iy,lat in enumerate(lats):
   for ix,lon in enumerate(lons):
    k=iy*len(lons)+ix; v=grid[k]
    if v is None: continue
    neighbors=[]
    for dy in (-1,0,1):
     for dx in (-1,0,1):
      ny,nx=iy+dy,ix+dx
      if (dy or dx) and 0<=ny<len(lats) and 0<=nx<len(lons):
       nv=grid[ny*len(lons)+nx]
       if nv is not None: neighbors.append(nv)
    if neighbors and v<=min(neighbors) and v<1018:
     lows.append({"lat":lat,"lon":lon,"pressure":round(v,1)})
  lows.sort(key=lambda x:x["pressure"])
  detections.append({"time":times[ti],"lows":lows[:5]})
 data={"generated_at":time.time(),"source":"Open-Meteo pressure_msl forecast grid","grid":{"latitudes":lats,"longitudes":lons},"detections":detections,
       "method":"Staðbundin lágmörk sjávarmálsþrýstings á 5° x 10° spáneti. Þetta er sjálfvirk greining, ekki opinber lægðaspá."}
 CACHE["lows"].update(at=time.time(),data=data)
 return data

import asyncio, os, time, math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
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
 {"name":"Vestmannaeyjar","lat":63.4427,"lon":-20.2734},
 {"name":"Kópavogur","lat":64.1125,"lon":-21.9123},
 {"name":"Hafnarfjörður","lat":64.0671,"lon":-21.9378},
 {"name":"Garðabær","lat":64.0886,"lon":-21.9228},
 {"name":"Álftanes","lat":64.1007,"lon":-22.0167},
 {"name":"Seltjarnarnes","lat":64.1534,"lon":-22.0024},
 {"name":"Mosfellsbær","lat":64.1665,"lon":-21.6987},
 {"name":"Kjalarnes","lat":64.2585,"lon":-21.7750},
 {"name":"Breiðholt","lat":64.1074,"lon":-21.8402},
 {"name":"Grafarvogur","lat":64.1477,"lon":-21.8027},
 {"name":"Árbær","lat":64.1156,"lon":-21.7878},
 {"name":"Grafarholt","lat":64.1173,"lon":-21.7566},
 {"name":"Laugardalur","lat":64.1441,"lon":-21.8745},
 {"name":"Vesturbær","lat":64.1519,"lon":-21.9657},
 {"name":"Kársnes","lat":64.1085,"lon":-21.9294},
 {"name":"Smárahverfi","lat":64.1004,"lon":-21.8948},
 {"name":"Lindir og Salir","lat":64.0972,"lon":-21.8757},
 {"name":"Vellir","lat":64.0674,"lon":-21.9803},
 {"name":"Norðurbær","lat":64.0750,"lon":-21.9590},
 {"name":"Keflavík","lat":63.9998,"lon":-22.5582},
 {"name":"Akranes","lat":64.3219,"lon":-22.07},
 {"name":"Borgarnes","lat":64.5383,"lon":-21.9206},
 {"name":"Stykkishólmur","lat":65.075,"lon":-22.7297},
 {"name":"Patreksfjörður","lat":65.5978,"lon":-23.995},
 {"name":"Bolungarvík","lat":66.1592,"lon":-23.2495},
 {"name":"Sauðárkrókur","lat":65.7461,"lon":-19.6394},
 {"name":"Siglufjörður","lat":66.1519,"lon":-18.9082},
 {"name":"Húsavík","lat":66.0449,"lon":-17.3389},
 {"name":"Seyðisfjörður","lat":65.2592,"lon":-14.0097},
 {"name":"Neskaupstaður","lat":65.1482,"lon":-13.6837},
 {"name":"Höfn","lat":64.2539,"lon":-15.2082},
 {"name":"Selfoss","lat":63.933,"lon":-20.9971},
 {"name":"Hveragerði","lat":64.0005,"lon":-21.186},
 {"name":"Kirkjubæjarklaustur","lat":63.789,"lon":-18.0567}
]
URL="https://api.open-meteo.com/v1/forecast"
YR_URL="https://api.met.no/weatherapi/locationforecast/2.0/compact"
YR_USER_AGENT="Nordur-Vedurvakt/1.0 (https://github.com/hljodxrin-byte/nordur-vedurvakt)"
IMO_WEATHER="https://api.vedur.is/weather"
IMO_CAP="https://api.vedur.is/cap/v1"
CACHE={"dashboard":{"at":0,"data":None},"alerts":{"at":0,"data":None},"observations":{"at":0,"data":None},"lows":{"at":0,"data":None}}
ROAD_CACHE={}
TTL=max(1800,int(os.getenv("CACHE_TTL_SECONDS","1800")))

async def get_json(client,url,params=None,headers=None,timeout=35):
 request_headers=headers or {"User-Agent":"Nordur-Vedurvakt/1.0 (https://github.com/hljodxrin-byte/nordur-vedurvakt)"}
 r=await client.get(url,params=params,timeout=timeout,headers=request_headers)
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

async def fetch_gust_fallback(client, place):
 """Fetch gust values from Open-Meteo to fill gaps in MET Norway's long-range forecast."""
 params={"latitude":place["lat"],"longitude":place["lon"],
  "current":"wind_gusts_10m","daily":"wind_gusts_10m_max",
  "forecast_days":9,"timezone":"Atlantic/Reykjavik","wind_speed_unit":"ms"}
 return await get_json(client,URL,params)


YR_SYMBOL_TO_WMO = {
 "clearsky":0,"fair":1,"partlycloudy":2,"cloudy":3,"fog":45,
 "lightrain":61,"rain":63,"heavyrain":65,"lightrainshowers":80,
 "rainshowers":81,"heavyrainshowers":82,"lightsleet":66,"sleet":67,
 "heavysleet":67,"lightsnow":71,"snow":73,"heavysnow":75,
 "lightsnowshowers":85,"snowshowers":85,"heavysnowshowers":86,
 "rainandthunder":95,"lightrainandthunder":95,"heavyrainandthunder":99,
 "rainshowersandthunder":95,"heavyrainshowersandthunder":99,"lightsnowshowersandthunder":96,"snowshowersandthunder":96,
 "sleetandthunder":96,"snowandthunder":96
}

def yr_symbol_to_wmo(symbol):
 if not symbol: return 3
 key=str(symbol).split("_")[0]
 if key in YR_SYMBOL_TO_WMO: return YR_SYMBOL_TO_WMO[key]
 for prefix,code in sorted(YR_SYMBOL_TO_WMO.items(),key=lambda x:-len(x[0])):
  if key.startswith(prefix): return code
 return 3

def convert_yr_forecast(place, payload):
 """Normalize MET Norway Locationforecast data to the dashboard's forecast shape."""
 series=payload.get("properties",{}).get("timeseries",[])
 if not series: raise ValueError("MET Norway returned an empty forecast")
 local_tz=ZoneInfo("Atlantic/Reykjavik")
 rows=[]
 for item in series:
  instant=item.get("data",{}).get("instant",{}).get("details",{})
  if not instant: continue
  dt=datetime.fromisoformat(item["time"].replace("Z","+00:00")).astimezone(local_tz)
  data=item.get("data",{})
  next1=data.get("next_1_hours",{})
  next6=data.get("next_6_hours",{})
  summary=next1.get("summary",{}) or next6.get("summary",{})
  details=next1.get("details",{}) or next6.get("details",{})
  symbol=summary.get("symbol_code")
  rows.append({
   "dt":dt,"temp":instant.get("air_temperature"),
   "wind":instant.get("wind_speed"),"gust":instant.get("wind_speed_of_gust"),
   "pressure":instant.get("air_pressure_at_sea_level"),
   "precip":details.get("precipitation_amount",0) or 0,
   "symbol":symbol,"code":yr_symbol_to_wmo(symbol)
  })
 if not rows: raise ValueError("MET Norway forecast had no usable time steps")
 first=rows[0]
 current={"temperature_2m":first["temp"],"precipitation":first["precip"],
  "weather_code":first["code"],"wind_speed_10m":first["wind"],
  "wind_direction_10m":None,"wind_gusts_10m":first["gust"],
  "pressure_msl":first["pressure"],"is_day":1}
 hourly=[{"time":row["dt"].isoformat(),"temperature_2m":row["temp"],
  "precipitation":row["precip"],"weather_code":row["code"],
  "wind_speed_10m":row["wind"],"wind_gusts_10m":row["gust"],
  "pressure_msl":row["pressure"],"is_day":1 if 6<=row["dt"].hour<20 else 0}
  for row in rows]
 by_day={}
 for row in rows:
  key=row["dt"].date().isoformat()
  day=by_day.setdefault(key,{"temps":[],"winds":[],"gusts":[],"pressures":[],"precip":0.0,"codes":[]})
  if row["temp"] is not None: day["temps"].append(float(row["temp"]))
  if row["wind"] is not None: day["winds"].append(float(row["wind"]))
  if row["gust"] is not None: day["gusts"].append(float(row["gust"]))
  if row["pressure"] is not None: day["pressures"].append(float(row["pressure"]))
  if row["precip"] is not None: day["precip"]+=max(0.0,float(row["precip"]))
  day["codes"].append(row["code"])
 dates=sorted(by_day)
 daily={"time":dates,"weather_code":[],"temperature_2m_max":[],"temperature_2m_min":[],
  "precipitation_sum":[],"wind_speed_10m_max":[],"wind_gusts_10m_max":[],"pressure_msl_mean":[]}
 for date in dates:
  d=by_day[date]
  daily["weather_code"].append(max(set(d["codes"]),key=d["codes"].count) if d["codes"] else 3)
  daily["temperature_2m_max"].append(max(d["temps"]) if d["temps"] else None)
  daily["temperature_2m_min"].append(min(d["temps"]) if d["temps"] else None)
  daily["precipitation_sum"].append(round(d["precip"],1))
  daily["wind_speed_10m_max"].append(max(d["winds"]) if d["winds"] else None)
  daily["wind_gusts_10m_max"].append(max(d["gusts"]) if d["gusts"] else None)
  daily["pressure_msl_mean"].append(round(sum(d["pressures"])/len(d["pressures"]),1) if d["pressures"] else None)
 return {"current":current,"hourly":hourly,"daily":daily,"source":"MET Norway Locationforecast 2.0","forecast_days":len(dates)}

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
  results=await asyncio.gather(*(get_json(client,YR_URL,{"lat":round(p["lat"],2),"lon":round(p["lon"],2)},headers={"User-Agent":YR_USER_AGENT}) for p in PLACES),return_exceptions=True)
  gust_results=await asyncio.gather(*(fetch_gust_fallback(client,p) for p in PLACES),return_exceptions=True)
  points=[]
  for place,result,gust_result in zip(PLACES,results,gust_results):
   try:
    normalized=convert_yr_forecast(place,result) if not isinstance(result,Exception) else None
    if normalized and not isinstance(gust_result,Exception):
     fallback_current=gust_result.get("current",{}).get("wind_gusts_10m")
     if normalized["current"].get("wind_gusts_10m") is None and fallback_current is not None:
      normalized["current"]["wind_gusts_10m"]=fallback_current
     fallback_daily=gust_result.get("daily",{})
     fallback_dates=fallback_daily.get("time",[])
     fallback_values=fallback_daily.get("wind_gusts_10m_max",[])
     fallback_by_date=dict(zip(fallback_dates,fallback_values))
     for index,forecast_date in enumerate(normalized["daily"]["time"]):
      if normalized["daily"]["wind_gusts_10m_max"][index] is None:
       normalized["daily"]["wind_gusts_10m_max"][index]=fallback_by_date.get(forecast_date)
     normalized["gust_source"]="MET Norway, with Open-Meteo fallback where gust data is unavailable"
    points.append({**place,"data":normalized,"error":str(result) if isinstance(result,Exception) else None})
   except Exception as e:
    points.append({**place,"data":None,"error":str(e)})
  model_names=["ECMWF IFS","GFS","ICON"]
  model_ids=["ecmwf_ifs025","gfs_seamless","icon_seamless"]
  models_raw=await asyncio.gather(*(fetch(client,PLACES[0],model) for model in model_ids),return_exceptions=True)
  models=[{"name":name,"current":result.get("current")} if not isinstance(result,Exception) else {"name":name,"error":str(result)} for name,result in zip(model_names,models_raw)]
 data={"generated_at":time.time(),"forecast_source":"MET Norway Locationforecast 2.0","points":points,"models":models}
 CACHE["dashboard"].update(at=time.time(),data=data)
 return data

@app.get("/api/alerts")
async def alerts():
 """Official active CAP alerts from the Icelandic Met Office."""
 if cache_ok("alerts"): return CACHE["alerts"]["data"]
 # CAP-viðmótið getur stundum verið mjög hægt. Sækjum gögn samhliða
 # og látum ekki ein biluð svör stöðva allt mælaborðið.
 async with httpx.AsyncClient() as client:
  alerts_result,regions_result=await asyncio.gather(
   get_json(client,f"{IMO_CAP}/capbroker/active/detailed/all",timeout=10),
   get_json(client,f"{IMO_CAP}/capcreator/forecast_regions",timeout=10),
   return_exceptions=True
  )
 if isinstance(alerts_result,Exception):
  cached=CACHE["alerts"]["data"]
  if cached is not None:
   stale={**cached,"stale":True,"warning":"Ekki tókst að uppfæra viðvaranir; sýni síðast sóttu gögn."}
   return stale
  alert_rows=[]
  source_warning="Ekki tókst að sækja nýjar viðvaranir frá Veðurstofu Íslands."
 else:
  alerts_data=alerts_result
  alert_rows=alerts_data if isinstance(alerts_data,list) else alerts_data.get("messages",alerts_data.get("data",[])) if isinstance(alerts_data,dict) else []
  source_warning=None
 regions=regions_result if not isinstance(regions_result,Exception) else []
 region_rows=regions if isinstance(regions,list) else regions.get("data",[]) if isinstance(regions,dict) else []
 region_names={str(r.get("id") or r.get("area_id")):r.get("name_is") or r.get("name_en") or r.get("name") for r in region_rows}
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
 if source_warning: data["warning"]=source_warning
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


ROAD_WFS="https://gagnaveita.vegagerdin.is/geoserver/gis/ows"
ROAD_STATUS_RANK={"ALLUR_AKSTUR_BANN":0,"LOKAD":1,"OFAERT_VEDUR":2,"OFAERT_ANNAD":3,"FLUGHALT":4,"HALKA":5,"HALKUBLETTIR":6,"THUNGFAERT":7,"THAEFINGUR":8,"SNJOTHEKJA":9,"KRAP":10,"GREIDFAERT":11}
ROAD_STATUS_IS={"ALLUR_AKSTUR_BANN":"Allur akstur bannaður","LOKAD":"Vegur lokaður","OFAERT_VEDUR":"Ófært vegna veðurs","OFAERT_ANNAD":"Ófært","FLUGHALT":"Flughált","HALKA":"Hálka","HALKUBLETTIR":"Hálkublettir","THUNGFAERT":"Þungfært","THAEFINGUR":"Þæfingsfærð","SNJOTHEKJA":"Snjóþekja","KRAP":"Krap","GREIDFAERT":"Greiðfært","FAERT_FJALLABILUM":"Fært fjallabílum","EKKI_I_THJONUSTU":"Ekki í þjónustu Vegagerðarinnar","OTHEKKT":"Óþekkt"}
def _road_value(props,*names):
 for name in names:
  for key,value in props.items():
   if key.lower()==name.lower() and value not in (None,""): return value
 return None
def _road_coords(geometry):
 if not isinstance(geometry,dict): return []
 coords=geometry.get("coordinates")
 found=[]
 def walk(value):
  if isinstance(value,(list,tuple)) and len(value)>=2 and all(isinstance(v,(int,float)) for v in value[:2]):
   found.append((float(value[0]),float(value[1])))
  elif isinstance(value,(list,tuple)):
   for child in value: walk(child)
 walk(coords)
 return found
def _distance_km(lat1,lon1,lat2,lon2):
 p1,p2=math.radians(lat1),math.radians(lat2)
 dp=math.radians(lat2-lat1);dl=math.radians(lon2-lon1)
 a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
 return 6371*2*math.asin(min(1,math.sqrt(a)))
def _point_line_distance_km(point_geometry,line_geometry):
 """Nálægð punktatilkynningar við næsta veglínubút, í km."""
 points=_road_coords(point_geometry);line=_road_coords(line_geometry)
 if not points or len(line)<2: return float("inf")
 lat0=sum(y for _,y in points)/len(points)
 sx=111.32*math.cos(math.radians(lat0));sy=110.57
 best=float("inf")
 for px,py in points:
  qx,qy=px*sx,py*sy
  for (ax,ay),(bx,by) in zip(line,line[1:]):
   ax*=sx;bx*=sx;ay*=sy;by*=sy
   dx,dy=bx-ax,by-ay;den=dx*dx+dy*dy
   t=0 if den==0 else max(0,min(1,((qx-ax)*dx+(qy-ay)*dy)/den))
   best=min(best,math.hypot(qx-(ax+t*dx),qy-(ay+t*dy)))
 return best
@app.get("/api/roads")
async def roads(lat:float=64.1466,lon:float=-21.9426):
 """Nearby road conditions and incidents from the Icelandic Road and Coastal Administration open WFS."""
 if not (-90<=lat<=90 and -180<=lon<=180): return {"source":"Vegagerðin","items":[],"error":"Ógild staðsetning"}
 cache_key=(round(lat,2),round(lon,2))
 cached=ROAD_CACHE.get(cache_key)
 if cached and time.time()-cached["at"]<300: return cached["data"]
 lat_delta=0.38;lon_delta=min(1.2,0.48/max(0.25,math.cos(math.radians(lat))))
 bbox=f"{lon-lon_delta},{lat-lat_delta},{lon+lon_delta},{lat+lat_delta},EPSG:4326"
 common={"service":"WFS","version":"1.0.0","request":"GetFeature","srsName":"EPSG:4326","outputFormat":"application/json","bbox":bbox,"maxFeatures":2500}
 line_params={**common,"typeName":"gis:faerdferlar2017_1"}
 point_params={**common,"typeName":"gis:faerdpunktar2017_1"}
 async with httpx.AsyncClient() as client:
  line_result,point_result=await asyncio.gather(get_json(client,ROAD_WFS,line_params),get_json(client,ROAD_WFS,point_params),return_exceptions=True)
 features=[]
 for kind,result in (("road",line_result),("point",point_result)):
  if isinstance(result,Exception): continue
  rows=result.get("features",[]) if isinstance(result,dict) else []
  for feature in rows:
   props=feature.get("properties") or {}
   coords=_road_coords(feature.get("geometry"))
   if not coords: continue
   distance=min(_distance_km(lat,lon,y,x) for x,y in coords)
   if distance>48: continue
   if kind=="road":
    raw=_road_value(props,"AstandYfirbord") or "OTHEKKT"
    extra=_road_value(props,"AstandVidbotaruppl")
    extra_code=_road_value(props,"AstandVidbotaruppl")
    work_code=_road_value(props,"FrkvAudkenni")
    title=_road_value(props,"FulltNafnButs","StuttNafnButs") or "Vegkafli"
    description=_road_value(props,"AstandLysing") or ROAD_STATUS_IS.get(str(raw).upper(),str(raw))
    work=_road_value(props,"FrkvLysing")
    weight=_road_value(props,"AsthungiLysing")
    recorded=_road_value(props,"DagsSkrad")
    updated=_road_value(props,"DagsKeyrtUt")
   else:
    raw=_road_value(props,"Astand") or "ANNAD"
    extra=None;extra_code=None;work_code=None
    title=_road_value(props,"Aths") or "Staðbundin tilkynning"
    description=_road_value(props,"Lysing") or str(raw)
    work=None;weight=None
    recorded=_road_value(props,"DagsSkrad")
    updated=_road_value(props,"DagsKeyrtUt")
   code=str(raw).upper()
   features.append({"kind":kind,"code":code,"status":ROAD_STATUS_IS.get(code,description or code),"description":description,"road":str(title),"extra":str(extra) if extra else None,"extra_code":str(extra_code or "").upper(),
    "work_code":str(work_code or "").upper(),"work":str(work) if work else None,"weight":str(weight) if weight else None,"distance_km":round(distance,1),"recorded_at":recorded,"updated_at":updated,"rank":ROAD_STATUS_RANK.get(code,5)})
 features.sort(key=lambda x:(x["rank"],x["distance_km"]))
 data={"generated_at":time.time(),"source":"Vegagerðin – opin gagnaveita (WFS)","count":len(features),"items":features[:35],"priority":features[0] if features else None,"radius_km":48,"attribution":"Gögn frá Vegagerðinni. Ástand getur breyst; staðfestu aðstæður áður en lagt er af stað.","links":{"map":"https://umferdin.is/","info":"https://www.vegagerdin.is/ferdaupplysingar"}}
 ROAD_CACHE[cache_key]={"at":time.time(),"data":data}
 return data


ROAD_MAP_CACHE={"at":0,"data":None}
@app.get("/api/road-map")
async def road_map():
 """Latest nationwide road condition lines and point reports from Vegagerðin WFS."""
 cached=ROAD_MAP_CACHE["data"]
 if cached is not None and time.time()-ROAD_MAP_CACHE["at"]<300: return cached
 bbox="-25.0,63.0,-12.0,67.6,EPSG:4326"
 common={"service":"WFS","version":"1.0.0","request":"GetFeature","srsName":"EPSG:4326","outputFormat":"application/json","bbox":bbox,"maxFeatures":12000}
 params=[{**common,"typeName":"gis:faerdferlar2017_1"},{**common,"typeName":"gis:faerdpunktar2017_1"}]
 async with httpx.AsyncClient() as client:
  results=await asyncio.gather(*(get_json(client,ROAD_WFS,p) for p in params),return_exceptions=True)
 features=[];latest=None;errors=[]
 for kind,result in zip(("road","point"),results):
  if isinstance(result,Exception):
   errors.append(str(result));continue
  for feature in result.get("features",[]) if isinstance(result,dict) else []:
   props=feature.get("properties") or {};geometry=feature.get("geometry")
   if not geometry or not _road_coords(geometry): continue
   if kind=="road":
    raw=_road_value(props,"AstandYfirbord") or "OTHEKKT"
    title=_road_value(props,"FulltNafnButs","StuttNafnButs") or "Vegkafli"
    description=_road_value(props,"AstandLysing") or ROAD_STATUS_IS.get(str(raw).upper(),str(raw))
    extra=_road_value(props,"AstandVidbotaruppl")
    extra_code=_road_value(props,"AstandVidbotaruppl")
    work_code=_road_value(props,"FrkvAudkenni")
    work=_road_value(props,"FrkvLysing");weight=_road_value(props,"AsthungiLysing")
   else:
    raw=_road_value(props,"Astand") or "ANNAD"
    title=_road_value(props,"Aths") or "Tilkynning frá Vegagerðinni"
    description=_road_value(props,"Lysing") or str(raw)
    extra=None;extra_code=None;work_code=None;work=None;weight=None
   recorded=_road_value(props,"DagsSkrad");updated=_road_value(props,"DagsKeyrtUt")
   valid_to=_road_value(props,"GildirTil")
   # Sleppa punkttilkynningum sem eru útrunnar; þær eiga ekki að lita veginn lengur.
   if kind=="point" and valid_to:
    try:
     expiry=datetime.fromisoformat(str(valid_to).replace("Z","+00:00"))
     if expiry.tzinfo is None: expiry=expiry.replace(tzinfo=timezone.utc)
     if expiry<=datetime.now(timezone.utc): continue
    except (TypeError,ValueError): pass
   stamp=updated or recorded
   if stamp and (latest is None or str(stamp)>str(latest)): latest=stamp
   code=str(raw).upper()
   incident_text=" ".join(str(v or "") for v in (code,title,description)).casefold()
   incident_key=incident_text.translate(str.maketrans({"á":"a","é":"e","í":"i","ó":"o","ú":"u","ý":"y","ð":"d","þ":"th"}))
   traffic_incident=any(term in incident_key for term in ("slys","arekst","umferdarohapp","umferdarslys"))
   segment_id=_road_value(props,"IdButur")
   features.append({"type":"Feature","geometry":geometry,"properties":{
    "kind":kind,"code":code,"id_butur":str(segment_id) if segment_id is not None else None,
    "valid_to":valid_to,"status":ROAD_STATUS_IS.get(code,description or code),
    "road":str(title),"description":str(description or ""),
    "extra":str(extra) if extra else None,"extra_code":str(extra_code or "").upper(),"work":str(work) if work else None,
    "work_code":str(work_code or "").upper(),
    "traffic_incident":bool(kind=="point" and traffic_incident),
    "roadwork":bool(
     (kind=="point" and (
      code=="VEGAVINNA" or
      (code=="ALLUR_AKSTUR_BANN" and "vegavinn" in str(description or "").casefold())
     )) or
     (kind=="road" and (
      str(work_code or "").upper()=="VEGAVINNA" or
      "vegavinn" in str(work or "").casefold()
     ))
    ),
    "weight":str(weight) if weight else None,"recorded_at":recorded,"updated_at":updated,
    "rank":ROAD_STATUS_RANK.get(code,5)}})
 # IdButur á punktum getur vísað á leiðarnúmer en ekki alltaf sama auðkenni
 # og á einstökum línubútum. Reynum fyrst auðkennið og notum síðan raunverulega
 # fjarlægð punkts frá veglínu (aðeins innan 250 m) sem varatengingu.
 roads=[item for item in features if item["properties"].get("kind")=="road"]
 points=[item for item in features if item["properties"].get("kind")=="point"]
 alerts_by_segment={}
 for point in points:
  pp=point["properties"]
  matches=[road for road in roads if pp.get("id_butur") and
           road["properties"].get("id_butur")==pp.get("id_butur")]
  if not matches:
   nearest=min(roads,key=lambda road:_point_line_distance_km(point.get("geometry"),road.get("geometry")),default=None)
   if nearest and _point_line_distance_km(point.get("geometry"),nearest.get("geometry"))<=0.25:
    matches=[nearest]
  for road in matches:
   alerts_by_segment.setdefault(id(road),[]).append(pp)
 for item in roads:
  props=item["properties"]
  linked=alerts_by_segment.get(id(item),[])
  codes={str(a.get("code") or "").upper() for a in linked}
  props["roadwork"]=bool(props.get("roadwork") or "VEGAVINNA" in codes or props.get("work_code")=="VEGAVINNA")
  props["traffic_incident"]=bool(props.get("traffic_incident") or any(a.get("traffic_incident") for a in linked))
  own_extra=props.get("extra_code","")
  own_work=props.get("work_code","")
  if linked:
   props["linked_alerts"]=[{"code":a.get("code"),"status":a.get("status"),"description":a.get("description"),"road":a.get("road"),"valid_to":a.get("valid_to"),"recorded_at":a.get("recorded_at"),"traffic_incident":a.get("traffic_incident")} for a in linked]
  if "ALLUR_AKSTUR_BANN" in codes or "ALLUR_AKSTUR_BANN" in own_extra:
   props["map_code"]="ALLUR_AKSTUR_BANN"
  elif "VEGAVINNA" in codes or own_work=="VEGAVINNA":
   props["map_code"]="VEGAVINNA"
  elif codes.intersection({"VATNASKEMMDIR","STEINKAST","OSLETTUR_VEGUR"}) or own_extra in {"VATNASKEMMDIR","STEINKAST","OSLETTUR_VEGUR","OVEDUR","SANDBYLUR","SKAFRENNINGUR","SNJOKOMA","STORHRID","THOKA","ELJAGANGUR"}:
   props["map_code"]="ANNAD_ATVIK"
 if not features and errors:
  raise HTTPException(status_code=502,detail="Ekki tókst að sækja vegagögn frá Vegagerðinni")
 data={"generated_at":time.time(),"source":"Vegagerðin – opin gagnaveita (WFS)",
  "updated_at":latest,"count":len(features),"features":features,
  "attribution":"Vegagerðin – opin gagnaveita. Skoðaðu umferdin.is fyrir nýjustu staðfestu upplýsingar.",
  "links":{"map":"https://umferdin.is/","info":"https://www.vegagerdin.is/ferdaupplysingar"}}
 ROAD_MAP_CACHE.update(at=time.time(),data=data)
 return data

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

import ee
import pandas as pd

ee.Initialize(project="dimasti-karhutla-2026")

titik = ee.Geometry.Point([102.0, 0.5])
koleksi = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterDate("2026-01-01", "2026-01-15").select("precipitation")

baris = koleksi.getRegion(titik, 5000).getInfo()
df = pd.DataFrame(baris[1:], columns=baris[0])
df["date"] = pd.to_datetime(df["time"], unit="ms").dt.strftime("%Y-%m-%d")
print(df[["date", "precipitation"]])
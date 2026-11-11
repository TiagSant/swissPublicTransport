"""Unit test for scripts/build_quays.py on a synthetic ATLAS-like CSV (plain and zipped)."""
import importlib.util, io, json, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_quays", ROOT / "scripts/build_quays.py")
bq = importlib.util.module_from_spec(spec); spec.loader.exec_module(bq)

header = "sloid;servicePointNumber;designation;designationOperational;trafficPointElementType;wgs84East;wgs84North"
rows = [
    "ch:1:sloid:87387:0:1;8587387;F;F;BOARDING_PLATFORM;6.143100;46.204700",   # Bel-Air F
    "ch:1:sloid:87387:0:2;8587387;A;;BOARDING_PLATFORM;6.142900;46.204900",    # Bel-Air A
    "ch:1:sloid:87387:9;8587387;Zone;;BOARDING_AREA;6.143000;46.204800",       # area → ignored
    "ch:1:sloid:7000:1:3;8507000;3;3;BOARDING_PLATFORM;7.439100;46.948800",    # Bern → outside the zone
    "ch:1:sloid:1008:1:4;;4;4AB;BOARDING_PLATFORM;6.142400;46.210100",         # Genève track 4, number from SLOID
]
rows += [f"ch:1:sloid:9{i:04d}:0:1;859{i:04d};B;;BOARDING_PLATFORM;6.1{i:03d};46.2{i:03d}" for i in range(60)]
csv_text = header + "\n" + "\n".join(rows) + "\n"

stops, kept, types = bq.build(csv_text)
assert stops["8587387"] == {"F": [46.2047, 6.1431], "A": [46.2049, 6.1429]}, stops["8587387"]
assert "8507000" not in stops                       # outside the area
assert stops["8501008"] == {"4": [46.2101, 6.1424], "4AB": [46.2101, 6.1424]}, stops["8501008"]  # id rebuilt from SLOID
assert types == {"BOARDING_PLATFORM": 64, "BOARDING_AREA": 1}, types
print("plain CSV OK:", len(stops), "stops,", kept, "platforms")

with tempfile.TemporaryDirectory() as d:
    zpath = Path(d) / "tp.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("actual-date-world-traffic-point.csv", "﻿" + csv_text)   # zipped, with BOM
    out = Path(d) / "quays.js"
    sys.argv = ["build_quays.py", str(out), str(zpath)]
    bq.main()
    js = out.read_text(encoding="utf-8")
    data = json.loads(js.split("window.QUAYS = ", 1)[1].rstrip().rstrip(";"))
    assert data["stops"]["8587387"]["F"] == [46.2047, 6.1431] and "licence" in data
print("zipped CSV + output file OK")

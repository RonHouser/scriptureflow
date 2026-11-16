#!/usr/bin/env python3
"""
Builds data/kjv/<Book>.json for Scripture Flow (KJV, public domain).

Output format per book:  {"book": "John", "chapters": [["verse 1", "verse 2", ...], ...]}

Source 1: github.com/aruljohn/Bible-kjv (one zip download, fast)
Source 2: bible-api.com (fallback, per chapter, slow because of its rate limit)
Every book is checked against the KJV chapter / verse counts used by index.html.
Standard library only. Run from the repo root:  python tools/build_kjv.py
"""
import io, json, os, re, sys, time, urllib.request, zipfile

OUT_DIR = os.path.join("data", "kjv")
ARUL_ZIP = "https://github.com/aruljohn/Bible-kjv/archive/refs/heads/master.zip"
API = "https://bible-api.com/data/kjv/{id}/{ch}"

# (name, usfm id, chapters, verses)  - same numbers as bookChapterCounts / bookVerseCounts in index.html
BOOKS = [
 ("Genesis","GEN",50,1533),("Exodus","EXO",40,1213),("Leviticus","LEV",27,859),("Numbers","NUM",36,1288),
 ("Deuteronomy","DEU",34,959),("Joshua","JOS",24,658),("Judges","JDG",21,618),("Ruth","RUT",4,85),
 ("1 Samuel","1SA",31,810),("2 Samuel","2SA",24,695),("1 Kings","1KI",22,816),("2 Kings","2KI",25,719),
 ("1 Chronicles","1CH",29,942),("2 Chronicles","2CH",36,822),("Ezra","EZR",10,280),("Nehemiah","NEH",13,406),
 ("Esther","EST",10,167),("Job","JOB",42,1070),("Psalms","PSA",150,2461),("Proverbs","PRO",31,915),
 ("Ecclesiastes","ECC",12,222),("Song of Solomon","SNG",8,117),("Isaiah","ISA",66,1292),("Jeremiah","JER",52,1364),
 ("Lamentations","LAM",5,154),("Ezekiel","EZK",48,1273),("Daniel","DAN",12,357),("Hosea","HOS",14,197),
 ("Joel","JOL",3,73),("Amos","AMO",9,146),("Obadiah","OBA",1,21),("Jonah","JON",4,48),("Micah","MIC",7,105),
 ("Nahum","NAM",3,47),("Habakkuk","HAB",3,56),("Zephaniah","ZEP",3,53),("Haggai","HAG",2,38),
 ("Zechariah","ZEC",14,211),("Malachi","MAL",4,55),("Matthew","MAT",28,1071),("Mark","MRK",16,678),
 ("Luke","LUK",24,1151),("John","JHN",21,879),("Acts","ACT",28,1007),("Romans","ROM",16,433),
 ("1 Corinthians","1CO",16,437),("2 Corinthians","2CO",13,257),("Galatians","GAL",6,149),("Ephesians","EPH",6,155),
 ("Philippians","PHP",4,104),("Colossians","COL",4,95),("1 Thessalonians","1TH",5,89),("2 Thessalonians","2TH",3,47),
 ("1 Timothy","1TI",6,113),("2 Timothy","2TI",4,83),("Titus","TIT",3,46),("Philemon","PHM",1,25),
 ("Hebrews","HEB",13,303),("James","JAS",5,108),("1 Peter","1PE",5,105),("2 Peter","2PE",3,61),
 ("1 John","1JN",5,105),("2 John","2JN",1,13),("3 John","3JN",1,14),("Jude","JUD",1,25),("Revelation","REV",22,404),
]

def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "scripture-flow-builder"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def clean(t): return re.sub(r"\s+", " ", str(t)).strip()

def valid(chapters, nch, nv):
    return (len(chapters) == nch and sum(len(c) for c in chapters) == nv
            and all(c and all(v for v in c) for c in chapters))

def from_arul(files, name):
    keys = {norm(name), norm(name).replace("psalms", "psalm"), norm(name).replace("songofsolomon", "songofsongs")}
    raw = next((files[k] for k in keys if k in files), None)
    if raw is None: return None
    data = json.loads(raw)
    chs = sorted(data["chapters"], key=lambda c: int(c["chapter"]))
    return [[clean(v["text"]) for v in sorted(c["verses"], key=lambda v: int(v["verse"]))] for c in chs]

def from_api(uid, nch):
    out = []
    for ch in range(1, nch + 1):
        for attempt in range(6):
            try:
                data = json.loads(get(API.format(id=uid, ch=ch)))
                break
            except Exception as e:
                if attempt == 5: raise
                time.sleep(10 * (attempt + 1))
        out.append([clean(v["text"]) for v in sorted(data["verses"], key=lambda v: int(v["verse"]))])
        time.sleep(2.2)   # stay under ~15 requests / 30 s
    return out

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = {}
    try:
        z = zipfile.ZipFile(io.BytesIO(get(ARUL_ZIP)))
        for n in z.namelist():
            if n.lower().endswith(".json"):
                files[norm(os.path.splitext(os.path.basename(n))[0])] = z.read(n)
        print(f"Downloaded source 1 ({len(files)} json files)")
    except Exception as e:
        print(f"Source 1 unavailable: {e}")

    failed = []
    for name, uid, nch, nv in BOOKS:
        chapters, src = None, ""
        try:
            chapters, src = from_arul(files, name), "aruljohn"
        except Exception as e:
            print(f"  {name}: source 1 parse error {e}")
        if not chapters or not valid(chapters, nch, nv):
            print(f"  {name}: using fallback source (slow)...")
            try:
                chapters, src = from_api(uid, nch), "bible-api"
            except Exception as e:
                print(f"  {name}: fallback failed {e}")
                chapters = None
        if not chapters or not valid(chapters, nch, nv):
            failed.append(name); continue
        path = os.path.join(OUT_DIR, name.replace(" ", "") + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"book": name, "chapters": chapters}, f, ensure_ascii=False, separators=(",", ":"))
        print(f"OK {name:16} {nch:3} ch {nv:5} v  [{src}]")

    if failed:
        print("FAILED:", ", ".join(failed)); sys.exit(1)
    print("All 66 books written, 31,102 verses.")

if __name__ == "__main__":
    main()

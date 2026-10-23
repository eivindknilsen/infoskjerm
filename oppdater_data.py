#!/usr/bin/env python3
"""Byt ut datablokka i infoskjerm-sida (index.html).

Bruk:
  python3 -I oppdater_data.py index.html ny_data.json ut.html            # skriv ny side
  python3 -I oppdater_data.py index.html skuleaaret.html ut.html         # hent data frå Skuleåret-artefakten
                                                                          # (claude.ai/code/artifact/365480f0-...)
  python3 -I oppdater_data.py index.html --dump gammal_data.json          # hent ut dagens data

ny_data.json: {"UPDATED": "DD.MM.ÅÅÅÅ kl. HH:MM", "WEEKS": [...], "VF": {...}, "TS": {...}, "NAMES": {...}}
Berre blokka mellom /* DATA START */ og /* DATA END */ blir endra. Skriptet sjekkar formatet
og skriv ut eit samandrag av kva som er endra.
"""
import json, re, sys

KINDS = {"", "linje", "tur", "tun", "ferie", "valfag"}
START, END = "/* DATA START */", "/* DATA END */"


def read_block(html):
    a, b = html.index(START), html.index(END)
    out = {}
    for line in html[a + len(START):b].strip().splitlines():
        m = re.match(r"var (\w+) = (.*);$", line.strip())
        if m:
            out[m.group(1)] = json.loads(m.group(2))
    return out


def from_artifact(path):
    """Hent WEEKS, VF, TS, NAMES og tidspunkt frå Skuleåret-artefakten (blir oppdatert dagleg frå arka)."""
    h = open(path, encoding="utf-8").read()
    out = {}
    for k in ("WEEKS", "VF", "TS", "NAMES"):
        m = re.search(r"^(?:const|var|let) " + k + r" = (.*?);\s*(?://.*)?$", h, re.M)
        if not m:
            raise SystemExit(f"Fann ikkje {k} i {path}")
        out[k] = json.loads(m.group(1))
    m = re.search(r"TILSYNSLISTA (\d{2}\.\d{2}\.\d{4} kl\. \d{2}:\d{2})", h)
    if not m:
        raise SystemExit(f"Fann ikkje tidspunkt (Henta frå arka ...) i {path}")
    out["UPDATED"] = m.group(1)
    return out


def validate(d):
    err = []
    for k in ("UPDATED", "WEEKS", "VF", "TS", "NAMES"):
        if k not in d:
            err.append(f"manglar {k}")
    if err:
        return err
    if not re.match(r"^\d{2}\.\d{2}\.\d{4} kl\. \d{2}:\d{2}$", d["UPDATED"]):
        err.append("UPDATED må vere på forma DD.MM.ÅÅÅÅ kl. HH:MM")
    if len(d["WEEKS"]) < 30:
        err.append(f"berre {len(d['WEEKS'])} veker i WEEKS")
    for w in d["WEEKS"]:
        if not isinstance(w.get("w"), int) or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(w.get("mon"))):
            err.append(f"ugyldig veke: {w.get('w')}")
        if len(w.get("days", [])) != 7:
            err.append(f"veke {w.get('w')}: må ha 7 dagar")
        for d_ in w.get("days", []):
            if d_.get("k") not in KINDS or not isinstance(d_.get("t"), str):
                err.append(f"veke {w.get('w')}: ugyldig dag {d_}")
        for f in ("plan", "party"):
            if not isinstance(w.get(f), str):
                err.append(f"veke {w.get('w')}: {f} må vere tekst")
    for k, g in d["VF"].items():
        if not isinstance(g.get("title"), str) or not isinstance(g.get("subs"), list) or not isinstance(g.get("pv"), bool):
            err.append(f"VF {k}: manglar title/pv/subs")
        for s in g.get("subs", []):
            if not isinstance(s.get("l"), list):
                err.append(f"VF {k}: l må vere liste")
    for date, v in d["TS"].items():
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date) or not set(v) <= {"o", "t", "n"}:
            err.append(f"TS {date}: ugyldig")
    return err


def summary(old, new):
    lines = []
    ow = {w["w"]: w for w in old.get("WEEKS", [])}
    for w in new["WEEKS"]:
        o = ow.get(w["w"])
        if o is None:
            lines.append(f"veke {w['w']}: ny")
            continue
        if o.get("plan") != w["plan"] or o.get("party") != w["party"]:
            lines.append(f"veke {w['w']}: timeplan/oppvask endra")
        for i, (a, b) in enumerate(zip(o["days"], w["days"])):
            if a != b:
                lines.append(f"veke {w['w']} dag {i + 1}: «{a['t']}» -> «{b['t']}» ({b['k']})")
    for k in sorted(set(old.get("VF", {})) | set(new["VF"])):
        if old.get("VF", {}).get(k) != new["VF"].get(k):
            lines.append(f"valfag/prosjekt {k}: endra")
    ts_o, ts_n = old.get("TS", {}), new["TS"]
    for date in sorted(set(ts_o) | set(ts_n)):
        if ts_o.get(date) != ts_n.get(date):
            lines.append(f"vakter {date}: {ts_o.get(date)} -> {ts_n.get(date)}")
    if old.get("NAMES") != new["NAMES"]:
        lines.append("lærarnamn (NAMES) endra")
    return lines


def main():
    html = open(sys.argv[1], encoding="utf-8").read()
    old = read_block(html)
    if len(sys.argv) == 4 and sys.argv[2] == "--dump":
        json.dump(old, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("Skreiv", sys.argv[3]); return
    src = sys.argv[2]
    new = from_artifact(src) if src.endswith((".html", ".htm")) else json.load(open(src, encoding="utf-8"))
    err = validate(new)
    if err:
        print("FEIL I DATA – ingenting skrive:\n" + "\n".join(err[:40])); sys.exit(1)
    block = START + "\n" + "\n".join(
        f"var {k} = {json.dumps(new[k], ensure_ascii=False, separators=(',', ':'))};"
        for k in ("UPDATED", "WEEKS", "VF", "TS", "NAMES")) + "\n"
    a, b = html.index(START), html.index(END)
    out = html[:a] + block + html[b:]
    out = re.sub(r'<span id="updated">[^<]*</span>', f'<span id="updated">{new["UPDATED"]}</span>', out)
    open(sys.argv[3], "w", encoding="utf-8").write(out)
    ch = summary(old, new)
    print(f"Skreiv {sys.argv[3]}. {len(ch)} endringar:" if ch else f"Skreiv {sys.argv[3]}. Ingen endringar i data.")
    for l in ch:
        print(" -", l)


if __name__ == "__main__":
    main()

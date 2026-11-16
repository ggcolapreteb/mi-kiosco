#!/usr/bin/env python3
"""Lee todos los feeds de fuentes.json y deja las noticias en data.json.

Lo ejecuta GitHub Actions cada cierto rato (ver .github/workflows/actualizar.yml).
Solo usa la biblioteca estándar de Python.
"""
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

LARGO_RESUMEN = 600      # caracteres máximos del párrafo de cada tarjeta
MAX_POR_FUENTE = 40      # notas que se guardan por fuente
DIAS_MAXIMO = 3          # se descartan notas más viejas que esto
ESPERA = 20              # segundos de espera por feed

# Para los feeds "mixtos": qué trozo de la URL manda la nota a qué categoría.
RUTAS_MIXTO = [
    (re.compile(r"/(deportes|futbol)/"), "deportes"),
    (re.compile(r"/(internacional|mundo)/"), "internacional"),
    (re.compile(r"/(nacional|pais|economia|politica)/"), "nacional"),
]

NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
ES_BUSCADOR = re.compile(r"news\.google\.|bing\.com")


def bajar(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": NAVEGADOR,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=ESPERA) as r:
        return r.read()


def local(tag):
    """Nombre de la etiqueta sin el espacio de nombres."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def texto_plano(s):
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def primera_imagen(s):
    m = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", s or "", re.I)
    return m.group(1) if m else ""


def resumir(texto):
    """Oraciones completas del texto que publica el medio, hasta el largo máximo."""
    texto = re.sub(r"\s*(The post|La entrada) .{0,200}$", "", texto).strip()
    if len(texto) <= LARGO_RESUMEN:
        return texto
    oraciones = re.split(r"(?<=[.!?…»”\"])\s+(?=[A-ZÁÉÍÓÚÑ¿¡\"“«])", texto)
    out = ""
    for o in oraciones:
        if out and len(out) + 1 + len(o) > LARGO_RESUMEN:
            break
        out = f"{out} {o}" if out else o
        if len(out) >= LARGO_RESUMEN * 0.6:
            break
    if len(out) > LARGO_RESUMEN:
        out = re.sub(r"\s+\S*$", "", out[:LARGO_RESUMEN]) + "…"
    return out


def fecha_ms(s):
    s = (s or "").strip()
    if not s:
        return 0
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return 0
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp() * 1000)


def leer_feed(datos):
    """Devuelve las notas de un RSS, Atom o RDF como lista de diccionarios."""
    raiz = ET.fromstring(datos)
    notas = []
    for nodo in raiz.iter():
        if local(nodo.tag) not in ("item", "entry"):
            continue
        d = {"titulo": "", "link": "", "fecha": "", "desc": "", "cont": "", "img": ""}
        for h in nodo:
            n, t = local(h.tag), (h.text or "").strip()
            if n == "title":
                d["titulo"] = t
            elif n == "link":
                href = h.get("href")
                if href:
                    if h.get("rel", "alternate") == "alternate":
                        d["link"] = href
                elif t:
                    d["link"] = t
            elif n == "guid" and not d["link"] and t.startswith("http"):
                d["link"] = t
            elif n in ("pubDate", "date", "published") or (n == "updated" and not d["fecha"]):
                d["fecha"] = t
            elif n in ("description", "summary"):
                d["desc"] = t
            elif n in ("encoded", "content") and t:
                d["cont"] = t
            if n in ("content", "thumbnail", "enclosure") and h.get("url") and not d["img"]:
                tipo = h.get("type") or h.get("medium") or "image"
                if "image" in tipo:
                    d["img"] = h.get("url")
        notas.append(d)
    return notas


def convertir(f, crudas, ahora_ms):
    """Pasa las notas crudas de un feed al formato de data.json, descartando las viejas."""
    notas = []
    sufijo = re.compile(r"\s+[-–|]\s+[^-–|]{2,40}$")
    for x in crudas:
        link = x["link"]
        titulo = texto_plano(x["titulo"])
        if not titulo or not link.startswith("http"):
            continue
        buscador = bool(ES_BUSCADOR.search(link))
        if "news.google." in link:
            titulo = sufijo.sub("", titulo)
        cat = f["cat"]
        if cat == "auto":
            ruta = urlparse(link).path
            cat = next((c for patron, c in RUTAS_MIXTO if patron.search(ruta)), None)
            if not cat:
                continue
        ts = fecha_ms(x["fecha"])
        if ts and ahora_ms - ts > DIAS_MAXIMO * 86400000:
            continue
        bajada = "" if buscador else texto_plano(x["desc"])
        cuerpo = "" if buscador else texto_plano(x["cont"])
        res = resumir(cuerpo if len(cuerpo) > len(bajada) else bajada)
        if res.lower() == titulo.lower():
            res = ""
        img = "" if buscador else (x["img"] or primera_imagen(x["cont"]) or primera_imagen(x["desc"]))
        if not img.startswith("http"):
            img = ""
        nota = {"titulo": titulo, "link": link, "ts": ts, "medio": f["medio"], "cat": cat,
                "desc": bajada[:300], "res": res, "img": img}
        if f.get("sub"):
            nota["sub"] = f["sub"]
        if f.get("afuera"):
            nota["afuera"] = True
        if buscador:
            nota["buscador"] = True
        notas.append(nota)
    notas.sort(key=lambda n: -n["ts"])
    return notas[:MAX_POR_FUENTE]


def procesar(f, ahora_ms):
    """Trae una fuente probando sus URL en orden hasta que una entregue notas recientes."""
    notas, usada, avisos = [], "", []
    for url in f["urls"]:
        sitio = urlparse(url).netloc
        try:
            crudas = leer_feed(bajar(url))
        except Exception as e:  # noqa: BLE001 - cualquier fallo pasa a la URL siguiente
            avisos.append(f"{sitio}: {type(e).__name__} {str(e)[:80]}".strip())
            continue
        notas = convertir(f, crudas, ahora_ms)
        if notas:
            usada = url
            break
        avisos.append(f"{sitio}: " + ("sin notas recientes" if crudas else "feed vacío"))
    estado = {"medio": f["medio"], "cat": f["cat"], "tipo": f["tipo"]}
    if not notas:
        estado.update(ok=False, n=0, msg=" · ".join(avisos))
        return estado, []
    por_buscador = bool(ES_BUSCADOR.search(usada)) and f["tipo"] == "rss"
    estado.update(ok=True, n=len(notas), msg="por buscador" if por_buscador else "")
    return estado, notas


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "."
    with open(f"{carpeta}/fuentes.json", encoding="utf-8") as fh:
        fuentes = json.load(fh)
    ahora_ms = int(time.time() * 1000)
    with ThreadPoolExecutor(max_workers=8) as pool:
        resultados = list(pool.map(lambda f: procesar(f, ahora_ms), fuentes))
    estados = [e for e, _ in resultados]
    notas = [n for _, ns in resultados for n in ns]
    for e in estados:
        print(("OK   " if e["ok"] and e["n"] else "FALLA"), e["medio"], f"[{e['cat']}]", e["n"], e["msg"])
    print(f"Total: {len(notas)} notas de {sum(1 for e in estados if e['n'])}/{len(estados)} fuentes")
    if not notas:
        print("No llegó ninguna nota: se conserva el data.json anterior.")
        return
    with open(f"{carpeta}/data.json", "w", encoding="utf-8") as fh:
        json.dump({"generado": ahora_ms, "fuentes": estados, "notas": notas}, fh, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()

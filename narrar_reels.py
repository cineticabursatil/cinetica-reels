# -*- coding: utf-8 -*-
"""
Cinética Bursátil · Narrador de reels · v1 (08-11-2026)
Quita la música de cada reel y pone una voz masculina sintética (Microsoft Neural, gratis vía edge-tts)
leyendo el texto de cada escena en su segundo exacto.

REQUISITOS (una sola vez):
  1) Python 3.9+  (python.org, marcar "Add Python to PATH")
  2) FFmpeg       (Windows: abre PowerShell y ejecuta:  winget install Gyan.FFmpeg )
  3) pip install edge-tts

USO (en la carpeta donde están los 15 .mp4 de Reels_FINAL_desde_08-11.zip):
  python narrar_reels.py --muestras        -> crea 4 muestras de voz para elegir (carpeta muestras_voz)
  python narrar_reels.py                   -> narra los 15 reels con la voz por defecto
  python narrar_reels.py --voz es-ES-AlvaroNeural
  python narrar_reels.py --solo 01         -> solo el reel que empieza por 01
Salida: carpeta  final_voz/  (mismos nombres). Los originales NO se tocan.
"""
import asyncio, json, os, subprocess, sys, argparse, shutil, tempfile

VOCES = {  # voces masculinas en español; ninguna permite elegir "50 años", se ajusta tono y ritmo
    "es-MX-JorgeNeural":   "México, cálida y madura (recomendada)",
    "es-ES-AlvaroNeural":  "España, grave y seria",
    "es-CO-GonzaloNeural": "Colombia, neutra",
    "es-US-AlonsoNeural":  "EE. UU. hispano, neutra",
}
PITCH = "-8Hz"     # más grave = suena mayor. Prueba -4Hz a -12Hz
RATE  = "-4%"      # algo más pausado
GAP   = 0.15       # segundos mínimos entre frases
MAX_ACEL = 1.22    # si una frase no cabe en su escena, se acelera hasta 18 %; si aún no cabe, empuja la siguiente

AQUI = os.path.dirname(os.path.abspath(__file__))

def dur(path):
    out = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",path],
                         capture_output=True, text=True).stdout.strip()
    return float(out)

async def tts(texto, voz, salida):
    import edge_tts
    await edge_tts.Communicate(texto, voz, rate=RATE, pitch=PITCH).save(salida)

def buscar(nombre):
    for c in [os.getcwd(), os.path.join(os.getcwd(),"final"), AQUI, os.path.join(AQUI,"final")]:
        p = os.path.join(c, nombre)
        if os.path.exists(p): return p
    return None

def narrar(nombre, segs, voz, outdir, tmp):
    src = buscar(nombre)
    if not src: print("  [FALTA]", nombre); return
    vdur = dur(src)
    partes, cursor = [], 0.0
    for i, s in enumerate(segs):
        mp3 = os.path.join(tmp, f"s{i}.mp3"); wav = os.path.join(tmp, f"s{i}.wav")
        asyncio.run(tts(s["texto"], voz, mp3))
        d = dur(mp3)
        ini = max(s["inicio"], cursor + (GAP if i else 0))
        sig = segs[i+1]["inicio"] if i+1 < len(segs) else vdur - 3.2   # deja libre la placa final de 3 s
        espacio = max(sig - ini - GAP, 0.5)
        f = min(max(d / espacio, 1.0), MAX_ACEL)
        subprocess.run(["ffmpeg","-y","-v","error","-i",mp3,"-af",f"atempo={f:.3f}","-ar","48000","-ac","2",wav], check=True)
        d2 = d / f
        partes.append((wav, ini)); cursor = ini + d2
    if cursor > vdur - 0.3: print(f"  [AVISO] la voz termina en {cursor:.1f}s y el video dura {vdur:.1f}s")
    ins, filt = ["-i", src], []
    for j,(w,ini) in enumerate(partes):
        ins += ["-i", w]; ms = int(ini*1000)
        filt.append(f"[{j+1}:a]adelay={ms}|{ms}[a{j}]")
    filt.append("".join(f"[a{j}]" for j in range(len(partes))) + f"amix=inputs={len(partes)}:normalize=0,"
                f"apad,atrim=0:{vdur:.2f},highpass=f=70,acompressor=threshold=-20dB:ratio=3,loudnorm=I=-14:TP=-1.5[v]")
    out = os.path.join(outdir, nombre)
    subprocess.run(["ffmpeg","-y","-v","error",*ins,"-filter_complex",";".join(filt),
                    "-map","0:v","-map","[v]","-c:v","copy","-c:a","aac","-b:a","192k","-shortest",out], check=True)
    print(f"  OK  {nombre}  ({cursor:.1f}s de voz / {vdur:.1f}s)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voz", default="es-MX-JorgeNeural")
    ap.add_argument("--muestras", action="store_true")
    ap.add_argument("--solo", default="")
    a = ap.parse_args()
    for exe in ("ffmpeg","ffprobe"):
        if not shutil.which(exe): sys.exit(f"Falta {exe}. Instálalo: winget install Gyan.FFmpeg  (y cierra/abre la ventana)")
    try: import edge_tts  # noqa
    except ImportError: sys.exit("Falta edge-tts. Ejecuta:  pip install edge-tts")
    if a.muestras:
        os.makedirs("muestras_voz", exist_ok=True)
        t = "El precio también tiene energía. No adivina: mide. Sígueme y aprende a leer la cinética del precio."
        for v,desc in VOCES.items():
            asyncio.run(tts(t, v, os.path.join("muestras_voz", v+".mp3"))); print("  muestra:", v, "-", desc)
        print("Escucha la carpeta muestras_voz y luego ejecuta:  python narrar_reels.py --voz NOMBRE"); return
    data = json.load(open(os.path.join(AQUI,"narraciones.json"), encoding="utf-8"))
    os.makedirs("final_voz", exist_ok=True)
    print("Voz:", a.voz)
    for nombre, segs in data.items():
        if a.solo and not nombre.startswith(a.solo): continue
        with tempfile.TemporaryDirectory() as tmp:
            try: narrar(nombre, segs, a.voz, "final_voz", tmp)
            except Exception as e: print("  [ERROR]", nombre, e)
    print("\nListo. Revisa la carpeta final_voz y súbela a Drive.")

if __name__ == "__main__":
    main()

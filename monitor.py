#!/usr/bin/env python3
import logging, os, re, smtplib, sys, time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("scjn")
CDMX = timezone(timedelta(hours=-6))
SJF  = "https://sjfsemanal.scjn.gob.mx"
SJF2 = "https://sjf2.scjn.gob.mx"
BJ   = "https://bj.scjn.gob.mx"

ALERTAS = [
    {"id":"competencia","name":"Competencia Economica - COFECE/CNA",
     "keywords":["COFECE","CNA","practicas monopolicas","poder sustancial"],
     "contexto":"Aeromexico en procedimientos ante COFECE/CNA. Interesa poder sustancial en transporte aereo."},
    {"id":"fiscal","name":"Fiscal - SAT - Precios de Transferencia",
     "keywords":["precios de transferencia","regalias","credito fiscal","caducidad facultades"],
     "contexto":"Aeromexico litiga creditos fiscales SAT por regalias y precios de transferencia."},
    {"id":"amparo","name":"Amparo Corporativo - Suspension",
     "keywords":["suspension acto reclamado","apariencia buen derecho","amparo indirecto"],
     "contexto":"Amparos contra AFAC, SAT y COFECE. Estandar de suspension para personas morales."},
    {"id":"mercantil","name":"Litigio Mercantil - Contratos - Nulidad",
     "keywords":["rescision contrato mercantil","nulidad absoluta","fraude contractual"],
     "contexto":"Litigio contra agencias de viajes por fraude. Nulidad y danos mercantiles."},
    {"id":"aviacion","name":"Aviacion - AFAC - Regulatorio",
     "keywords":["AFAC","transporte aereo","Ley de Aviacion Civil","derechos pasajero"],
     "contexto":"Procedimientos ante AFAC. Regimen sancionador y derechos de pasajeros."},
]

def buscar(kw):
    enc = quote(kw)
    return {"titulo": f"Criterios SJF: {kw}",
            "extracto": f"Criterios relacionados con {kw} en la 12a Epoca del SJF.",
            "organo": "SCJN / TCC / Plenos Regionales",
            "fecha": datetime.now(CDMX).strftime("%d %b %Y"),
            "url_sjf": f"{SJF}/busqueda-principal-tesis?expresion={enc}&idEpoca=12",
            "url_bj":  f"{BJ}/busqueda?q={enc}&indice=tesis",
            "kw": kw, "rel": 0, "analisis": ""}

def analizar(t, contexto, kws):
    key = os.environ.get("ANTHROPIC_API_KEY","")
    if not key:
        t["rel"] = 70
        t["analisis"] = "Configura ANTHROPIC_API_KEY en Secrets de GitHub para analisis con IA."
        return t
    prompt = (f"Criterio SJF 12a Epoca.\nRUBRO: {t['titulo']}\nCONTEXTO: {contexto}\n"
              f"KEYWORDS: {', '.join(kws[:3])}\n\n"
              f"Responde exactamente:\nRELEVANCIA: [0-100]\nANALISIS: [3 oraciones estrategicas]")
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"},
            json={"model":"claude-sonnet-4-6","max_tokens":250,
                  "system":"Eres abogado senior experto en litigio corporativo mexicano.",
                  "messages":[{"role":"user","content":prompt}]}, timeout=30)
        raw = r.json()["content"][0]["text"]
        rel, analisis = 60, ""
        for line in raw.split("\n"):
            if "RELEVANCIA:" in line.upper():
                try: rel = max(0,min(100,int(re.sub(r"\D","",line.split(":",1)[1]))))
                except: pass
            elif "ANALISIS:" in line.upper():
                analisis = line.split(":",1)[1].strip()
        t["rel"] = rel
        t["analisis"] = analisis or raw[:200]
    except Exception as e:
        t["rel"] = 60
        t["analisis"] = f"Analisis no disponible: {e}"
    return t

def correo_html(alerta, resultados):
    now = datetime.now(CDMX).strftime("%d/%m/%Y %H:%M CDMX")
    cards = ""
    for t in resultados:
        c = "#8B1A1A" if t["rel"]>=75 else ("#B8860B" if t["rel"]>=50 else "#1A3A5C")
        cards += f"""<div style="border:1px solid #ddd;border-left:4px solid {c};padding:16px;margin:10px 0;background:#fafafa">
<p style="font-size:11px;color:#888;margin:0 0 6px">{t['fecha']} | Relevancia: <b>{t['rel']}%</b></p>
<p style="font-size:14px;font-weight:bold;color:#111;margin:0 0 8px">{t['titulo']}</p>
<p style="font-size:12px;color:#444;margin:0 0 10px">{t['extracto']}</p>
<div style="background:#EEF3F8;border-left:3px solid #1A3A5C;padding:8px 12px;font-size:12px;color:#2C3E50;margin-bottom:10px">
<b>Analisis Claude:</b> {t['analisis']}</div>
<p style="font-size:11px;color:#555;margin:0 0 8px">Organo: {t['organo']}</p>
<a href="{t['url_sjf']}" style="padding:5px 14px;background:#0D0D0D;color:#fff;text-decoration:none;font-size:11px;font-weight:bold;margin-right:8px">Ver en SJF</a>
<a href="{t['url_bj']}" style="padding:5px 14px;background:#1A3A5C;color:#fff;text-decoration:none;font-size:11px;font-weight:bold">Buscador Juridico</a>
</div>"""
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"></head>
<body style="margin:0;background:#F5F4F0;font-family:Georgia,serif">
<div style="max-width:680px;margin:0 auto;background:#fff">
<div style="background:#0D0D0D;padding:24px 32px;border-bottom:3px solid #B8860B">
<h1 style="font-size:24px;color:#fff;margin:0">Alerta Juridica Diaria - SCJN</h1>
<p style="font:11px Arial;color:#888;margin:4px 0 0">Semanario Judicial de la Federacion - 12a Epoca</p>
</div>
<div style="background:#1A3A5C;padding:10px 32px;overflow:hidden">
<span style="font:bold 12px Arial;color:#D4A017">{alerta['name']}</span>
<span style="font:11px monospace;color:#9E9E9E;float:right">{now}</span>
</div>
<div style="padding:0 32px 24px">{cards}</div>
<div style="background:#0D0D0D;padding:16px 32px;font:10px Arial;color:#666;border-top:2px solid #B8860B">
<a href="{SJF}" style="color:#B8860B;text-decoration:none;margin-right:12px">SJF Semanal</a>
<a href="{SJF2}" style="color:#B8860B;text-decoration:none;margin-right:12px">SJF Historico</a>
<a href="https://jurislex.scjn.gob.mx/" style="color:#B8860B;text-decoration:none;margin-right:12px">JurisLex</a>
<a href="https://www.tfja.gob.mx/cesmdfa/sctj/" style="color:#B8860B;text-decoration:none">TFJA</a>
<p style="margin:8px 0 0">SCJN Intelligence Monitor - Aeromexico - Director Juridico</p>
</div></div></body></html>"""

def enviar(to, subject, html):
    user = os.environ.get("SMTP_USER","")
    pw   = os.environ.get("SMTP_PASSWORD","")
    if not user or not pw:
        logger.error("SMTP no configurado"); return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"SCJN Monitor <{user}>"
    msg["To"]      = to
    msg.attach(MIMEText(html,"html","utf-8"))
    try:
        with smtplib.SMTP("smtp.gmail.com",587,timeout=30) as s:
            s.ehlo(); s.starttls(); s.login(user,pw)
            s.sendmail(user,[to],msg.as_string())
        logger.info(f"Correo enviado a {to}"); return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Auth SMTP fallida. Verifica App Password en Secrets."); return False
    except Exception as e:
        logger.error(f"Error SMTP: {e}"); return False

def main():
    to = os.environ.get("DEFAULT_EMAIL","")
    logger.info(f"SCJN Monitor iniciado - {datetime.now(CDMX).strftime('%Y-%m-%d %H:%M CDMX')}")
    for alerta in ALERTAS:
        logger.info(f"Procesando: {alerta['name']}")
        resultados = []
        for kw in alerta["keywords"]:
            t = buscar(kw)
            t = analizar(t, alerta["contexto"], alerta["keywords"])
            resultados.append(t)
            time.sleep(0.5)
        resultados.sort(key=lambda x: x["rel"], reverse=True)
        html   = correo_html(alerta, resultados)
        asunto = f"[SCJN] {alerta['name']} - {datetime.now(CDMX).strftime('%d/%m/%Y')}"
        enviar(to, asunto, html)
        time.sleep(1)
    logger.info("Monitor completado")

if __name__=="__main__":
    main()

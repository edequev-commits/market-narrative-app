MARKET NARRATIVE DASHBOARD v1.0

========================================
ESTADO DEL PROYECTO
===================

Versión oficial estable y productiva del dashboard de narrativa de mercado.

Esta versión reemplaza completamente la arquitectura anterior basada en Web Service (Streamlit server), la cual fue descontinuada por problemas de disponibilidad (Error 521).

---

## URL OFICIAL

https://market-narrative-appv2.onrender.com

---

## ARQUITECTURA FINAL

1. Extracción de datos:

   * Lectura de correos Gmail (label: "Noticias Trading")
   * Filtro por ventana de tiempo (01:00 – 09:00, hora Monterrey)

2. Procesamiento:

   * Extracción de fuentes clave:
     • Vital Knowledge
     • Reuters
   * Normalización y consolidación de señales
   * Eliminación de ruido y contradicciones (LLM Signal Filter)

3. Generación de narrativa:

   * Construcción de prompt estructurado
   * Ejecución de modelo LLM
   * Generación de narrativa macro institucional

4. Generación de dashboard:

   * Script: build_static_dashboard.py
   * Salida: dist/index.html (HTML estático)

5. Publicación:

   * GitHub Actions:
     • Ejecuta app.py
     • Ejecuta build_static_dashboard.py
     • Hace commit automático de outputs
   * Render Static Site:
     • Publica carpeta /dist
     • Despliegue automático al detectar cambios

---

## HORARIOS DE EJECUCIÓN (UTC-6 Monterrey)

• 02:00 AM
• 10:00 AM
• 03:00 PM
• 08:00 PM

---

## MEJORAS IMPLEMENTADAS EN v1.0

• Corrección de timezone a Monterrey (UTC-6)
• Formato de fecha:
DD/MM/AAAA - HH:MM
• Eliminación de correos en fuentes (mejora visual)
• Eliminación de campo "Contribución" en dashboard web
• Corrección de layout:

* Altura consistente entre narrativa y fuentes
  • Migración completa a arquitectura estática
  • Eliminación de dependencia de puertos / servidor
  • Eliminación de errores Cloudflare 521

---

## ESTRUCTURA DEL PROYECTO

/data
dashboard_payload.json
market_narrative.txt
filtered_signal.json
last_refresh.json
...

/dist
index.html  ← dashboard final publicado

/prompts
/src
app.py
build_static_dashboard.py
dashboard.py

---

## FLUJO OPERATIVO

Local → GitHub → GitHub Actions → Render Static Site

---

## NOTAS IMPORTANTES

• No usar servicios Web Service (Streamlit en servidor)
• Toda la lógica productiva depende de HTML estático
• Render solo sirve contenido, no ejecuta lógica
• GitHub es el orquestador del sistema

---

## VERSIONAMIENTO

Versión actual: v1.0

Esta versión es el punto base para:
• Escalamiento
• Migración a mobile
• Evolución a SaaS

---

## AUTOR

Proyecto desarrollado como sistema profesional de análisis para trading institucional.

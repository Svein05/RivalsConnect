---
name: rivalsconnect-gitflow
description: Reglas obligatorias para el flujo de trabajo de Git (GitFlow) y ramas en RivalsConnect.
---

# Reglas de GitFlow para RivalsConnect

Al trabajar en este proyecto, DEBES seguir estrictamente estas reglas:

## 1. Ramas Principales
- **\main\**: Es la rama de producción. NUNCA programes ni hagas commits directamente aquí.
- **\develop\**: Es la rama principal de desarrollo. Tampoco programes directamente aquí, úsala como base para sacar nuevas ramas.

## 2. Flujo de Trabajo (GitFlow)
- Para cada nueva característica, bugfix o tarea, DEBES crear una nueva rama temporal partiendo de \develop\.
- Nombres de ramas permitidos:
  - \eature/nombre-de-la-tarea\ (Para nuevas funcionalidades)
  - \ix/nombre-del-error\ (Para correcciones de errores)
  - \chore/nombre-de-tarea-menor\ (Para mantenimiento)

## 3. Fusiones (Merges) y Gráfico de Historial
- Cuando termines el trabajo en tu rama temporal, debes fusionarla de vuelta a \develop\.
- **CRÍTICO:** DEBES preservar el historial para que se vean las burbujas o divisiones en herramientas visuales de Git (como SourceTree). Utiliza SIEMPRE el comando \git merge --no-ff nombre-de-rama\.
- NO borres las ramas inmediatamente del historial remoto, de forma que el usuario pueda ver el progreso.

## 4. Despliegue a Producción
- Solo después de que el usuario verifique y apruebe manualmente el código en \develop\, se procederá a fusionar \develop\ en \main\.
- Al fusionar a \main\, usa también \git merge --no-ff develop\ para mantener el gráfico visible.

## 5. Revisión de Código
- Antes de cada commit o push, SIEMPRE revisa el código meticulosamente.
- Evita dejar errores de sintaxis o variables que generen "shadowing".

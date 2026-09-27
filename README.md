# League of Legends Discord RPC para macOS 🎮✨

[![macOS](https://img.shields.io/badge/Platform-macOS%2012%2B-blue?logo=apple)](https://www.apple.com/macos/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-brightgreen?logo=python)](https://www.python.org/)
[![PyObjC](https://img.shields.io/badge/UI-PyObjC%20Cocoa%20%2B%20WebKit-orange)](https://pyobjc.readthedocs.io/)
[![Discord IPC](https://img.shields.io/badge/Discord-Rich%20Presence-5865F2?logo=discord)](https://discord.com/)
[![Tests](https://img.shields.io/badge/Tests-149%2F149%20Passing%20(100%25)-success)](#-suite-de-pruebas)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success)]()

Aplicación nativa para la barra de menús de macOS (**Menubar Agent / `LSUIElement`**) que sincroniza en tiempo real tu presencia enriquecida (**Rich Presence**) de **League of Legends** en Discord. Diseñada con una estética moderna **Liquid Glass (Dark Aqua HUD)**, buscador de 173 campeones con avatares en tiempo real y arquitectura concurrente de sockets sin bloqueos en la interfaz.

---

## 📑 Tabla de Contenidos

- [Características Principales](#-características-principales)
- [Requisitos Previos](#-requisitos-previos)
- [Instalación Paso a Paso (Desde Cero)](#-instalación-paso-a-paso-desde-cero)
- [Guía Completa de Uso](#-guía-completa-de-uso)
  - [1. Dónde encontrar la aplicación](#1-dónde-encontrar-la-aplicación)
  - [2. Estados del icono en la barra de menú](#2-estados-del-icono-en-la-barra-de-menú)
  - [3. Selector de Modo (Oficial vs Detallado)](#3-selector-de-modo-oficial-vs-detallado)
  - [4. Buscador interactivo de 173 Campeones](#4-buscador-interactivo-de-173-campeones)
  - [5. Modos de Juego y Modo Personalizado](#5-modos-de-juego-y-modo-personalizado)
  - [6. Rangos y Emblemas Clasificatorios](#6-rangos-y-emblemas-clasificatorios)
  - [7. Interruptores y Automatización](#7-interruptores-y-automatización)
  - [8. Pausar y Reanudar Presencia](#8-pausar-y-reanudar-presencia)
  - [9. Selector de los 10 Juegos Más Jugados y Client ID (⚙️)](#9-selector-de-los-10-juegos-más-jugados-y-client-id-️)
- [Arranque Automático con macOS](#-arranque-automático-con-macos)
- [Arquitectura del Proyecto](#-arquitectura-del-proyecto)
- [Suite de Pruebas Automatizadas](#-suite-de-pruebas-automatizadas)
- [Resolución de Problemas Frecuentes (FAQ)](#-resolución-de-problemas-frecuentes-faq)
- [Licencia](#-licencia)

---

## 🌟 Características Principales

- **Diseño Liquid Glass Unificado**: Ventana flotante nativa (`NSPopover`) sin bordes dobles, con transparencia translúcida macOS HUD Window y reflejos sutiles.
- **Icono Reactivo en la Barra de Menús**: Muestra un punto azul dinámico cuando estás conectado y sincronizando presencia en Discord.
- **Buscador de 173 Campeones con Avatares en Vivo**: Búsqueda instantánea con fotos oficiales en alta resolución desde la CDN de Riot Games Data Dragon, con control por teclado (`↑`, `↓`, `Enter`) o ratón.
- **Modos de Juego Canónicos**: Soporte para Clasificatoria Solo/Dúo, Flex, Normal, ARAM, Arena 2v2v2v2, Clash, Swiftplay, o entrada personalizada de texto libre.
- **Rangos Oficiales de LoL**: Soporte desde Hierro hasta Challenger, con divisiones romanas y supresión automática en rangos Apex (*Master, Grandmaster, Challenger*).
- **Arranque Silencioso**: No muestra icono temporal de Python en el Dock (`LSUIElement = true`) e inicia automáticamente al encender el Mac.
- **Concurrencia Resiliente**: Modelo de Actor protegido contra carreras de hilos (`threading.Lock`) con reconexión automática si Discord se cierra o se abre en segundo plano.

---

## 📋 Requisitos Previos

Antes de instalar, asegúrate de contar con:

1. **macOS**: Versión 12.0 (Monterey), 13.0 (Ventura), 14.0 (Sonoma), 15.0 (Sequoia) o superior.
2. **Procesador**: Compatible de forma nativa con **Apple Silicon** (M1, M2, M3, M4) y procesadores **Intel**.
3. **Python 3.9 o superior**: Puedes verificar si lo tienes con:
   ```bash
   python3 --version
   ```
   *(Si no lo tienes instalado, puedes instalarlo fácilmente con `brew install python` o desde [python.org](https://www.python.org/downloads/mac-osx/))*.
4. **Discord**: La aplicación oficial de escritorio de Discord abierta en tu Mac.

---

## 🚀 Instalación Paso a Paso (Desde Cero)

Sigue estos 4 pasos sencillos en tu terminal para dejar la app instalada en tu sistema:

### Paso 1: Clonar el repositorio
Abre la aplicación **Terminal** en tu Mac y clona este proyecto:
```bash
git clone https://github.com/vcamachoone/Discord-RPC.git
cd Discord-RPC
```

### Paso 2: Crear el entorno virtual de Python
Crea un entorno aislado para no interferir con las librerías del sistema:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Paso 3: Instalar las dependencias
Instala los módulos necesarios (`pyobjc`, `pypresence`, `Pillow`, etc.):
```bash
pip install -r requirements.txt
```

### Paso 4: Sincronizar y compilar el Bundle de macOS
Ejecuta el sincronizador para empaquetar la aplicación directamente en tu carpeta de `/Applications`:
```bash
python sync_bundle.py
```
> ✅ **Listo**: Esto creará el ejecutable oficial `/Applications/League of Legends RPC.app` con su icono nativo y configuración de menubar.

---

## 🎮 Guía Completa de Uso

### 1. Dónde encontrar la aplicación
Una vez abierta, la aplicación **no aparece en el Dock** para no estorbar. Vive directamente en la **barra superior de menús** de tu Mac (al lado del reloj, Wi-Fi y batería), representada por el icono oficial de Discord.

Para abrirla por primera vez:
- Búscala en **Spotlight** (`Cmd + Espacio`) escribiendo: `League of Legends RPC`
- O ábrela desde la terminal:
  ```bash
  open -a "/Applications/League of Legends RPC.app"
  ```

---

### 2. Estados del icono en la barra de menú

El icono en la parte superior te indica el estado de tu conexión en todo momento:

| Icono | Estado | Descripción |
| :---: | :---: | :--- |
| ![Icono Normal](assets/menubar_normal@2x.png) | **En espera / Normal** | Discord está abierto pero la presencia está en pausa o esperando conexión. |
| ![Icono Activo](assets/menubar_active@2x.png) | **Activo (Punto Azul)** | **Conectado**. Tu perfil de Discord está mostrando en vivo tu partida de League of Legends. |
| ![Icono Pausado](assets/menubar_paused@2x.png) | **Pausado / Desconectado** | Presencia detenida manualmente o Discord está cerrado. |

---

### 3. Selector de Modo (Oficial vs Detallado)

Al hacer un clic en el icono de la barra superior, se despliega la ventana flotante **Liquid Glass**. Puedes elegir entre dos modos:

1. **Modo Oficial** *(Por defecto)*:
   - Presencia minimalista y limpia.
   - Muestra el logotipo de League of Legends, el nombre del juego y el cronómetro de tiempo transcurrido.
   - Ideal si solo quieres mostrar que estás jugando sin dar más detalles.

2. **Modo Detallado**:
   - Despliega la configuración completa con el campeón actual, rango y modo de juego.
   - Al seleccionarlo (o al hacer clic en el engranaje ⚙️ de la esquina superior derecha), se abre el panel de personalización avanzada.

---

### 4. Buscador interactivo de 173 Campeones

En el **Modo Detallado**, encontrarás el buscador inteligente de campeones:

- **Escribe para filtrar**: Empieza a escribir el nombre de cualquier campeón (ejemplo: `Ahri`, `Yasuo`, `Jinx`, `Aatrox`, `Kai'Sa`).
- **Avatares en tiempo real**: Al escribir, se despliega una lista con las fotos oficiales en alta resolución traídas directamente de la CDN de **Riot Games Data Dragon**.
- **Control total por teclado**:
  - `↓` (Flecha abajo) y `↑` (Flecha arriba): Navega fluidamente por la lista de resultados.
  - `Enter`: Selecciona el campeón resaltado y actualiza tu presencia de inmediato.
  - `Escape`: Cierra el menú desplegable.
- **Control por ratón**: Haz clic directamente sobre la foto o el nombre de cualquier campeón para seleccionarlo.
- **Normalización inteligente**: Soporta nombres especiales y apodos comunes (ejemplo: escribir `wukong` resuelve automáticamente a `MonkeyKing`, `chogath` a `Chogath`, `kaisa` a `Kaisa`).

---

### 5. Modos de Juego y Modo Personalizado

Puedes indicar exactamente qué tipo de partida estás jugando:

- **Modos oficiales incluidos en la lista**:
  - 🏆 Clasificatoria Solo/Dúo
  - 👥 Clasificatoria Flexible
  - ⚔️ Partida Normal (Reclutamiento)
  - 🎯 Partida Rápida (Swiftplay)
  - ❄️ ARAM (Abismo de los Lamentos)
  - 🥊 Arena (2v2v2v2)
  - 🛡️ Torneo Clash
  - 🤖 Cooperativo vs IA
  - 🎯 Herramienta de Práctica
- **Modo Personalizado**:
  - Selecciona la opción `✏️ Personalizado (Escribir texto libre)...`.
  - Aparecerá una caja de texto donde puedes escribir lo que quieras (ejemplo: `Torneo Universitario`, `1v1 en el Abismo`, `Scouting scrims`).

---

### 6. Rangos y Emblemas Clasificatorios

Muestra tu división competitiva en Discord:

- **Rangos soportados**: Hierro, Bronce, Plata, Oro, Platino, Esmeralda, Diamante, Maestro, Gran Maestro, Challenger y Unranked.
- **Divisiones**: I, II, III y IV.
- **Regla Apex inteligente**: Si seleccionas *Maestro*, *Gran Maestro* o *Challenger*, el selector de divisiones se oculta automáticamente, respetando el formato competitivo oficial de Riot Games (no existe "Challenger II").

---

### 7. Interruptores y Automatización

En la sección intermedia de la ventana flotante dispones de dos interruptores interactivos estilo iOS:

1. **Reiniciar partida (automáticamente cada 20–30 min)**:
   - Al tenerlo activado, la aplicación reinicia el contador de tiempo de la partida en intervalos de 20 a 30 minutos de forma aleatoria y realista.
   - Evita que tu perfil muestre partidas irreales de "Jugando hace 7 horas".
2. **Iniciar automáticamente con macOS (Auto-run)**:
   - Al activarlo, registra un servicio de usuario (`LaunchAgent`) en tu sistema.
   - Cada vez que enciendas o reinicies tu Mac, la aplicación arrancará sola en la barra superior en segundo plano, sin abrir terminales ni ventanas molestas.

---

### 8. Pausar y Reanudar Presencia

En la parte inferior de la ventana tienes el botón principal de control:

- **⏹ DETENER EN DISCORD**: Pausa la presencia y retira la actividad de tu perfil en Discord.
- **▶ INICIAR PRESENCIA**: Vuelve a conectar con Discord y publica tu presencia al instante.

---

### 9. Selector de los 10 Juegos Más Jugados y Client ID (⚙️)

Al hacer clic en el botón de engranaje (**⚙️**) en la esquina superior derecha, se abre la pantalla dedicada de **Configuración & Juegos**:

1. **Top 10 Presets Oficiales**:
   - Puedes cambiar de juego al instante seleccionándolo en el menú desplegable:
     - 🏆 **League of Legends** (Riot Games)
     - 🎯 **VALORANT** (Riot Games)
     - 🔫 **Counter-Strike 2** (Valve)
     - ⛏️ **Minecraft** (Mojang)
     - 🪂 **Fortnite** (Epic Games)
     - 🚗 **Grand Theft Auto V** (Rockstar Games)
     - ⚡ **Apex Legends** (Respawn / EA)
     - 🛡️ **Overwatch 2** (Blizzard Entertainment)
     - ⚔️ **Dota 2** (Valve)
     - 🚀 **Rocket League** (Psyonix)
     - ✏️ **Personalizado (Custom)**: Para escribir un Client ID propio y nombre de juego libre.
2. **Auto-rellenado Inteligente**:
   - Al seleccionar cualquier juego, la aplicación auto-rellena automáticamente el **Discord Application Client ID oficial**, el icono del juego y la duración estimada.
3. **Restauración con un solo clic**:
   - Si modificas el Client ID y quieres volver al valor oficial de League of Legends o del juego elegido, haz clic en **"Restaurar Oficial"**.
4. **Guardado en Caliente**:
   - Pulsa **💾 GUARDAR Y RECONECTAR** para aplicar el cambio inmediatamente sin tener que cerrar ni reiniciar la aplicación.

---

## 🔄 Arranque Automático con macOS

Si activas el interruptor **"Iniciar automáticamente con macOS"**, la aplicación gestiona de forma transparente el siguiente archivo de configuración del sistema:

```
~/Library/LaunchAgents/com.victormanuel.lolrpc.plist
```

### Comandos útiles para verificar el servicio:
- **Verificar que el servicio está cargado**:
  ```bash
  launchctl list | grep lolrpc
  ```
- **Detener el autoarranque manualmente**:
  ```bash
  launchctl unload ~/Library/LaunchAgents/com.victormanuel.lolrpc.plist
  ```
- **Volver a cargar el autoarranque**:
  ```bash
  launchctl load ~/Library/LaunchAgents/com.victormanuel.lolrpc.plist
  ```

---

## 🏛️ Arquitectura del Proyecto

```
discord-rpc/
├── /Applications/League of Legends RPC.app   # Aplicación empaquetada e instalada en macOS
├── app_gui.py              # Controlador principal de la aplicación y bucle de eventos Cocoa
├── popover_ui.py           # Ventana flotante NSPopover nativa y puente WebKit (PyObjC)
├── liquid_html.py          # Interfaz de usuario Liquid Glass en HTML5/CSS3/JavaScript
├── discord_rpc_manager.py  # Actor concurrente de comunicación IPC con Discord (pypresence)
├── status_item.py          # Gestor reactivo del icono de la barra de menús (NSStatusItem)
├── lol_champions.py        # Catálogo de 173 campeones con resolución de CDN Data Dragon
├── lol_ranks.py            # Lógica y validación de rangos, divisiones y emblemas de LoL
├── sync_bundle.py          # Utilidad para compilar y sincronizar el bundle en /Applications
├── requirements.txt        # Dependencias de Python del proyecto
├── launcher.sh             # Script de lanzamiento con variables de entorno de macOS
├── start.sh / stop.sh      # Scripts rápidos para iniciar o matar el proceso en segundo plano
├── assets/                 # Iconos de barra de menús en resoluciones 1x y @2x Retina
└── tests/                  # Suite integral de pruebas automatizadas (149 pruebas)
    ├── test_tier1_features.py       # Cobertura funcional (60 tests)
    ├── test_tier2_boundaries.py     # Casos límite y esquinas (60 tests)
    ├── test_tier3_interactions.py   # Interacciones cruzadas entre módulos (14 tests)
    ├── test_tier4_scenarios.py      # Escenarios de usuario real en macOS (5 tests)
    ├── test_adversarial_stress.py   # Estrés adversarial y reconexión de sockets (10 tests)
    └── run_tests.py                 # Ejecutor maestro de pruebas
```

---

## 🧪 Suite de Pruebas Automatizadas

El proyecto incluye una suite de pruebas exhaustiva con **149 pruebas automatizadas** divididas en 5 niveles de rigor (Tiers 1 al 5):

Para ejecutar la verificación completa:
```bash
venv/bin/python tests/run_tests.py
```

### Resumen de auditoría de pruebas:
```
==============================================================================
FINAL TEST SUITE SUMMARY
==============================================================================
  Tier Name                                Total    Pass    Skip    Fail     Time
  -------------------------------------- ------- ------- ------- ------- --------
  Tier 1: Feature Coverage                    60      60       0       0   1.495s
  Tier 2: Boundary & Corner Cases             60      60       0       0   0.834s
  Tier 3: Cross-Feature Interactions          14      14       0       0   0.063s
  Tier 4: Real-World Scenarios                 5       5       0       0   0.524s
  Tier 5: Adversarial Stress & Faults         10      10       0       0  13.884s
  -------------------------------------- ------- ------- ------- ------- --------
  TOTAL                                      149     149       0       0  16.800s
==============================================================================
✓ ALL EXECUTED TESTS PASSED CLEANLY (100% SUCCESS)
```

---

## ❓ Resolución de Problemas Frecuentes (FAQ)

### 1. ¿Qué pasa si abro la app antes que Discord?
No hay problema. El gestor de RPC cuenta con un bucle de reconexión automático. En cuanto abras Discord en tu Mac, la aplicación detectará el socket local y se conectará en cuestión de segundos, cambiando el icono de la barra al estado activo (punto azul).

### 2. ¿No veo el icono en la barra de menú superior?
En los MacBooks recientes con "Notch" (isla de la cámara), si tienes muchas aplicaciones abiertas, macOS puede ocultar los iconos que queden detrás del notch. Puedes usar herramientas como *Hidden Bar*, *Ice* o *Bartender*, o cerrar temporalmente iconos que no uses para que se vuelva visible.

### 3. ¿Cómo puedo cerrar la aplicación por completo?
Puedes ejecutar en tu terminal:
```bash
cd /Users/victormanuel/discord-rpc
./stop.sh
```
O buscar `app_gui.py` en la app **Monitor de Actividad** de macOS y pulsar forzar salida.

### 4. ¿Cómo actualizo el código si hay cambios en el repositorio?
Solo ejecuta:
```bash
git pull origin main
python sync_bundle.py
./stop.sh && ./start.sh
```

### 5. ¿El repositorio contiene datos privados o credenciales de mi cuenta de Discord?
**No, en absoluto.** La tecnología de Discord Rich Presence no utiliza correos, contraseñas ni tokens de usuario:
- Se comunica directamente mediante el socket local del sistema operativo (`/tmp/discord-ipc-0` en macOS).
- Cualquier persona que descargue este proyecto y lo abra en su Mac verá su presencia reflejada **automáticamente en su propia cuenta de Discord** abierta en ese equipo.
- No hay ningún dato confidencial en el repositorio.

### 6. ¿Cómo puede otra persona usar su propia aplicación de Discord? (Opcional)
La app viene configurada con el Client ID oficial de League of Legends para funcionar **inmediatamente sin configuración adicional**.

Si alguien desea crear su propia aplicación personalizada desde cero:
1. Entra a [Discord Developer Portal](https://discord.com/developers/applications).
2. Haz clic en **New Application**, asígnale el nombre que prefieras y sube los iconos en la pestaña **Rich Presence**.
3. Copia el **Application ID (Client ID)**.
4. En macOS, puedes definir tu ID antes de iniciar la app mediante la variable de entorno:
   ```bash
   export DISCORD_CLIENT_ID="tu_client_id_aqui"
   open -a "/Applications/League of Legends RPC.app"
   ```
   O modificar directamente `DEFAULT_CLIENT_ID` en `discord_rpc_manager.py`.

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Consulta el código para más detalles.  
*League of Legends* y *Riot Games* son marcas comerciales registradas de Riot Games, Inc.  
*Discord* es una marca registrada de Discord, Inc.

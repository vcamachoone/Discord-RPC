# League of Legends Discord RPC for macOS 🎮✨

[![macOS](https://img.shields.io/badge/Platform-macOS%2012%2B-blue?logo=apple)](https://www.apple.com/macos/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-brightgreen?logo=python)](https://www.python.org/)
[![PyObjC](https://img.shields.io/badge/UI-PyObjC%20Cocoa%20%2B%20WebKit-orange)](https://pyobjc.readthedocs.io/)
[![Discord IPC](https://img.shields.io/badge/Discord-Rich%20Presence-5865F2?logo=discord)](https://discord.com/)
[![Tests](https://img.shields.io/badge/Tests-149%2F149%20Passing%20(100%25)-success)](#-suite-de-pruebas)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success)]()

Aplicación nativa para la barra de menú de macOS (**Menubar Agent / `LSUIElement`**) que sincroniza en tiempo real tu presencia enriquecida (**Rich Presence**) de **League of Legends** en Discord. Diseñada con una arquitectura robusta, estética moderna **Liquid Glass (Dark Aqua HUD)** y gestión concurrente de sockets sin bloqueos en la interfaz.

---

## 📸 Vista Previa y Características

- **Diseño Liquid Glass Unificado**: Ventana flotante nativa (`NSPopover`) anclada a la barra superior con efecto translúcido HUD, reflejos sutiles y controles interactivos sin recortes ni marcos duplicados.
- **Icono Reactivo en la Barra de Menús**:
  - ⚪ **Normal**: Icono Discord neutro.
  - 🔵 **Activo**: Icono Discord con indicador azul en tiempo real.
  - 🔘 **Pausado / Desconectado**: Icono atenuado/semitransparente.
- **Selector de Modo Rápido**:
  - **Modo Oficial**: Presencia minimalista (Solo estado de LoL y cronómetro transcurrido).
  - **Modo Detallado**: Muestra Campeón, Rango Clasificatorio y Modo de Juego.
- **Buscador de 173 Campeones con Avatares en Vivo**:
  - Autocompletado interactivo con avatares oficiales en alta resolución servidos desde la CDN de **Riot Games Data Dragon**.
  - Soporte completo de navegación por teclado (`Flecha Arriba`, `Flecha Abajo`, `Enter`, `Escape`) y selección con ratón.
  - Normalización automática de nombres complejos (*Wukong → MonkeyKing, Cho'Gath → Chogath, Kai'Sa → Kaisa, Nunu & Willump → Nunu*).
- **Selector Canónico de Modos de Juego**:
  - Modos oficiales precargados (*Clasificatoria Solo/Dúo, Flex, Normal, ARAM, Arena 2v2v2v2, Swiftplay, Clash, etc.*).
  - Entrada libre personalizada para partidas privadas o modos rotativos.
- **Rangos y Emblemas**:
  - Selector desde *Hierro* hasta *Challenger* con divisiones romanas (*I, II, III, IV*).
  - Supresión automática de divisiones en rangos Apex (*Master, Grandmaster, Challenger*).
- **Automatización**:
  - **Reiniciar partida**: Reinicia el tiempo transcurrido periódicamente (cada 20–30 min) para simular partidas reales.
  - **Iniciar con macOS (Auto-run)**: Registro automático mediante `LaunchAgent` (`~/Library/LaunchAgents/com.victormanuel.lolrpc.plist`). Se ejecuta silenciosamente al encender el Mac sin mostrar iconos temporales en el Dock.
- **Estabilidad y Concurrencia**:
  - Modelo de Actor protegido con cerrojos (`threading.Lock`) para comunicación con el socket IPC de Discord (`pypresence`).
  - Cero congelamientos en el bucle principal de interfaz gráfica (`AppKit.NSApplication`).
  - Reconexión automática resiliente si Discord se abre, se cierra o se reinicia.

---

## 🏛️ Arquitectura del Proyecto

```
discord-rpc/
├── /Applications/League of Legends RPC.app   # Bundle nativo instalado en macOS
├── app_gui.py              # Controlador principal y ciclo de vida Cocoa (AppKit)
├── popover_ui.py           # NSPopover nativo, controles fallback Cocoa y WebKit Bridge
├── liquid_html.py          # Interfaz Liquid Glass en HTML5/CSS3/JS para WKWebView
├── discord_rpc_manager.py  # Actor de IPC Discord concurrente y resiliente
├── status_item.py          # Gestor reactivo del icono de la barra de menús
├── lol_champions.py        # Catálogo de 173 campeones y resolución CDN Data Dragon
├── lol_ranks.py            # Lógica de rangos, divisiones y crestas de LoL
├── sync_bundle.py          # Script de sincronización e integridad del Bundle .app
├── requirements.txt        # Dependencias de Python del proyecto
├── launcher.sh             # Script lanzador con flags de macOS
├── start.sh / stop.sh      # Scripts de inicio y detención rápida
├── assets/                 # Iconos de barra de menús en 1x y @2x
└── tests/                  # Suite integral de pruebas end-to-end (149 pruebas)
    ├── test_tier1_features.py       # Cobertura funcional (60 tests)
    ├── test_tier2_boundaries.py     # Casos límite y esquinas (60 tests)
    ├── test_tier3_interactions.py   # Interacciones cruzadas (14 tests)
    ├── test_tier4_scenarios.py      # Escenarios de usuario real (5 tests)
    ├── test_adversarial_stress.py   # Estrés adversarial y fallos de red (10 tests)
    └── run_tests.py                 # Ejecutor maestro de pruebas
```

---

## ⚙️ Requisitos del Sistema

- **Sistema Operativo**: macOS 12.0 (Monterey) o superior (Ventura, Sonoma, Sequoia).
- **Procesador**: Compatible con Apple Silicon (M1/M2/M3/M4) e Intel (x86_64).
- **Python**: 3.9 o superior.
- **Discord**: Discord cliente de escritorio instalado y en ejecución en macOS.

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el repositorio
```bash
git clone https://github.com/vcamachoone/Discord-RPC.git
cd Discord-RPC
```

### 2. Crear y activar el entorno virtual
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Sincronizar el Bundle de macOS
Este paso compila los recursos y genera `/Applications/League of Legends RPC.app` con su `Info.plist` y permisos ejecutables:
```bash
python sync_bundle.py
```

### 4. Iniciar la aplicación
Puedes abrirla de tres formas:

- **Desde el Finder o Spotlight**: Abre `/Applications/League of Legends RPC.app`.
- **Desde la terminal**:
  ```bash
  open -a "/Applications/League of Legends RPC.app"
  ```
- **Modo directo (desarrollo)**:
  ```bash
  venv/bin/python app_gui.py
  ```

---

## 🧪 Suite de Pruebas Automatizadas

El proyecto cuenta con un sistema de verificación exhaustivo de 5 niveles que valida la interfaz, concurrencia, integración con el sistema operativo y casos extremos:

```bash
venv/bin/python tests/run_tests.py
```

### Resultados de la auditoría:
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

## 🔄 Arranque Automático con macOS (LaunchAgent)

Para habilitar que la aplicación inicie silenciosamente al encender el Mac:

1. Activa el interruptor **"Iniciar automáticamente con macOS"** en la interfaz popover.
2. La aplicación generará y registrará automáticamente:
   `~/Library/LaunchAgents/com.victormanuel.lolrpc.plist`

Para comprobar el estado del servicio:
```bash
launchctl list | grep lolrpc
```

---

## 📦 Despliegue a Producción y Git

Para actualizar tu repositorio remoto con las últimas mejoras:

```bash
git add .
git commit -m "feat: complete production release with Liquid Glass UI, 173 champions, and LaunchAgent"
git push origin main
```

*(Nota: Si usas HTTPS y GitHub solicita autenticación, introduce tu usuario y tu **Personal Access Token (PAT)** de GitHub, o utiliza tu clave SSH si está configurada).*

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo de licencia para más detalles.
League of Legends y Riot Games son marcas comerciales registradas de Riot Games, Inc.
Discord es una marca registrada de Discord, Inc.

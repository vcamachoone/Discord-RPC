# Original User Request

## Initial Request — 2026-09-27T08:32:42Z

Auditar y rediseñar la aplicación de Discord RPC de League of Legends para macOS, reemplazando el menú textual actual por una interfaz flotante nativa (NSPopover) con tema oscuro, controles interactivos e iconos de estado dinámicos según la maqueta de diseño de referencia (123.png).

Working directory: /Users/victormanuel/discord-rpc
Integrity mode: development

## Context & Design Reference

La maqueta visual de referencia se encuentra en /Users/victormanuel/Desktop/123.png (y copiada en la carpeta de artefactos como /Users/victormanuel/.gemini/antigravity/brain/7bc6b881-49f2-492f-b654-3a4c515dc9b1/design_mockup.png). Representa una aplicación de barra de menú de macOS con:
1. **Icono de barra de menús reactivo** con 3 estados: Normal (logo Discord), Activo (logo Discord con punto azul indicador en la esquina inferior) y Pausado (logo Discord atenuado).
2. **Ventana Popover (NSPopover / Cocoa)** oscura y flotante conectada a la barra con flecha superior:
   - Cabecera: Icono de Discord, título "Discord RPC", subtítulo "League of Legends", botón de ajustes (engranaje).
   - Opciones de Modo (Radio / Tarjeta):
     - "Modo Oficial" (Solo LoL + Tiempo)
     - "Modo Detallado" (Campeón, Rango y Modo)
   - Interruptores tipo switch:
     - "Reiniciar partida" (automáticamente cada 20–30 min)
     - "Iniciar automáticamente" (con macOS Auto-run)
   - Botón de control: "⏹ DETENER EN DISCORD" / "▶ INICIAR PRESENCIA".
   - Vista o panel de Configuración / Modo Detallado para seleccionar Campeón y Rango.

## Requirements

### R1. Interfaz Flotante Nativa (NSPopover en macOS con Python & PyObjC)
Implementar una ventana flotante `NSPopover` anclada al `NSStatusItem` de la barra de menú. La interfaz debe tener estética oscura moderna inspirada en `123.png`, conteniendo:
- Encabezado con icono, títulos y botón de engranaje para configuración.
- Selector de modo (Oficial vs Detallado) con retroalimentación visual clara.
- Interruptores (switches) para "Reiniciar partida (20-30 min)" e "Iniciar con macOS".
- Botón inferior prominente para alternar estado activo/pausado ("DETENER EN DISCORD" / "INICIAR").

### R2. Icono Dinámico en la Barra de Menús con Indicador de Estado
Crear y alternar dinámicamente los recursos gráficos del icono de la barra de menús según el estado del servicio:
- **Normal**: Logo de Discord neutro.
- **Activo**: Logo de Discord con punto azul indicador de conexión activa.
- **Pausado / Desconectado**: Logo de Discord semitransparente / atenuado.

### R3. Panel de Ajustes y Modo Detallado
En el modo detallado o mediante el botón de configuración (engranaje), permitir configurar el Campeón y el Rango clasificatorio:
- Normalización automática de nombres de campeones para URLs de Riot Data Dragon (manejo de mayúsculas y campeones con nombres especiales como Wukong -> MonkeyKing, Cho'Gath -> Chogath, Kai'Sa -> Kaisa, etc.).
- Soporte para rangos (Hierro a Challenger), formateando correctamente las divisiones (evitando sufijos como "Challenger II").

### R4. Gestión Concurrente, Estabilidad y Empaquetado
- Todas las interacciones con `pypresence` y sockets de Discord deben estar protegidas contra condiciones de carrera (`threading.Lock`), evitando bloqueos en el hilo principal de la interfaz (`AppKit` runloop).
- Reconexión resiliente si Discord se abre o se cierra en segundo plano.
- Sincronización o actualización del bundle `/Applications/League of Legends RPC.app` con su `Info.plist`, icono `.icns` y ejecutables.

## Acceptance Criteria

### Interfaz de Usuario y Estética
- [ ] Al hacer clic en el icono de la barra de menú, se despliega una ventana flotante (`NSPopover`) con flecha hacia la barra, siguiendo la estética y estructura de `123.png`.
- [ ] El icono en la barra de menú cambia visualmente reflejando los estados: Activo (con punto azul), Normal y Pausado.
- [ ] Los interruptores de reinicio automático y autoarranque con macOS pueden activarse/desactivarse reflejando su estado inmediatamente.
- [ ] El botón inferior alterna correctamente la presencia en Discord entre activa y detenida.

### Lógica y Robustez
- [ ] El cambio de modos y la interacción con la UI no congelan la interfaz ni lanzan excepciones de socket o rate-limit en `pypresence`.
- [ ] En Modo Detallado, el nombre de cualquier campeón introducido se resuelve hacia una imagen válida en Data Dragon sin fallar por minúsculas o caracteres especiales.
- [ ] La aplicación se puede compilar/instalar y ejecutar sin errores en `/Applications/League of Legends RPC.app`.

## Follow-up — 2026-09-27T16:39:44Z

Comprehensive end-to-end audit and defect discovery for the League of Legends Discord RPC macOS application, verifying that the entire system functions flawlessly, identifying any edge-case failures or regressions, and hardening recent additions (173-champion avatar searcher, canonical game modes, macOS LaunchAgent auto-start, and Liquid Glass popover).

Working directory: /Users/victormanuel/discord-rpc
Integrity mode: development

## Requirements

### R1. Auditoría Funcional y de Interfaz (Liquid Glass & Popover UI)
Auditar minuciosamente la interfaz flotante `NSPopover` en Cocoa con overlay `WebKit`:
- Validar el funcionamiento del nuevo buscador interactivo de campeones con fotos/avatares en tiempo real (173 campeones), navegación por teclado y selección fluida.
- Validar el selector de modos de juego canónicos de LoL y el modo de texto personalizado.
- Validar la actualización de rangos, crestas y supresión automática de divisiones en rangos Apex (Master, Grandmaster, Challenger).
- Validar la respuesta visual y funcional de los switches (autoreset, autorun) y el botón principal de presencia.

### R2. Auditoría de Concurrencia y Resiliencia de Discord IPC
Auditar la estabilidad del Actor `DiscordRPCManager`:
- Verificar la protección contra carreras de hilos (`threading.Lock`) durante cambios rápidos de estado o interacción agresiva.
- Probar la reconexión resiliente cuando Discord se cierra y se vuelve a abrir.
- Comprobar que no se produzcan bloqueos en el hilo principal (`AppKit` runloop) ni excepciones de socket no controladas.

### R3. Auditoría de Integración con macOS y Arranque Automático
- Verificar que el icono de la barra de menús (`NSStatusItem`) permanezca visible y accesible (junto al Wi-Fi) con sus 3 estados gráficos.
- Verificar que el agente de inicio `~/Library/LaunchAgents/com.victormanuel.lolrpc.plist` y los Ítems de Inicio de macOS inicien el bundle silenciosamente al encender el Mac.
- Asegurar que al abrir la app o ejecutar el lanzador no haya parpadeo de iconos de Python en el Dock y que la ventana flotante se presente correctamente al frente.

### R4. Corrección de Defectos y Verificación Automatizada
- Ejecutar la suite completa de pruebas end-to-end (`tests/run_tests.py`) abarcando Tiers 1 al 5.
- Si se detecta cualquier falla, regresión o cuello de botella durante la auditoría, implementar la solución inmediatamente y verificar que todas las pruebas pasen al 100%.

## Verification Resources
- Test Runner: `/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py`
- Test Suites: `tests/test_tier1_features.py`, `tests/test_tier2_boundaries.py`, `tests/test_tier3_interactions.py`, `tests/test_tier4_scenarios.py`, `tests/test_adversarial_stress.py`
- Reference Mockup: `/Users/victormanuel/Desktop/123.png` (and artifact `design_mockup.png`)
- Application Bundle: `/Applications/League of Legends RPC.app`

## Acceptance Criteria

### Estabilidad y Concurrencia
- [ ] Cero bloqueos, cuelgues o congelamientos de la interfaz ante eventos rápidos de red o clics repetitivos.
- [ ] La presencia en Discord refleja exactamente el modo, campeón, rango y modo de juego seleccionados sin retrasos ni excepciones de socket.

### Experiencia de Usuario y Liquid Glass
- [ ] El buscador de campeones filtra instantáneamente entre los 173 campeones mostrando su foto oficial de Riot CDN y permitiendo selección con ratón y teclado.
- [ ] El selector de modos de juego actualiza la actividad en Discord y permite modo personalizado si se requiere.
- [ ] La ventana flotante `NSPopover` se despliega anclada al icono de Discord en la barra superior con efecto Liquid Glass nítido.

### Integración con el Sistema y Suite de Pruebas
- [ ] El bundle `/Applications/League of Legends RPC.app` arranca silenciosamente sin mostrar icono temporal de Python en el Dock.
- [ ] El LaunchAgent inicia la aplicación de forma persistente tras el inicio de sesión del usuario.
- [ ] El 100% de las pruebas automatizadas (149/149) pasan de forma limpia e independiente.

## Follow-up — 2026-09-29T23:10:58Z

Transform the League of Legends Discord RPC macOS application from a functional development build into a polished, commercial-grade production product with complete lifecycle management, interactive Discord profile buttons, and automated CI/CD distribution.

Working directory: /Users/victormanuel/discord-rpc
Integrity mode: development

## Requirements

### R1. Native App Lifecycle, Menubar Controls & Hardened Auto-Start
Implement complete user-facing lifecycle management for the macOS accessory application:
- Add a visible and accessible "Salir de la aplicación" (Quit App) control within the popover interface and configuration view.
- Support secondary right-click on the status bar icon (`NSStatusItem`) displaying a native Cocoa `NSMenu` with: Open Popover, Toggle Presence (Pause/Resume), Settings (⚙️), and Quit (Cmd+Q).
- Implement a single-instance lock ensuring that launching the app when already running brings the existing popover to the front instead of spawning duplicate processes.
- Harden macOS Auto-start (LaunchAgent & Login Items):
  * Point LaunchAgent directly to the bundle binary (`/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC`) rather than indirect `/usr/bin/open`.
  * Configure log destinations (`StandardOutPath` and `StandardErrorPath` in `~/Library/Logs/`).
  * Display a brief system notification upon launch confirming active menubar presence.

### R2. Discord Interactive Profile Buttons (Clickable Buttons)
Expose support for up to two interactive clickable buttons in the Discord Rich Presence payload:
- Allow users in `#view-config` to configure Button 1 and Button 2 (Label and URL, e.g. "Ver OP.GG", "Twitch Stream", "Servidor de Discord", "Mi Perfil").
- Sanitize and validate button URLs (HTTPS enforcement, length limits).
- Dispatch the button array cleanly to `pypresence` without crashing on empty or partial fields.

### R3. Automated GitHub Actions CI/CD Release Pipeline
Implement a production `.github/workflows/release.yml` GitHub Actions workflow:
- Automatically trigger on release publication or semver git tags (`v*.*.*`).
- Run on macOS runners (`macos-latest`).
- Set up Python, install dependencies, run the complete 149-test suite across all 5 tiers.
- Execute `build_dmg.py` to compile the standalone compressed `.dmg` installer.
- Automatically attach the generated `.dmg` and its SHA-256 checksum to the GitHub Release.

### R4. System Event Listeners (Discord Launch & Sleep/Wake Resilience)
- Register Cocoa `NSWorkspaceDidLaunchApplicationNotification` to instantly connect when Discord starts up after system boot.
- Register Cocoa `NSWorkspaceDidWakeNotification` to immediately re-establish Discord IPC connection when the Mac wakes from sleep.
- Implement an in-app error boundary so WebKit or socket exceptions display a friendly toast rather than silently terminating.

## Verification Resources
- Test Runner: `/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py`
- DMG Builder: `/Users/victormanuel/discord-rpc/venv/bin/python build_dmg.py`
- Test Suites: `tests/test_tier1_features.py`, `tests/test_tier2_boundaries.py`, `tests/test_tier3_interactions.py`, `tests/test_tier4_scenarios.py`, `tests/test_adversarial_stress.py`, `tests/test_audit_fixes.py`
- Bundle Path: `/Applications/League of Legends RPC.app`

## Acceptance Criteria

### Lifecycle, Auto-Start & Menubar Controls
- [ ] Users can cleanly terminate the application from the UI without terminal or Activity Monitor.
- [ ] Right-clicking the menubar icon displays a native Cocoa context menu with functional Open, Pause/Resume, and Quit options.
- [ ] Launching a second instance focuses the running instance without starting duplicate background daemons.
- [ ] Auto-start at system boot launches the bundle cleanly with a visual notification and logs to `~/Library/Logs/`.
- [ ] Automatically detects when Discord opens via `NSWorkspaceDidLaunchApplicationNotification` and immediately connects to the active IPC socket.

### Discord Rich Presence Features
- [ ] Discord profile displays up to two custom clickable buttons redirecting to the configured URLs.
- [ ] Configuration persists between sessions in `~/.config/lol_discord_rpc/config.json`.

### CI/CD and Distribution
- [ ] `.github/workflows/release.yml` passes syntax validation and successfully builds DMG artifacts on GitHub Actions.
- [ ] 100% of automated tests pass across all tiers with zero regressions.


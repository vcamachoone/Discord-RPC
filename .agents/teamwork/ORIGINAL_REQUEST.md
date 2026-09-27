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

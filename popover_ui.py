#!/usr/bin/env python3
"""
popover_ui.py - Native Dark NSPopover UI Component for Discord RPC

Implements LoLPopoverController:
  - Native Cocoa NSPopover with Dark Aqua HUD appearance (NSAppearanceNameDarkAqua)
  - Transient behavior (NSPopoverBehaviorTransient) for clean dismissal on outside click
  - Anchors to NSStatusItem button with showRelativeToRect_ofView_preferredEdge_
  - Header: Discord Clyde icon (32x32 pt), bold "Discord RPC" title, "League of Legends" subtitle,
    and settings gear button
  - Mode Selection Cards: "Modo Oficial" (Solo LoL + Tiempo) vs "Modo Detallado" (Campeón, Rango y Modo)
  - Interactive NSSwitch controls:
      * "Reiniciar partida" (automáticamente cada 20–30 min)
      * "Iniciar automáticamente" (con macOS Auto-run)
  - Settings / Detailed View:
      * Champion input field integrated in real-time with ChampionResolver
      * Rank popup (Hierro to Challenger, Unranked)
      * Division popup (I-IV, automatically disabled for Apex tiers Master, Grandmaster, Challenger, Unranked)
      * Game mode field ("Grieta del Invocador (Clasificatoria)", "ARAM", etc.)
  - Prominent Bottom Action Button ("⏹ DETENER EN DISCORD" / "▶ INICIAR PRESENCIA")
  - Non-blocking actor dispatch to DiscordRPCManager
"""

import os
import sys
import json
import subprocess
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple

import AppKit
import objc
from Foundation import NSObject

try:
    import WebKit
    HAS_WEBKIT = True
except ImportError:
    WebKit = None
    HAS_WEBKIT = False

# Suppress ObjCPointerWarning for CGColor / layer pointers
warnings.filterwarnings("ignore", category=objc.ObjCPointerWarning)
warnings.filterwarnings("ignore", message=".*PyObjCPointer.*")
warnings.simplefilter("ignore", objc.ObjCPointerWarning)

# Ensure local modules are accessible
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

try:
    from liquid_html import generate_liquid_html
except ImportError:
    generate_liquid_html = None

try:
    from lol_champions import ChampionResolver
except ImportError:
    ChampionResolver = None

try:
    from lol_ranks import (
        APEX_TIERS,
        DEFAULT_DIVISIONS,
        DEFAULT_RANKS_ES,
        format_rank_display,
        get_rank_crest_url,
        is_apex_tier,
    )
except ImportError:
    DEFAULT_RANKS_ES = [
        "Hierro", "Bronce", "Plata", "Oro", "Platino",
        "Esmeralda", "Diamante", "Maestro", "Gran Maestro", "Challenger", "Unranked"
    ]
    DEFAULT_DIVISIONS = ["I", "II", "III", "IV"]
    APEX_TIERS = {"Master", "Maestro", "Grandmaster", "Gran Maestro", "Challenger", "Unranked"}

    def is_apex_tier(t: str) -> bool:
        return str(t).strip().lower() in {x.lower() for x in APEX_TIERS}

    def format_rank_display(t: str, d: str = "II") -> str:
        return f"{t}" if is_apex_tier(t) else f"{t} {d}"

    def get_rank_crest_url(t: str) -> str:
        return ""


class FlippedVisualEffectView(AppKit.NSVisualEffectView):
    """
    Subclass of NSVisualEffectView with flipped coordinates (origin at top-left).
    """

    def isFlipped(self) -> bool:
        return True


class FlippedView(AppKit.NSView):
    """
    Subclass of NSView with flipped coordinates (origin at top-left).
    """

    def isFlipped(self) -> bool:
        return True


class FlippedButton(AppKit.NSButton):
    """
    Subclass of NSButton with flipped coordinates (origin at top-left).
    """

    def isFlipped(self) -> bool:
        return True


class LoLWebBridge(NSObject):
    """Bridge receiving messages from the WebKit Liquid Glass UI."""

    def initWithController_(self, controller):
        self = objc.super(LoLWebBridge, self).init()
        if self is not None:
            self._controller = controller
        return self

    def userContentController_didReceiveScriptMessage_(self, ucc, message):
        body = message.body()
        if not body or not self._controller:
            return
        action = body.get("action")
        if action == "select_mode":
            self._controller.select_mode(body.get("mode"))
        elif action == "toggle_autoreset":
            self._controller.set_autoreset_state(bool(body.get("value")))
        elif action == "toggle_autorun":
            self._controller.toggle_autorun(bool(body.get("value")))
        elif action == "action_button":
            self._controller.handle_action_button_click()
        elif action == "toggle_settings":
            self._controller.toggle_settings_panel()
        elif action == "change_champion":
            self._controller.set_selected_champion(body.get("name", ""))
        elif action == "change_rank":
            self._controller.set_selected_rank(body.get("rank", "Oro"))
        elif action == "change_division":
            self._controller.set_selected_division(body.get("division", "II"))
        elif action == "change_game_mode":
            self._controller.set_game_mode_text(body.get("game_mode", ""))


class LoLPopoverController(NSObject):
    """
    Controller managing the Cocoa NSPopover dark HUD interface for League of Legends Discord RPC.
    """

    def __new__(cls, *args, **kwargs):
        # Support both standard Python instantiation LoLPopoverController(...)
        # and Objective-C style LoLPopoverController.alloc().init()
        instance = cls.alloc().init()
        instance._configure(*args, **kwargs)
        return instance

    def init(self):
        self = objc.super(LoLPopoverController, self).init()
        if self is not None:
            self._initialized = False
            self._setup_defaults()
        return self

    def _setup_defaults(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        # State attributes
        self._is_shown: bool = False
        self._current_mode: str = "oficial"  # "oficial" or "detallado"
        self._settings_expanded: bool = False
        self._autoreset_state: bool = True
        self._autorun_state: bool = self.check_autorun()
        self._presence_active: bool = True
        self._connection_state: str = "disconnected"

        # LoL Settings State
        self._champion: str = "Malzahar"
        self._rank: str = "Oro"
        self._division: str = "II"
        self._division_enabled: bool = not is_apex_tier(self._rank)
        self._game_mode: str = "Grieta del Invocador (Clasificatoria)"

        # Resolvers and actors
        self._champion_resolver = ChampionResolver() if ChampionResolver else None
        self._rpc_manager: Optional[Any] = None

        # Callbacks
        self._on_mode_change: Optional[Callable[[str], None]] = None
        self._on_autorun_toggle: Optional[Callable[[bool], None]] = None
        self._on_action_toggle: Optional[Callable[[bool], None]] = None
        self._on_config_change: Optional[Callable[..., None]] = None

        # Cocoa UI References
        self._popover: Optional[AppKit.NSPopover] = None
        self._content_vc: Optional[AppKit.NSViewController] = None
        self._content_view: Optional[FlippedVisualEffectView] = None

        self._title_label: Optional[AppKit.NSTextField] = None
        self._subtitle_label: Optional[AppKit.NSTextField] = None
        self._gear_button: Optional[AppKit.NSButton] = None

        self._card_official: Optional[FlippedButton] = None
        self._card_detailed: Optional[FlippedButton] = None
        self._card_official_radio: Optional[AppKit.NSTextField] = None
        self._card_detailed_radio: Optional[AppKit.NSTextField] = None

        self._autoreset_switch: Optional[AppKit.NSSwitch] = None
        self._autorun_switch: Optional[AppKit.NSSwitch] = None

        self._settings_container: Optional[FlippedView] = None
        self._champion_field: Optional[AppKit.NSTextField] = None
        self._rank_popup: Optional[AppKit.NSPopUpButton] = None
        self._division_popup: Optional[AppKit.NSPopUpButton] = None
        self._game_mode_field: Optional[AppKit.NSTextField] = None
        self._feedback_label: Optional[AppKit.NSTextField] = None

        self._action_button: Optional[AppKit.NSButton] = None
        self._web_view = None
        self._web_bridge = None

        # Build Cocoa View Hierarchy
        self._build_ui()

    def _configure(
        self,
        on_mode_change: Optional[Callable[[str], None]] = None,
        on_autorun_toggle: Optional[Callable[[bool], None]] = None,
        on_action_toggle: Optional[Callable[[bool], None]] = None,
        on_config_change: Optional[Callable[..., None]] = None,
        rpc_manager: Optional[Any] = None,
        **kwargs,
    ) -> None:
        """Configures controller callbacks and optional RPC actor."""
        if on_mode_change is not None:
            self._on_mode_change = on_mode_change
        if on_autorun_toggle is not None:
            self._on_autorun_toggle = on_autorun_toggle
        if on_action_toggle is not None:
            self._on_action_toggle = on_action_toggle
        if on_config_change is not None:
            self._on_config_change = on_config_change
        if rpc_manager is not None:
            self._rpc_manager = rpc_manager

    # =========================================================================
    # Cocoa UI Construction
    # =========================================================================

    def _build_ui(self) -> None:
        """Constructs the native macOS dark HUD popover view hierarchy."""
        # 1. NSPopover Container
        self._popover = AppKit.NSPopover.alloc().init()
        self._popover.setBehavior_(AppKit.NSPopoverBehaviorTransient)
        self._popover.setAnimates_(True)

        dark_appearance = AppKit.NSAppearance.appearanceNamed_(
            AppKit.NSAppearanceNameDarkAqua
        )
        if dark_appearance is None:
            dark_appearance = AppKit.NSAppearance.appearanceNamed_(
                AppKit.NSAppearanceNameVibrantDark
            )
        self._popover.setAppearance_(dark_appearance)
        self._popover.setDelegate_(self)

        # 2. Main Visual Effect View (Dark Aqua HUD)
        self._content_vc = AppKit.NSViewController.alloc().init()
        self._content_view = FlippedVisualEffectView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, 340, 380)
        )
        self._content_view.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
        self._content_view.setBlendingMode_(
            AppKit.NSVisualEffectBlendingModeBehindWindow
        )
        self._content_view.setState_(AppKit.NSVisualEffectStateActive)
        self._content_view.setWantsLayer_(True)
        if self._content_view.layer():
            self._content_view.layer().setCornerRadius_(14.0)

        self._content_vc.setView_(self._content_view)
        self._popover.setContentViewController_(self._content_vc)
        self._popover.setContentSize_(AppKit.NSMakeSize(340, 380))

        # 3. Header View (Discord Icon, Titles, Gear Button)
        self._build_header()

        # 4. Mode Selection Cards ("Modo Oficial" vs "Modo Detallado")
        self._build_mode_cards()

        # 5. Interactive NSSwitches ("Reiniciar partida" + "Iniciar con macOS")
        self._build_switches()

        # 6. Detailed Settings Panel (Champion, Rank, Division, Game Mode)
        self._build_settings_panel()

        # 7. Bottom Action Button ("DETENER EN DISCORD" / "INICIAR PRESENCIA")
        self._build_action_button()

        # Synchronize visual state
        self._update_mode_cards_visuals()
        self._update_action_button_style()
        self._update_layout()

        # 8. WebKit Liquid Glass UI (if WebKit is available)
        if HAS_WEBKIT:
            self._build_web_ui()

    def _build_header(self) -> None:
        """Builds header elements: Discord logo, title, subtitle, and gear button."""
        # Discord Logo Image
        logo_view = AppKit.NSImageView.alloc().initWithFrame_(
            AppKit.NSMakeRect(16, 14, 34, 34)
        )
        logo_view.setImageScaling_(AppKit.NSImageScaleProportionallyUpOrDown)

        # Attempt to load Discord/app icon
        icon_paths = [
            os.path.join(_BASE_DIR, "assets", "menubar_active@2x.png"),
            os.path.join(_BASE_DIR, "assets", "menubar_normal@2x.png"),
            os.path.join(_BASE_DIR, "triangle_menubar.png"),
            os.path.join(_BASE_DIR, "lol_icon.png"),
        ]
        loaded_img = None
        for p in icon_paths:
            if os.path.exists(p):
                loaded_img = AppKit.NSImage.alloc().initWithContentsOfFile_(p)
                if loaded_img:
                    loaded_img.setSize_(AppKit.NSMakeSize(34, 34))
                    break
        if loaded_img:
            logo_view.setImage_(loaded_img)
        self._content_view.addSubview_(logo_view)

        # Title Label ("Discord RPC")
        self._title_label = AppKit.NSTextField.labelWithString_("Discord RPC")
        self._title_label.setFrame_(AppKit.NSMakeRect(58, 13, 220, 18))
        self._title_label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(15))
        self._title_label.setTextColor_(AppKit.NSColor.whiteColor())
        self._content_view.addSubview_(self._title_label)

        # Subtitle Label ("League of Legends")
        self._subtitle_label = AppKit.NSTextField.labelWithString_(
            "League of Legends"
        )
        self._subtitle_label.setFrame_(AppKit.NSMakeRect(58, 31, 220, 16))
        self._subtitle_label.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        self._subtitle_label.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        self._content_view.addSubview_(self._subtitle_label)

        # Settings Gear Button
        self._gear_button = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(296, 16, 28, 28)
        )
        self._gear_button.setButtonType_(AppKit.NSButtonTypeMomentaryChange)
        self._gear_button.setBezelStyle_(AppKit.NSBezelStyleRegularSquare)
        self._gear_button.setWantsLayer_(True)
        if self._gear_button.layer():
            self._gear_button.layer().setCornerRadius_(6.0)
            self._gear_button.layer().setBackgroundColor_(
                AppKit.NSColor.colorWithWhite_alpha_(1.0, 0.08).CGColor()
            )

        gear_icon = None
        if hasattr(
            AppKit.NSImage, "imageWithSystemSymbolName_accessibilityDescription_"
        ):
            gear_icon = (
                AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                    "gearshape", "Settings"
                )
            )
        if gear_icon:
            self._gear_button.setImage_(gear_icon)
            self._gear_button.setImagePosition_(AppKit.NSImageOnly)
        else:
            self._gear_button.setTitle_("⚙")
            self._gear_button.setFont_(AppKit.NSFont.systemFontOfSize_(14))

        self._gear_button.setTarget_(self)
        self._gear_button.setAction_(b"gearButtonClicked:")
        self._content_view.addSubview_(self._gear_button)

    def _build_mode_cards(self) -> None:
        """Builds two card-like radio buttons for Modo Oficial and Modo Detallado."""
        # Card 1: Modo Oficial
        self._card_official = FlippedButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(16, 64, 308, 48)
        )
        self._card_official.setButtonType_(AppKit.NSButtonTypeMomentaryChange)
        self._card_official.setBezelStyle_(AppKit.NSBezelStyleRegularSquare)
        self._card_official.setTitle_("")
        self._card_official.setWantsLayer_(True)
        if self._card_official.layer():
            self._card_official.layer().setCornerRadius_(8.0)
            self._card_official.layer().setBorderWidth_(1.0)

        self._card_official_radio = AppKit.NSTextField.labelWithString_("◉")
        self._card_official_radio.setFrame_(AppKit.NSMakeRect(12, 14, 20, 20))
        self._card_official_radio.setFont_(AppKit.NSFont.systemFontOfSize_(14))
        self._card_official.addSubview_(self._card_official_radio)

        t1 = AppKit.NSTextField.labelWithString_("Modo Oficial")
        t1.setFrame_(AppKit.NSMakeRect(36, 8, 250, 16))
        t1.setFont_(AppKit.NSFont.boldSystemFontOfSize_(13))
        t1.setTextColor_(AppKit.NSColor.whiteColor())
        self._card_official.addSubview_(t1)

        s1 = AppKit.NSTextField.labelWithString_("Solo LoL + Tiempo")
        s1.setFrame_(AppKit.NSMakeRect(36, 26, 250, 14))
        s1.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        s1.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        self._card_official.addSubview_(s1)

        self._card_official.setTarget_(self)
        self._card_official.setAction_(b"officialCardClicked:")
        self._content_view.addSubview_(self._card_official)

        # Card 2: Modo Detallado
        self._card_detailed = FlippedButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(16, 118, 308, 48)
        )
        self._card_detailed.setButtonType_(AppKit.NSButtonTypeMomentaryChange)
        self._card_detailed.setBezelStyle_(AppKit.NSBezelStyleRegularSquare)
        self._card_detailed.setTitle_("")
        self._card_detailed.setWantsLayer_(True)
        if self._card_detailed.layer():
            self._card_detailed.layer().setCornerRadius_(8.0)
            self._card_detailed.layer().setBorderWidth_(1.0)

        self._card_detailed_radio = AppKit.NSTextField.labelWithString_("○")
        self._card_detailed_radio.setFrame_(AppKit.NSMakeRect(12, 14, 20, 20))
        self._card_detailed_radio.setFont_(AppKit.NSFont.systemFontOfSize_(14))
        self._card_detailed.addSubview_(self._card_detailed_radio)

        t2 = AppKit.NSTextField.labelWithString_("Modo Detallado")
        t2.setFrame_(AppKit.NSMakeRect(36, 8, 250, 16))
        t2.setFont_(AppKit.NSFont.boldSystemFontOfSize_(13))
        t2.setTextColor_(AppKit.NSColor.whiteColor())
        self._card_detailed.addSubview_(t2)

        s2 = AppKit.NSTextField.labelWithString_("Campeón, Rango y Modo")
        s2.setFrame_(AppKit.NSMakeRect(36, 26, 250, 14))
        s2.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        s2.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        self._card_detailed.addSubview_(s2)

        self._card_detailed.setTarget_(self)
        self._card_detailed.setAction_(b"detailedCardClicked:")
        self._content_view.addSubview_(self._card_detailed)

    def _build_switches(self) -> None:
        """Builds switch rows for autoreset match and macOS autorun."""
        # Row 1: Reiniciar partida
        r1_icon = AppKit.NSImageView.alloc().initWithFrame_(
            AppKit.NSMakeRect(16, 180, 24, 24)
        )
        r1_icon.setImageScaling_(AppKit.NSImageScaleProportionallyUpOrDown)
        if hasattr(
            AppKit.NSImage, "imageWithSystemSymbolName_accessibilityDescription_"
        ):
            r1_img = (
                AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                    "arrow.clockwise", "Restart"
                )
            )
            if r1_img:
                r1_icon.setImage_(r1_img)
        self._content_view.addSubview_(r1_icon)

        t_r1 = AppKit.NSTextField.labelWithString_("Reiniciar partida")
        t_r1.setFrame_(AppKit.NSMakeRect(48, 176, 200, 16))
        t_r1.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        t_r1.setTextColor_(AppKit.NSColor.whiteColor())
        self._content_view.addSubview_(t_r1)

        s_r1 = AppKit.NSTextField.labelWithString_(
            "automáticamente cada 20–30 min"
        )
        s_r1.setFrame_(AppKit.NSMakeRect(48, 194, 210, 14))
        s_r1.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        s_r1.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        self._content_view.addSubview_(s_r1)

        self._autoreset_switch = AppKit.NSSwitch.alloc().initWithFrame_(
            AppKit.NSMakeRect(274, 180, 50, 24)
        )
        self._autoreset_switch.setState_(
            AppKit.NSControlStateValueOn
            if self._autoreset_state
            else AppKit.NSControlStateValueOff
        )
        self._autoreset_switch.setTarget_(self)
        self._autoreset_switch.setAction_(b"autoresetSwitchChanged:")
        self._content_view.addSubview_(self._autoreset_switch)

        # Row 2: Iniciar automáticamente con macOS
        r2_icon = AppKit.NSImageView.alloc().initWithFrame_(
            AppKit.NSMakeRect(16, 226, 24, 24)
        )
        r2_icon.setImageScaling_(AppKit.NSImageScaleProportionallyUpOrDown)
        if hasattr(
            AppKit.NSImage, "imageWithSystemSymbolName_accessibilityDescription_"
        ):
            r2_img = (
                AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                    "laptopcomputer", "Autorun"
                )
            )
            if r2_img:
                r2_icon.setImage_(r2_img)
        self._content_view.addSubview_(r2_icon)

        t_r2 = AppKit.NSTextField.labelWithString_("Iniciar automáticamente")
        t_r2.setFrame_(AppKit.NSMakeRect(48, 222, 200, 16))
        t_r2.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        t_r2.setTextColor_(AppKit.NSColor.whiteColor())
        self._content_view.addSubview_(t_r2)

        s_r2 = AppKit.NSTextField.labelWithString_("con macOS (Auto-run)")
        s_r2.setFrame_(AppKit.NSMakeRect(48, 240, 210, 14))
        s_r2.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        s_r2.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        self._content_view.addSubview_(s_r2)

        self._autorun_switch = AppKit.NSSwitch.alloc().initWithFrame_(
            AppKit.NSMakeRect(274, 226, 50, 24)
        )
        self._autorun_switch.setState_(
            AppKit.NSControlStateValueOn
            if self._autorun_state
            else AppKit.NSControlStateValueOff
        )
        self._autorun_switch.setTarget_(self)
        self._autorun_switch.setAction_(b"autorunSwitchChanged:")
        self._content_view.addSubview_(self._autorun_switch)

    def _build_settings_panel(self) -> None:
        """Builds the collapsible detailed settings panel for champion, rank, and game mode."""
        self._settings_container = FlippedView.alloc().initWithFrame_(
            AppKit.NSMakeRect(16, 268, 308, 146)
        )
        self._settings_container.setWantsLayer_(True)
        if self._settings_container.layer():
            self._settings_container.layer().setCornerRadius_(10.0)
            self._settings_container.layer().setBackgroundColor_(
                AppKit.NSColor.colorWithWhite_alpha_(1.0, 0.05).CGColor()
            )
            self._settings_container.layer().setBorderColor_(
                AppKit.NSColor.colorWithWhite_alpha_(1.0, 0.1).CGColor()
            )
            self._settings_container.layer().setBorderWidth_(1.0)

        # Champion Input Row
        lbl_champ = AppKit.NSTextField.labelWithString_("Campeón:")
        lbl_champ.setFrame_(AppKit.NSMakeRect(10, 14, 65, 20))
        lbl_champ.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        lbl_champ.setTextColor_(AppKit.NSColor.whiteColor())
        self._settings_container.addSubview_(lbl_champ)

        self._champion_field = AppKit.NSTextField.alloc().initWithFrame_(
            AppKit.NSMakeRect(78, 12, 218, 22)
        )
        self._champion_field.setStringValue_(self._champion)
        self._champion_field.setPlaceholderString_("Ej: Ahri, Yasuo, Kai'Sa")
        self._champion_field.setTarget_(self)
        self._champion_field.setAction_(b"championFieldChanged:")
        self._settings_container.addSubview_(self._champion_field)

        # Rank & Division Row
        lbl_rank = AppKit.NSTextField.labelWithString_("Rango:")
        lbl_rank.setFrame_(AppKit.NSMakeRect(10, 46, 65, 20))
        lbl_rank.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        lbl_rank.setTextColor_(AppKit.NSColor.whiteColor())
        self._settings_container.addSubview_(lbl_rank)

        self._rank_popup = (
            AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(
                AppKit.NSMakeRect(78, 44, 138, 24), False
            )
        )
        self._rank_popup.addItemsWithTitles_(self.get_available_rank_tiers())
        self._rank_popup.selectItemWithTitle_(self._rank)
        self._rank_popup.setTarget_(self)
        self._rank_popup.setAction_(b"rankPopupChanged:")
        self._settings_container.addSubview_(self._rank_popup)

        self._division_popup = (
            AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(
                AppKit.NSMakeRect(222, 44, 74, 24), False
            )
        )
        self._division_popup.addItemsWithTitles_(self.get_available_divisions())
        self._division_popup.selectItemWithTitle_(self._division)
        self._division_popup.setEnabled_(self._division_enabled)
        self._division_popup.setTarget_(self)
        self._division_popup.setAction_(b"divisionPopupChanged:")
        self._settings_container.addSubview_(self._division_popup)

        # Game Mode Row
        lbl_mode = AppKit.NSTextField.labelWithString_("Modo:")
        lbl_mode.setFrame_(AppKit.NSMakeRect(10, 78, 65, 20))
        lbl_mode.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        lbl_mode.setTextColor_(AppKit.NSColor.whiteColor())
        self._settings_container.addSubview_(lbl_mode)

        self._game_mode_field = AppKit.NSTextField.alloc().initWithFrame_(
            AppKit.NSMakeRect(78, 76, 218, 22)
        )
        self._game_mode_field.setStringValue_(self._game_mode)
        self._game_mode_field.setTarget_(self)
        self._game_mode_field.setAction_(b"gameModeFieldChanged:")
        self._settings_container.addSubview_(self._game_mode_field)

        # Dynamic Status / Feedback Label
        self._feedback_label = AppKit.NSTextField.labelWithString_(
            "✓ Riot Data Dragon sincronizado"
        )
        self._feedback_label.setFrame_(AppKit.NSMakeRect(10, 112, 286, 16))
        self._feedback_label.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        self._feedback_label.setTextColor_(
            AppKit.NSColor.colorWithRed_green_blue_alpha_(
                0.0, 0.66, 0.99, 1.0
            )  # #00A8FC
        )
        self._settings_container.addSubview_(self._feedback_label)

        self._content_view.addSubview_(self._settings_container)

    def _build_action_button(self) -> None:
        """Builds prominent bottom toggle button ('DETENER EN DISCORD' / 'INICIAR PRESENCIA')."""
        self._action_button = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(16, 276, 308, 38)
        )
        self._action_button.setButtonType_(AppKit.NSButtonTypeMomentaryChange)
        self._action_button.setBezelStyle_(AppKit.NSBezelStyleRegularSquare)
        self._action_button.setFont_(AppKit.NSFont.boldSystemFontOfSize_(13))
        self._action_button.setWantsLayer_(True)
        if self._action_button.layer():
            self._action_button.layer().setCornerRadius_(8.0)
            self._action_button.layer().setMasksToBounds_(True)

        self._action_button.setTarget_(self)
        self._action_button.setAction_(b"actionButtonClicked:")
        self._content_view.addSubview_(self._action_button)

    # =========================================================================
    # Visual State Updaters
    # =========================================================================

    def _update_mode_cards_visuals(self) -> None:
        """Updates card border, background, and radio dots based on active mode."""
        is_official = self._current_mode == "oficial"

        # Update Card 1 (Oficial)
        if self._card_official and self._card_official.layer():
            if is_official:
                self._card_official.layer().setBackgroundColor_(
                    AppKit.NSColor.colorWithWhite_alpha_(1.0, 0.12).CGColor()
                )
                self._card_official.layer().setBorderColor_(
                    AppKit.NSColor.colorWithRed_green_blue_alpha_(
                        0.0, 0.66, 0.99, 0.5
                    ).CGColor()
                )
                if self._card_official_radio:
                    self._card_official_radio.setStringValue_("◉")
                    self._card_official_radio.setTextColor_(
                        AppKit.NSColor.colorWithRed_green_blue_alpha_(
                            0.0, 0.66, 0.99, 1.0
                        )
                    )
            else:
                self._card_official.layer().setBackgroundColor_(
                    AppKit.NSColor.colorWithWhite_alpha_(1.0, 0.04).CGColor()
                )
                self._card_official.layer().setBorderColor_(
                    AppKit.NSColor.clearColor().CGColor()
                )
                if self._card_official_radio:
                    self._card_official_radio.setStringValue_("○")
                    self._card_official_radio.setTextColor_(
                        AppKit.NSColor.secondaryLabelColor()
                    )

        # Update Card 2 (Detallado)
        if self._card_detailed and self._card_detailed.layer():
            if not is_official:
                self._card_detailed.layer().setBackgroundColor_(
                    AppKit.NSColor.colorWithWhite_alpha_(1.0, 0.12).CGColor()
                )
                self._card_detailed.layer().setBorderColor_(
                    AppKit.NSColor.colorWithRed_green_blue_alpha_(
                        0.0, 0.66, 0.99, 0.5
                    ).CGColor()
                )
                if self._card_detailed_radio:
                    self._card_detailed_radio.setStringValue_("◉")
                    self._card_detailed_radio.setTextColor_(
                        AppKit.NSColor.colorWithRed_green_blue_alpha_(
                            0.0, 0.66, 0.99, 1.0
                        )
                    )
            else:
                self._card_detailed.layer().setBackgroundColor_(
                    AppKit.NSColor.colorWithWhite_alpha_(1.0, 0.04).CGColor()
                )
                self._card_detailed.layer().setBorderColor_(
                    AppKit.NSColor.clearColor().CGColor()
                )
                if self._card_detailed_radio:
                    self._card_detailed_radio.setStringValue_("○")
                    self._card_detailed_radio.setTextColor_(
                        AppKit.NSColor.secondaryLabelColor()
                    )

    def _update_action_button_style(self) -> None:
        """Updates action button title and distinct styling for active vs stopped states."""
        if not self._action_button:
            return

        title = self.get_action_button_title()
        self._action_button.setTitle_(title)

        if self._action_button.layer():
            if self._presence_active:
                # Active presence: dark slate gray
                c = AppKit.NSColor.colorWithRed_green_blue_alpha_(
                    0.20, 0.23, 0.28, 1.0
                )
                self._action_button.layer().setBackgroundColor_(c.CGColor())
            else:
                # Stopped presence: Discord Blurple (#5865F2)
                c = AppKit.NSColor.colorWithRed_green_blue_alpha_(
                    0.35, 0.40, 0.95, 1.0
                )
                self._action_button.layer().setBackgroundColor_(c.CGColor())

    def _build_web_ui(self) -> None:
        """Constructs WebKit Liquid Glass UI and overlays it seamlessly onto _content_view."""
        if not HAS_WEBKIT or not self._content_view or generate_liquid_html is None:
            return
        try:
            ucc = WebKit.WKUserContentController.alloc().init()
            self._web_bridge = LoLWebBridge.alloc().initWithController_(self)
            ucc.addScriptMessageHandler_name_(self._web_bridge, "lolrpc")
            config = WebKit.WKWebViewConfiguration.alloc().init()
            config.setUserContentController_(ucc)

            bounds = self._content_view.bounds()
            self._web_view = WebKit.WKWebView.alloc().initWithFrame_configuration_(
                bounds, config
            )
            self._web_view.setValue_forKey_(False, "drawsBackground")
            self._web_view.setAutoresizingMask_(
                AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
            )
            champ_url = ""
            if self._champion_resolver:
                try:
                    cid, _ = self._champion_resolver.resolve_champion(self._champion)
                    champ_url = self._champion_resolver.get_square_icon_url(cid)
                except Exception:
                    pass
            state = {
                "mode": self._current_mode,
                "autoreset": self._autoreset_state,
                "autorun": self._autorun_state,
                "presence_active": self._presence_active,
                "connection_state": self._connection_state,
                "settings_expanded": self._settings_expanded,
                "champion": self._champion,
                "rank": self._rank,
                "division": self._division,
                "game_mode": self._game_mode,
                "champ_url": champ_url,
                "is_apex": is_apex_tier(self._rank),
            }
            html = generate_liquid_html(state)
            self._web_view.loadHTMLString_baseURL_(html, None)
            self._content_view.addSubview_(self._web_view)
        except Exception:
            pass

    def _sync_to_web(self) -> None:
        """Pushes current state to the WebKit Liquid Glass UI via evaluateJavaScript."""
        if not getattr(self, "_web_view", None):
            return
        champ_url = ""
        if self._champion_resolver:
            try:
                cid, _ = self._champion_resolver.resolve_champion(self._champion)
                champ_url = self._champion_resolver.get_square_icon_url(cid)
            except Exception:
                pass
        state = {
            "mode": self._current_mode,
            "autoreset": self._autoreset_state,
            "autorun": self._autorun_state,
            "presence_active": self._presence_active,
            "connection_state": self._connection_state,
            "settings_expanded": self._settings_expanded,
            "champion": self._champion,
            "rank": self._rank,
            "division": self._division,
            "game_mode": self._game_mode,
            "champ_url": champ_url,
            "is_apex": is_apex_tier(self._rank),
        }
        js = f"if (window.updateLiquidUI) {{ window.updateLiquidUI({json.dumps(state)}); }}"
        try:
            self._web_view.evaluateJavaScript_completionHandler_(js, None)
        except Exception:
            pass

    def _update_layout(self) -> None:
        """Adjusts popover frame size and action button position when settings expand/collapse."""
        show_settings = self.is_settings_panel_visible()
        total_height = 515 if show_settings else 360

        if self._settings_container:
            self._settings_container.setHidden_(not show_settings)

        if self._content_view:
            self._content_view.setFrame_(
                AppKit.NSMakeRect(0, 0, 340, total_height)
            )

        if self._popover:
            self._popover.setContentSize_(AppKit.NSMakeSize(340, total_height))

        if getattr(self, "_web_view", None) and self._content_view:
            self._web_view.setFrame_(self._content_view.bounds())

        # Position action button at the bottom of the container
        btn_y = total_height - 52
        if self._action_button:
            self._action_button.setFrame_(
                AppKit.NSMakeRect(16, btn_y, 308, 38)
            )

        self._sync_to_web()

    # =========================================================================
    # Cocoa Actions (@objc.IBAction)
    # =========================================================================

    @objc.IBAction
    def actionButtonClicked_(self, sender: Any) -> None:
        self.handle_action_button_click()

    @objc.IBAction
    def gearButtonClicked_(self, sender: Any) -> None:
        self.toggle_settings_panel()

    @objc.IBAction
    def officialCardClicked_(self, sender: Any) -> None:
        self.select_mode("oficial")

    @objc.IBAction
    def detailedCardClicked_(self, sender: Any) -> None:
        self.select_mode("detallado")

    @objc.IBAction
    def autoresetSwitchChanged_(self, sender: Any) -> None:
        if self._autoreset_switch:
            is_on = (
                self._autoreset_switch.state() == AppKit.NSControlStateValueOn
            )
            self.set_autoreset_state(is_on)

    @objc.IBAction
    def autorunSwitchChanged_(self, sender: Any) -> None:
        if self._autorun_switch:
            is_on = self._autorun_switch.state() == AppKit.NSControlStateValueOn
            self.toggle_autorun(is_on)

    @objc.IBAction
    def championFieldChanged_(self, sender: Any) -> None:
        if self._champion_field:
            self.set_selected_champion(self._champion_field.stringValue())

    @objc.IBAction
    def rankPopupChanged_(self, sender: Any) -> None:
        if self._rank_popup:
            self.select_rank(self._rank_popup.titleOfSelectedItem())

    @objc.IBAction
    def divisionPopupChanged_(self, sender: Any) -> None:
        if self._division_popup:
            self.select_division(self._division_popup.titleOfSelectedItem())

    @objc.IBAction
    def gameModeFieldChanged_(self, sender: Any) -> None:
        if self._game_mode_field:
            self.set_game_mode_text(self._game_mode_field.stringValue())

    # =========================================================================
    # NSPopover Lifecycle & Public Controls
    # =========================================================================

    def get_popover(self) -> AppKit.NSPopover:
        """Returns the managed Cocoa NSPopover instance."""
        return self._popover

    def get_content_view_controller(self) -> AppKit.NSViewController:
        """Returns the NSViewController hosting the popover content view."""
        return self._content_vc

    def get_content_size(self) -> AppKit.NSSize:
        """Returns the popover content size (NSSize)."""
        if self._popover and hasattr(self._popover, "contentSize"):
            try:
                sz = self._popover.contentSize()
                if sz is not None and hasattr(sz, "width"):
                    return sz
            except Exception:
                pass
        h = 515 if self.is_settings_panel_visible() else 360
        return AppKit.NSMakeSize(340, h)

    def get_title_text(self) -> str:
        """Returns header title string."""
        return "Discord RPC"

    def get_subtitle_text(self) -> str:
        """Returns header subtitle string."""
        return "League of Legends"

    def get_gear_button(self) -> Optional[AppKit.NSButton]:
        """Returns settings gear button."""
        return self._gear_button

    def show(self, positioning_view: Any = None) -> None:
        """
        Shows the popover anchored to the specified positioning view.
        Safe and idempotent if already shown.
        """
        if self._is_shown:
            return
        self._is_shown = True

        if positioning_view is not None and self._popover is not None:
            try:
                rect = getattr(
                    positioning_view,
                    "bounds",
                    lambda: AppKit.NSMakeRect(0, 0, 0, 0),
                )()
                if not isinstance(rect, (AppKit.NSRect, tuple)):
                    rect = AppKit.NSMakeRect(0, 0, 0, 0)
                self._popover.showRelativeToRect_ofView_preferredEdge_(
                    rect, positioning_view, AppKit.NSRectEdgeMinY
                )
                app = AppKit.NSApplication.sharedApplication()
                if app:
                    app.activateIgnoringOtherApps_(True)
            except Exception:
                pass

    def close(self) -> None:
        """
        Closes the popover. Safe and idempotent if already closed.
        """
        if not self._is_shown:
            return
        self._is_shown = False

        if self._popover is not None:
            try:
                self._popover.close()
            except Exception:
                pass

    def toggle(self, positioning_view: Any = None) -> None:
        """Toggles popover visibility."""
        if self.is_shown():
            self.close()
        else:
            self.show(positioning_view)

    def is_shown(self) -> bool:
        """Returns True if the popover is currently presented."""
        return bool(
            self._is_shown
            or (hasattr(self._popover, "isShown") and self._popover.isShown())
        )

    def popoverDidClose_(self, notification: Any) -> None:
        """NSPopoverDelegate callback triggered when dismissed by outside click."""
        self._is_shown = False

    # =========================================================================
    # Mode Selection (F4)
    # =========================================================================

    def get_current_mode(self) -> str:
        """Returns the currently active mode ('oficial' or 'detallado')."""
        return self._current_mode

    def select_mode(self, mode: str) -> None:
        """
        Switches between 'oficial' and 'detallado' modes.
        Case-insensitive, idempotent on repeated selections, and updates UI.
        """
        if not mode:
            return
        norm = str(mode).lower().strip()
        if norm not in ("oficial", "detallado"):
            return
        if norm == self._current_mode:
            return

        self._current_mode = norm
        if norm == "oficial":
            self._settings_expanded = False
        elif norm == "detallado":
            self._settings_expanded = True

        self._update_mode_cards_visuals()
        self._update_layout()

        # Notify callback
        if callable(self._on_mode_change):
            try:
                self._on_mode_change(self._current_mode)
            except Exception:
                pass

        # Push to DiscordRPCManager actor
        if self._rpc_manager:
            try:
                self._rpc_manager.update_presence_config(mode=self._current_mode)
            except Exception:
                pass

    def is_mode_card_selected(self, mode: str) -> bool:
        """Returns True if the given mode card is currently selected."""
        if not mode:
            return False
        return str(mode).lower().strip() == self._current_mode

    # =========================================================================
    # Interactive Switches (F5)
    # =========================================================================

    def get_autoreset_state(self) -> bool:
        """Returns match auto-restart switch state."""
        return bool(self._autoreset_state)

    def set_autoreset_state(self, val: Any) -> None:
        """Sets match auto-restart state (converts 0, 1, 'true' cleanly)."""
        if isinstance(val, str):
            b_val = val.lower().strip() in ("true", "1", "yes", "on")
        else:
            b_val = bool(val)
        self._autoreset_state = b_val

        if self._autoreset_switch:
            self._autoreset_switch.setState_(
                AppKit.NSControlStateValueOn
                if b_val
                else AppKit.NSControlStateValueOff
            )

        if self._rpc_manager:
            try:
                self._rpc_manager.update_presence_config(autoreset=b_val)
            except Exception:
                pass

        self._sync_to_web()

    def get_autorun_state(self) -> bool:
        """Returns macOS login item autorun state."""
        return bool(self._autorun_state)

    def set_autorun_state(self, val: Any) -> None:
        """Sets macOS autorun state without triggering login item commands."""
        if isinstance(val, str):
            b_val = val.lower().strip() in ("true", "1", "yes", "on")
        else:
            b_val = bool(val)
        self._autorun_state = b_val
        if self._autorun_switch:
            self._autorun_switch.setState_(
                AppKit.NSControlStateValueOn
                if b_val
                else AppKit.NSControlStateValueOff
            )
        self._sync_to_web()

    def toggle_autorun(self, val: Any = None) -> None:
        """Toggles or sets macOS autorun state and synchronizes login item."""
        if val is None:
            b_val = not self._autorun_state
        elif isinstance(val, str):
            b_val = val.lower().strip() in ("true", "1", "yes", "on")
        else:
            b_val = bool(val)

        self._autorun_state = b_val
        if self._autorun_switch:
            self._autorun_switch.setState_(
                AppKit.NSControlStateValueOn
                if b_val
                else AppKit.NSControlStateValueOff
            )

        if callable(self._on_autorun_toggle):
            try:
                self._on_autorun_toggle(b_val)
            except Exception:
                pass

        self._sync_login_item(b_val)
        self._sync_to_web()

    def get_autoreset_switch_view(self) -> Optional[AppKit.NSSwitch]:
        """Returns NSSwitch instance for autoreset."""
        return self._autoreset_switch

    def get_autorun_switch_view(self) -> Optional[AppKit.NSSwitch]:
        """Returns NSSwitch instance for autorun."""
        return self._autorun_switch

    def check_autorun(self) -> bool:
        """Queries macOS LaunchAgent or System Events for login item presence."""
        try:
            plist_path = os.path.expanduser(
                "~/Library/LaunchAgents/com.victormanuel.lolrpc.plist"
            )
            if os.path.exists(plist_path):
                return True
        except Exception:
            pass

        try:
            res = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to get (exists login item "League of Legends RPC")',
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=0.2,
            )
            return res.stdout.strip().lower() == "true"
        except Exception:
            return False

    def _sync_login_item(self, enabled: bool) -> None:
        """Adds or removes the application from macOS LaunchAgent and login items."""
        plist_path = os.path.expanduser(
            "~/Library/LaunchAgents/com.victormanuel.lolrpc.plist"
        )
        try:
            if enabled:
                # 1. Manage LaunchAgent plist
                os.makedirs(os.path.dirname(plist_path), exist_ok=True)
                plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.victormanuel.lolrpc</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>-a</string>
        <string>/Applications/League of Legends RPC.app</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>ProcessType</key>
    <string>Interactive</string>
</dict>
</plist>
"""
                with open(plist_path, "w", encoding="utf-8") as f:
                    f.write(plist_content)
                subprocess.run(
                    ["launchctl", "load", "-w", plist_path],
                    capture_output=True,
                    check=False,
                    timeout=0.5,
                )
                cmd = (
                    'tell application "System Events" to make login item at end with properties '
                    '{path:"/Applications/League of Legends RPC.app", hidden:false, name:"League of Legends RPC"}'
                )
            else:
                if os.path.exists(plist_path):
                    subprocess.run(
                        ["launchctl", "unload", "-w", plist_path],
                        capture_output=True,
                        check=False,
                        timeout=0.5,
                    )
                    try:
                        os.remove(plist_path)
                    except OSError:
                        pass
                cmd = 'tell application "System Events" to delete login item "League of Legends RPC"'

            subprocess.run(
                ["osascript", "-e", cmd],
                capture_output=True,
                check=False,
                timeout=0.5,
            )
        except Exception:
            pass

    # =========================================================================
    # Bottom Action Button (F6)
    # =========================================================================

    def is_presence_active(self) -> bool:
        """Returns True if Discord presence is currently enabled."""
        return bool(self._presence_active)

    def set_presence_active(self, active: Any) -> None:
        """Sets presence active flag and updates button title and styling."""
        self._presence_active = bool(active)
        self._update_action_button_style()

    def get_action_button_title(self) -> str:
        """Returns current action button title."""
        if self._presence_active:
            return "⏹ DETENER EN DISCORD"
        return "▶ INICIAR PRESENCIA"

    def get_action_button_style(self) -> Dict[str, Any]:
        """Returns distinct style dictionary reflecting button state."""
        if self._presence_active:
            return {
                "state": "active",
                "title": self.get_action_button_title(),
                "color": "#36393F",
                "active": True,
            }
        return {
            "state": "stopped",
            "title": self.get_action_button_title(),
            "color": "#5865F2",
            "active": False,
        }

    def handle_action_button_click(self) -> None:
        """Toggles presence state, updates visuals, and notifies listeners."""
        self._presence_active = not self._presence_active
        self._update_action_button_style()

        if callable(self._on_action_toggle):
            try:
                self._on_action_toggle(self._presence_active)
            except Exception:
                pass

        if self._rpc_manager:
            try:
                self._rpc_manager.set_active(self._presence_active)
            except Exception:
                pass
        self._sync_to_web()

    def set_connection_state(self, state: str) -> None:
        """Handles connection status updates from DiscordRPCManager."""
        if not state:
            return
        norm = str(state).lower().strip()
        self._connection_state = norm
        if norm == "paused":
            self.set_presence_active(False)
        elif norm in ("connected", "active"):
            self.set_presence_active(True)
        self._sync_to_web()

    def get_action_button(self) -> Optional[AppKit.NSButton]:
        """Returns bottom action button widget."""
        return self._action_button

    # =========================================================================
    # Settings / Detailed View (F7)
    # =========================================================================

    def get_selected_champion(self) -> str:
        """Returns currently selected champion name."""
        return self._champion

    def set_selected_champion(self, name: Any) -> None:
        """
        Sets selected champion name, normalizes via ChampionResolver, and updates RPC config.
        Safely defaults empty/whitespace input to 'Malzahar'.
        """
        if name is None or (isinstance(name, str) and not name.strip()):
            self._champion = "Malzahar"
        else:
            self._champion = str(name).strip()

        if self._champion_field:
            try:
                self._champion_field.setStringValue_(self._champion)
            except Exception:
                pass

        # Resolve champion icon and display name
        if self._champion_resolver:
            try:
                cid, dname = self._champion_resolver.resolve_champion(self._champion)
                icon_url = self._champion_resolver.get_square_icon_url(cid)
                if self._feedback_label:
                    self._feedback_label.setStringValue_(
                        f"✓ Resuelto: {dname} (DDragon: {cid})"
                    )
                if self._rpc_manager and self._current_mode == "detallado":
                    self._rpc_manager.update_presence_config(
                        champion_name=dname,
                        champion_image_url=icon_url,
                    )
            except Exception:
                pass
        self._sync_to_web()

    def get_available_rank_tiers(self) -> List[str]:
        """Returns list of competitive rank tiers in Spanish."""
        return list(DEFAULT_RANKS_ES)

    def get_available_divisions(self) -> List[str]:
        """Returns list of roman divisions (I-IV)."""
        return list(DEFAULT_DIVISIONS)

    def get_selected_rank(self) -> str:
        """Returns currently selected rank tier."""
        return self._rank

    def select_rank(self, rank_tier: str) -> None:
        """
        Sets competitive rank tier. Automatically disables division selection for Apex tiers.
        """
        if not rank_tier:
            return
        self._rank = str(rank_tier).strip()
        self._division_enabled = not is_apex_tier(self._rank)

        if self._division_popup:
            try:
                self._division_popup.setEnabled_(self._division_enabled)
            except Exception:
                pass

        if self._rank_popup:
            try:
                self._rank_popup.selectItemWithTitle_(self._rank)
            except Exception:
                pass

        if self._rpc_manager and self._current_mode == "detallado":
            try:
                rank_str = format_rank_display(self._rank, self._division)
                crest_url = get_rank_crest_url(self._rank)
                self._rpc_manager.update_presence_config(
                    rank_text=rank_str,
                    rank_image_url=crest_url,
                )
            except Exception:
                pass
        self._sync_to_web()

    def get_selected_division(self) -> str:
        """Returns currently selected division."""
        return self._division

    def select_division(self, division: str) -> None:
        """Sets division (I, II, III, IV)."""
        if not division:
            return
        self._division = str(division).strip()

        if self._division_popup:
            try:
                self._division_popup.selectItemWithTitle_(self._division)
            except Exception:
                pass

        if self._rpc_manager and self._current_mode == "detallado":
            try:
                rank_str = format_rank_display(self._rank, self._division)
                crest_url = get_rank_crest_url(self._rank)
                self._rpc_manager.update_presence_config(
                    rank_text=rank_str,
                    rank_image_url=crest_url,
                )
            except Exception:
                pass
        self._sync_to_web()

    def is_division_selector_enabled(self) -> bool:
        """Returns True if division selector is enabled (False for Apex tiers)."""
        return bool(self._division_enabled)

    def get_game_mode_text(self) -> str:
        """Returns game mode description string."""
        return self._game_mode

    def set_game_mode_text(self, text: str) -> None:
        """Sets game mode string and dispatches to RPC manager."""
        self._game_mode = str(text) if text is not None else ""
        if self._game_mode_field:
            try:
                self._game_mode_field.setStringValue_(self._game_mode)
            except Exception:
                pass

        if self._rpc_manager and self._current_mode == "detallado":
            try:
                self._rpc_manager.update_presence_config(
                    game_mode=self._game_mode
                )
            except Exception:
                pass
        self._sync_to_web()

    def is_settings_panel_visible(self) -> bool:
        """Returns True if the detailed settings panel is currently expanded/visible."""
        return bool(self._current_mode == "detallado" or self._settings_expanded)

    def toggle_settings_panel(self) -> None:
        """Toggles settings panel expansion state."""
        self._settings_expanded = not self._settings_expanded
        self._update_layout()

    def get_champion_field(self) -> Optional[AppKit.NSTextField]:
        """Returns champion input text field."""
        return self._champion_field

    def get_rank_popup(self) -> Optional[AppKit.NSPopUpButton]:
        """Returns rank selector popup button."""
        return self._rank_popup

    def get_division_popup(self) -> Optional[AppKit.NSPopUpButton]:
        """Returns division selector popup button."""
        return self._division_popup

    def get_game_mode_field(self) -> Optional[AppKit.NSTextField]:
        """Returns game mode text field."""
        return self._game_mode_field

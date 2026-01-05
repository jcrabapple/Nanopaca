# preferences.py

from gi.repository import Adw, Gtk, Gio, GLib
import importlib.util, icu, sys, os, requests, json, logging
from ..constants import (
    TTS_VOICES,
    STT_MODELS,
    SPEACH_RECOGNITION_LANGUAGES,
    REMBG_MODELS,
    IN_FLATPAK,
)
from . import dialog
from ..sql_manager import Instance as SQL
from .instances import NanoGPT

logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/com/jeffser/Alpaca/preferences.ui")
class PreferencesDialog(Adw.PreferencesDialog):
    __gtype_name__ = "AlpacaPreferencesDialog"

    # GENERAL
    show_model_manager_shortcut_switch = Gtk.Template.Child()
    folder_search_mode_switch = Gtk.Template.Child()
    zoom_spin = Gtk.Template.Child()
    regenerate_after_edit = Gtk.Template.Child()
    image_size_spin = Gtk.Template.Child()

    # NANOGPT
    nanogpt_api_key = Gtk.Template.Child()
    test_api_key_button = Gtk.Template.Child()
    balance_label = Gtk.Template.Child()
    balance_row = Gtk.Template.Child()
    balance_amount_label = Gtk.Template.Child()
    refresh_balance_button = Gtk.Template.Child()
    default_model = Gtk.Template.Child()
    title_model = Gtk.Template.Child()
    subscription_only = Gtk.Template.Child()
    web_search_enabled = Gtk.Template.Child()
    web_search_depth = Gtk.Template.Child()
    temperature_slider = Gtk.Template.Child()
    max_tokens = Gtk.Template.Child()
    system_prompt_row = Gtk.Template.Child()
    system_prompt = Gtk.Template.Child()
    auto_youtube_transcripts = Gtk.Template.Child()
    context_memory_days = Gtk.Template.Child()

    # AUDIO
    mic_group = Gtk.Template.Child()
    mic_model_combo = Gtk.Template.Child()
    mic_language_combo = Gtk.Template.Child()
    mic_auto_send_switch = Gtk.Template.Child()
    tts_group = Gtk.Template.Child()
    tts_voice_combo = Gtk.Template.Child()
    tts_auto_mode_combo = Gtk.Template.Child()
    tts_speed_spin = Gtk.Template.Child()
    audio_page = Gtk.Template.Child()

    # ACTIVITIES
    activity_mode = Gtk.Template.Child()
    default_tool = Gtk.Template.Child()

    activity_terminal_type = Gtk.Template.Child()
    activity_terminal_ssh_user = Gtk.Template.Child()
    activity_terminal_ssh_ip = Gtk.Template.Child()
    activity_terminal_flatpak_warning = Gtk.Template.Child()
    activity_terminal_flatpak_warning_command = Gtk.Template.Child()

    activity_background_remover_default_model = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def zoom_changed(self, spinner):
        set_zoom(int(spinner.get_value()))

    @Gtk.Template.Callback()
    def delete_all_chats_button_pressed(self, button):
        root = self.get_root()

        def delete_all_chats():
            SQL.factory_reset()
            root_folder = list(root.chat_list_navigationview.get_navigation_stack())[0]
            GLib.idle_add(root.chat_list_navigationview.pop_to_page, root_folder)
            root_folder.update()

        dialog.simple(
            parent=root,
            heading=_("Delete All Chats"),
            body=_("Are you sure you want to delete every chat and folder?"),
            callback=delete_all_chats,
            button_appearance="destructive",
        )
        self.close()

    def activity_terminal_type_changed(self, dropdown, gparam=None):
        selected_index = dropdown.get_selected()
        self.activity_terminal_ssh_user.set_visible(selected_index == 1)
        self.activity_terminal_ssh_ip.set_visible(selected_index == 1)
        self.activity_terminal_flatpak_warning.set_visible(
            selected_index == 0 and IN_FLATPAK
        )
        self.activity_terminal_flatpak_warning_command.set_visible(
            selected_index == 0 and IN_FLATPAK
        )

    @Gtk.Template.Callback()
    def on_test_api_key(self, button):
        """Test NanoGPT API key and show balance"""
        api_key = self.nanogpt_api_key.get_text().strip()

        if not api_key:
            self.balance_label.set_text(_("Please enter an API key"))
            self.balance_label.remove_css_class("success")
            self.balance_label.add_css_class("error")
            return

        # Clear previous status and show testing state
        self.balance_label.set_text(_("Testing API key..."))
        self.balance_label.remove_css_class("success")
        self.balance_label.remove_css_class("error")
        
        button.set_sensitive(False)
        button.set_label(_("Testing..."))

        GLib.timeout_add(100, lambda: self.test_nanogpt_api_key(api_key, button))

    def test_nanogpt_api_key(self, api_key, button):
        """Validate API key by fetching models"""
        try:
            response = requests.get(
                "https://nano-gpt.com/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )

            if response.status_code == 200:
                self.balance_label.set_text(_("API key is valid"))
                self.balance_label.remove_css_class("error")
                self.balance_label.add_css_class("success")

                # Save API key to instance
                self.save_nanogpt_settings()
                
                # Try to get balance from models response first
                data = response.json()
                balance = 0
                
                # Check if balance is included in models response
                if "balance" in data:
                    balance = data["balance"]
                elif "data" in data and "balance" in data["data"]:
                    balance = data["data"]["balance"]
                elif "credit" in data:
                    balance = data["credit"]
                elif "data" in data and "credit" in data["data"]:
                    balance = data["data"]["credit"]
                
                # If we found a balance, display it
                if balance > 0:
                    self.balance_amount_label.set_text(_("${:.2f}").format(balance))
                    logger.info(f"Balance found in models response: ${balance:.2f}")
                else:
                    # If no balance in models response, try the balance endpoint
                    self.balance_amount_label.set_text(_("--"))
                    GLib.timeout_add(100, lambda: self.fetch_balance(api_key))
                
                logger.info(f"API validation successful, models response: {data}")
            else:
                self.balance_label.set_text(_("Invalid API key"))
                self.balance_label.remove_css_class("success")
                self.balance_label.add_css_class("error")
                self.balance_amount_label.set_text(_("--"))

        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            self.balance_label.set_text(_("Connection error"))
            self.balance_label.remove_css_class("success")
            self.balance_label.add_css_class("error")
            self.balance_amount_label.set_text(_("--"))

        finally:
            button.set_sensitive(True)
            button.set_label(_("Test"))

    def save_nanogpt_settings(self):
        """Save NanoGPT settings to database"""
        try:
            instances = SQL.get_instances()
            nanogpt_instance = next(
                (i for i in instances if i.get("type") == "nanogpt"), None
            )

            if nanogpt_instance:
                properties = nanogpt_instance.get("properties", {})
                properties["api"] = self.nanogpt_api_key.get_text()
                properties["temperature"] = self.temperature_slider.get_value()
                properties["max_tokens"] = int(self.max_tokens.get_value())
                properties["web_search_enabled"] = self.web_search_enabled.get_active()
                properties["web_search_depth"] = (
                    "standard" if self.web_search_depth.get_selected() == 0 else "deep"
                )
                properties["auto_youtube_transcripts"] = (
                    self.auto_youtube_transcripts.get_active()
                )
                properties["context_memory_days"] = int(
                    self.context_memory_days.get_value()
                )

                # Save system prompt
                buffer = self.system_prompt.get_buffer()
                properties["system_prompt"] = buffer.get_text(
                    buffer.get_start_iter(), buffer.get_end_iter(), False
                )

                SQL.insert_or_update_instance(
                    instance_id=nanogpt_instance.get("id"),
                    pinned=True,
                    instance_type="nanogpt",
                    properties=properties,
                )
        except Exception as e:
            logger.error(f"Failed to save NanoGPT settings: {e}")

    def load_nanogpt_settings(self):
        """Load NanoGPT settings from database"""
        try:
            instances = SQL.get_instances()
            nanogpt_instance = next(
                (i for i in instances if i.get("type") == "nanogpt"), None
            )

            if nanogpt_instance:
                properties = nanogpt_instance.get("properties", {})

                # Load API key
                api_key = properties.get("api", "")
                self.nanogpt_api_key.set_text(api_key)

                if api_key:
                    # Test connection and show balance
                    GLib.timeout_add(500, lambda: self.fetch_balance(api_key))

                # Load generation parameters
                self.temperature_slider.set_value(properties.get("temperature", 0.7))
                self.max_tokens.set_value(properties.get("max_tokens", 4096))

                # Load web search settings
                self.web_search_enabled.set_active(
                    properties.get("web_search_enabled", False)
                )
                depth = properties.get("web_search_depth", "standard")
                self.web_search_depth.set_selected(0 if depth == "standard" else 1)

                # Load advanced features
                self.auto_youtube_transcripts.set_active(
                    properties.get("auto_youtube_transcripts", True)
                )
                self.context_memory_days.set_value(
                    properties.get("context_memory_days", 30)
                )

                # Load system prompt
                system_prompt = properties.get("system_prompt", "")
                buffer = self.system_prompt.get_buffer()
                buffer.set_text(system_prompt)

        except Exception as e:
            logger.error(f"Failed to load NanoGPT settings: {e}")

    def fetch_balance(self, api_key):
        """Fetch and display balance from NanoGPT API using exact working example format"""
        try:
            # Make API request exactly as shown in working example
            response = requests.post(
                "https://nano-gpt.com/api/check-balance",
                headers={"x-api-key": api_key},
                timeout=10,
            )

            logger.info(f"Balance API response status: {response.status_code}")
            logger.info(f"Balance API raw response: {response.text}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"Balance API parsed data: {data}")
                    
                    # Simple and robust balance extraction
                    balance = 0
                    
                    # Handle different response formats
                    if isinstance(data, dict):
                        # Try the actual field names from the API response first
                        if "usd_balance" in data:
                            balance = float(data["usd_balance"])
                            logger.info(f"Found USD balance: {balance}")
                        elif "nano_balance" in data:
                            balance = float(data["nano_balance"])
                            logger.info(f"Found Nano balance: {balance}")
                        # Also try the previous field names for compatibility
                        elif "balance" in data:
                            balance = data["balance"]
                        elif "credit" in data:
                            balance = data["credit"]
                        elif "amount" in data:
                            balance = data["amount"]
                        elif "data" in data:
                            # Check nested data
                            nested = data["data"]
                            if isinstance(nested, dict):
                                if "usd_balance" in nested:
                                    balance = float(nested["usd_balance"])
                                elif "nano_balance" in nested:
                                    balance = float(nested["nano_balance"])
                                elif "balance" in nested:
                                    balance = nested["balance"]
                                elif "credit" in nested:
                                    balance = nested["credit"]
                                elif "amount" in nested:
                                    balance = nested["amount"]
                    elif isinstance(data, (int, float)):
                        # Direct numeric response
                        balance = data
                    elif isinstance(data, list) and len(data) > 0:
                        # List response - try first item
                        first = data[0]
                        if isinstance(first, (int, float)):
                            balance = first
                        elif isinstance(first, dict):
                            if "balance" in first:
                                balance = first["balance"]
                            elif "credit" in first:
                                balance = first["credit"]
                            elif "amount" in first:
                                balance = first["amount"]
                    
                    # Display the balance
                    if isinstance(balance, (int, float)):
                        self.balance_amount_label.set_text(_("${:.2f}").format(balance))
                        logger.info(f"Successfully displayed balance: ${balance:.2f}")
                    else:
                        logger.error(f"Balance value is not numeric: {balance} (type: {type(balance)})")
                        self.balance_amount_label.set_text(_("--"))
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Raw response: {response.text}")
                    self.balance_amount_label.set_text(_("--"))
            else:
                logger.error(f"API request failed with status {response.status_code}")
                self.balance_amount_label.set_text(_("--"))

        except Exception as e:
            logger.error(f"Balance fetch failed: {e}")
            self.balance_amount_label.set_text(_("--"))
            logger.error(f"Failed to fetch balance: {e}")
            self.balance_label.set_text(_("Connection error"))
            self.balance_label.remove_css_class("success")
            self.balance_label.add_css_class("error")
            self.balance_amount_label.set_text(_("--"))

    def on_refresh_balance(self, button):
        """Refresh the account balance"""
        api_key = self.nanogpt_api_key.get_text().strip()
        if api_key:
            self.balance_amount_label.set_text(_("--"))  # Clear old balance while fetching
            GLib.timeout_add(100, lambda: self.fetch_balance(api_key))
        else:
            self.balance_label.set_text(_("Please enter an API key first"))
            self.balance_label.remove_css_class("success")
            self.balance_label.add_css_class("error")

    def load_nanogpt_models(self):
        """Load available NanoGPT models into dropdowns"""
        try:
            instances = SQL.get_instances()
            nanogpt_instance = next(
                (i for i in instances if i.get("type") == "nanogpt"), None
            )

            if nanogpt_instance:
                properties = nanogpt_instance.get("properties", {})
                api_key = properties.get("api")

                if not api_key:
                    return

                # Fetch models
                response = requests.get(
                    "https://nano-gpt.com/api/v1/models",
                    params={"detailed": "true"},
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    models = data.get("data", [])

                    # Get model store and clear by creating new StringList
                    model_store = Gio.ListStore.new(Gtk.StringObject)
                    self.default_model.set_model(model_store)
                    title_store = Gio.ListStore.new(Gtk.StringObject)
                    self.title_model.set_model(title_store)

                    # Add models
                    for model in models:
                        model_name = model.get("name", model["id"])
                        model_store.append(Gtk.StringObject.new(model_name))
                        title_store.append(Gtk.StringObject.new(model_name))

                    # Set selected models
                    default_model = properties.get("default_model")
                    title_model = properties.get("title_model")

                    # Find and select models
                    for i in range(len(model_store)):
                        if model_store.get_item(i).get_string() == default_model:
                            self.default_model.set_selected(i)
                            break

                    for i in range(len(title_store)):
                        if title_store.get_item(i).get_string() == title_model:
                            self.title_model.set_selected(i)
                            break

        except Exception as e:
            logger.error(f"Failed to load NanoGPT models: {e}")

    def on_nanogpt_model_changed(self, dropdown, prop_name):
        """Save model selection when changed"""
        selected = dropdown.get_selected_item()
        if selected:
            self.save_nanogpt_settings()

    def __init__(self):
        super().__init__()

        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")

        dropdown_factory = Gtk.SignalListItemFactory()
        dropdown_factory.connect(
            "setup",
            lambda factory, list_item: list_item.set_child(
                Gtk.Label(ellipsize=0, xalign=0)
            ),
        )
        dropdown_factory.connect(
            "bind",
            lambda factory, list_item: list_item.get_child().set_text(
                list_item.get_item().get_string()
            ),
        )

        # NANOGPT signal connections
        self.test_api_key_button.connect("clicked", self.on_test_api_key)
        self.refresh_balance_button.connect("clicked", self.on_refresh_balance)
        self.default_model.connect("notify::selected", self.on_nanogpt_model_changed)

        # GENERAL
        self.settings.bind(
            "show-model-manager-shortcut",
            self.show_model_manager_shortcut_switch,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "folder-search-mode",
            self.folder_search_mode_switch,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "zoom", self.zoom_spin, "value", Gio.SettingsBindFlags.DEFAULT
        )
        self.settings.bind(
            "regenerate-after-edit",
            self.regenerate_after_edit,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.mic_group.set_visible(importlib.util.find_spec("whisper"))

        self.settings.bind(
            "max-image-size",
            self.image_size_spin,
            "value",
            Gio.SettingsBindFlags.DEFAULT,
        )

        # AUDIO
        for model, size in STT_MODELS.items():
            self.mic_model_combo.get_model().append(
                "{} ({})".format(model.title(), size)
            )
        self.mic_model_combo.set_factory(dropdown_factory)
        self.settings.bind(
            "stt-model", self.mic_model_combo, "selected", Gio.SettingsBindFlags.DEFAULT
        )

        for lan in SPEACH_RECOGNITION_LANGUAGES:
            self.mic_language_combo.get_model().append(
                "{} ({})".format(
                    icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title(), lan
                )
            )
        self.mic_language_combo.set_factory(dropdown_factory)
        self.settings.bind(
            "stt-language",
            self.mic_language_combo,
            "selected",
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.settings.bind(
            "stt-auto-send",
            self.mic_auto_send_switch,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.tts_group.set_visible(
            importlib.util.find_spec("kokoro")
            and importlib.util.find_spec("sounddevice")
        )

        self.audio_page.set_visible(
            importlib.util.find_spec("kokoro")
            and importlib.util.find_spec("sounddevice")
            and importlib.util.find_spec("whisper")
        )

        for name in TTS_VOICES:
            self.tts_voice_combo.get_model().append(name)
        self.tts_voice_combo.set_factory(dropdown_factory)
        self.settings.bind(
            "tts-model", self.tts_voice_combo, "selected", Gio.SettingsBindFlags.DEFAULT
        )

        self.settings.bind(
            "tts-auto-dictate",
            self.tts_auto_mode_combo,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "tts-speed", self.tts_speed_spin, "value", Gio.SettingsBindFlags.DEFAULT
        )

        # ACTIVITIES
        self.settings.bind(
            "activity-mode",
            self.activity_mode,
            "selected",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.activity_mode.set_factory(dropdown_factory)
        self.settings.bind(
            "default-tool", self.default_tool, "selected", Gio.SettingsBindFlags.DEFAULT
        )
        self.default_tool.set_factory(dropdown_factory)

        self.settings.bind(
            "activity-terminal-type",
            self.activity_terminal_type,
            "selected",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.activity_terminal_type.set_factory(dropdown_factory)
        self.settings.bind(
            "activity-terminal-username",
            self.activity_terminal_ssh_user,
            "text",
            Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "activity-terminal-ip",
            self.activity_terminal_ssh_ip,
            "text",
            Gio.SettingsBindFlags.DEFAULT,
        )

        if not self.settings.get_value("activity-terminal-ip").unpack():
            self.settings.set_string("activity-terminal-ip", "127.0.0.1")
        self.activity_terminal_type.connect("notify::selected", self.activity_terminal_type_changed)
        self.activity_terminal_type_changed(self.activity_terminal_type)

        for m in REMBG_MODELS.values():
            self.activity_background_remover_default_model.get_model().append(
                "{} ({})".format(m.get("display_name"), m.get("size"))
            )
        self.activity_background_remover_default_model.set_factory(dropdown_factory)
        self.settings.bind(
            "activity-background-remover-model",
            self.activity_background_remover_default_model,
            "selected",
            Gio.SettingsBindFlags.DEFAULT,
        )

        # NANOGPT
        self.load_nanogpt_settings()
        self.load_nanogpt_models()
        
        # Initialize balance UI
        self.balance_label.set_text("")  # Clear the "Loading..." text
        self.balance_amount_label.set_text(_("--"))  # Show "--" for no balance initially


def get_zoom():
    settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
    return settings.get_value("zoom").unpack() or 100


def set_zoom(new_value):
    new_value = max(100, min(200, new_value))
    new_value = (new_value // 10) * 10  # Snap to nearest 10
    settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
    settings.set_int("zoom", new_value)

    # Baseline DPI is 96*1024 (at 100%)
    # Always recalculate from baseline
    gtk_settings = Gtk.Settings.get_default()
    gtk_settings.reset_property("gtk-xft-dpi")
    dpi = (96 * 1024) + (new_value - 100) * 400
    gtk_settings.set_property("gtk-xft-dpi", dpi)


def zoom_in(*_):
    set_zoom(get_zoom() + 10)


def zoom_out(*_):
    set_zoom(get_zoom() - 10)

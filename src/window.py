# window.py
#
# Copyright 2024-2025 Jeffser
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Handles the main window
"""

import json, threading, os, re, gettext, shutil, logging, time, requests, sys, tempfile, importlib.util
import numpy as np

from datetime import datetime

from gi.repository import Adw, Gtk, Gdk, GLib, GtkSource, Gio, Spelling

from .sql_manager import (
    generate_uuid,
    generate_numbered_name,
    prettify_model_name,
    Instance as SQL,
)
from . import widgets as Widgets
from .constants import data_dir, source_dir, cache_dir

logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/com/jeffser/Alpaca/window.ui")
class AlpacaWindow(Adw.ApplicationWindow):
    __gtype_name__ = "AlpacaWindow"

    localedir = os.path.join(source_dir, "locale")

    gettext.bindtextdomain("com.jeffser.Alpaca", localedir)
    gettext.textdomain("com.jeffser.Alpaca")
    _ = gettext.gettext

    # Elements
    new_chat_splitbutton = Gtk.Template.Child()
    model_manager = Gtk.Template.Child()
    instance_manager_stack = Gtk.Template.Child()
    main_navigation_view = Gtk.Template.Child()
    split_view_overlay = Gtk.Template.Child()
    toast_overlay = Gtk.Template.Child()
    chat_bin = Gtk.Template.Child()
    chat_list_navigationview = Gtk.Template.Child()
    global_footer = Gtk.Template.Child()
    message_searchbar = Gtk.Template.Child()
    searchentry_messages = Gtk.Template.Child()

    file_filter_db = Gtk.Template.Child()

    banner = Gtk.Template.Child()

    instance_preferences_page = Gtk.Template.Child()
    instance_listbox = Gtk.Template.Child()
    last_selected_instance_row = None

    chat_split_view_overlay = Gtk.Template.Child()
    activity_manager = Gtk.Template.Child()
    chat_page = Gtk.Template.Child()
    small_breakpoint = Gtk.Template.Child()

    chat_searchbar = Gtk.Template.Child()

    # NanoGPT features
    context_memory_toggle = Gtk.Template.Child()
    web_search_depth_button = Gtk.Template.Child()
    standard_search = Gtk.Template.Child()
    deep_search = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def chat_list_page_changed(self, navigationview, page=None):
        if self.chat_searchbar.get_search_mode():
            self.chat_searchbar.set_search_mode(False)
            previous_page = navigationview.get_previous_page(
                navigationview.get_visible_page()
            )
            if previous_page:
                previous_page.on_search("")

    @Gtk.Template.Callback()
    def first_breakpoint_applied(self, bp):
        if len(self.activity_manager.tabview.get_pages()) == 0:
            self.chat_split_view_overlay.set_show_sidebar(False)

    @Gtk.Template.Callback()
    def add_instance(self, button):
        logger.info("add_instance: called")
        
        # For NanoGPT, directly show the instance preferences dialog
        from .widgets.instances.openai_instances import NanoGPT
        instance = NanoGPT(instance_id=None, properties={})
        logger.info(f"add_instance: created NanoGPT instance, instance_type={instance.instance_type}")
        
        Widgets.instances.InstancePreferencesDialog(instance).present(self)
        logger.info("add_instance: presented dialog")

        Widgets.instances.update_instance_list(
            instance_listbox=self.instance_listbox,
            selected_instance_id=self.settings.get_value("selected-instance").unpack(),
        )

    def on_context_memory_toggled(self, toggle):
        """Toggle context memory for the current chat"""
        if toggle.get_active():
            toggle.add_css_class("suggested-action")
        else:
            toggle.remove_css_class("suggested-action")

        # Update instance property
        instance = self.get_active_instance()
        if instance and instance.instance_type == "nanogpt":
            instance.properties["context_memory_enabled"] = toggle.get_active()

    @Gtk.Template.Callback()
    def on_web_search_standard_toggled(self, radio):
        """Set web search to standard depth"""
        if radio.get_active():
            instance = self.get_active_instance()
            if instance and instance.instance_type == "nanogpt":
                instance.properties["web_search_depth"] = "standard"
                self.web_search_depth_button.set_tooltip_text(
                    _("Standard Search ($0.006)")
                )

    @Gtk.Template.Callback()
    def on_web_search_deep_toggled(self, radio):
        """Set web search to deep depth"""
        if radio.get_active():
            instance = self.get_active_instance()
            if instance and instance.instance_type == "nanogpt":
                instance.properties["web_search_depth"] = "deep"
                self.web_search_depth_button.set_tooltip_text(_("Deep Search ($0.06)"))

    @Gtk.Template.Callback()
    def chat_search_changed(self, search_entry):
        """Handle chat search text changes"""
        chat_list_page = self.get_chat_list_page()
        if chat_list_page:
            chat_list_page.on_search(search_entry.get_text())

    @Gtk.Template.Callback()
    def message_search_changed(self, search_entry):
        """Handle message search text changes"""
        pass

    @Gtk.Template.Callback()
    def instance_changed(self, listbox, row):
        """Handle instance selection changes"""
        pass

    @Gtk.Template.Callback()
    def closing_app(self, widget):
        """Handle window close request"""
        pass

    def reload_instances(self):
        """Reload the instance list from SQL"""
        Widgets.instances.update_instance_list(
            instance_listbox=self.instance_listbox,
            selected_instance_id=self.settings.get_value("selected-instance").unpack(),
        )
        if self.model_manager:
            GLib.idle_add(self.model_manager.update_added_model_list)

    def prepare_alpaca(self):
        """Prepare the main Alpaca interface"""
        # Initialize instance list
        self.reload_instances()

        # Initialize chat list with root folder if empty
        stack = self.chat_list_navigationview.get_navigation_stack()
        if not stack or len(stack) == 0:
            root_folder = Widgets.chat.Folder()
            self.chat_list_navigationview.add(root_folder)

    def send_message(self, mode:int=0, available_tools:dict={}):
        """Send message from global footer - called by message widget as callback"""
        logger.info("send_message: called")
        
        # Get current chat
        chat = self.chat_bin.get_child()
        if not chat:
            logger.warning("send_message: no chat in chat_bin")
            # Create a new chat automatically
            chat_list_page = self.get_chat_list_page()
            if chat_list_page:
                chat = chat_list_page.new_chat()
                chat_list_page.chat_list_box.select_row(chat.row)
                # Retry send after UI update
                GLib.idle_add(lambda: self.send_message(mode, available_tools))
                return
            return
            
        # Get active instance
        instance = self.get_active_instance()
        if not instance:
            logger.warning("send_message: no active instance")
            return
            
        # Get model
        model = instance.get_default_model()
        if not model:
            logger.warning("send_message: no model selected")
            return

        # Get message text
        buffer = self.global_footer.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        raw_message = buffer.get_text(start, end, False)
        
        if not raw_message or not raw_message.strip():
            return
            
        # Clear the buffer
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        
        # Create and add user message
        from .widgets.message import Message
        user_message = Message(
            dt=datetime.now(),
            mode=mode,
            author=_("You")
        )
        chat.container.append(user_message)
        user_message.block_container.set_content(raw_message)
        
        # Save user message to database
        SQL.insert_or_update_message(user_message)
        
        # Create bot message
        bot_message = Message(
            dt=datetime.now(),
            mode=1,
            author=model
        )
        chat.container.append(bot_message)
        
        # Generate AI response
        chat.busy = True
        self.global_footer.toggle_action_button(False)
        threading.Thread(target=instance.generate_message, args=(bot_message, model), daemon=True).start()
        
    def on_setup_complete(self):
        """Called when setup wizard completes"""
        # Reload main interface
        pass  # Setup already pushed the main view

    def get_active_instance(self):
        """Get the currently active instance"""
        instance_list = list(self.instance_listbox)
        if instance_list:
            selected = self.instance_listbox.get_selected_row()
            if selected:
                return selected.instance
        return None

    def get_current_instance(self):
        return self.get_active_instance()

    def on_chat_imported(self, file):
        if file:
            if os.path.isfile(os.path.join(cache_dir, "import.db")):
                os.remove(os.path.join(cache_dir, "import.db"))
            file.copy(
                Gio.File.new_for_path(os.path.join(cache_dir, "import.db")),
                Gio.FileCopyFlags.OVERWRITE,
                None,
                None,
                None,
                None,
            )
            chat_names = [
                tab.chat.get_name()
                for tab in list(self.get_chat_list_page().chat_list_box)
            ]
            for chat in SQL.import_chat(
                os.path.join(cache_dir, "import.db"),
                chat_names,
                self.get_chat_list_page().folder_id,
            ):
                self.get_chat_list_page().add_chat(
                    chat_name=chat[1], chat_id=chat[0], is_template=False, mode=1
                )
            Widgets.dialog.show_toast(_("Chat imported successfully"), self)

    def toggle_searchbar(self):
        current_tag = self.main_navigation_view.get_visible_page_tag()

        searchbars = {
            "chat": self.message_searchbar,
            "model_manager": self.model_manager.searchbar,
        }

        if searchbars.get(current_tag):
            searchbars.get(current_tag).set_search_mode(
                not searchbars.get(current_tag).get_search_mode()
            )

    def get_chat_list_page(self):
        return self.chat_list_navigationview.get_visible_page()

    def push_or_pop(self, page_name: str):
        if self.main_navigation_view.get_visible_page().get_tag() != page_name:
            GLib.idle_add(self.main_navigation_view.push_by_tag, page_name)
        else:
            GLib.idle_add(self.main_navigation_view.pop_to_tag, "chat")

    def open_available_model_page(self):
        self.main_navigation_view.push_by_tag("model_manager")
        self.model_manager.view_stack.set_visible_child_name("available_models")

    def prepare_screenshoter(self):
        # used to take screenshots of widgets for documentation
        widget = self.get_focus().get_parent()
        while True:
            if "Alpaca" in repr(widget):
                break
            widget = widget.get_parent()

        widget.unparent()
        Adw.ApplicationWindow(
            width_request=640, height_request=10, content=widget
        ).present()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        actions = [
            [
                {
                    "label": _("New Chat"),
                    "callback": lambda: self.get_application()
                    .lookup_action("new_chat")
                    .activate(),
                    "icon": "chat-message-new-symbolic",
                },
                {
                    "label": _("New Folder"),
                    "callback": lambda: self.get_application()
                    .lookup_action("new_folder")
                    .activate(),
                    "icon": "folder-new-symbolic",
                },
            ]
        ]
        popover = Widgets.dialog.Popover(actions)
        popover.set_has_arrow(True)
        popover.set_halign(0)
        self.new_chat_splitbutton.set_popover(popover)

        self.set_focus(self.global_footer.message_text_view)

        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        for el in ("default-width", "default-height", "maximized", "hide-on-close"):
            self.settings.bind(el, self, el, Gio.SettingsBindFlags.DEFAULT)

        # Zoom
        Widgets.preferences.set_zoom(Widgets.preferences.get_zoom())

        universal_actions = {
            "new_chat": [
                lambda *_: self.get_chat_list_page().new_chat(),
                ["<primary>n"],
            ],
            "new_folder": [
                lambda *_: self.get_chat_list_page().prompt_new_folder(),
                ["<primary>d"],
            ],
            "import_chat": [
                lambda *_: Widgets.dialog.simple_file(
                    parent=self,
                    file_filters=[self.file_filter_db],
                    callback=self.on_chat_imported,
                )
            ],
            "duplicate_current_chat": [
                lambda *_: self.chat_bin.get_child().row.duplicate()
            ],
            "delete_current_chat": [
                lambda *_: self.chat_bin.get_child().row.prompt_delete(),
                ["<primary>w"],
            ],
            "edit_current_chat": [
                lambda *_: self.chat_bin.get_child().row.prompt_edit(),
                ["F2"],
            ],
            "export_current_chat": [
                lambda *_: self.chat_bin.get_child().row.prompt_export()
            ],
            "toggle_sidebar": [
                lambda *_: self.split_view_overlay.set_show_sidebar(
                    not self.split_view_overlay.get_show_sidebar()
                ),
                ["F9"],
            ],
            "toggle_search": [lambda *_: self.toggle_searchbar(), ["<primary>f"]],
            "model_manager": [
                lambda *_: self.push_or_pop("model_manager"),
                ["<primary>m"],
            ],
            "model_manager_available": [lambda *_: self.open_available_model_page()],
            "instance_manager": [
                lambda *_: self.push_or_pop("instance_manager"),
                ["<primary>i"],
            ],
            "add_model_by_name": [
                lambda *i: Widgets.dialog.simple_entry(
                    parent=self,
                    heading=_("Pull Model"),
                    body=_(
                        "Please enter the model name following this template: name:tag"
                    ),
                    callback=lambda name: Widgets.models.basic.confirm_pull_model(
                        window=self, model_name=name
                    ),
                    entries={"placeholder": "deepseek-r1:7b"},
                )
            ],
            "reload_added_models": [
                lambda *_: GLib.idle_add(self.model_manager.update_added_model_list)
            ],
            "start_quick_ask": [
                lambda *_: self.get_application().create_quick_ask().present(),
                ["<primary><alt>a"],
            ],
            "model_creator_existing": [
                lambda *_: Widgets.models.common.prompt_existing(self)
            ],
            "model_creator_gguf": [lambda *_: Widgets.models.common.prompt_gguf(self)],
            "preferences": [
                lambda *_: Widgets.preferences.PreferencesDialog().present(self),
                ["<primary>comma"],
            ],
            "zoom_in": [lambda *_: Widgets.preferences.zoom_in(), ["<primary>plus"]],
            "zoom_out": [lambda *_: Widgets.preferences.zoom_out(), ["<primary>minus"]],
        }
        if os.getenv("ALPACA_ENABLE_SCREENSHOT_ACTION", "0") == "1":
            universal_actions["screenshoter"] = [
                lambda *_: self.prepare_screenshoter(),
                ["F3"],
            ]

        for action_name, data in universal_actions.items():
            self.get_application().create_action(
                action_name, data[0], data[1] if len(data) > 1 else None
            )

        def verify_powersaver_mode():
            self.banner.set_revealed(
                Gio.PowerProfileMonitor.dup_default().get_power_saver_enabled()
                and self.settings.get_value("powersaver-warning").unpack()
                and self.get_active_instance()
                and self.get_active_instance().instance_type == "ollama:managed"
            )

        Gio.PowerProfileMonitor.dup_default().connect(
            "notify::power-saver-enabled", lambda *_: verify_powersaver_mode()
        )
        self.banner.connect(
            "button-clicked", lambda *_: self.banner.set_revealed(False)
        )

        self.prepare_alpaca()

        # Check if NanoGPT is configured, otherwise show setup dialog
        nanogpt_instances = [
            i for i in SQL.get_instances() if i.get("type") == "nanogpt"
        ]
        if not nanogpt_instances:
            # Show setup dialog instead of welcome
            setup_dialog = Widgets.setup.SetupDialog()
            setup_dialog.present(self)
            setup_dialog.connect("closed", lambda *_: self.reload_instances())
        else:
            # Normal startup - create new chat if none exist
            def ensure_chat():
                chat_list_page = self.get_chat_list_page()
                if not chat_list_page:
                    logger.warning("ensure_chat: chat_list_page is None")
                    return False
                    
                logger.info(f"ensure_chat: chat_list_page = {type(chat_list_page).__name__}")
                
                chats = SQL.get_chats_by_folder()
                logger.info(f"ensure_chat: chats = {chats}, len = {len(chats) if chats else 0}")
                
                if not chats:
                    logger.info("ensure_chat: no chats found, creating new chat")
                    new_chat = chat_list_page.new_chat()
                    if new_chat and new_chat.row:
                        chat_list_page.chat_list_box.select_row(new_chat.row)
                        logger.info(f"ensure_chat: created and selected chat = {new_chat.get_name()}")
                    else:
                        logger.warning(f"ensure_chat: new_chat or new_chat.row is None: new_chat={new_chat}")
                else:
                    logger.info(f"ensure_chat: chats already exist, selecting first one")
                    if chat_list_page.chat_list_box:
                        first_row = chat_list_page.chat_list_box.get_row_at_index(0)
                        if first_row:
                            chat_list_page.chat_list_box.select_row(first_row)
                            
                return False  # Don't repeat
            
            GLib.timeout_add(300, ensure_chat)

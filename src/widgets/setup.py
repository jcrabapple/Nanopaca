# setup.py
#
# Copyright 2025 Jeffser
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, GObject

import requests, json, logging
from ..sql_manager import generate_uuid, Instance as SQL
from . import dialog

logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/com/jeffser/Alpaca/setup.ui")
class SetupDialog(Adw.Dialog):
    __gtype_name__ = "AlpacaSetupDialog"

    navigationview = Gtk.Template.Child()

    # Page 1: Welcome
    welcome_page = Gtk.Template.Child()
    get_started_button = Gtk.Template.Child()

    # Page 2: API Key
    api_key_page = Gtk.Template.Child()
    api_key_entry = Gtk.Template.Child()
    test_api_key_button = Gtk.Template.Child()
    api_key_status_label = Gtk.Template.Child()
    balance_label = Gtk.Template.Child()
    next_button = Gtk.Template.Child()

    # Page 3: Model Selection
    model_page = Gtk.Template.Child()
    model_dropdown = Gtk.Template.Child()
    model_description_label = Gtk.Template.Child()
    finish_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validated_api_key = None
        self.selected_model = None
        self.model_store = None

        # Initialize model store
        self.model_store = Gio.ListStore.new(ModelRow)
        self.model_dropdown.set_model(self.model_store)

        # Connect signals
        self.test_api_key_button.connect("clicked", self.on_test_api_key)
        self.next_button.connect("clicked", self.on_next_to_model)
        self.finish_button.connect("clicked", self.on_finish_setup)

        # Setup model dropdown
        self.model_dropdown.connect("notify::selected-item", self.on_model_selected)

    @Gtk.Template.Callback()
    def on_get_started(self, button):
        """Navigate to API key page"""
        self.navigationview.push(self.api_key_page)

    @Gtk.Template.Callback()
    def on_test_api_key(self, button):
        """Validate API key by checking balance"""
        api_key = self.api_key_entry.get_text().strip()

        if not api_key:
            self.api_key_status_label.set_text(_("Please enter your NanoGPT API key"))
            return

        # Disable button during test
        self.test_api_key_button.set_sensitive(False)
        self.test_api_key_button.set_label(_("Testing..."))

        # Test the API key
        GLib.timeout_add(100, lambda: self.validate_api_key(api_key))

    def validate_api_key(self, api_key):
        """Validate API key and fetch balance"""
        try:
            response = requests.post(
                "https://nano-gpt.com/api/v1/check-balance",
                headers={"x-api-key": api_key},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                balance = data.get("balance", 0)
                self.validated_api_key = api_key
                self.balance_label.set_text(f"${balance:.2f}")
                self.api_key_status_label.set_text(_("✓ Valid API key"))
                self.api_key_status_label.add_css_class("success")
                self.next_button.set_sensitive(True)
            else:
                self.api_key_status_label.set_text(_("✗ Invalid API key"))
                self.api_key_status_label.add_css_class("error")
                self.next_button.set_sensitive(False)

        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            self.api_key_status_label.set_text(_("✗ Connection error"))
            self.api_key_status_label.add_css_class("error")

        finally:
            self.test_api_key_button.set_sensitive(True)
            self.test_api_key_button.set_label(_("Test Connection"))

    def on_next_to_model(self, button):
        """Fetch models and show model selection page"""
        if not self.validated_api_key:
            return

        # Push model page
        self.navigationview.push(self.model_page)

        # Fetch models
        self.fetch_models()

    def fetch_models(self):
        """Fetch available models from NanoGPT"""
        try:
            response = requests.get(
                "https://nano-gpt.com/api/v1/models",
                params={"detailed": "true"},
                headers={"Authorization": f"Bearer {self.validated_api_key}"},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])

                # Clear and populate model store
                self.model_store.remove_all()

                for model in models:
                    model_row = ModelRow(
                        id=model["id"],
                        name=model.get("name", model["id"]),
                        description=model.get("description", ""),
                    )
                    self.model_store.append(model_row)

                # Select first model
                if len(self.model_store) > 0:
                    self.model_dropdown.set_selected(0)

        except Exception as e:
            logger.error(f"Failed to fetch models: {e}")
            dialog.simple_error(
                parent=self,
                title=_("Error"),
                body=_(
                    "Failed to fetch models. Please check your internet connection."
                ),
                error_log=e,
            )

    def on_model_selected(self, dropdown, _):
        """Show model description when selected"""
        selected = dropdown.get_selected_item()
        if selected:
            self.selected_model = selected.id
            self.model_description_label.set_text(selected.description)

    def on_finish_setup(self, button):
        """Save configuration and complete setup"""
        if not self.validated_api_key or not self.selected_model:
            return

        # Create NanoGPT instance
        instance_id = generate_uuid()
        SQL.insert_or_update_instance(
            instance_id=instance_id,
            pinned=True,
            instance_type="nanogpt",
            properties={
                "name": "NanoGPT",
                "api": self.validated_api_key,
                "default_model": self.selected_model,
                "temperature": 0.7,
                "max_tokens": 4096,
                "web_search_enabled": False,
                "web_search_depth": "standard",
                "auto_youtube_transcripts": True,
                "context_memory_enabled": False,
                "context_memory_days": 30,
                "system_prompt": "",
            },
        )

        # Mark setup as complete
        self.get_root().settings.set_value("skip-welcome", GLib.Variant("b", True))

        # Close setup and reload
        self.get_root().on_setup_complete()


class ModelRow(GObject.Object):
    __gtype_name__ = "ModelRow"

    def __init__(self, id: str, name: str, description: str):
        super().__init__()
        self._id = id
        self._name = name
        self._description = description

    @GObject.Property(type=str)
    def id(self):
        return self._id

    @GObject.Property(type=str)
    def name(self):
        return self._name

    @GObject.Property(type=str)
    def description(self):
        return self._description

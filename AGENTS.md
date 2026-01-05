# AGENTS.md - Alpaca Development Guide

## Project Overview

**Alpaca** is a GNOME desktop AI chat client powered by NanoGPT. Built with Python 3, GTK4, Adwaita, and distributed primarily via Flatpak.

- **Version**: 9.0.0
- **License**: GPL-3.0-or-later
- **Architecture**: MVC-like pattern with widget-based UI, SQLite backend
- **Tech Stack**: Python 3.13+, GTK 4.0, Adwaita 1, Meson build system
- **AI Backend**: NanoGPT API (OpenAI-compatible)

## Build, Lint & Test Commands

### Building with Meson

```bash
# Development build
meson setup build
ninja -C build

# Install locally
ninja -C build install

# Clean build
rm -rf build && meson setup build

# Reconfigure
meson configure build

# Run development version
./build/src/alpaca
```

### Flatpak Build (Detailed)

```bash
# Install prerequisites (GNOME 46+ SDK and Platform)
flatpak install flathub org.gnome.Sdk//46 org.gnome.Platform//46

# Build and install locally for testing
flatpak-builder --user --install --force-clean build-dir com.jeffser.Alpaca.yml

# Run Flatpak version
flatpak run com.jeffser.Alpaca

# Build only (no install)
flatpak-builder --force-clean build-dir com.jeffser.Alpaca.yml

# Export to local repository
flatpak-builder --repo=repo --force-clean build-dir com.jeffser.Alpaca.yml

# Install from local repo
flatpak --user remote-add --no-gpg-verify alpaca-repo repo
flatpak --user install alpaca-repo com.jeffser.Alpaca

# Common flags:
# --force-clean: Clean build directory before building
# --ccache: Enable ccache for faster rebuilds
# --keep-build-dirs: Keep build artifacts for debugging
```

### Linting

```bash
# Run pylint on source code
pylint src/

# Lint specific file
pylint src/main.py
```

**Pylint Configuration** (`.pylintrc`):
- Max line length: 200 characters
- Disabled checks: `undefined-variable`, `line-too-long`, `missing-function-docstring`, `consider-using-f-string`, `import-error`
- Rationale: `_()` translator not defined in source, f-strings incompatible with translation

### Testing

**Current State**: No formal test suite exists. Testing is manual.

**Manual Testing Approach**:
```bash
# Test specific features with command-line arguments
./build/src/alpaca --quick-ask                    # Test Quick Ask window
./build/src/alpaca --activity live-chat           # Test Live Chat
./build/src/alpaca --new-chat "Test Chat"         # Create new chat
./build/src/alpaca --ask "Test message"           # Test with message
./build/src/alpaca --list-activities              # List all activities

# Test in Flatpak environment (primary distribution)
flatpak run com.jeffser.Alpaca --quick-ask

# Test with different AI backends
# - Configure Ollama instance in preferences
# - Configure OpenAI-compatible instance
# - Test streaming, vision models, tool use
```

**Recommended Testing Framework Setup**:
1. Install testing dependencies: `pip install pytest pytest-gtk pytest-cov`
2. Create `tests/` directory structure:
   ```
   tests/
   ├── test_sql_manager.py      # Database operations
   ├── test_constants.py         # Constants and helpers
   ├── test_widgets/             # Widget tests
   │   ├── test_chat.py
   │   └── test_message.py
   └── conftest.py               # Pytest configuration
   ```
3. Mock external services (Ollama, OpenAI APIs) using `unittest.mock` or `pytest-mock`
4. Run tests: `pytest tests/ -v --cov=src`

## Code Style Guidelines

### Import Order

```python
# 1. GTK/GI imports with version requirements
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, GLib

# 2. Standard library imports
import os, sys, logging, json, threading

# 3. Local imports (relative)
from .constants import SAMPLE_PROMPTS, cache_dir
from ..sql_manager import Instance as SQL
from . import widgets, dialog
```

### Python Formatting

- **Max line length**: 200 characters
- **Type hints**: Encouraged (e.g., `def function(param: str) -> dict:`)
- **Docstrings**: Optional - only when code isn't self-explanatory
- **Logging**: Use `logger = logging.getLogger(__name__)`
- **Translation function**: Use `_()` for all user-facing strings
  - ❌ `_(f"Hello {name}")` - Never use f-strings inside `_()`
  - ✓ `_("Hello {}").format(name)` - Format after translation

### Naming Conventions

- **Files**: `snake_case.py` (e.g., `sql_manager.py`, `quick_ask.py`)
- **Classes**: `PascalCase` (e.g., `AlpacaApplication`, `ChatRow`, `Message`)
- **Functions/Methods**: `snake_case()` (e.g., `generate_uuid()`, `on_drop_chat()`)
- **Constants**: `SCREAMING_SNAKE_CASE` (e.g., `SAMPLE_PROMPTS`, `TTS_VOICES`)
- **Private**: Prefix with `_` (e.g., `_scroll_timeout_id`, `_on_internal_event()`)
- **GTK widget types**: Use `__gtype_name__ = 'AlpacaWidgetName'`

### File Headers

```python
# filename.py
#
# Copyright 2025 Jeffser
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Optional module docstring explaining file purpose
"""
```

## GTK & UI Development Patterns

### Blueprint (.blp) Files

**Location**: `src/ui/` and `src/ui/widgets/`

**Blueprint Syntax**:
```blp
using Gtk 4.0;
using Adw 1;

template $AlpacaWidgetName : Adw.Bin {
  Gtk.Box {
    orientation: vertical;
    spacing: 12;
    
    Gtk.Label label {
      label: _("Translatable Text");
    }
    
    Gtk.Button my_button {
      label: _("Click Me");
      clicked => $on_button_clicked();
    }
  }
}
```

**Compilation**: Meson automatically compiles `.blp` → `.ui` during build

**Python Integration**:
```python
@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/my_widget.ui')
class MyWidget(Adw.Bin):
    __gtype_name__ = 'AlpacaWidgetName'
    
    label = Gtk.Template.Child()
    my_button = Gtk.Template.Child()
    
    @Gtk.Template.Callback()
    def on_button_clicked(self, button):
        self.label.set_label(_("Button clicked!"))
```

### GTK Widget Patterns

- **Templates**: Use `@Gtk.Template` for UI-backed widgets
- **Child access**: `Gtk.Template.Child()` binds template children as class attributes
- **Signals**: Use `@Gtk.Template.Callback()` or `.connect("signal", handler)`
- **Custom widgets**: Inherit from appropriate base (Adw.Bin, Gtk.Box, Adw.NavigationPage, etc.)
- **Navigation**: Use `Adw.NavigationView` with `Adw.NavigationPage` for hierarchical UI

### Threading & Async Operations

```python
# Run function on main thread
GLib.idle_add(update_ui_function, arg1, arg2)

# Timer/timeout
timeout_id = GLib.timeout_add(1000, callback_function)  # milliseconds
GLib.source_remove(timeout_id)  # Cancel timer

# Background work
def background_task():
    result = expensive_operation()
    GLib.idle_add(update_ui_with_result, result)

thread = threading.Thread(target=background_task)
thread.start()
```

**Critical**: All GTK operations must run on the main thread. Use `GLib.idle_add()` to return from background threads.

### Resource Management

- **Icons**: Use symbolic names (e.g., `'language-symbolic'`, `'code-symbolic'`)
- **CSS classes**: `.add_css_class('accent')`, `.remove_css_class('error')`
- **Custom styles**: `src/style.css` (light) and `src/style-dark.css` (dark theme)
- **Resources**: Loaded via GResource (compiled in Meson)

## Backend Architecture & Patterns

### Database (sql_manager.py)

```python
# Initialize at startup (done in main.py)
SQL.initialize()

# UUID generation with timestamp prefix
chat_id = generate_uuid()  # Format: YYYYMMDDHHMMSSffffff + UUID hex

# CRUD operations
SQL.insert_or_update_chat(chat_object)
chats = SQL.get_chats_by_folder(folder_id)
SQL.delete_chat(chat_id)

# Data directories
from .constants import data_dir, config_dir, cache_dir
```

### NanoGPT Instance Pattern

```python
from .instances import NanoGPT

# Get active instance
instance = window.get_active_instance()

# Web search
result = instance.web_search(query)

# Check balance
balance = instance.check_balance()

# Generate image
result = instance.generate_image(prompt, size="1024x1024")
```

### Module Organization

- `src/main.py` - Application entry, DBus service, CLI argument handling
- `src/window.py` - Main window implementation and orchestration
- `src/constants.py` - App constants, configurations, sample data
- `src/sql_manager.py` - SQLite database operations
- `src/widgets/` - Widget implementations
  - `chat.py` - Chat interface widget
  - `message.py` - Message display widget
  - `blocks/` - Content blocks (code, text, LaTeX, etc.)
  - `activities/` - Detached windows (camera, terminal, transcriber, etc.)
  - `instances/` - AI backend connectors (Ollama, OpenAI-compatible)
  - `models/` - Model management UI
  - `tools/` - Tool integration widgets

### Internationalization (i18n)

```python
# Use _() for all user-facing strings
label.set_label(_("Hello World"))

# Format with placeholders AFTER translation
message = _("Hello {}").format(name)
message = _("Processing {} of {}").format(current, total)

# Constants that need translation
SAMPLE_PROMPTS = [
    _("What can you do?"),
    _("Give me a pancake recipe"),
]
```

**Translations**: 27 languages supported in `po/` directory

### AI Instance Pattern

- Plugin-like architecture in `src/widgets/instances/`
- Each backend (Ollama, OpenAI-compatible) has its own module
- Common interface for chat streaming and model management
- Instance configs stored in SQLite via `sql_manager.py`

## Common Pitfalls & Best Practices

### Avoid

- ❌ Using f-strings with `_()`: `_(f"Error: {msg}")` - Breaks translation
- ❌ Forgetting `gi.require_version()` before imports - Causes warnings
- ❌ Hardcoding paths - Use constants (`data_dir`, `config_dir`, `cache_dir`)
- ❌ Blocking main thread - Long operations must use threading + `GLib.idle_add()`
- ❌ Direct file operations - Check `IN_FLATPAK` and use XDG directories
- ❌ Logging API keys - Never log or expose NanoGPT API keys

### Best Practices

- ✓ Test in Flatpak environment (primary distribution method)
- ✓ Use `get_xdg_home()` helper for XDG directories
- ✓ Log appropriately: `logger.info()`, `logger.warning()`, `logger.error()`
- ✓ GTK operations only on main thread
- ✓ Follow existing widget patterns for consistency
- ✓ Check existing code before adding dependencies
- ✓ Store API keys securely via `sql_manager` instance properties

## Development Workflow

1. **IDE**: GNOME Builder recommended (per CONTRIBUTING.md), but any Python IDE works
2. **Before contributing**: 
   - Check for existing issue or create one
   - Ask for maintainer approval before starting work
3. **Development cycle**:
   - Make changes
   - Build: `ninja -C build`
   - Test manually with various CLI arguments
   - Test in Flatpak if UI changes
4. **Submit PR**: Ensure code follows style guide, test thoroughly

## Quick Reference

```bash
# Build & Run
meson setup build && ninja -C build
./build/src/alpaca

# Flatpak
flatpak-builder --user --install --force-clean build-dir com.jeffser.Alpaca.yml
flatpak run com.jeffser.Alpaca

# Lint
pylint src/

# Test Features
./build/src/alpaca --version
./build/src/alpaca --quick-ask
./build/src/alpaca --activity live-chat
./build/src/alpaca --list-activities
./build/src/alpaca --new-chat "Test"
./build/src/alpaca --ask "Hello AI"

# Clean
rm -rf build
```

## Additional Resources

- **Contributing**: See `CONTRIBUTING.md` for full guidelines
- **License**: GPL-3.0 (see `COPYING`)
- **Issues**: https://github.com/Jeffser/Alpaca/issues
- **Translations**: See discussion #153 on GitHub

---

*This guide is for AI coding agents and human developers working on Alpaca.*

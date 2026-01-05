# AGENTS.md - Nanopaca Development Guide

## Project Overview

**Nanopaca** is a GNOME desktop AI chat client forked from Alpaca, powered by NanoGPT API. Built with Python 3, GTK4, Adwaita, and distributed via Flatpak.

- **Tech Stack**: Python 3.13+, GTK 4.0, Adwaita 1, Meson build system
- **License**: GPL-3.0-or-later

## Build, Lint & Test Commands

### Build with Meson
```bash
meson setup build
ninja -C build
./build/src/alpaca

# Clean rebuild
rm -rf build && meson setup build
```

### Flatpak Build
```bash
flatpak install flathub org.gnome.Sdk//46 org.gnome.Platform//46
flatpak-builder --user --install --force-clean build-dir com.jeffser.Alpaca.yml
flatpak run com.jeffser.Alpaca
```

### Linting
```bash
pylint src/                    # Lint all source code
pylint src/main.py             # Lint specific file
```

### Testing (Manual)
```bash
./build/src/alpaca --quick-ask              # Quick Ask window
./build/src/alpaca --activity live-chat     # Live Chat
./build/src/alpaca --new-chat "Test Chat"   # Create new chat
./build/src/alpaca --ask "Test message"     # Test with message
flatpak run com.jeffser.Alpaca --quick-ask  # Test in Flatpak
```

## Code Style Guidelines

### Import Order
```python
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, GLib

import os, sys, logging, json, threading

from .constants import SAMPLE_PROMPTS, cache_dir
from ..sql_manager import Instance as SQL
```

### Formatting & Naming
- **Max line length**: 200 characters
- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Methods**: `snake_case()`
- **Constants**: `SCREAMING_SNAKE_CASE`
- **Private**: Prefix with `_` (e.g., `_scroll_timeout_id`)
- **GTK widgets**: `__gtype_name__ = 'AlpacaWidgetName'`
- **Type hints**: Encouraged (`def function(param: str) -> dict:`)
- **Logging**: `logger = logging.getLogger(__name__)`

### Translation (i18n)
- Use `_()` for all user-facing strings
- NEVER use f-strings inside `_()`: `_(f"Error: {msg}")` is WRONG
- Format after translation: `_("Hello {}").format(name)`

### GTK Patterns
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

### Threading
All GTK operations must run on main thread. Use `GLib.idle_add()` to return from background threads:
```python
GLib.idle_add(update_ui_function, arg1, arg2)
GLib.timeout_add(1000, callback_function)  # milliseconds
```

## File Structure
- `src/main.py` - Application entry, DBus, CLI args
- `src/window.py` - Main window
- `src/constants.py` - Constants
- `src/sql_manager.py` - SQLite database
- `src/widgets/` - Widget implementations (chat.py, message.py, blocks/, activities/, instances/, models/, tools/)

## Common Pitfalls
- Never log API keys
- Don't block main thread
- Don't hardcode paths - use `data_dir`, `config_dir`, `cache_dir`
- Use `IN_FLATPAK` constant and XDG directories

## Quick Reference
```bash
meson setup build && ninja -C build && ./build/src/alpaca
pylint src/
```
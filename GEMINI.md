# Nanopaca

Nanopaca is a GNOME desktop AI chat client forked from Alpaca, powered by NanoGPT. It allows users to chat with advanced AI models, search the web, generate images, and more, all within a native GTK4 interface.

## Project Overview

- **Language:** Python
- **UI Toolkit:** GTK4, Libadwaita
- **Build System:** Meson, Ninja
- **Package Manager:** Flatpak
- **Version:** 8.5.1

## Building and Running

### Flatpak (Recommended)

The primary distribution method is Flatpak. This ensures all dependencies (including specific Python libraries) are correctly installed.

**Build and Install:**
```bash
flatpak-builder --user --install --force-clean build-dir com.jeffser.Alpaca.yml
```

**Run:**
```bash
flatpak run com.jeffser.Alpaca
```

### Local Build (Meson)

For faster development iteration, you can build and run locally using Meson, provided you have the necessary system dependencies installed (GTK4, Libadwaita, Python dependencies listed in the manifest).

1.  **Setup:**
    ```bash
    meson setup build
    ```

2.  **Compile:**
    ```bash
    meson compile -C build
    ```

3.  **Run:**
    ```bash
    meson run -C build
    ```

    *Note: If `msgfmt` is missing, internationalization (i18n) modules might be disabled in `meson.build`.*

## Project Structure

- **`src/`**: Contains the Python source code.
    - **`main.py`**: The application entry point and `AlpacaApplication` class.
    - **`window.py`**: Logic for the main application window.
    - **`ui/`**: User Interface definitions written in Blueprint (`.blp`).
    - **`widgets/`**: Python classes corresponding to custom widgets.
- **`data/`**: Metadata files including GSettings schemas, desktop entries, and icons.
- **`po/`**: Internationalization (translation) files.
- **`com.jeffser.Alpaca.yml`**: Flatpak manifest defining the build environment and dependencies.

## Key Files

- **`src/main.py`**: Initializes the application, handles command-line arguments, and sets up the DBus service.
- **`src/alpaca.py.in`**: Template for the executable script; sets up paths and loads resources before calling `main`.
- **`meson.build`**: Root build configuration file.
- **`CONTRIBUTING.md`**: Guidelines for contributing to the project.

## Development Conventions

- **Code Style:** Python code should be clear and readable. Comments are generally not required unless the logic is complex.
- **UI Design:** UI is defined using Blueprint (`.blp`) files in `src/ui/`.
- **Tools:** GNOME Builder is the recommended IDE, but any editor works.
- **Testing:** There are currently no automated tests found in the repository. Testing is primarily manual.

## Dependencies

Key Python dependencies (managed via Flatpak manifest) include:
- `openai`
- `pillow`
- `opencv-python`
- `matplotlib`
- `numpy`

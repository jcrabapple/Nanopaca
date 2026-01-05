# tools.py

import gettext
from gi.repository import GObject, GLib, Gio, Gtk
from .. import activities, dialog, attachments, chat
from ...sql_manager import Instance as SQL, generate_uuid
import os, threading, requests, logging

_ = gettext.gettext
logger = logging.getLogger(__name__)


class Property:
    def __init__(
        self, name: str, description: str, var_type: str, required: bool = False
    ):
        self.name = name
        self.description = description
        self.var_type = var_type
        self.required = required


class Base(GObject.Object):
    display_name: str = ""
    icon_name: str = "wrench-wide-symbolic"

    name: str = ""
    description: str = ""
    properties: list = []

    runnable: bool = True
    required_libraries: list = []

    def get_metadata(self) -> dict:
        properties = {}
        required_properties = []
        for p in self.properties:
            properties[p.name] = {"type": p.var_type, "description": p.description}
            if p.required and p.name not in required_properties:
                required_properties.append(p.name)

        metadata = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required_properties,
                },
            },
        }

        return metadata


class NoTool(Base):
    display_name: str = _("No Tool")
    icon_name: str = "cross-large-symbolic"
    name: str = "no_tool"
    runnable: bool = False


class AutoTool(Base):
    display_name: str = _("Auto Detect Tool")
    name: str = "auto_tool"
    runnable: bool = False


class WebSearch(Base):
    display_name: str = _("Web Search")
    icon_name: str = "globe-symbolic"

    name: str = "web_search"
    description: str = "Search the web for current information using NanoGPT API"
    properties: list = [
        Property(
            name="query",
            description="The search query, be specific and use keywords",
            var_type="string",
            required=True,
        )
    ]

    def run(self, arguments, messages, bot_message) -> tuple:
        query = arguments.get("query", "").strip()
        if not query:
            return "Please provide a search query", "Error: No query provided"

        try:
            instance = bot_message.get_root().get_active_instance()
            if not instance or instance.instance_type != "nanogpt":
                return "Web search requires NanoGPT", "Error: Wrong instance type"

            result = instance.web_search(query)
            return None, result

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"Search failed: {str(e)}", f"Error: {str(e)}"


class YouTubeTranscript(Base):
    display_name: str = _("YouTube Transcript")
    icon_name: str = "play-symbolic"

    name: str = "youtube_transcript"
    description: str = "Get transcript from a YouTube video"
    properties: list = [
        Property(
            name="url",
            description="YouTube video URL",
            var_type="string",
            required=True,
        )
    ]

    def run(self, arguments, messages, bot_message) -> tuple:
        url = arguments.get("url", "").strip()
        if not url or ("youtube.com" not in url and "youtu.be" not in url):
            return "Please provide a valid YouTube URL", "Error: Invalid URL"

        try:
            instance = bot_message.get_root().get_active_instance()
            if not instance or instance.instance_type != "nanogpt":
                return (
                    "YouTube transcription requires NanoGPT",
                    "Error: Wrong instance type",
                )

            response = requests.post(
                "https://nano-gpt.com/api/youtube-transcribe",
                headers={"x-api-key": instance.properties.get("api")},
                json={"urls": [url]},
                timeout=30,
            )
            data = response.json()

            if data.get("transcripts") and len(data["transcripts"]) > 0:
                transcript = data["transcripts"][0]
                if transcript.get("success"):
                    cost = data.get("summary", {}).get("totalCost", 0)
                    return (
                        None,
                        f"**{transcript['title']}**\n\n{transcript['transcript']}\n\n*Cost: ${cost:.2f}*",
                    )
                else:
                    return (
                        f"Failed: {transcript.get('error')}",
                        f"Error: {transcript.get('error')}",
                    )
            return "No transcript available", "Error: No transcript"

        except Exception as e:
            logger.error(f"YouTube transcription failed: {e}")
            return f"Failed to get transcript: {str(e)}", f"Error: {str(e)}"


class WebScrape(Base):
    display_name: str = _("Web Scrape")
    icon_name: str = "document-save-symbolic"

    name: str = "web_scrape"
    description: str = "Extract content from a webpage"
    properties: list = [
        Property(
            name="url",
            description="Website URL to scrape",
            var_type="string",
            required=True,
        )
    ]

    def run(self, arguments, messages, bot_message) -> tuple:
        url = arguments.get("url", "").strip()
        if not url:
            return "Please provide a URL", "Error: No URL provided"

        try:
            instance = bot_message.get_root().get_active_instance()
            if not instance or instance.instance_type != "nanogpt":
                return "Web scraping requires NanoGPT", "Error: Wrong instance type"

            response = requests.post(
                "https://nano-gpt.com/api/scrape-urls",
                headers={"x-api-key": instance.properties.get("api")},
                json={"urls": [url]},
                timeout=30,
            )
            data = response.json()

            if data.get("results") and len(data["results"]) > 0:
                result = data["results"][0]
                if result.get("success"):
                    cost = data.get("summary", {}).get("totalCost", 0)
                    return (
                        None,
                        f"**{result['title']}**\n\n{result['markdown']}\n\n*Cost: ${cost:.4f}*",
                    )
                else:
                    return (
                        f"Failed: {result.get('error')}",
                        f"Error: {result.get('error')}",
                    )
            return "Failed to scrape", "Error: No results"

        except Exception as e:
            logger.error(f"Web scraping failed: {e}")
            return f"Scraping failed: {str(e)}", f"Error: {str(e)}"


class CheckBalance(Base):
    display_name: str = _("Check Balance")
    icon_name: str = "wallet-symbolic"

    name: str = "check_balance"
    description: str = "Check your NanoGPT account balance and usage"
    properties: list = []

    def run(self, arguments, messages, bot_message) -> tuple:
        try:
            instance = bot_message.get_root().get_active_instance()
            if not instance or instance.instance_type != "nanogpt":
                return "Balance check requires NanoGPT", "Error: Wrong instance type"

            balance_info = instance.check_balance()
            if "balance" in balance_info:
                balance = balance_info.get("balance", 0)
                return None, f"**NanoGPT Balance:** ${balance:.2f}"
            else:
                return (
                    "Failed to check balance",
                    f"Error: {balance_info.get('error', 'Unknown error')}",
                )

        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return f"Failed to check balance: {str(e)}", f"Error: {str(e)}"


class Terminal(Base):
    display_name: str = _("Terminal")
    icon_name: str = "terminal-symbolic"

    name: str = "run_command"
    description: str = "Request permission to run a command in a terminal returning its result, add sudo if root permission is needed"
    properties: list = [
        Property(
            name="command",
            description="The command to run and its parameters",
            var_type="string",
            required=True,
        ),
        Property(
            name="explanation",
            description="Explain in simple words what the command will do to the system, be clear and honest",
            var_type="string",
            required=True,
        ),
    ]

    required_libraries: list = ["gi.repository.Vte"]

    global_page = None
    current_commands = []

    def run(self, arguments, messages, bot_message) -> tuple:
        if not arguments.get("command"):
            return (
                "I could not figure out what you want me to run",
                "Error: No command was provided",
            )

        self.current_commands = [
            "clear",
            'echo -e "🦙 {}" | fold -s -w "$(tput cols)"'.format(
                arguments.get("explanation"), _("No explanation was provided")
            ),
            'read -e -i "{}" cmd'.format(arguments.get("command").replace('"', '\\"')),
            "clear",
            'eval "$cmd"',
        ]

        if not self.global_page or not self.global_page.get_root():
            self.global_page = activities.Terminal(
                language="auto",
                code_getter=lambda: ";".join(self.current_commands),
                close_callback=lambda: setattr(self, "waiting_terminal", False),
            )
            chat_element = bot_message.get_ancestor(chat.Chat)
            GLib.idle_add(
                activities.show_activity,
                self.global_page,
                bot_message.get_root(),
                not chat_element or not chat_element.chat_id,
            )

        self.waiting_terminal = True
        self.global_page.run()

        while self.waiting_terminal:
            continue

        return "I ran the command successfully!", "```\n{}\n```".format(
            self.global_page.get_text()
        )


class BackgroundRemover(Base):
    display_name: str = _("Background Remover")
    icon_name: str = "image-missing-symbolic"

    name: str = "background_remover"
    description: str = (
        "Requests the user to upload an image and automatically removes its background"
    )

    required_libraries: list = ["rembg"]

    def get_latest_image(self, messages, root) -> str:
        messages.reverse()
        for message in messages:
            if len(message.get("images", [])) > 0:
                return message.get("images")[0]
        self.image_requested = 0

        def on_attachment(file: Gio.File, remove_original: bool = False):
            if not file:
                self.image_requested = None
                return
            self.image_requested = attachments.extract_image(
                file.get_path(), root.settings.get_value("max-image-size").unpack()
            )

        file_filter = Gtk.FileFilter()
        file_filter.add_pixbuf_formats()
        dialog.simple_file(
            parent=root, file_filters=[file_filter], callback=on_attachment
        )

        while self.image_requested == 0:
            continue

        return self.image_requested

    def on_save(self, data: str, bot_message):
        if data:
            attachment = bot_message.add_attachment(
                file_id=generate_uuid(),
                name=_("Output"),
                attachment_type="image",
                content=data,
            )
            SQL.insert_or_update_attachment(bot_message, attachment)
            self.status = 1
        else:
            self.status = 2

    def on_close(self):
        self.status = 2

    def run(self, arguments, messages, bot_message) -> tuple:
        threading.Thread(
            target=bot_message.update_message,
            args=(_("Loading Image...") + "\n",),
            daemon=True,
        ).start()
        image_b64 = self.get_latest_image(messages, bot_message.get_root())
        if image_b64:
            self.status = 0  # 0 waiting, 1 finished, 2 canceled / empty image
            page = activities.BackgroundRemover(
                save_func=lambda data, bm=bot_message: self.on_save(data, bm),
                close_callback=self.on_close,
            )
            chat_element = bot_message.get_ancestor(chat.Chat)
            GLib.idle_add(
                activities.show_activity,
                page,
                bot_message.get_root(),
                not chat_element or not chat_element.chat_id,
            )
            page.load_image(image_b64)

            while self.status == 0:
                continue

            if self.status == 1:
                return "Background removed successfully!", "Successful"
            else:
                return "Sorry, an error occurred", "An error occurred"
        else:
            return (
                "Please provide an image and try again!",
                "Error: User didn't attach an image",
            )
        return "Sorry, an error occurred", "Error: Couldn't remove the background"


class ImageGeneration(Base):
    display_name: str = _("Image Generation")
    icon_name: str = "camera-photo-symbolic"

    name: str = "generate_image"
    description: str = "Generate an image from a text description using NanoGPT"
    properties: list = [
        Property(
            name="prompt",
            description="Description of the image to generate",
            var_type="string",
            required=True,
        ),
        Property(
            name="size",
            description="Image size: 1024x1024, 1024x1792, or 1792x1024",
            var_type="string",
            required=False,
        ),
    ]

    def run(self, arguments, messages, bot_message) -> tuple:
        prompt = arguments.get("prompt", "").strip()
        size = arguments.get("size", "1024x1024")

        if not prompt:
            return "Please provide an image description", "Error: No prompt provided"

        try:
            instance = bot_message.get_root().get_active_instance()
            if not instance or instance.instance_type != "nanogpt":
                return "Image generation requires NanoGPT", "Error: Wrong instance type"

            # Show loading indicator
            GLib.idle_add(
                bot_message.update_message,
                (_("Generating image...") + "\n"),
            )

            result = instance.generate_image(prompt, size=size)

            if result.get("success"):
                # Add image as attachment
                attachment = bot_message.add_attachment(
                    file_id=generate_uuid(),
                    name=_("Generated Image"),
                    attachment_type="image",
                    content=result["url"],
                )
                SQL.insert_or_update_attachment(bot_message, attachment)

                return (
                    None,
                    f"**Generated Image**\n\n{result.get('revised_prompt', prompt)}\n\n*Image generated successfully*",
                )
            else:
                return (
                    f"Failed: {result.get('error')}",
                    f"Error: {result.get('error')}",
                )

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return (
                f"Image generation failed: {str(e)}",
                f"Error: {str(e)}",
            )


# End of tools.py

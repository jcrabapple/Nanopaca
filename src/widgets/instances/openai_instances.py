# openai_instances.py

from gi.repository import Adw, GLib

import openai, requests, json, logging, threading, re
from pydantic import BaseModel

from .. import dialog, tools, chat
from ...sql_manager import generate_uuid, Instance as SQL
from ...constants import MAX_TOKENS_TITLE_GENERATION, TITLE_GENERATION_PROMPT_OPENAI

logger = logging.getLogger(__name__)


# Base instance, don't use directly
class BaseInstance:
    instance_id = None
    description = None
    limitations = ()

    default_properties = {
        "name": _("Instances"),
        "api": "",
        "max_tokens": 2048,
        "override_parameters": True,
        "temperature": 0.7,
        "seed": 0,
        "default_model": None,
        "title_model": None,
    }

    def __init__(self, instance_id: str, properties: dict):
        self.row = None
        self.instance_id = instance_id
        self.available_models = None
        self.properties = {}
        for key in self.default_properties:
            self.properties[key] = properties.get(key, self.default_properties.get(key))
        if "no-seed" in self.limitations and "seed" in self.properties:
            del self.properties["seed"]
        self.properties["url"] = self.instance_url

        self.client = openai.OpenAI(
            base_url=self.properties.get("url").strip(),
            api_key=self.properties.get("api"),
        )

    def stop(self):
        pass

    def start(self):
        pass

    def prepare_chat(self, bot_message):
        chat_element = bot_message.get_ancestor(chat.Chat)
        bot_message.block_container.show_generating_block()
        if chat_element and chat_element.chat_id:
            chat_element.row.spinner.set_visible(True)
            try:
                bot_message.get_root().global_footer.toggle_action_button(False)
            except:
                pass

            chat_element.busy = True
            chat_element.set_visible_child_name("content")

        messages = chat_element.convert_to_json()[
            : list(chat_element.container).index(bot_message)
        ]
        return chat_element, messages

    def generate_message(self, bot_message, model: str):
        chat, messages = self.prepare_chat(bot_message)

        if (
            chat.chat_id
            and [m.get("role") for m in messages].count("assistant") == 0
            and chat.get_name().startswith(_("New Chat"))
        ):
            threading.Thread(
                target=self.generate_chat_title,
                args=(
                    chat,
                    "\n".join(
                        [
                            c.get("text")
                            for c in messages[-1].get("content")
                            if c.get("type") == "text"
                        ]
                    ),
                    model,
                ),
                daemon=True,
            ).start()

        self.generate_response(bot_message, chat, messages, model)

    def use_tools(
        self, bot_message, model: str, available_tools: dict, generate_message: bool
    ):
        chat, messages = self.prepare_chat(bot_message)

        if (
            chat.chat_id
            and [m.get("role") for m in messages].count("assistant") == 0
            and chat.get_name().startswith(_("New Chat"))
        ):
            threading.Thread(
                target=self.generate_chat_title,
                args=(
                    chat,
                    "\n".join(
                        [
                            c.get("text")
                            for c in messages[-1].get("content")
                            if c.get("type") == "text"
                        ]
                    ),
                    model,
                ),
                daemon=True,
            ).start()

        message_response = ""
        try:
            completion = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=[v.get_metadata() for v in available_tools.values()],
            )
            if completion.choices[0] and completion.choices[0].message:
                if completion.choices[0].message.tool_calls:
                    for call in completion.choices[0].message.tool_calls:
                        if available_tools.get(call.function.name):
                            message_response, tool_response = available_tools.get(
                                call.function.name
                            ).run(call.function.arguments, messages, bot_message)
                            generate_message = generate_message and not bool(
                                message_response
                            )

                            attachment_content = []

                            if len(json.loads(call.function.arguments)) > 0:
                                attachment_content += [
                                    "## {}".format(_("Arguments")),
                                    "| {} | {} |".format(_("Argument"), _("Value")),
                                    "| --- | --- |",
                                ]
                                attachment_content += [
                                    "| {} | {} |".format(k, v)
                                    for k, v in json.loads(
                                        call.function.arguments
                                    ).items()
                                ]

                            attachment_content += [
                                "## {}".format(_("Result")),
                                tool_response,
                            ]

                            attachment = bot_message.add_attachment(
                                file_id=generate_uuid(),
                                name=available_tools.get(call.function.name).name,
                                attachment_type="tool",
                                content="\n".join(attachment_content),
                            )
                            SQL.insert_or_update_attachment(bot_message, attachment)
                        else:
                            tool_response = ""

                        arguments = json.loads(call.function.arguments)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.id,
                                "content": str(tool_response),
                            }
                        )

        except Exception as e:
            dialog.simple_error(
                parent=bot_message.get_root(),
                title=_("Tool Error"),
                body=_("An error occurred while running tool"),
                error_log=e,
            )
            logger.error(e)

        if generate_message:
            self.generate_response(bot_message, chat, messages, model)
        else:
            bot_message.block_container.set_content(str(message_response))
            bot_message.finish_generation("")

    def generate_response(self, bot_message, chat, messages: list, model: str):
        if "no-system-messages" in self.limitations:
            for i in range(len(messages)):
                if messages[i].get("role") == "system":
                    messages[i]["role"] = "user"

        if "text-only" in self.limitations:
            for i in range(len(messages)):
                for c in range(len(messages[i].get("content", []))):
                    if messages[i].get("content")[c].get("type") != "text":
                        del messages[i]["content"][c]
                    else:
                        messages[i]["content"] = (
                            messages[i].get("content")[c].get("text")
                        )

        params = {"model": model, "messages": messages, "stream": True}

        if self.properties.get("max_tokens", 0) > 0:
            if "use_max_completion_tokens" in self.limitations:
                params["max_completion_tokens"] = int(
                    self.properties.get("max_tokens", 0)
                )
            else:
                params["max_tokens"] = int(self.properties.get("max_tokens", 0))

        if self.properties.get("override_parameters"):
            params["temperature"] = self.properties.get("temperature", 0.7)
            if self.properties.get("seed", 0) != 0:
                params["seed"] = self.properties.get("seed")

        if chat.busy:
            try:
                bot_message.block_container.clear()
                response = self.client.chat.completions.create(**params)
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            bot_message.update_message(delta.content)
                    if not chat.busy:
                        break
            except Exception as e:
                dialog.simple_error(
                    parent=bot_message.get_root(),
                    title=_("Instance Error"),
                    body=_("Message generation failed"),
                    error_log=e,
                )
                logger.error(e)
                if self.row:
                    self.row.get_parent().unselect_all()
        bot_message.finish_generation()

    def generate_chat_title(self, chat, prompt: str, fallback_model: str):
        class ChatTitle(BaseModel):  # Pydantic
            title: str
            emoji: str = ""

        messages = [
            {
                "role": "user"
                if "no-system-messages" in self.limitations
                else "system",
                "content": TITLE_GENERATION_PROMPT_OPENAI,
            },
            {
                "role": "user",
                "content": "Generate a title for this prompt:\n{}".format(prompt),
            },
        ]
        model = self.get_title_model()
        params = {
            "temperature": 0.2,
            "model": model if model else fallback_model,
            "messages": messages,
            "max_tokens": MAX_TOKENS_TITLE_GENERATION,
        }
        new_chat_title = chat.get_name()

        try:
            completion = self.client.chat.completions.parse(
                **params, response_format=ChatTitle
            )
            response = completion.choices[0].message
            if response.parsed:
                emoji = response.parsed.emoji if len(response.parsed.emoji) == 1 else ""
                new_chat_title = "{} {}".format(emoji, response.parsed.title)
        except Exception as e:
            try:
                response = self.client.chat.completions.create(**params)
                new_chat_title = str(response.choices[0].message.content)
            except Exception as e:
                logger.error(e)

        new_chat_title = re.sub(r"<think>.*?</think>", "", new_chat_title).strip()

        if len(new_chat_title) > 30:
            new_chat_title = new_chat_title[:30].strip() + "..."

        chat.row.edit(new_name=new_chat_title, is_template=chat.is_template)

    def get_default_model(self):
        local_models = self.get_local_models()
        if len(local_models) > 0:
            if not self.properties.get("default_model") or not self.properties.get(
                "default_model"
            ) in [m.get("name") for m in local_models]:
                self.properties["default_model"] = local_models[0].get("name")
            return self.properties.get("default_model")

    def get_title_model(self):
        local_models = self.get_local_models()
        if len(local_models) > 0:
            if self.properties.get("title_model") and not self.properties.get(
                "title_model"
            ) in [m.get("name") for m in local_models]:
                self.properties["title_model"] = local_models[0].get("name")
            return self.properties.get("title_model")

    def get_available_models(self) -> dict:
        try:
            if not self.available_models or len(self.available_models) == 0:
                self.available_models = {}
                for m in self.client.models.list():
                    if all(
                        s not in m.id.lower()
                        for s in [
                            "embedding",
                            "davinci",
                            "dall",
                            "tts",
                            "whisper",
                            "image",
                        ]
                    ):
                        self.available_models[m.id] = {}
            return self.available_models
        except Exception as e:
            dialog.simple_error(
                parent=self.row.get_root() if self.row else None,
                title=_("Instance Error"),
                body=_("Could not retrieve added models"),
                error_log=e,
            )
            logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()
            return {}

    def pull_model(self, model):
        SQL.append_online_instance_model_list(self.instance_id, model.get_name())
        GLib.timeout_add(5000, lambda: model.update_progressbar(-1) and False)

    def get_local_models(self) -> list:
        local_models = []
        for model in SQL.get_online_instance_model_list(self.instance_id):
            local_models.append({"name": model})
        return local_models

    def delete_model(self, model_name: str) -> bool:
        SQL.remove_online_instance_model_list(self.instance_id, model_name)
        return True

    def get_model_info(self, model_name: str) -> dict:
        return {}


class NanoGPT(BaseInstance):
    instance_type = "nanogpt"
    instance_type_display = "NanoGPT"
    instance_url = "https://nano-gpt.com/api/v1"

    default_properties = {
        "name": "NanoGPT",
        "api": "",
        "max_tokens": 4096,
        "override_parameters": True,
        "temperature": 0.7,
        "seed": 0,
        "default_model": None,
        "title_model": None,
        "web_search_depth": "standard",
        "auto_youtube_transcripts": True,
        "context_memory_enabled": False,
        "context_memory_days": 30,
        "system_prompt": "",
    }

    def get_available_models(self) -> dict:
        try:
            if not self.available_models or len(self.available_models) == 0:
                self.available_models = {}
                response = requests.get(
                    f"{self.instance_url}/models",
                    params={"detailed": "true"},
                    headers={"Authorization": f"Bearer {self.properties.get('api')}"},
                )
                data = response.json()

                for model in data.get("data", []):
                    model_data = {
                        "name": model.get("name", model["id"]),
                        "description": model.get("description", ""),
                        "context_length": model.get("context_length"),
                        "pricing": model.get("pricing", {}),
                        "capabilities": model.get("capabilities", {}),
                    }

                    # Mark image-capable models
                    model_id_lower = model["id"].lower()
                    if (
                        "vision" in model_id_lower
                        or "gpt-4o" in model_id_lower
                        or "claude-3" in model_id_lower
                        or "gemini" in model_id_lower
                    ):
                        model_data["capabilities"]["vision"] = True

                    self.available_models[model["id"]] = model_data

            return self.available_models
        except Exception as e:
            logger.error(f"Failed to fetch NanoGPT models: {e}")
            return {}

    def get_subscription_models(self) -> dict:
        try:
            response = requests.get(
                "https://nano-gpt.com/api/subscription/v1/models",
                params={"detailed": "true"},
                headers={"Authorization": f"Bearer {self.properties.get('api')}"},
            )
            data = response.json()

            subscription_models = {}
            for model in data.get("data", []):
                subscription_models[model["id"]] = {
                    "name": model.get("name", model["id"]),
                    "description": model.get("description", ""),
                    "subscription_included": True,
                }
            return subscription_models
        except Exception as e:
            logger.error(f"Failed to fetch subscription models: {e}")
            return {}

    def web_search(self, query: str) -> str:
        depth = self.properties.get("web_search_depth", "standard")

        try:
            response = requests.post(
                "https://nano-gpt.com/api/web",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.properties.get("api"),
                },
                json={"query": query, "depth": depth, "outputType": "sourcedAnswer"},
            )
            result = response.json()

            if "data" in result and "answer" in result["data"]:
                answer = result["data"]["answer"]
                sources = result["data"].get("sources", [])

                formatted = f"{answer}\n\n**Sources:**\n"
                for source in sources:
                    formatted += f"- [{source['name']}]({source['url']})\n"

                cost = result.get("metadata", {}).get("cost", 0)
                formatted += f"\n*Search cost: ${cost:.4f}*"

                return formatted
            return "No results found"
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"Error: {str(e)}"

    def check_balance(self) -> dict:
        try:
            response = requests.post(
                f"{self.instance_url}/check-balance",
                headers={"x-api-key": self.properties.get("api")},
            )
            return response.json()
        except:
            return {"balance": 0, "error": "Failed to fetch balance"}

    def generate_response(self, bot_message, chat, messages: list, model: str):
        params = {"model": model, "messages": messages, "stream": True}

        # Auto YouTube transcripts
        if self.properties.get("auto_youtube_transcripts", True):
            params["youtube_transcripts"] = True

        # Context memory
        if self.properties.get("context_memory_enabled", False):
            memory_days = self.properties.get("context_memory_days", 30)
            params["model"] = f"{model}:memory-{memory_days}"

        # System prompt
        if self.properties.get("system_prompt"):
            messages.insert(
                0, {"role": "system", "content": self.properties.get("system_prompt")}
            )

        super().generate_response(bot_message, chat, messages, model)

    def generate_image(
        self,
        prompt: str,
        model: str = "dall-e-3",
        size: str = "1024x1024",
        quality: str = "standard",
    ) -> dict:
        try:
            response = self.client.images.generate(
                model=model, prompt=prompt, size=size, quality=quality, n=1
            )
            return {
                "success": True,
                "url": response.data[0].url,
                "revised_prompt": getattr(response.data[0], "revised_prompt", prompt),
            }
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {"success": False, "error": str(e)}

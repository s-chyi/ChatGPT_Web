import base64
import json
import requests
import openai

import interpreter


class ChatGPT:
    def __init__(self, model_config, init_system=None):
        """初始化ChatGPT的配置、訊息的queue以及初始系統訊息。

        Args:
            model_config (dict): 模型相關配置的字典。
            queue (Queue): 用於存儲和獲取回答的queue。
            init_system (dict, optional): 初始化時的系統訊息。如果為None，則使用預設值。
        """
        if init_system is None:
            init_system = {
                "role": "system",
                "content": "你是一个人工智能助手，帮助人們查找信息。"
            }
        self.messages = [init_system]
        self.model_config = model_config
        self.init_client()

    def init_client(self):
        """初始化基於Azure的openai客戶端和相關配置。"""
        openai.api_type = "azure"
        openai.api_base = self.model_config["endpoint"]
        openai.api_version = self.model_config["api-version"]
        openai.api_key = self.model_config["key"]

        deployment = self.model_config["deployment"]
        interpreter.model = f"azure/{deployment}"
        interpreter.api_base = self.model_config["endpoint"]
        interpreter.api_key = self.model_config["key"]
        interpreter.api_version = self.model_config["api-version"]
        interpreter.context_window = 128000
        interpreter.auto_run = True
        interpreter.system_message += """\n
        If the user does not specify the programming language to use, Python will be used preferentially. 
        \nOutput message with Chinese Traditional.
        \nIf the user provides a txt file, read it with UTF-8 encoding.
        \nIf there is a file output, return the full path end of the message."""
        

    def get_response(self, question, max_tokens, image_path=None, system_message=""):
        """根據提問得到GPT的回答。

        Args:
            question (str): 用戶的提問。
            max_tokens (int): 最大 token 數。
            image_path (str, optional): 圖片的路徑，如果有的話。
            system_message (str): 需要傳遞給模型的系統訊息。
        """
        if system_message:
            self.messages[0] = {"role": "system", "content": system_message}
        if self.model_config["model_name"] == "GPT4 Vision":
            return self._handle_vision_model(question, max_tokens, image_path)
        elif self.model_config["model_name"] == "GPT4 Code Interpreter":
            return self._handle_code_interpreter_model(question)
        else:
            return self._handle_default_model(question, max_tokens)

    def _handle_vision_model(self, question, max_tokens, image_path):
        """專門處理有視覺輸入的GPT模型。

        Args:
            question (str): 用戶的提問。
            max_tokens (int): 最大 token 數。
            image_path (str, optional): 圖片的路徑，如果有的話。
        """
        headers = {
            "Content-Type": "application/json",
            "api-key": self.model_config["key"]
        }
        endpoint = self.model_config["endpoint"]
        deployment = self.model_config["deployment"]
        api_version = self.model_config["api-version"]
        url = f"{endpoint}openai/deployments/{deployment}/chat/completions?api-version={api_version}"

        if image_path:
            base64_image = self._get_base64_from_image(image_path)
            content_data = [
                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"},
                {"type": "text", "text": question}
            ]
        else:
            content_data = [{"type": "text", "text": question}]

        body = self.messages + [{"role": "user", "content": content_data}]
        data = {"messages": body, "max_tokens": max_tokens}
        self.messages = body
        response = requests.post(url, headers=headers, data=json.dumps(data))
        answer = response.json()["choices"][0]["message"]["content"]
        self.messages.append({"role": "assistant", "content": answer})
        yield answer

    def _handle_code_interpreter_model(self, question):
        """專門處理代碼解釋器GPT模型的方法。

        Args:
            question  (str): 用戶的提問。
        """
        active_block_type = ""
        response = ""
        for chunk in interpreter.chat(question, stream=True, display=False):
            if "message" in chunk:
                if active_block_type != "message":
                    active_block_type = "message"
                response += chunk["message"]
                yield response

            if "language" in chunk:
                language = chunk["language"]
            if "code" in chunk:
                if active_block_type != "code":
                    active_block_type = "code"
                    response += f"\n```{language}\n"
                response += chunk["code"]
                yield response

            if "executing" in chunk:
                response += "\n```\n\n```text\n"
                yield response
            if "output" in chunk:
                if chunk["output"] != "KeyboardInterrupt":
                    response += chunk["output"] + "\n"
                    yield response
            if "end_of_execution" in chunk:
                response = response.strip()
                response += "\n```\n"
                yield response

    def _handle_default_model(self, question, max_tokens):
        """專門處理標準GPT模型流式輸出。

        Args:
            question (str): 用戶的提問。
            max_tokens (int): 最大 token 數。
        """
        self.messages.append({"role": "user", "content": question})
        response_stream = openai.ChatCompletion.create(
            engine=self.model_config["deployment"],
            messages=self.messages,
            max_tokens=max_tokens,
            stream=True
        )
        answer = ""
        for event in response_stream:
            if event['choices'] and "content" in event["choices"][0].delta:
                content = event["choices"][0]["delta"]["content"]
                answer += content
                yield answer
            if event["choices"][0]["finish_reason"] == "stop":
                yield answer
        self.messages.append({"role": "assistant", "content": answer})

    def _format_code_chunk(self, chunk):
        """格式化代碼塊以便於閱讀。

        Args:
            chunk (dict): 從interpreter返回的代碼塊。
        """
        if chunk in ["start_of_code", "executing"]:
            return "\n\n```python\n"
        elif chunk in ["end_of_code", "end_of_execution"]:
            return "\n```\n\n"
        
    def _get_base64_from_image(self, image_path):
        """將圖片轉換為base64編碼。

        Args:
            image_path (str): 圖片的檔案路徑。

        Returns:
            str: 圖片的base64編碼字符串。
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
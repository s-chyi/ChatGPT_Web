import json
import time

import gradio as gr

from call_gpt import ChatGPT



class WebBot:
    def __init__(self, config_path='model_config.json', web_name='Nick GPT', server_port=None):
        """初始化WebBot的配置並加載模型。

        Args:
            config_path (str): 模型配置檔案的路徑。
            web_name (str): 網站的名稱。
            server_port (int): 伺服器的端口號碼。
        """
        self.config_path = config_path
        self.web_name = web_name
        self.server_port = server_port

        with open(self.config_path, 'r') as f:
            model_list = json.load(f)

        self.init_system = {
            "role": "system",
            "content": (
                "你是一個人工智能助理，幫助人們查找資訊，以繁體中文回覆。"
                "你是ChatGPT，一個由 OpenAI 訓練的大型語言模型，基於 GPT-4 架構。"
                "知識截止時間：2023-04。請根據用戶的問題一步步思考後謹慎回答，"
                "並再次確認答案是否正確。"
            )
        }
        
        self.chatgpt = {
            config["model_name"]: ChatGPT(config, self.init_system)
            for config in model_list
        }
        
        self.chat_history = {
            config["model_name"]: [] for config in model_list
        }
        
        self.model_deployment_list = [
            model["model_name"] for model in model_list
        ]

    def update_chat_history(self, model_select, chatbot):
        """根據選擇的模型更新chatbot的歷史紀錄。

        Args:
            model_select (str): 選擇的模型名稱。
            chatbot (bot): 選擇的chatbot歷史紀錄
        """
        chatbot = self.chat_history[model_select]
        return chatbot
    
    def reset_input(self):
        """送出訊息後清除選擇框。"""
        time.sleep(1)
        return gr.update(value=None)


    def slow_echo(self, message, history, model, max_tokens, system_message, image=None, file=None):
        """處理接收到的訊息並透過GPT模型生成回答，然後返回一個生成回答的生成器。

        Args:
            message (str): 用戶發送的訊息。
            history (list): 當前對話的歷史列表。
            model (str): 選擇的GPT模型名稱。
            max_tokens (int): 生成回應的最大token數。
            system_message (str): 系統訊息。
            image (str, optional): 圖片路徑，如果有的話。
            file (str, optional): 檔案路徑，如果有的話。
        Returns:
            generator: 生成回應的生成器。
        """
        history = self.chat_history[model]
        question = ""
        question += message
        question += file if file else ""
        responses = self.chatgpt[model].get_response(question, max_tokens, image, system_message=system_message)
        response = ""
        for response in responses:
            yield response

        history.append((message, response))
        self.chat_history[model] = history
        return history

    def run_web(self):
        """啟動Gradio網頁介面。"""
        with gr.Blocks() as demo:
            gr.HTML(f"<h1 align='center'>{self.web_name}</h1>")
            with gr.Row():
                with gr.Row(1):
                    with gr.Column(scale=1):
                        model_select = gr.Dropdown(
                            label="Choose a model", 
                            choices=self.model_deployment_list, 
                            value=self.model_deployment_list[0]
                        )
                    with gr.Column(scale=1):
                        number_input = gr.Number(
                            label="Max tokens", 
                            minimum=100, 
                            maximum=4096, 
                            step=1, 
                            value=800
                        )
                    with gr.Column(scale=1):
                        system_message = gr.Textbox(
                            label="System Message", 
                            placeholder="System message...", 
                            lines=6, 
                            max_lines=6, 
                            value=self.init_system["content"]
                        )
                with gr.Row(1):
                    image_input = gr.Image(
                        show_label=False,
                        type="filepath"
                    ) 
                    file_input = gr.File(
                        show_label=False,
                        type="filepath"
                    )
            bot = gr.ChatInterface(
                fn=self.slow_echo,
                additional_inputs=[model_select, number_input, system_message, image_input, file_input]
            ).queue()
            model_select.change(
                fn=self.update_chat_history, 
                inputs=[model_select, bot.chatbot], 
                outputs=[bot.chatbot])
            bot.submit_btn.click(self.reset_input, [], [file_input])
            bot.textbox.submit(self.reset_input, [], [file_input])
            bot.submit_btn.click(self.reset_input, [], [image_input])
            bot.textbox.submit(self.reset_input, [], [image_input])
            if self.server_port:
                demo.launch(inbrowser=True, server_port=self.server_port)
            else:
                demo.launch(inbrowser=True)

if __name__ == '__main__':
    web = WebBot()
    web.run_web()
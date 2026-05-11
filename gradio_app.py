#!/usr/bin/env python3
"""SP-Mind Gradio Web Interface."""

import gradio as gr
import os
import uuid
from pathlib import Path

from spmind.agent import SPMindAgent


class SPMindGradioApp:
    def __init__(self):
        self.agent: SPMindAgent | None = None
        self.model = os.getenv("SPMIND_MODEL", "claude-sonnet-4-20250514")
        self._init_agent()

    def _init_agent(self):
        """Initialize the SP-Mind agent."""
        try:
            self.agent = SPMindAgent(
                path="./data",
                model=self.model,
                permission_mode="bypassPermissions",
            )
        except Exception as e:
            print(f"Agent initialization failed: {e}")
            self.agent = None

    def reset_conversation(self):
        """Reset the agent session and clear chat history."""
        if self.agent:
            self.agent.reset_session()
        return [], ""

    def chat_response(self, message: str, history: list):
        """Process user message and return agent response."""
        if not self.agent:
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": "Agent not initialized. Check server logs."})
            return history, ""

        if not message.strip():
            return history, ""

        history.append({"role": "user", "content": message})

        try:
            result = self.agent.go(message, verbose=False)
            history.append({"role": "assistant", "content": result})
        except Exception as e:
            history.append({"role": "assistant", "content": f"Error: {e}"})

        return history, ""

    def create_interface(self):
        """Create the Gradio interface."""

        custom_css = """
        body {
            background: radial-gradient(circle at top, #f5f7fb 0%, #e6ebf4 45%, #dfe3ec 100%) !important;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: #1d1d1f;
        }
        .gradio-container {
            max-width: 960px !important;
            margin: 2rem auto !important;
        }
        .app-surface {
            padding: 32px 28px;
            border-radius: 28px;
            background: rgba(255, 255, 255, 0.88);
            backdrop-filter: saturate(180%) blur(30px);
            box-shadow:
                0 30px 60px rgba(15, 23, 42, 0.08),
                0 16px 32px rgba(15, 23, 42, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.6);
            gap: 24px;
        }
        .app-header {
            text-align: center;
            padding-bottom: 12px;
        }
        .app-header h1 {
            font-size: 32px;
            font-weight: 650;
            letter-spacing: -0.015em;
            margin: 0;
            color: #111827;
        }
        .app-header p {
            font-size: 16px;
            color: #6e6e73;
            margin: 8px 0 0 0;
            letter-spacing: 0.01em;
        }
        .toolbar {
            display: flex;
            gap: 12px;
            align-items: center;
            justify-content: flex-end;
            padding: 12px 20px;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(17, 24, 39, 0.06);
        }
        .toolbar .gradio-button {
            border-radius: 14px !important;
            font-weight: 500 !important;
            border: none !important;
            background: rgba(142, 142, 147, 0.16) !important;
            color: #1d1d1f !important;
        }
        .chat-card {
            border-radius: 24px;
            padding: 24px;
            background: rgba(250, 250, 252, 0.96);
            border: 1px solid rgba(17, 24, 39, 0.05);
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
            gap: 16px;
        }
        .chat-card .gradio-chatbot {
            border-radius: 18px !important;
            border: 1px solid rgba(17, 24, 39, 0.08) !important;
            background: rgba(255, 255, 255, 0.92) !important;
        }
        .input-row {
            display: flex;
            gap: 12px;
            align-items: stretch;
        }
        .input-row .gradio-textbox {
            flex: 1;
            border-radius: 16px !important;
            border: 1px solid rgba(17, 24, 39, 0.08) !important;
            background: rgba(255, 255, 255, 0.92) !important;
        }
        .input-row .gradio-button {
            width: 120px;
            border-radius: 16px !important;
            font-weight: 600 !important;
            border: none !important;
            background: linear-gradient(135deg, #0a84ff, #147efb) !important;
            color: #fff !important;
            box-shadow: 0 14px 28px rgba(20, 126, 251, 0.28);
        }
        """

        with gr.Blocks(title="SP-Mind", theme=gr.themes.Soft(), css=custom_css) as interface:
            with gr.Column(elem_classes=["app-surface"]):
                gr.HTML(
                    """
                    <div class="app-header">
                        <h1>SP-Mind</h1>
                        <p>LLM-based reasoning agent for spatial proteomics analysis</p>
                    </div>
                    """
                )

                with gr.Row(elem_classes=["toolbar"]):
                    reset_btn = gr.Button("New Chat", variant="secondary")

                with gr.Column(elem_classes=["chat-card"]):
                    chatbot = gr.Chatbot(
                        label="",
                        height=480,
                        show_copy_button=True,
                        type="messages",
                        show_label=False,
                    )

                    with gr.Row(elem_classes=["input-row"]):
                        msg = gr.Textbox(
                            label="",
                            placeholder="Describe your spatial proteomics task...",
                            lines=1,
                            show_label=False,
                        )
                        send_btn = gr.Button("Send", variant="primary")

                gr.Examples(
                    examples=[
                        ["Stitch and register the tile images in ./data/raw_tiles/"],
                        ["Run cell segmentation on the stitched image at ./data/stitched.ome.tif"],
                        ["Quantify marker expression using the masks in ./data/masks/"],
                        ["Cluster the cells in ./data/quantification.csv and annotate cell types"],
                    ],
                    inputs=msg,
                    label="",
                )

            reset_btn.click(self.reset_conversation, outputs=[chatbot, msg])
            msg.submit(self.chat_response, inputs=[msg, chatbot], outputs=[chatbot, msg])
            send_btn.click(self.chat_response, inputs=[msg, chatbot], outputs=[chatbot, msg])

        return interface


def main():
    app = SPMindGradioApp()
    interface = app.create_interface()
    interface.launch(
        server_name="0.0.0.0",
        share=True,
        show_error=True,
    )


if __name__ == "__main__":
    main()

"""
Flask backend for the MediInform chatbot.
Talks to the Gemini API and enforces a single, fixed topic scope defined in
chatbot_config.py.
"""
import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai
from google.genai import types

from chatbot_config import SYSTEM_PROMPT, BOT_NAME

load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

_client = None


def get_client():
    """Create the Gemini client lazily so a missing key doesn't crash startup."""
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your .env file locally, "
                "or to the environment variables of your hosting platform."
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


@app.route("/")
def home():
    return render_template("index.html", bot_name=BOT_NAME)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify({"reply": "Please type a message before sending."}), 400

    try:
        client = get_client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.6,
                max_output_tokens=800,
            ),
        )
        reply_text = (response.text or "").strip() or (
            "Sorry, I could not generate a response. Please try again."
        )
        return jsonify({"reply": reply_text})

    except RuntimeError as e:
        return jsonify({"reply": f"Configuration error: {e}"}), 500
    except Exception as e:
        # Never leak raw exception details to the client in production,
        # but keep a short, safe message + log the real error server-side.
        app.logger.error("Gemini API call failed: %s", e)
        return jsonify(
            {"reply": "Something went wrong while contacting the AI service. "
                      "Please try again in a moment."}
        ), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Local development only. In production (e.g. Render) gunicorn runs the app,
    # see the Procfile / start command instead of this block.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

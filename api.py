from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import yagmail
from dotenv import load_dotenv
import traceback
import logging

# Load .env lokaal (Render injecteert env vars automatisch)
load_dotenv()

app = Flask(__name__)
CORS(app)

# Logging instellen
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

ZOHO_USER = os.getenv("ZOHO_USER")
ZOHO_PASS = os.getenv("ZOHO_APP_PASSWORD")
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

@app.route("/ping", methods=["GET"])
def ping():
    """Simpele check om te zien of API draait"""
    return jsonify({"status": "ok", "message": "TK Sports Mailer API draait"}), 200


@app.route("/send-confirmation", methods=["POST"])
def send_confirmation():
    data = request.get_json() or {}
    email = data.get("email")
    name = data.get("name", "sportieveling")

    if not email:
        return jsonify({"success": False, "error": "Email ontbreekt"}), 400

    logging.info(f"Ontvangen verzoek om mail te sturen naar: {email}")

    try:
        # SMTP setup
        yag = yagmail.SMTP(
            user=ZOHO_USER,
            password=ZOHO_PASS,
            host='smtp.zoho.eu',
            port=465,
            smtp_ssl=True
        )

        subject = "Bevestiging van je inschrijving"
        html = f"""
        <h2>Hoi {name}!</h2>
        <p>Bedankt voor je inschrijving bij <b>TK Sports Academy</b> 🎉</p>
        <p>We hebben je formulier goed ontvangen en nemen snel contact met je op.</p>
        <br/>
        <p>Sportieve groeten,<br/>Het TK Sports Academy Team</p>
        """

        yag.send(to=email, subject=subject, contents=html)
        logging.info(f"✅ Mail succesvol verstuurd naar {email}")
        return jsonify({"success": True, "message": f"Mail verzonden naar {email}"}), 200

    except Exception as e:
        error_msg = f"❌ Fout bij mailverzending: {e}"
        logging.error(error_msg)
        if DEBUG_MODE:
            traceback.print_exc()
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc() if DEBUG_MODE else None}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=DEBUG_MODE)

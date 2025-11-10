from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import logging
import traceback

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)

# ───────────────────────────────────────────────
# API Keys via environment variables
# ───────────────────────────────────────────────
MJ_APIKEY_PUBLIC = os.getenv("MJ_APIKEY_PUBLIC")
MJ_APIKEY_PRIVATE = os.getenv("MJ_APIKEY_PRIVATE")

if not MJ_APIKEY_PUBLIC or not MJ_APIKEY_PRIVATE:
    logging.warning("⚠️ Mailjet API keys are not set in environment variables.")

# ───────────────────────────────────────────────
# Helper: HTML e-mailtemplate
# ───────────────────────────────────────────────
def build_html_email(name: str, parent_info: dict, participants: list):
    participant_summary = ""
    for i, p in enumerate(participants, 1):
        participant_summary += f"""
        <p style="margin:6px 0;">
            <b>Participant {i}:</b> {p.get('firstname','')} {p.get('lastname','')}  
            ({p.get('position','')} – {p.get('club','')}, Shirt: {p.get('tshirt','')})
        </p>
        """

    html = f"""
    <div style="font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background:#ffffff; color:#333; padding:30px; max-width:700px; margin:auto; border-radius:10px; border:1px solid #eee;">
        <div style="text-align:center; margin-bottom:25px;">
            <img src="https://tksportsacademy.nl/assets/imgs/logo-blac.png" alt="TK Sports Academy" style="width:120px; margin-bottom:10px;">
        </div>
        <h2 style="color:#ff6b00;">Hi {name.split()[0]},</h2>
        <p style="font-size:1.05rem; line-height:1.6;">
            Thank you for signing up for <b>TK Sports Academy</b>! We're thrilled to have you join us.  
            Your registration has been received successfully.
        </p>
        <p style="font-size:1.05rem; line-height:1.6;">
            To secure your place in the camp, we kindly ask that you complete your <b>deposit payment</b> as soon as possible.
            Your spot will only be <b>guaranteed after the deposit has been received</b>.  
            We will send you a separate email shortly with the payment details.
        </p>
        <p style="font-size:1.05rem; line-height:1.6;">
            Meanwhile, please review your registration details below.  
            If you notice any incorrect information, just reply to this email and let us know.
        </p>
        <hr style="margin:30px 0; border:none; border-top:1px solid #eee;">
        <h3 style="color:#ff6b00;">Registration Summary</h3>
        <div style="margin-top:10px; font-size:0.95rem;">
            <p><b>Parent/Guardian:</b> {parent_info.get('firstname','')} {parent_info.get('lastname','')}</p>
            <p><b>Email:</b> {parent_info.get('email','')}</p>
            <p><b>Phone:</b> {parent_info.get('phone','')}</p>
            <p><b>Address:</b> {parent_info.get('address','')}, {parent_info.get('postcode','')} {parent_info.get('city','')}, {parent_info.get('country','')}</p>
        </div>
        <div style="margin-top:15px;">{participant_summary}</div>
        <hr style="margin:30px 0; border:none; border-top:1px solid #eee;">
        <p style="font-size:1.05rem; line-height:1.6;">
            We’re looking forward to seeing you on the ice soon!  
            If you have any questions, don’t hesitate to reach out to us at 
            <a href="mailto:info@tksportsacademy.nl" style="color:#ff6b00; text-decoration:none;">info@tksportsacademy.nl</a>.
        </p>
        <p style="margin-top:25px; font-style:italic; color:#777;">Kind regards,<br><b>The TK Sports Academy Team</b></p>
        <hr style="margin:30px 0; border:none; border-top:1px solid #eee;">
        <div style="text-align:center; font-size:0.85rem; color:#aaa;">
            <p>© 2025 TK Sports Academy — Eindhoven, The Netherlands</p>
            <p>Powered by <a href="https://spectux.com" style="color:#ff6b00; text-decoration:none; font-weight:bold;">Spectux.com</a></p>
        </div>
    </div>
    """
    return html


# ───────────────────────────────────────────────
# Helper: Mail versturen via Mailjet
# ───────────────────────────────────────────────
def send_mailjet_confirmation(email: str, name: str, parent_info: dict, participants: list):
    html = build_html_email(name, parent_info, participants)
    url = "https://api.mailjet.com/v3.1/send"

    data = {
        "Messages": [
            {
                "From": {"Email": "info@tksportsacademy.nl", "Name": "TK Sports Academy"},
                "To": [{"Email": email, "Name": name}],
                "Subject": f"Registration Confirmation - TK Sports Academy",
                "HTMLPart": html
            }
        ]
    }

    r = requests.post(
        url,
        auth=(MJ_APIKEY_PUBLIC, MJ_APIKEY_PRIVATE),
        headers={"Content-Type": "application/json"},
        data=json.dumps(data),
        timeout=15
    )

    if r.status_code != 200:
        raise Exception(f"Mailjet error {r.status_code}: {r.text}")

    result = r.json()
    if result.get("Messages", [{}])[0].get("Status") != "success":
        raise Exception(f"Mailjet response error: {result}")

    return result


# ───────────────────────────────────────────────
# ROUTE
# ───────────────────────────────────────────────
@app.route("/send-confirmation", methods=["POST"])
def send_confirmation():
    try:
        data = request.get_json() or {}
        email = data.get("email")
        name = data.get("name", "Athlete")

        if not email:
            return jsonify({"success": False, "error": "Email missing"}), 400

        parent_info = data.get("parent_info", {})
        participants = data.get("participants", [])

        result = send_mailjet_confirmation(email, name, parent_info, participants)
        return jsonify({"success": True, "result": result}), 200

    except Exception as e:
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

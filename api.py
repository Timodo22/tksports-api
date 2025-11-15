from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import logging
import traceback
import datetime

# Google Sheets API
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)

# ───────────────────────────────────────────────
# Mailjet keys
# ───────────────────────────────────────────────
MJ_APIKEY_PUBLIC = os.getenv("MJ_APIKEY_PUBLIC")
MJ_APIKEY_PRIVATE = os.getenv("MJ_APIKEY_PRIVATE")

if not MJ_APIKEY_PUBLIC or not MJ_APIKEY_PRIVATE:
    logging.warning("⚠️ Mailjet API keys are NOT set!")


# ───────────────────────────────────────────────
# Google Sheets settings
# ───────────────────────────────────────────────
SPREADSHEET_ID = "1owN41X9KcQL_Ipl6wxzFe-M6Xsbe5Y3glfoUrZN6YPY"
SECRET_PATH = "/etc/secrets/google-credentials.json"   # Secret File in Render


def append_to_google_sheet(parent_info, participants):
    logging.info("🟧 append_to_google_sheet() aangeroepen")

    try:
        # Check if secret exists
        if not os.path.exists(SECRET_PATH):
            logging.error("❌ Secret file NIET gevonden op: " + SECRET_PATH)
            return

        logging.info("🔐 Secret file gevonden!")

        # Load JSON key
        with open(SECRET_PATH, "r") as f:
            key_data = json.load(f)

        logging.info(f"🔑 Service account e-mail: {key_data.get('client_email')}")

        # Credentials
        credentials = service_account.Credentials.from_service_account_info(
            key_data,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        logging.info("✅ Google credentials geladen")

        # Sheets API client
        service = build("sheets", "v4", credentials=credentials)
        logging.info("📄 Sheets service aangemaakt")

        # Prepare row
        row = [
            datetime.datetime.utcnow().isoformat(),

            parent_info.get("email", ""),
            parent_info.get("firstname", ""),
            parent_info.get("lastname", ""),
            parent_info.get("dob", ""),
            parent_info.get("address", ""),
            parent_info.get("postcode", ""),
            parent_info.get("city", ""),
            parent_info.get("country", ""),
            parent_info.get("phone", ""),

            json.dumps(participants)
        ]

        logging.info(f"🟩 Data naar Google Sheets: {row}")

        # Append to sheet
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Clients!A:Z",
            valueInputOption="RAW",
            body={"values": [row]}
        ).execute()

        logging.info("🎉 SUCCESS: Row toegevoegd aan Google Sheets!")

    except Exception as e:
        logging.error("❌ Google Sheets append ERROR:")
        logging.error(e)
        logging.error(traceback.format_exc())



# ───────────────────────────────────────────────
# HTML Email template
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
    <div style="font-family: 'Segoe UI'; background:#ffffff; padding:30px; max-width:700px; margin:auto;">
        <h2 style="color:#ff6b00;">Hi {name.split()[0]},</h2>
        <p>Thank you for registering!</p>
        <hr>
        {participant_summary}
        <hr>
        <p>Kind regards,<br><b>TK Sports Academy</b></p>
    </div>
    """
    return html



# ───────────────────────────────────────────────
# Send Mailjet email
# ───────────────────────────────────────────────
def send_mailjet_confirmation(email, name, parent_info, participants):
    logging.info("📧 Sending confirmation email...")

    html = build_html_email(name, parent_info, participants)
    url = "https://api.mailjet.com/v3.1/send"

    data = {
        "Messages": [
            {
                "From": {"Email": "info@tksportsacademy.nl", "Name": "TK Sports Academy"},
                "To": [{"Email": email, "Name": name}],
                "Subject": "Registration Confirmation - TK Sports Academy",
                "HTMLPart": html
            }
        ]
    }

    response = requests.post(
        url,
        auth=(MJ_APIKEY_PUBLIC, MJ_APIKEY_PRIVATE),
        headers={"Content-Type": "application/json"},
        data=json.dumps(data),
        timeout=15
    )

    logging.info(f"📨 Mailjet status: {response.status_code}")

    if response.status_code != 200:
        logging.error("❌ Mailjet ERROR:")
        logging.error(response.text)
        raise Exception("Mailjet failed: " + response.text)

    return response.json()



# ───────────────────────────────────────────────
# Route: send email + save to sheet
# ───────────────────────────────────────────────
@app.route("/send-confirmation", methods=["POST"])
def send_confirmation():
    logging.info("🚀 /send-confirmation HIT!")

    try:
        data = request.get_json() or {}
        logging.info(f"📦 Ontvangen JSON: {data}")

        email = data.get("email")
        if not email:
            return jsonify({"success": False, "error": "Email missing"}), 400

        name = data.get("name", "Athlete")
        parent_info = data.get("parent_info", {})
        participants = data.get("participants", [])

        logging.info("📧 Sending Mailjet email...")
        result = send_mailjet_confirmation(email, name, parent_info, participants)

        logging.info("📊 Saving to Google Sheets...")
        append_to_google_sheet(parent_info, participants)

        logging.info("🎉 DONE: email + sheet saved")

        return jsonify({"success": True}), 200

    except Exception as e:
        logging.error("🔥 ERROR in /send-confirmation")
        logging.error(e)
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500



# ───────────────────────────────────────────────
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"}), 200



if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

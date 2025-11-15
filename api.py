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
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)

# ───────────────────────────────────────────────
# Mailjet keys
# ───────────────────────────────────────────────
MJ_APIKEY_PUBLIC = os.getenv("MJ_APIKEY_PUBLIC")
MJ_APIKEY_PRIVATE = os.getenv("MJ_APIKEY_PRIVATE")

# ───────────────────────────────────────────────
# Google Sheets config
# ───────────────────────────────────────────────
SPREADSHEET_ID = "1owN41X9KcQL_Ipl6wxzFe-M6Xsbe5Y3glfoUrZN6YPY"
SECRET_PATH = "/etc/secrets/google-credentials.json"


def append_to_google_sheet(parent_info, participants):
    logging.info("🟧 append_to_google_sheet() gestart")

    try:
        if not os.path.exists(SECRET_PATH):
            logging.error("❌ Google secret NIET gevonden: " + SECRET_PATH)
            return

        with open(SECRET_PATH, "r") as f:
            key_data = json.load(f)

        credentials = service_account.Credentials.from_service_account_info(
            key_data,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )

        service = build("sheets", "v4", credentials=credentials)

        all_rows = []

        for p in participants:
            row = [
                datetime.datetime.now(datetime.UTC).isoformat(),

                parent_info.get("email", ""),
                parent_info.get("firstname", ""),
                parent_info.get("lastname", ""),
                parent_info.get("dob", ""),
                parent_info.get("address", ""),
                parent_info.get("postcode", ""),
                parent_info.get("city", ""),
                parent_info.get("country", ""),
                parent_info.get("phone", ""),

                p.get("firstname", ""),
                p.get("lastname", ""),
                p.get("dob", ""),
                p.get("club", ""),
                p.get("position", ""),
                p.get("tshirt", ""),
                p.get("allergy", ""),
                p.get("other", "")
            ]

            all_rows.append(row)

        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Sheet1!A1:Z",
            valueInputOption="RAW",
            body={"values": all_rows}
        ).execute()

        logging.info("🎉 SUCCESS: Rijen toegevoegd aan Google Sheets")

    except Exception as e:
        logging.error("❌ Google Sheets ERROR")
        logging.error(traceback.format_exc())


# ───────────────────────────────────────────────
# EMAIL TEMPLATE
# ───────────────────────────────────────────────
def build_html_email(name, parent_info, participants):
    participant_summary = ""
    for i, p in enumerate(participants, 1):
        participant_summary += f"""
        <p>
            <b>Participant {i}:</b> {p.get('firstname')} {p.get('lastname')}
            ({p.get('position')} – {p.get('club')})
        </p>
        """

    return f"""
    <div style="font-family:Segoe UI; padding:20px">
        <h2>Hi {name.split()[0]},</h2>
        <p>Thank you for registering.</p>
        <h3>Participants:</h3>
        {participant_summary}
        <br>
        <p>See you soon!<br><b>TK Sports Academy</b></p>
    </div>
    """


# ───────────────────────────────────────────────
# SEND EMAIL (Mailjet)
# ───────────────────────────────────────────────
def send_mailjet_confirmation(email, name, parent_info, participants):
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

    r = requests.post(
        url,
        auth=(MJ_APIKEY_PUBLIC, MJ_APIKEY_PRIVATE),
        headers={"Content-Type": "application/json"},
        data=json.dumps(data)
    )

    if r.status_code != 200:
        raise Exception(r.text)

    return r.json()


# ───────────────────────────────────────────────
# MAIN FORM HANDLER
# ───────────────────────────────────────────────
@app.route("/send-confirmation", methods=["POST"])
def send_confirmation():
    try:
        data = request.get_json()

        parent_info = data.get("parent_info")
        participants = data.get("participants")

        send_mailjet_confirmation(
            data["email"],
            data["name"],
            parent_info,
            participants
        )

        append_to_google_sheet(parent_info, participants)

        return jsonify({"success": True})

    except Exception as e:
        logging.error("🔥 ERROR in send-confirmation")
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)})


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

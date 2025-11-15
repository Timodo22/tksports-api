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
    logging.warning("⚠️ Mailjet API keys are not set in environment variables.")


# ───────────────────────────────────────────────
# Google Sheets — opslaan van registraties
# ───────────────────────────────────────────────
SPREADSHEET_ID = "1owN41X9KcQL_Ipl6wxzFe-M6Xsbe5Y3glfoUrZN6YPY"   # <<<< vul deze in

def append_to_google_sheet(parent_info, participants):
    try:
        key_data = json.loads(os.getenv("GOOGLE_SHEETS_KEY"))

        credentials = service_account.Credentials.from_service_account_info(
            key_data,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )

        service = build("sheets", "v4", credentials=credentials)

        values = [[
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
        ]]

        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Clients!A:Z",
            valueInputOption="RAW",
            body={"values": values}
        ).execute()

        print("✅ Row appended to Google Sheets")

    except Exception as e:
        print("❌ Google Sheets append error:", e)
        traceback.print_exc()



# ───────────────────────────────────────────────
# Email template
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
            Thank you for signing up for <b>TK Sports Academy</b>!
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
            We’re looking forward to seeing you soon!
        </p>
        <p style="margin-top:25px; font-style:italic; color:#777;">Kind regards,<br><b>The TK Sports Academy Team</b></p>
    </div>
    """
    return html


# ───────────────────────────────────────────────
# Mail versturen
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
# Route: Send Confirmation + Save to Sheets
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

        # 1. Verstuur email
        result = send_mailjet_confirmation(email, name, parent_info, participants)

        # 2. Opslaan in Google Sheets
        append_to_google_sheet(parent_info, participants)

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

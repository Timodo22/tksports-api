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
    participant_html = ""
    for i, p in enumerate(participants, 1):
        participant_html += f"""
            <tr>
                <td style="padding:10px 0; font-size:16px; color:#333;">
                    <b>Participant {i}:</b> {p.get("firstname")} {p.get("lastname")} <br>
                    <span style="color:#555;">
                        Position: {p.get("position")} <br>
                        Club: {p.get("club")} <br>
                        T-shirt size: {p.get("tshirt")}
                    </span>
                </td>
            </tr>
            <tr><td style="border-bottom:1px solid #eee; padding-bottom:10px;"></td></tr>
        """

    return f"""
    <html>
    <body style="font-family:Segoe UI, sans-serif; background:#f7f7f7; padding:30px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:auto; background:#fff; border-radius:10px; padding:20px;">
            
            <!-- LOGO -->
            <tr>
                <td style="text-align:center; padding-bottom:20px;">
                    <img src="https://tksportsacademy.nl/assets/imgs/logo-blac.png" width="120" alt="TK Sports Academy">
                </td>
            </tr>

            <!-- HEADER -->
            <tr>
                <td style="font-size:24px; font-weight:bold; color:#ff6b00; padding-bottom:10px;">
                    Hi {name.split()[0]},
                </td>
            </tr>

            <tr>
                <td style="font-size:16px; color:#333; padding-bottom:20px;">
                    Thank you for signing up for <b>TK Sports Academy</b>!
                </td>
            </tr>

            <!-- PARENT INFO -->
            <tr>
                <td style="background:#fff4ec; padding:15px; border-radius:6px; color:#333;">
                    <h3 style="margin:0; margin-bottom:10px; color:#ff6b00;">Registration Summary</h3>

                    <b>Parent/Guardian:</b> {parent_info.get("firstname")} {parent_info.get("lastname")} <br>
                    <b>Email:</b> {parent_info.get("email")} <br>
                    <b>Phone:</b> {parent_info.get("phone")} <br>
                    <b>Address:</b> {parent_info.get("address")}, {parent_info.get("postcode")} {parent_info.get("city")}, {parent_info.get("country")}
                </td>
            </tr>

            <tr><td style="height:20px;"></td></tr>

            <!-- PARTICIPANTS -->
            <tr>
                <td>
                    <h3 style="color:#ff6b00; margin-bottom:10px;">Participants</h3>
                </td>
            </tr>

            {participant_html}

            <tr><td style="height:20px;"></td></tr>

            <tr>
                <td style="text-align:center; font-size:16px; padding-top:10px;">
                    We're looking forward to seeing you soon! <br><br>
                    <b>TK Sports Academy Team</b>
                </td>
            </tr>

        </table>
    </body>
    </html>
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


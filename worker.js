export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ===== CORS =====
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    if (url.pathname === "/ping") {
      return json({ status: "ok" });
    }

    // ==========================================
    // HANDLE REGISTRATION
    // ==========================================
    if (url.pathname === "/send-confirmation" && request.method === "POST") {
      try {
        const body = await request.json();

        const email = body.email;
        const name = body.name || "";
        const parent_info = body.parent_info || {};
        const participants = body.participants || [];

        if (!email) return json({ success: false, error: "Email missing" }, 400);

        // Build confirmation email
        const html = buildHtmlEmail(name, parent_info, participants);

        // Send email via Mailjet
        const result = await sendMailjet(
          email,
          name,
          html,
          env.MJ_APIKEY_PUBLIC,
          env.MJ_APIKEY_PRIVATE
        );

        const success =
          result.Messages && result.Messages[0]?.Status === "success";

        // Always push to Google Sheet
        for (const p of participants) {
          await appendToSheet(env, [
            new Date().toISOString(), // Date
            parent_info.email || "",
            parent_info.firstname || "",
            parent_info.lastname || "",
            parent_info.dob || "",
            parent_info.address || "",
            parent_info.postcode || "",
            parent_info.city || "",
            parent_info.country || "",
            parent_info.phone || "",

            p.firstname || "",
            p.lastname || "",
            p.dob || "",
            p.club || "",
            p.position || "",
            p.tshirt || "",
            p.allergy || "",
            p.other || ""
          ]);
        }

        return json({ success, result });
      } catch (e) {
        return json({ success: false, error: e.toString() }, 500);
      }
    }

    return json({ error: "Not found" }, 404);
  }
};

// =========================================
// HELPERS
// =========================================

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization"
  };
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders()
    }
  });
}

// =========================================
// MAILJET
// =========================================

async function sendMailjet(email, name, html, publicKey, privateKey) {
  const payload = {
    Messages: [
      {
        From: { Email: "info@tksportsacademy.nl", Name: "TK Sports Academy" },
        To: [{ Email: email, Name: name }],
        Subject: `Registration Confirmation - TK Sports Academy`,
        HTMLPart: html
      }
    ]
  };

  const response = await fetch("https://api.mailjet.com/v3.1/send", {
    method: "POST",
    headers: {
      Authorization: "Basic " + btoa(`${publicKey}:${privateKey}`),
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  return await response.json();
}

// =========================================
// GOOGLE SHEETS - JWT AUTH
// =========================================

// Convert private key to ArrayBuffer
function str2ab(str) {
  const cleaned = str
    .replace("-----BEGIN PRIVATE KEY-----", "")
    .replace("-----END PRIVATE KEY-----", "")
    .replace(/\n/g, "")
    .trim();

  const binary = atob(cleaned);
  const buffer = new ArrayBuffer(binary.length);
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return buffer;
}

async function getGoogleAccessToken(env) {
  const header = { alg: "RS256", typ: "JWT" };
  const now = Math.floor(Date.now() / 1000);

  const claim = {
    iss: env.GOOGLE_SERVICE_EMAIL,
    scope: "https://www.googleapis.com/auth/spreadsheets",
    aud: "https://oauth2.googleapis.com/token",
    exp: now + 3600,
    iat: now
  };

  const privateKey = await crypto.subtle.importKey(
    "pkcs8",
    str2ab(env.GOOGLE_PRIVATE_KEY),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"]
  );

  const encoder = new TextEncoder();
  const unsigned = `${btoa(JSON.stringify(header))}.${btoa(
    JSON.stringify(claim)
  )}`;

  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    privateKey,
    encoder.encode(unsigned)
  );

  const jwt = `${unsigned}.${btoa(
    String.fromCharCode(...new Uint8Array(signature))
  )}`;

  // Exchange JWT → Access Token
  const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=${jwt}`
  });

  return (await tokenRes.json()).access_token;
}

// =========================================
// ADD ROW TO GOOGLE SHEET
// =========================================

async function appendToSheet(env, rowData) {
  const token = await getGoogleAccessToken(env);
  const spreadsheetId = env.GOOGLE_SHEET_ID;
  const range = "Sheet1!A:Z";

  await fetch(
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${range}:append?valueInputOption=RAW`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ values: [rowData] })
    }
  );
}

// =========================================
// BEAUTIFUL FULL EMAIL TEMPLATE
// =========================================

function buildHtmlEmail(name, parent_info, participants) {
  let participantHTML = "";

  participants.forEach((p, i) => {
    participantHTML += `
      <div style="padding:12px;border-bottom:1px solid #eee;">
        <p style="margin:0;font-weight:bold;">Participant ${i + 1}</p>
        <p style="margin:0;">${p.firstname} ${p.lastname}</p>
        <p style="margin:0;">Position: ${p.position}</p>
        <p style="margin:0;">Club: ${p.club}</p>
        <p style="margin:0;">T-shirt size: ${p.tshirt}</p>
        <p style="margin:0;">Allergy: ${p.allergy || "None"}</p>
      </div>
    `;
  });

  return `
  <div style="font-family:Arial, sans-serif; background:#f7f7f7; padding:30px;">
    <div style="
      max-width:600px;
      margin:0 auto;
      background:white;
      padding:30px;
      border-radius:12px;
      box-shadow:0 0 10px rgba(0,0,0,0.05);
    ">

      <div style="text-align:center;">
        <img src="https://tksportsacademy.nl/assets/imgs/logo-blac.png" 
             width="120"
             style="margin-bottom:20px;" />
      </div>

      <h2 style="color:#ff6b00;">Hi ${name.split(" ")[0]},</h2>
      <p>Thank you for signing up for <b>TK Sports Academy!</b></p>

      <div style="background:#fff8ef;padding:20px;border-radius:8px;margin-top:20px;">
        <h3 style="color:#ff6b00;margin-top:0;">Registration Summary</h3>
        <p><b>Parent/Guardian:</b> ${parent_info.firstname} ${parent_info.lastname}</p>
        <p><b>Email:</b> ${parent_info.email}</p>
        <p><b>Phone:</b> ${parent_info.phone}</p>
        <p><b>Address:</b> ${parent_info.address}, ${parent_info.postcode} ${parent_info.city}, ${parent_info.country}</p>
      </div>

      <h3 style="color:#333;margin-top:30px;">Participants</h3>
      <div style="border:1px solid #eee;border-radius:8px;">
        ${participantHTML}
      </div>

      <p style="margin-top:30px;">We're looking forward to seeing you soon!</p>
      <p style="font-weight:bold;color:#ff6b00;">TK Sports Academy Team</p>

      <hr style="margin:30px 0;border:0;border-top:1px solid #ddd;">

      <p style="text-align:center;color:#777;font-size:12px;">
        Powered by 
        <a href="https://spectux.com" 
           style="color:#ff6b00;text-decoration:none;font-weight:bold;">
          Spectux
        </a>
      </p>

    </div>
  </div>
  `;
}

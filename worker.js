export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ---- CORS ----
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders()
      });
    }

    // ---- ROUTES ----
    if (url.pathname === "/ping") {
      return json({ status: "ok" });
    }

    if (url.pathname === "/send-confirmation" && request.method === "POST") {
      try {
        const body = await request.json();

        const email = body.email;
        const name = body.name || "Athlete";
        const parent_info = body.parent_info || {};
        const participants = body.participants || [];

        if (!email) {
          return json({ success: false, error: "Email missing" }, 400);
        }

        // Build HTML
        const html = buildHtmlEmail(name, parent_info, participants);

        // Send Mailjet request
        const result = await sendMailjet(
          email,
          name,
          html,
          env.MJ_APIKEY_PUBLIC,
          env.MJ_APIKEY_PRIVATE
        );

        return json({ success: true, result });
      } catch (e) {
        return json({ success: false, error: e.toString() }, 500);
      }
    }

    return json({ error: "Not found" }, 404);
  }
};

// -----------------------------
// Helpers
// -----------------------------

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

// -----------------------------
// Mailjet sending function
// -----------------------------
async function sendMailjet(email, name, html, publicKey, privateKey) {
  const response = await fetch("https://api.mailjet.com/v3.1/send", {
    method: "POST",
    headers: {
      "Authorization": "Basic " + btoa(`${publicKey}:${privateKey}`),
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      Messages: [
        {
          From: { "Email": "info@tksportsacademy.nl", "Name": "TK Sports Academy" },
          To: [{ "Email": email, "Name": name }],
          Subject: `Registration Confirmation - TK Sports Academy`,
          HTMLPart: html
        }
      ]
    })
  });

  const jsonRes = await response.json();
  return jsonRes;
}

// -----------------------------
// HTML template
// -----------------------------
function buildHtmlEmail(name, parent_info, participants) {
  let participant_summary = "";

  participants.forEach((p, i) => {
    participant_summary += `
      <p style="margin:6px 0;">
        <b>Participant ${i + 1}:</b> ${p.firstname || ""} ${p.lastname || ""}
        (${p.position || ""} – ${p.club || ""}, Shirt: ${p.tshirt || ""})
      </p>
    `;
  });

  return `
  <div style="font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background:#ffffff; color:#333; padding:30px; max-width:700px; margin:auto; border-radius:10px; border:1px solid #eee;">
      <div style="text-align:center; margin-bottom:25px;">
          <img src="https://tksportsacademy.nl/assets/imgs/logo-blac.png" alt="TK Sports Academy" style="width:120px; margin-bottom:10px;">
      </div>
      <h2 style="color:#ff6b00;">Hi ${name.split(" ")[0]},</h2>
      <p style="font-size:1.05rem; line-height:1.6;">
          Thank you for signing up for <b>TK Sports Academy</b>!
      </p>
      <p style="font-size:1.05rem; line-height:1.6;">
          To secure your place, please complete your <b>deposit payment</b>.
      </p>

      <hr style="margin:30px 0; border:none; border-top:1px solid #eee;">
      <h3 style="color:#ff6b00;">Registration Summary</h3>

      <div style="margin-top:10px; font-size:0.95rem;">
          <p><b>Parent/Guardian:</b> ${parent_info.firstname || ""} ${parent_info.lastname || ""}</p>
          <p><b>Email:</b> ${parent_info.email || ""}</p>
          <p><b>Phone:</b> ${parent_info.phone || ""}</p>
          <p><b>Address:</b> ${parent_info.address || ""}, ${parent_info.postcode || ""} ${parent_info.city || ""}, ${parent_info.country || ""}</p>
      </div>

      <div style="margin-top:15px;">${participant_summary}</div>

      <hr style="margin:30px 0; border:none; border-top:1px solid #eee;">
      <p style="font-size:1.05rem; line-height:1.6;">
          If you have questions, contact us at
          <a href="mailto:info@tksportsacademy.nl" style="color:#ff6b00;">info@tksportsacademy.nl</a>.
      </p>

      <p style="margin-top:25px; font-style:italic; color:#777;">Kind regards,<br><b>The TK Sports Academy Team</b></p>
  </div>`;
}

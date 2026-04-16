const JSON_HEADERS = {
  "content-type": "application/json; charset=UTF-8",
  "cache-control": "no-store",
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/i;
const ALLOWED_USE_CASES = new Set([
  "memory",
  "coding",
  "research",
  "writing",
  "assistant",
  "execution",
  "other",
]);

function jsonResponse(payload, init = {}) {
  return Response.json(payload, {
    status: init.status || 200,
    headers: {
      ...JSON_HEADERS,
      ...(init.headers || {}),
    },
  });
}

function cleanString(value, maxLength) {
  return String(value || "").trim().slice(0, maxLength);
}

async function ensureWaitlistTable(db) {
  await db.prepare(
    `CREATE TABLE IF NOT EXISTS beta_waitlist (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT NOT NULL UNIQUE,
      use_case TEXT NOT NULL,
      use_case_label TEXT NOT NULL,
      lang TEXT,
      source TEXT,
      status TEXT NOT NULL DEFAULT 'pending',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )`
  ).run();

  await db.prepare(
    "CREATE INDEX IF NOT EXISTS idx_beta_waitlist_status_created_at ON beta_waitlist(status, created_at DESC)"
  ).run();
}

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      Allow: "POST, OPTIONS",
      "cache-control": "no-store",
    },
  });
}

export async function onRequestPost(context) {
  const db = context.env && context.env.WAITLIST_DB;
  if (!db || typeof db.prepare !== "function") {
    return jsonResponse(
      {
        ok: false,
        error: "waitlist_storage_unavailable",
      },
      { status: 503 }
    );
  }

  let payload;
  try {
    payload = await context.request.json();
  } catch {
    return jsonResponse(
      {
        ok: false,
        error: "invalid_json",
      },
      { status: 400 }
    );
  }

  const trap = cleanString(payload.website, 200);
  if (trap) {
    return jsonResponse({ ok: true, accepted: true }, { status: 202 });
  }

  const email = cleanString(payload.email, 320).toLowerCase();
  const useCase = cleanString(payload.useCase, 64);
  const useCaseLabel = cleanString(payload.useCaseLabel, 160);
  const lang = cleanString(payload.lang, 24);
  const source = cleanString(payload.source, 160);

  if (!EMAIL_RE.test(email)) {
    return jsonResponse(
      {
        ok: false,
        error: "invalid_email",
      },
      { status: 400 }
    );
  }

  if (!ALLOWED_USE_CASES.has(useCase) || !useCaseLabel) {
    return jsonResponse(
      {
        ok: false,
        error: "invalid_use_case",
      },
      { status: 400 }
    );
  }

  try {
    await ensureWaitlistTable(db);

    await db.prepare(
      `INSERT INTO beta_waitlist (
        email,
        use_case,
        use_case_label,
        lang,
        source
      ) VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(email) DO UPDATE SET
        use_case = excluded.use_case,
        use_case_label = excluded.use_case_label,
        lang = excluded.lang,
        source = excluded.source,
        updated_at = CURRENT_TIMESTAMP`
    ).bind(email, useCase, useCaseLabel, lang || null, source || null).run();

    return jsonResponse({
      ok: true,
      status: "pending",
    });
  } catch (error) {
    console.error("Failed to store beta waitlist entry", error);

    return jsonResponse(
      {
        ok: false,
        error: "waitlist_write_failed",
      },
      { status: 500 }
    );
  }
}

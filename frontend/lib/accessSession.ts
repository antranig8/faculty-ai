const COOKIE_NAME = "faculty_ai_access";
const SESSION_TTL_SECONDS = 12 * 60 * 60;

function base64UrlEncode(bytes: ArrayBuffer): string {
  let chars = "";
  const byteArray = new Uint8Array(bytes);
  for (let index = 0; index < byteArray.length; index += 1) {
    chars += String.fromCharCode(byteArray[index]);
  }
  return btoa(chars).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }

  let result = 0;
  for (let index = 0; index < a.length; index += 1) {
    result |= a.charCodeAt(index) ^ b.charCodeAt(index);
  }
  return result === 0;
}

async function signPayload(payload: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload));
  return base64UrlEncode(signature);
}

export function getAccessCookieName(): string {
  return COOKIE_NAME;
}

export function getAccessSessionTtlSeconds(): number {
  return SESSION_TTL_SECONDS;
}

export async function createAccessSession(secret: string): Promise<string> {
  const issuedAt = Math.floor(Date.now() / 1000).toString();
  const signature = await signPayload(issuedAt, secret);
  return `${issuedAt}.${signature}`;
}

export async function verifyAccessSession(value: string | undefined, secret: string): Promise<boolean> {
  if (!value) {
    return false;
  }

  const [issuedAt, signature, extra] = value.split(".");
  if (!issuedAt || !signature || extra) {
    return false;
  }

  const issuedAtSeconds = Number(issuedAt);
  if (!Number.isFinite(issuedAtSeconds)) {
    return false;
  }

  const nowSeconds = Math.floor(Date.now() / 1000);
  if (issuedAtSeconds > nowSeconds || nowSeconds - issuedAtSeconds > SESSION_TTL_SECONDS) {
    return false;
  }

  const expected = await signPayload(issuedAt, secret);
  return timingSafeEqual(signature, expected);
}

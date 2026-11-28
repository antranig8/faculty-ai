import { existsSync, readFileSync } from "node:fs";
import { parse } from "dotenv";

const frontendKeys = [
  "NEXT_PUBLIC_API_BASE_URL",
  "NEXT_PUBLIC_FACULTY_AI_APP_API_KEY",
  "FACULTY_AI_ACCESS_CODE",
];

const rootEnvFile = new URL("../.env", import.meta.url);
if (existsSync(rootEnvFile)) {
  const rootEnv = parse(readFileSync(rootEnvFile));
  for (const key of frontendKeys) {
    if (process.env[key] === undefined && rootEnv[key] !== undefined) {
      process.env[key] = rootEnv[key];
    }
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = { agentRules: false };

export default nextConfig;


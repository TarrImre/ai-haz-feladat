// Kötelező környezeti változó; ha hiányzik, hibát dob.
export function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Hiányzó környezeti változó: ${name}`);
  return value;
}

import { expect, test } from "@playwright/test";

test("la landing vende con honestidad y abre el sandbox público", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Tu negocio al día/ })).toBeVisible();
  await expect(page.getByText("No emite ni presenta documentos reales.")).toBeVisible();
  const sandbox = page.getByRole("link", { name: "Explorar sandbox" });
  await expect(sandbox).toHaveAttribute("href", "/dashboard");
  await sandbox.click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Tu operación fiscal, al día." })).toBeVisible();
});

test("mantiene el shell al revisar un documento recibido", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "Tu operación fiscal, al día." }),
  ).toBeVisible();
  await expect(page.getByText("Ambiente demo")).toBeVisible();

  await page.getByRole("link", { name: /^Recibidos/ }).click();
  await expect(
    page.getByRole("heading", { name: "Documentos recibidos" }),
  ).toBeVisible();
  await page.locator('a[href="/recibidos/demo-33-7841"]').click();
  await expect(page).toHaveURL(/\/recibidos\/demo-33-7841$/);

  await expect(
    page.getByRole("heading", { name: "DISTRIBUIDORA CENTRAL SPA" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Inicio", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /^Recibidos/ })).toBeVisible();
});

test("recorre los asistentes tributarios sin perder el ambiente", async ({ page }) => {
  await page.goto("/emitir");
  await page.getByRole("link", { name: /Registrar una venta/ }).click();
  await expect(
    page.getByRole("heading", { name: "Registrar una venta" }),
  ).toBeVisible();
  await expect(page.getByText("Ensayo sin folios")).toBeVisible();

  await page.getByRole("link", { name: "Volver a tipos de documento" }).click();
  await page.getByRole("link", { name: /Corregir un documento/ }).click();
  await expect(
    page.getByRole("heading", { name: "¿Qué necesitas corregir?" }),
  ).toBeVisible();
  await expect(page.getByText("Builders 56/61 activos")).toBeVisible();
});

test("las áreas SII declaran el origen sintético de sus datos", async ({ page }) => {
  await page.goto("/f29");
  await expect(
    page.getByRole("heading", { name: "Propuesta F29 · julio 2026" }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Datos sintéticos");
  await expect(
    page.getByText("No es una declaración presentada ni una orden de pago."),
  ).toBeVisible();
});

test("ejecuta el ensayo offline sin habilitar CAF real", async ({ page }) => {
  await page.goto("/certificacion");
  await expect(page.getByRole("heading", { name: "Cockpit de preparación SII" })).toBeVisible();
  await expect(page.getByText("Certificado digital real")).toBeVisible();
  await page.getByLabel("Escenario de ensayo").selectOption("timeout_after_upload");
  await page.getByRole("button", { name: "Ejecutar ensayo offline" }).click();
  await expect(page.getByText("Estado final: unknown")).toBeVisible();
  await expect(page.getByText("CAF real bloqueado")).toBeVisible();
});

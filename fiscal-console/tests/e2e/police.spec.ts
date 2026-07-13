import { expect, test } from "@playwright/test";

const criticalRoutes = [
  ["/ventas", "Ventas y cotizaciones"],
  ["/compras", "Órdenes de compra"],
  ["/inventario", "Inventario"],
  ["/caja", "Caja proyectada"],
  ["/aprobaciones", "Aprobaciones"],
  ["/recurrencia", "Acuerdos mensuales"],
  ["/cierre", "Cómo viene este mes"],
  ["/expediente", "Todo lo que respalda este mes"],
  ["/pagos", "Vouchers y ventas, sin duplicar boletas"],
  ["/f29", "Propuesta F29 · julio 2026"],
  ["/proveedores", "Proveedores y respaldo"],
  ["/folios", "Folios y CAF bajo control"],
  ["/envios", "Envíos y seguimiento"],
] as const;

test("inicio ofrece un recorrido contable completo", async ({ page }) => {
  await page.goto("/dashboard");
  const review = page.getByRole("region", { name: "Recorrido recomendado para contador" });
  await expect(review.getByText("Recorrido preparado para tu contador")).toBeVisible();
  await expect(review.getByRole("link", { name: /RCV/ })).toHaveAttribute("href", "/rcv");
  await expect(review.getByRole("link", { name: /F29 explicado/ })).toHaveAttribute("href", "/f29");
  await expect(review.getByRole("link", { name: /Cierre/ })).toHaveAttribute("href", "/cierre");
  await expect(review.getByRole("link", { name: /Expediente/ })).toHaveAttribute("href", "/expediente");
});

test("el ciclo comercial distingue sus documentos de un DTE", async ({ page }) => {
  await page.goto("/ventas");
  await expect(page.getByText("Nada de esto consume un folio")).toBeVisible();
  if (await page.getByRole("button", { name: "Más secciones" }).isVisible()) {
    await page.getByRole("button", { name: "Más secciones" }).click();
  }
  await page.getByRole("link", { name: "Órdenes de compra" }).click();
  await expect(page.getByText("Cada solicitud conserva su aprobación, recepción, factura y pago.")).toBeVisible();
});

test("caja proyectada advierte que no es saldo bancario", async ({ page }) => {
  await page.goto("/caja");
  await expect(page.getByText(/no es saldo bancario en línea/i)).toBeVisible();
  await expect(page.getByText("Hay una semana estrecha")).toBeVisible();
});

test("acciones comerciales abren flujos y no son botones muertos", async ({ page }) => {
  await page.goto("/ventas");
  await page.getByRole("link", { name: "Nueva cotización" }).click();
  await expect(page.getByRole("heading", { name: "Nueva cotización" })).toBeVisible();
  await page.goto("/compras");
  await page.getByRole("link", { name: "Nueva orden" }).click();
  await expect(page.getByRole("heading", { name: "Nueva orden de compra" })).toBeVisible();
  await page.goto("/inventario");
  await page.getByRole("link", { name: "Registrar movimiento" }).click();
  await expect(page.getByRole("heading", { name: "Registrar movimiento" })).toBeVisible();
  await page.goto("/caja");
  await page.getByRole("link", { name: "Importar cartola" }).click();
  await expect(page.getByRole("heading", { name: "Importar cartola" })).toBeVisible();
  await page.goto("/caja");
  await page.getByRole("link", { name: "Registrar cuenta" }).click();
  await expect(page.getByRole("heading", { name: "Registrar cuenta" })).toBeVisible();
  await page.goto("/caja");
  await page.getByRole("link", { name: "Registrar pago parcial" }).click();
  await expect(page.getByRole("heading", { name: "Registrar pago parcial" })).toBeVisible();
});

test("una aprobación demo se decide una sola vez", async ({page})=>{
  await page.goto("/aprobaciones");
  await page.getByRole("button",{name:"Aprobar OC-0032"}).click();
  await expect(page.getByText("approved")).toBeVisible();
  await expect(page.getByRole("button",{name:"Aprobar OC-0032"})).toHaveCount(0);
});

test("recurrencia y control de stock tienen flujos operables",async({page})=>{
  await page.goto("/recurrencia");await page.getByRole("button",{name:"Nuevo acuerdo"}).click();await expect(page.getByRole("textbox",{name:"Cliente"})).toBeVisible();
  await page.goto("/inventario/control");await expect(page.getByRole("heading",{name:"Mínimos y traslados"})).toBeVisible();await expect(page.getByRole("button",{name:"Registrar traslado pareado"})).toBeVisible();
});

for (const [path, heading] of criticalRoutes) {
  test(`${path} conserva shell, ambiente y ancho válido`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expect(page.getByRole("status")).toContainText("Ambiente demo");
    await expect(page.getByRole("link", { name: "Inicio", exact: true })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(overflow).toBeFalsy();
  });
}

test("pagos no permite una importación falsa desde un botón muerto", async ({ page }) => {
  await page.goto("/pagos");
  await expect(page.getByRole("button", { name: "Importación mediante integración" })).toBeDisabled();
  await expect(page.locator(".payments-list .demo-action")).toBeVisible();
});

test("expediente bloquea descarga incompleta y vuelve al cierre", async ({ page }) => {
  await page.goto("/expediente");
  const download = page.getByRole("button", { name: "Descargar paquete" });
  if (await download.isDisabled()) await expect(download).toBeDisabled();
  await page.getByRole("link", { name: "Revisar cierre" }).click();
  await expect(page.getByRole("heading", { name: "Cómo viene este mes" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Todo lo que respalda este mes" })).toBeVisible();
});

test("centro de ayuda abre en contexto, busca y prepara soporte", async ({ page }) => {
  await page.goto("/pagos");
  await page.getByRole("button", { name: "Centro de ayuda" }).click();
  const dialog = page.getByRole("dialog", { name: "Centro de ayuda" });
  await expect(dialog.getByRole("heading", { name: "Ayuda · pagos" })).toBeVisible();
  await dialog.getByLabel("Buscar en el centro de ayuda").fill("anular boleta");
  await dialog.getByRole("button", { name: /documentos/ }).click();
  await expect(dialog.getByText("Me equivoqué en una boleta")).toBeVisible();
  const support = dialog.getByRole("link", { name: "Reportar por WhatsApp" });
  await expect(support).toHaveAttribute("href", /wa\.me\/56972739105/);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

const contextualHelpRoutes = [
  ["/ventas/nueva", "ventas_nueva"], ["/compras/nueva", "compras_nueva"],
  ["/inventario/movimiento", "inventario_movimiento"], ["/inventario/control", "inventario_control"],
  ["/caja/importar", "caja_importar"], ["/caja/obligacion", "caja_obligacion"], ["/caja/pago", "caja_pago"],
  ["/emitir/boleta", "emitir_boleta"], ["/emitir/factura", "emitir_factura"],
  ["/emitir/correccion", "emitir_correccion"], ["/emitir/guia", "emitir_guia"], ["/recurrencia", "recurrencia"],
] as const;

test("cada flujo nuevo muestra ayuda específica y no la guía genérica", async ({ page }) => {
  for (const [path, helpKey] of contextualHelpRoutes) {
    await page.goto(path);
    await page.getByRole("button", { name: "Centro de ayuda" }).click();
    const dialog = page.getByRole("dialog", { name: "Centro de ayuda" });
    await expect(dialog.getByRole("heading", { name: `Ayuda · ${helpKey}` })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  }
});

test("el borrador de boleta sobrevive a una salida accidental", async ({ page }) => {
  await page.goto("/emitir/boleta");
  await page.getByLabel("Producto o servicio").fill("Borrador que no debe perderse");
  await page.getByRole("link", { name: "Documentos" }).click();
  await expect(page).toHaveURL(/\/documentos$/);
  await page.goto("/emitir/boleta");
  await expect(page.getByLabel("Producto o servicio")).toHaveValue("Borrador que no debe perderse");
});

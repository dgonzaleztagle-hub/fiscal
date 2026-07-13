import { expect, test, type Page } from "@playwright/test";

const routes = [
  "/dashboard", "/emitir", "/documentos", "/recibidos", "/recibidos/demo-33-7841",
  "/ventas", "/ventas/nueva", "/compras", "/compras/nueva", "/inventario",
  "/inventario/movimiento", "/inventario/control", "/caja", "/caja/importar",
  "/caja/obligacion", "/caja/pago", "/aprobaciones", "/recurrencia", "/clientes",
  "/proveedores", "/productos", "/folios", "/envios", "/reportes", "/cierre",
  "/expediente", "/pagos", "/rcv", "/f29", "/bhe", "/situacion",
  "/sincronizaciones", "/certificacion", "/configuracion", "/emitir/boleta",
  "/emitir/factura", "/emitir/correccion", "/emitir/guia",
] as const;

function guard(page: Page) {
  const consoleErrors: string[] = [];
  const serverErrors: string[] = [];
  const clientErrors: string[] = [];
  const siiRequests: string[] = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", error => consoleErrors.push(error.message));
  page.on("response", response => { if (response.status() >= 500) serverErrors.push(`${response.status()} ${response.url()}`); else if (response.status() >= 400) clientErrors.push(`${response.status()} ${response.url()}`); });
  page.on("request", request => { if (/https?:\/\/([^/]+\.)?sii\.cl/i.test(request.url())) siiRequests.push(request.url()); });
  return () => {
    expect(siiRequests, "El sandbox intentó contactar al SII").toEqual([]);
    expect(serverErrors, "Una acción produjo error 5xx").toEqual([]);
    expect(clientErrors, "Una acción pidió un recurso inexistente").toEqual([]);
    expect(consoleErrors, "La interfaz produjo errores de consola").toEqual([]);
  };
}

test.describe("@obsessive policía obsesiva", () => {
  test.setTimeout(300_000);
  test.skip(({ isMobile }) => Boolean(isMobile), "La pasada exhaustiva corre una vez; la suite normal ya cubre responsive.");

  test("todos los destinos internos existen y conservan el modo demo", async ({ page }) => {
    const finish = guard(page);
    const internalLinks = new Set<string>();
    for (const route of routes) {
      const response = await page.goto(route);
      expect(response?.status(), route).toBeLessThan(400);
      await expect(page.locator("body"), route).not.toContainText("Application error");
      await expect(page.getByRole("status").filter({ hasText: "Ambiente demo" }), route).toBeVisible();
      const links = await page.locator('a[href^="/"]').evaluateAll(nodes => nodes.map(node => (node as HTMLAnchorElement).getAttribute("href")).filter(Boolean) as string[]);
      links.forEach(href => internalLinks.add(href));
    }
    for (const href of internalLinks) {
      const linked = await page.request.get(href);
      expect(linked.status(), href).toBeLessThan(400);
    }
    finish();
  });

  test("ningún botón habilitado de la vista inicial es silencioso", async ({ page }) => {
    const finish = guard(page);
    const silent: string[] = [];
    for (const route of routes) {
      await page.goto(route);
      const count = await page.locator("main button").count();
      for (let index = 0; index < count; index++) {
        await page.goto(route);
        const button = page.locator("main button").nth(index);
        if (!await button.count()) continue;
        if (!await button.isVisible() || await button.isDisabled()) continue;
        const name = (await button.innerText()).trim() || await button.getAttribute("aria-label") || `botón ${index + 1}`;
        if (await button.getAttribute("class")?.then(value => value?.includes("selected")) || await button.getAttribute("aria-pressed") === "true") continue;
        const before = await page.locator("main").innerHTML();
        const beforeUrl = page.url();
        let requests = 0;
        const observe = () => { requests += 1; };
        page.on("request", observe);
        await button.click();
        await page.waitForTimeout(180);
        page.off("request", observe);
        const after = await page.locator("main").innerHTML().catch(() => "navigated");
        const invalid = await page.locator("main :invalid").count().catch(() => 0);
        if (before === after && beforeUrl === page.url() && requests === 0 && invalid === 0) silent.push(`${route}: ${name}`);
      }
    }
    expect(silent, "Botones habilitados que no hacen nada").toEqual([]);
    finish();
  });

  test("ejercita todas las familias fiscales y sus variantes", async ({ page }) => {
    const finish = guard(page);
    for (const exempt of [false, true]) {
      await page.goto("/emitir/boleta");
      await page.getByLabel("Producto o servicio").fill(exempt ? "Servicio exento obsesivo" : "Venta afecta obsesiva");
      await page.getByLabel("Este producto está exento de IVA").setChecked(exempt);
      await page.getByRole("button", { name: "Revisar antes de emitir" }).click();
      await page.getByRole("button", { name: "Emitir en sandbox" }).click();
      await expect(page.getByText("Boleta procesada por el backend")).toBeVisible();
      await expect(page.locator(".tax-preview .document-preview")).toContainText(exempt ? "41" : "39");
    }
    for (const exempt of [false, true]) {
      await page.goto("/emitir/factura");
      await page.getByLabel("Tributación").selectOption(exempt ? "exempt" : "affected");
      await page.getByLabel("Condición de pago").selectOption("credit");
      await page.getByRole("button", { name: "Validar borrador" }).click();
      await page.getByRole("button", { name: "Emitir en sandbox" }).click();
      await expect(page.getByText("Factura procesada por el backend")).toBeVisible();
      await expect(page.locator(".tax-preview .document-preview")).toContainText(exempt ? "34" : "33");
    }
    const corrections = [
      { choice: "Anular completamente", direction: null, expected: "Nota de crédito electrónica" },
      { choice: "Corregir datos del receptor", direction: null, expected: "Nota de crédito electrónica" },
      { choice: "Corregir cantidades o montos", direction: "Disminuir monto", expected: "Nota de crédito electrónica" },
      { choice: "Corregir cantidades o montos", direction: "Aumentar monto", expected: "Nota de débito electrónica" },
    ];
    for (const correction of corrections) {
      await page.goto("/emitir/correccion");
      await expect(page.getByLabel("Documento original")).not.toHaveValue("");
      await page.getByRole("button", { name: new RegExp(correction.choice) }).click();
      if (correction.direction) await page.getByRole("button", { name: correction.direction }).click();
      await page.getByLabel("Motivo").fill(`Prueba obsesiva: ${correction.choice}`);
      await page.getByRole("button", { name: "Emitir corrección en sandbox" }).click();
      await expect(page.getByText(new RegExp(`${correction.expected} · folio`))).toBeVisible();
    }
    for (const reason of ["sale", "pending", "consignment", "internal", "return"]) {
      await page.goto("/emitir/guia");
      await page.getByLabel("¿Por qué se trasladan los bienes?").selectOption(reason);
      await page.getByRole("button", { name: "Validar borrador" }).click();
      await page.getByRole("button", { name: "Emitir guía en sandbox" }).click();
      await expect(page.getByText(/Guía folio .* emitida/)).toBeVisible();
      if (reason === "internal") await expect(page.locator(".tax-preview .total-row")).toContainText("$0");
    }
    finish();
  });

  test("los portales públicos demo aceptan decisiones y comprobantes", async ({ page, browser }) => {
    const finish = guard(page);
    await page.goto("/cotizacion/demo");
    await expect(page.getByRole("heading", { name: "CLIENTE DEMOSTRACIÓN SPA" })).toBeVisible();
    await page.getByRole("button", { name: "Aceptar cotización" }).click();
    await expect(page.getByText("Cotización aceptada")).toBeVisible();
    const secondContext = await browser.newContext();
    const second = await secondContext.newPage();
    const finishSecond = guard(second);
    await second.goto("http://127.0.0.1:3002/cotizacion/demo");
    await second.getByRole("button", { name: "Rechazar" }).click();
    await expect(second.getByText("Cotización no aceptada")).toBeVisible();
    finishSecond();
    await secondContext.close();
    await page.goto("/cobro/demo");
    await page.getByLabel("Comprobante PDF, JPG o PNG").setInputFiles({ name: "comprobante-demo.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 demo") });
    await page.getByRole("button", { name: "Enviar comprobante" }).click();
    await expect(page.getByText("Comprobante recibido")).toBeVisible();
    finish();
  });

  test("doble clic lógico no duplica folios y las referencias inválidas se bloquean", async ({ page }) => {
    const headers = { "Content-Type": "application/json", "Idempotency-Key": `policia-${Date.now()}` };
    const payload = { documentType: 39, receiver: "CONSUMIDOR FINAL", itemName: "Ensayo de idempotencia", quantity: 1, unitPrice: 11900 };
    const first = await page.request.post("/api/demo/fiscal-documents", { headers, data: payload });
    const second = await page.request.post("/api/demo/fiscal-documents", { headers, data: payload });
    expect(first.status()).toBe(201);
    expect(second.status()).toBe(200);
    const firstBody = await first.json() as { id: string; folio: string };
    const secondBody = await second.json() as { id: string; folio: string };
    expect(secondBody).toEqual(firstBody);
    const documents = await page.request.get("/api/demo/fiscal-documents");
    const rows = await documents.json() as Array<{ id: string }>;
    expect(rows.filter(row => row.id === firstBody.id)).toHaveLength(1);
    const illegal = await page.request.post("/api/demo/fiscal-documents", { data: { documentType: 61, receiver: "CLIENTE DEMO", itemName: "Referencia cruzada", quantity: 1, unitPrice: 1000, referenceId: "documento-de-otro-tenant", reason: "Debe fallar" } });
    expect(illegal.status()).toBe(422);
    await expect(illegal.json()).resolves.toMatchObject({ detail: expect.stringContaining("no existe") });
  });

  test("los cuatro desenlaces de certificación quedan explicados sin salir del sandbox", async ({ page }) => {
    const finish = guard(page);
    for (const scenario of ["accepted", "timeout_after_upload", "envelope_rejected", "rcof_rejected"]) {
      await page.goto("/certificacion");
      await page.getByLabel("Escenario de ensayo").selectOption(scenario);
      await page.getByRole("button", { name: "Ejecutar ensayo offline" }).click();
      await expect(page.getByText("Estado final:")).toBeVisible();
      await expect(page.locator("main")).toContainText("origen demo");
    }
    finish();
  });

  test("maestros, recepción y operación sobreviven una recarga", async ({ page }) => {
    const finish = guard(page);
    await page.goto("/clientes");
    await page.getByRole("button", { name: "Nuevo cliente" }).click();
    await page.getByLabel("Razón social").fill("CLIENTE CREADO POR POLICÍA SPA");
    await page.getByLabel("RUT", { exact: true }).fill("77.777.777-7");
    await page.getByLabel("Correo de intercambio").fill("policia@demo.cl");
    await page.getByRole("button", { name: "Guardar cliente demo" }).click();
    await expect(page.getByText("CLIENTE CREADO POR POLICÍA SPA")).toBeVisible();
    await page.reload();
    await expect(page.getByText("CLIENTE CREADO POR POLICÍA SPA")).toBeVisible();
    await page.goto("/productos");
    await page.getByRole("button", { name: "Nuevo producto" }).click();
    await page.getByLabel("SKU").fill("POLICIA-01");
    await page.getByLabel("Nombre").fill("Producto policial");
    await page.getByLabel("Precio neto").fill("9900");
    await page.getByRole("button", { name: "Guardar producto demo" }).click();
    await expect(page.getByText("Producto policial")).toBeVisible();
    await page.reload();
    await expect(page.getByText("Producto policial")).toBeVisible();
    await page.goto("/recibidos");
    await page.getByRole("button", { name: "Importar XML" }).click();
    await page.getByLabel("Seleccionar XML recibido").setInputFiles({ name: "factura-demo.xml", mimeType: "application/xml", buffer: Buffer.from("<DTE demo='true'/>") });
    await expect(page.getByText("XML sintético validado y persistido en sandbox")).toBeVisible();
    await page.goto("/recibidos/demo-33-7841");
    await page.getByRole("button", { name: /Aceptar contenido/ }).click();
    await page.getByRole("button", { name: "Confirmar en simulador" }).click();
    await expect(page.getByText("La decisión quedó persistida y bloqueada")).toBeVisible();
    await page.reload();
    await expect(page.getByText("La decisión quedó persistida y bloqueada")).toBeVisible();
    await page.goto("/recurrencia");
    await page.getByRole("button", { name: "Nuevo acuerdo" }).click();
    await page.getByLabel("Cliente", { exact: true }).fill("RECURRENTE POLICÍA SPA");
    await page.getByLabel("Concepto").fill("Servicio mensual de ensayo");
    await page.getByLabel("Monto").fill("45000");
    await page.getByRole("button", { name: "Guardar acuerdo" }).click();
    await expect(page.getByText("RECURRENTE POLICÍA SPA")).toBeVisible();
    await page.reload();
    await expect(page.getByText("RECURRENTE POLICÍA SPA")).toBeVisible();
    finish();
  });
});

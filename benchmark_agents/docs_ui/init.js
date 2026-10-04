"use strict";

window.ui = SwaggerUIBundle({
  url: new URL("../openapi.json", window.location.href).pathname,
  dom_id: "#swagger-ui",
  deepLinking: true,
  presets: [SwaggerUIBundle.presets.apis],
  layout: "BaseLayout",
  validatorUrl: null,
  persistAuthorization: false,
});

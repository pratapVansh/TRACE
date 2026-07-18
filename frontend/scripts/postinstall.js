const fs = require("fs");
const path = require("path");

const mjsPath = path.join(
  __dirname,
  "..",
  "node_modules",
  "vis-network",
  "peer",
  "esm",
  "vis-network.mjs",
);

if (!fs.existsSync(mjsPath)) {
  const reexport = `export * from "../../esnext/esm/vis-network.js";\n`;
  fs.mkdirSync(path.dirname(mjsPath), { recursive: true });
  fs.writeFileSync(mjsPath, reexport, "utf-8");
  console.log("Created missing vis-network.mjs entry point");
}

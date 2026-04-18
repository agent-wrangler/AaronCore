const fs = require('fs');
const path = require('path');
const pkg = require('./package.json');

const vendorRoot = path.resolve(__dirname, 'vendor_runtime');
const pythonRoot = path.join(vendorRoot, 'python');
const playwrightRoot = path.join(vendorRoot, 'ms-playwright');

for (const requiredPath of [pythonRoot, playwrightRoot]) {
  if (!fs.existsSync(requiredPath)) {
    throw new Error(`Bundled runtime is missing: ${requiredPath}. Run "npm run prepare:runtime" first.`);
  }
}

module.exports = {
  ...pkg.build,
  extraResources: [
    ...(pkg.build.extraResources || []),
    {
      from: pythonRoot,
      to: 'aaroncore/runtime/python',
    },
    {
      from: playwrightRoot,
      to: 'aaroncore/runtime/ms-playwright',
    },
  ],
};

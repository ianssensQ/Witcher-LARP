import fs from "node:fs";
import path from "node:path";
import { PNG } from "pngjs";

const assetDir = path.resolve("src/assets/generated/lords-login");
const sourcePath = path.join(assetDir, "menu-frame-warcraft.png");
const loginPath = path.join(assetDir, "menu-frame-warcraft-login.png");
const chainPath = path.join(assetDir, "menu-chain-extension.png");

const source = PNG.sync.read(fs.readFileSync(sourcePath));

function copyRect(src, dst, sx, sy, width, height, dx, dy) {
  for (let y = 0; y < height; y += 1) {
    const srcY = Math.max(0, Math.min(src.height - 1, sy + y));
    const dstY = dy + y;
    if (dstY < 0 || dstY >= dst.height) continue;

    for (let x = 0; x < width; x += 1) {
      const srcX = Math.max(0, Math.min(src.width - 1, sx + x));
      const dstX = dx + x;
      if (dstX < 0 || dstX >= dst.width) continue;

      const srcIndex = (src.width * srcY + srcX) * 4;
      const dstIndex = (dst.width * dstY + dstX) * 4;
      dst.data[dstIndex] = src.data[srcIndex];
      dst.data[dstIndex + 1] = src.data[srcIndex + 1];
      dst.data[dstIndex + 2] = src.data[srcIndex + 2];
      dst.data[dstIndex + 3] = src.data[srcIndex + 3];
    }
  }
}

function blendRect(src, dst, sx, sy, width, height, dx, dy) {
  for (let y = 0; y < height; y += 1) {
    const srcY = Math.max(0, Math.min(src.height - 1, sy + y));
    const dstY = dy + y;
    if (dstY < 0 || dstY >= dst.height) continue;

    for (let x = 0; x < width; x += 1) {
      const srcX = Math.max(0, Math.min(src.width - 1, sx + x));
      const dstX = dx + x;
      if (dstX < 0 || dstX >= dst.width) continue;

      const srcIndex = (src.width * srcY + srcX) * 4;
      const dstIndex = (dst.width * dstY + dstX) * 4;
      const alpha = src.data[srcIndex + 3] / 255;
      const inverse = 1 - alpha;

      dst.data[dstIndex] = Math.round(src.data[srcIndex] * alpha + dst.data[dstIndex] * inverse);
      dst.data[dstIndex + 1] = Math.round(src.data[srcIndex + 1] * alpha + dst.data[dstIndex + 1] * inverse);
      dst.data[dstIndex + 2] = Math.round(src.data[srcIndex + 2] * alpha + dst.data[dstIndex + 2] * inverse);
      dst.data[dstIndex + 3] = Math.max(dst.data[dstIndex + 3], src.data[srcIndex + 3]);
    }
  }
}

function makeLoginPanel() {
  const extraHeight = 185;
  const cutY = 730;
  const output = new PNG({ width: source.width, height: source.height + extraHeight });

  copyRect(source, output, 0, 0, source.width, cutY, 0, 0);

  for (let y = cutY; y < cutY + extraHeight; y += 1) {
    const srcY = 728 + ((y - cutY) % 138);
    copyRect(source, output, 0, srcY, source.width, 1, 0, y);
  }

  copyRect(source, output, 0, cutY, source.width, source.height - cutY, 0, cutY + extraHeight);

  // Duplicate the accepted lower slot into the added metal area.
  blendRect(source, output, 214, 565, 575, 170, 214, 750);

  // Repaint central dark well slightly wider to make the third button read as a full slot.
  blendRect(source, output, 250, 612, 490, 86, 250, 800);

  fs.writeFileSync(loginPath, PNG.sync.write(output));
}

function makeChainExtension() {
  const crop = new PNG({ width: 118, height: 470 });
  copyRect(source, crop, 24, 195, crop.width, crop.height, 0, 0);
  fs.writeFileSync(chainPath, PNG.sync.write(crop));
}

makeLoginPanel();
makeChainExtension();

console.log(`Wrote ${path.relative(process.cwd(), loginPath)}`);
console.log(`Wrote ${path.relative(process.cwd(), chainPath)}`);

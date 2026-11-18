export type InteractiveLookSettings = {
  exposure_stops: number;
  contrast: number;
  pivot: number;
  saturation: number;
  temperature_shift: number;
  tint_shift: number;
};

export type InteractiveLook = {
  settings: InteractiveLookSettings;
  curve_midpoint: number;
};

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const srgbToLinear = (value: number) =>
  value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
const linearToSrgb = (value: number) =>
  value <= 0.0031308 ? value * 12.92 : 1.055 * value ** (1 / 2.4) - 0.055;

function masterCurve(value: number, midpoint: number): number {
  // Piecewise-linear [0, 0] -> [0.5, midpoint] -> [1, 1].
  if (value <= 0.5) return value * (midpoint / 0.5);
  return midpoint + ((value - 0.5) / 0.5) * (1 - midpoint);
}

/**
 * Apply the interactive browser preview look to sRGB ImageData.
 * The browser has already decoded/colour-managed the source into its canvas
 * sRGB surface. This is a preview operation, not a camera Log input transform.
 */
export function applyInteractiveLook(
  imageData: ImageData,
  look: InteractiveLook,
): ImageData {
  const { exposure_stops, contrast, pivot, saturation, temperature_shift, tint_shift } = look.settings;
  const exposure = 2 ** exposure_stops;
  const gains = [
    exposure * 2 ** (0.35 * temperature_shift),
    exposure * 2 ** (0.25 * tint_shift),
    exposure * 2 ** (-0.35 * temperature_shift),
  ];
  const midpoint = Math.min(0.9, Math.max(0.1, look.curve_midpoint));
  const pixels = imageData.data;

  for (let offset = 0; offset < pixels.length; offset += 4) {
    let r = srgbToLinear(pixels[offset] / 255) * gains[0];
    let g = srgbToLinear(pixels[offset + 1] / 255) * gains[1];
    let b = srgbToLinear(pixels[offset + 2] / 255) * gains[2];

    r = pivot + (r - pivot) * contrast;
    g = pivot + (g - pivot) * contrast;
    b = pivot + (b - pivot) * contrast;

    const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    r = masterCurve(luma + (r - luma) * saturation, midpoint);
    g = masterCurve(luma + (g - luma) * saturation, midpoint);
    b = masterCurve(luma + (b - luma) * saturation, midpoint);

    pixels[offset] = Math.round(clamp01(linearToSrgb(Math.max(0, r))) * 255);
    pixels[offset + 1] = Math.round(clamp01(linearToSrgb(Math.max(0, g))) * 255);
    pixels[offset + 2] = Math.round(clamp01(linearToSrgb(Math.max(0, b))) * 255);
  }
  return imageData;
}

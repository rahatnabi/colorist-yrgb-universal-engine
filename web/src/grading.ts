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
  working_space_id: "scene-linear-rec709" | "acescg-linear";
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
  const aces = look.working_space_id === "acescg-linear";
  const lumaCoefficients = aces ? [0.2722287, 0.6740818, 0.0536895] : [0.2126, 0.7152, 0.0722];
  const toAces = (rgb: number[]) => [
    0.6130974 * rgb[0] + 0.3395231 * rgb[1] + 0.0473795 * rgb[2],
    0.0701937 * rgb[0] + 0.9163539 * rgb[1] + 0.0134524 * rgb[2],
    0.0206156 * rgb[0] + 0.1095698 * rgb[1] + 0.8698153 * rgb[2],
  ];
  const fromAces = (rgb: number[]) => [
    1.7048587 * rgb[0] - 0.6217160 * rgb[1] - 0.0832994 * rgb[2],
    -0.1300768 * rgb[0] + 1.1407358 * rgb[1] - 0.0105598 * rgb[2],
    -0.0239641 * rgb[0] - 0.1289755 * rgb[1] + 1.1530140 * rgb[2],
  ];
  const pixels = imageData.data;

  for (let offset = 0; offset < pixels.length; offset += 4) {
    let rgb = [
      srgbToLinear(pixels[offset] / 255),
      srgbToLinear(pixels[offset + 1] / 255),
      srgbToLinear(pixels[offset + 2] / 255),
    ];
    if (aces) rgb = toAces(rgb);
    rgb = rgb.map((value, index) => pivot + (value * gains[index] - pivot) * contrast);
    const luma = rgb[0] * lumaCoefficients[0] + rgb[1] * lumaCoefficients[1] + rgb[2] * lumaCoefficients[2];
    rgb = rgb.map(value => masterCurve(luma + (value - luma) * saturation, midpoint));
    if (aces) rgb = fromAces(rgb);
    pixels[offset] = Math.round(clamp01(linearToSrgb(Math.max(0, rgb[0]))) * 255);
    pixels[offset + 1] = Math.round(clamp01(linearToSrgb(Math.max(0, rgb[1]))) * 255);
    pixels[offset + 2] = Math.round(clamp01(linearToSrgb(Math.max(0, rgb[2]))) * 255);
  }
  return imageData;
}

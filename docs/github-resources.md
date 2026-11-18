# GitHub Resource Acquisition and Provenance

The engine should prefer pinned, inspectable GitHub resources for software, transform implementation references, and conformance fixtures. Every imported resource must record its upstream repository, revision or release, path/asset, license, checksum where available, intended use, and validation scope.

## Pinned ACES configuration

The repository includes `scripts/fetch_aces_config.py`, which downloads a release asset from the official AcademySoftwareFoundation OpenColorIO-Config-ACES GitHub release and verifies the published SHA-256 before writing it.

Fetch the Studio config:

```bash
python scripts/fetch_aces_config.py --variant studio --output .cache/ocio/aces-v4.0.0-studio.ocio
```

Other variants:

```bash
python scripts/fetch_aces_config.py --variant studio-all-views --output .cache/ocio/aces-v4.0.0-studio-all-views.ocio
python scripts/fetch_aces_config.py --variant reference --output .cache/ocio/aces-v4.0.0-reference.ocio
```

The expected SHA-256 values are pinned in `data/reference_sources/github_resources.json`. A changed asset or unexpected response is rejected. Do not replace the pinned config silently: its hash is part of every transform-validation record.

The upstream v4.0.0 release provides ACES 2.0 configurations for OCIO 2.5. This is useful for deterministic processor construction and color-space compatibility checks. It is **not** proof that a camera transform matches a particular camera, firmware, recording mode, or decode pipeline.

## Sony S-Log3 implementation cross-check

OpenColorIO's BSD-3-Clause-licensed `SonyCameras.cpp` contains separate S-Gamut3 and S-Gamut3.Cine primary definitions and S-Log3 decoding logic. The source is pinned in the resource manifest. Use it to cross-check implementation details and preserve the distinction between the two gamuts.

This source code is not a Sony camera capture, a measured chart, or independent reference-vector set. It must never be used to mark FX3/FX6/FX9 transforms as reference-validated.

## CLF full-half-float conformance fixture

OpenColorIO's `share/clf/CLF_testImage.exr` is described by its upstream README as a source target image sampling the full half-float domain. Upstream scripts process CLF transforms and compare output images. This is a valuable future fixture for checking LUT/CLF numerical behavior, including out-of-range values.

The asset-specific license is not separately confirmed in the upstream directory. Therefore this project records its location and purpose but does not vendor or redistribute the EXR. Confirm the asset license before downloading it into a distributable package.

## Camera footage discovery

GitHub searches did not identify a traceable, license-clear FX3/FX6/FX9 S-Log3 camera-original sample set suitable for scientific transform validation. Search hits that merely mention a camera or describe an aesthetic are not accepted as footage provenance. Do not substitute synthetic footage, generated images, generic S-Log3 examples, or metadata-only snippets for camera reference captures.

When a suitable source is found, the resource record must include:
- original repository and immutable commit/release;
- exact asset path and checksum;
- explicit camera model and recording mode;
- codec, bit depth, firmware and gamut where available;
- license and redistribution conditions;
- chart/reference source and patch-measurement method if used for transform validation.

## Source inventory

See `data/reference_sources/github_resources.json` for the machine-readable inventory. All resource imports must retain their original attribution and license obligations. Upstream implementation, sample media, and measured reference data are three different evidence classes and must remain separate.

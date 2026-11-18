# Still-image batch analysis

The `POST /v1/media/batch-analyze` endpoint accepts 1–24 still images in multipart field `files`. Each image is independently decoded through the optional OpenImageIO high-precision decoder and analyzed for RGB channel statistics.

## Limits

- Maximum 24 images per request.
- Maximum 512 MiB per image.
- Maximum 40 megapixels per decoded image.
- RGB channels must be explicitly named R, G and B by the decoder.
- Temporary upload files are removed after the request.

## Comparison semantics

The response includes adjacent-image differences in each decoded RGB channel mean. These values are descriptive sample-domain comparisons only. They are not exposure-stop differences, scene-linear luminance, white-balance estimates, or proof that two shots match.

The optional `scope_standard` query parameter accepts `bt709` or `bt2020` and only controls the coefficients used by the scope analysis contract. It does not transform the image or validate its source color encoding.

## Current exclusions

This first batch endpoint does not generate thumbnails/contact sheets, read camera RAW metadata beyond the decoder's current output, align images, detect corresponding regions, or apply camera transforms. Different dimensions, codecs and color encodings can therefore make mean comparisons misleading. Use the per-image `sample_domain` and decoder fields before interpreting the results.

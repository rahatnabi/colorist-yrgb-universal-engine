# Manual Luma Scope Standards

The still-image endpoint `POST /v1/media/analyze` and video-frame endpoint
`POST /v1/media/video-frame` accept an optional `scope_standard` query
parameter:

- `bt709`: coefficients 0.2126 / 0.7152 / 0.0722
- `bt2020`: coefficients 0.2627 / 0.6780 / 0.0593

When selected, the engine calculates a luma-weighted waveform raster and
vectorscope points from the decoded RGB samples. The selection is explicit:
the engine does not infer the standard from a filename, camera model, or
possibly conflicting metadata.

The resulting scopes remain in the decoder's sample domain. They are not IRE,
nits, scene-linear luminance, or proof that the source is encoded according to
the selected standard. The selection supplies luma coefficients only; it does
not perform a matrix conversion, transfer decode, gamut conversion, or camera
Log transform.

Without `scope_standard`, waveform and vectorscope remain unavailable and the
response explains how to enable them. RGB histogram and RGB Parade remain
available independently.

Examples:

```http
POST /v1/media/analyze?scope_standard=bt709
POST /v1/media/video-frame?timestamp_seconds=1.2&scope_standard=bt2020
```

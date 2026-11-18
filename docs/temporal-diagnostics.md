# Temporal diagnostics

The POST /v1/media/video-sample endpoint returns temporal_diagnostics alongside
its existing provisional histogram-based shot groups.

The diagnostics summarize R, G and B channel means independently within each
provisional shot group. They include sample count, median, minimum, maximum,
first-to-last delta, and a least-squares slope in decoder sample-domain units
per second. A segment with fewer than three samples is explicitly marked as
having insufficient samples for a trend.

These measurements are not exposure stops, scene-linear luminance, flicker
or camera auto-exposure measurements. A channel mean can change because of
subject movement, reframing, lighting, or scene content. Flicker assessment
remains unavailable because sparse timestamp sampling cannot establish
frame-rate temporal behavior. A future flicker test requires dense frame
sampling, a fixed region of interest, and a suitable signal domain.

Exposure drift assessment remains unavailable until a reference-validated
per-pixel transform provides scene-linear RGB and the analysis uses a fixed
region of interest. Shot boundaries remain provisional histogram-change
candidates rather than confirmed semantic cuts.

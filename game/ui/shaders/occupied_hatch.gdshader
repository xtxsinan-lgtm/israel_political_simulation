shader_type canvas_item;

// Occupied-territory hatch: the layer colour (Polygon2D.color arrives as COLOR) with 45° stripes.
// Polygon2D has no UVs by default, so UVs are derived from the local vertex position relative to
// the region bounding box (bbox = x0, y0, width, height; set by RegionPolygonNode as the union of
// all rings of the region, so multi-ring regions such as sinai / south_lebanon hatch seamlessly).
// period_px > 0 switches to a fixed on-map stripe period (isotropic, same look for tiny gaza and
// huge sinai); period_px = 0 keeps the legacy "density stripes across the bbox" behaviour.
uniform float density : hint_range(4.0, 48.0) = 14.0;
uniform vec4 hatch : source_color = vec4(0.1804, 0.1608, 0.1412, 0.55);
uniform vec4 bbox = vec4(0.0, 0.0, 1.0, 1.0);
uniform float period_px = 0.0;

varying vec2 hatch_uv;

void vertex() {
	vec2 span = max(bbox.zw, vec2(1.0));
	if (period_px > 0.0) {
		span = vec2(period_px * density);
	}
	hatch_uv = (VERTEX - bbox.xy) / span;
}

void fragment() {
	float stripe = step(0.55, fract((hatch_uv.x + hatch_uv.y) * density));
	COLOR.rgb = mix(COLOR.rgb, hatch.rgb, stripe * hatch.a);
}

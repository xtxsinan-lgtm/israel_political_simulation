shader_type canvas_item;

// Occupied-territory hatch: the layer colour (Polygon2D.color arrives as COLOR) with 45° stripes.
// Polygon2D has no UVs by default, so UVs are derived from the local vertex position normalised
// to the polygon bounding box (bbox = x0, y0, width, height; set by RegionPolygonNode).
uniform float density : hint_range(4.0, 48.0) = 14.0;
uniform vec4 hatch : source_color = vec4(0.1804, 0.1608, 0.1412, 0.55);
uniform vec4 bbox = vec4(0.0, 0.0, 1.0, 1.0);

varying vec2 hatch_uv;

void vertex() {
	hatch_uv = (VERTEX - bbox.xy) / max(bbox.zw, vec2(1.0));
}

void fragment() {
	float stripe = step(0.55, fract((hatch_uv.x + hatch_uv.y) * density));
	COLOR.rgb = mix(COLOR.rgb, hatch.rgb, stripe * hatch.a);
}

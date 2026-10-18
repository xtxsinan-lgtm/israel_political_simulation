shader_type canvas_item;

uniform float density : hint_range(4.0, 48.0) = 14.0;
uniform vec4 hatch : source_color = vec4(0.18, 0.16, 0.14, 0.55);

void fragment() {
	COLOR = texture(TEXTURE, UV);
	float stripe = step(0.55, fract((UV.x + UV.y) * density));
	COLOR.rgb = mix(COLOR.rgb, hatch.rgb, stripe * hatch.a);
}
